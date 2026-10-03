from fastapi import Request, HTTPException
from webfluid.core.ext import db, events, security as s
from webfluid.extensions.security.models import User
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from typing import Optional

from ...models.mobile import MobileSecurity
from ...services import mobile as service
from ...schemas.v1 import MobileKeys, MobileLogin


def _status(device: Optional[MobileSecurity]) -> dict:
    if not device:
        return { "enrolled": False, "enc_pubkey": None, "sig_pubkey": None }

    return {
        "enrolled": True,
        "enc_pubkey": device.enc_pubkey,
        "sig_pubkey": device.sig_pubkey
    }


async def _verify_keys(user: User, keys: MobileKeys):
    if not service.valid_keys(keys.enc_pubkey, keys.sig_pubkey):
        raise HTTPException(status_code=400, detail="INVALID_KEY")

    if not await service.consume_challenge(keys.challenge):
        raise HTTPException(status_code=401, detail="INVALID_CHALLENGE")

    message = service.register_message(
        user.id, keys.enc_pubkey, keys.sig_pubkey, keys.challenge
    )
    if not service.verify(keys.sig_pubkey, message, keys.signature):
        raise HTTPException(status_code=401, detail="INVALID_SIGNATURE")


def _trigger_replaced(user_id: int):
    from ... import additive
    try:
        events.trigger(additive.unique_name("mobile:replaced"), {
            "user_id": user_id
        })
    except ValueError: pass


async def challenge_request(request: Request):
    return {
        "challenge": await service.issue_challenge(),
        "expires": service.CHALLENGE_TTL
    }


async def status_request(user: User = s.user_service.require_2fa):
    return _status(await service.device(user.id))


async def register_request(
        request: Request, keys: MobileKeys,
        user: User = s.user_service.require_2fa
):
    if await service.device(user.id):
        raise HTTPException(status_code=409, detail="MOBILE_ALREADY_ENROLLED")

    await _verify_keys(user, keys)

    try:
        async with db.async_executor(model=MobileSecurity) as e:
            await e.insert(MobileSecurity(
                user.id, keys.enc_pubkey, keys.sig_pubkey
            ), True)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="MOBILE_ALREADY_ENROLLED")

    return { "status": "ok" }


async def replace_request(
        request: Request, keys: MobileKeys,
        user: User = s.user_service.require_2fa
):
    if request.session.get("mobile"):
        raise HTTPException(status_code=403, detail="REAUTHENTICATION_REQUIRED")

    await _verify_keys(user, keys)

    async with db.async_executor(model=MobileSecurity) as e:
        result = await e.exec(select(MobileSecurity).where(
            MobileSecurity.uid == user.id
        ))
        device = result.first()

        if not device:
            replaced = False
            await e.insert(MobileSecurity(
                user.id, keys.enc_pubkey, keys.sig_pubkey
            ))
        else:
            replaced = (device.enc_pubkey, device.sig_pubkey) != \
                       (keys.enc_pubkey, keys.sig_pubkey)
            device.enc_pubkey = keys.enc_pubkey
            device.sig_pubkey = keys.sig_pubkey

    if replaced: _trigger_replaced(user.id)
    return { "status": "ok", "replaced": replaced }


async def login_request(request: Request, login: MobileLogin):
    if not await service.consume_challenge(login.challenge):
        raise HTTPException(status_code=401, detail="INVALID_CHALLENGE")

    device = await service.device(login.user_id)
    message = service.login_message(login.user_id, login.challenge)
    if not device or not service.verify(device.sig_pubkey, message, login.signature):
        raise HTTPException(status_code=401, detail="MOBILE_AUTH_FAILED")

    request.session.clear()
    request.session["user_id"] = login.user_id
    request.session["2fa_verified"] = True
    request.session["mobile"] = True
    return s.token_service.csrf_response(request)
