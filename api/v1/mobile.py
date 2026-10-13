from fastapi import Request, HTTPException
from webfluid.core.ext import db, events, security as s
from webfluid.extensions.security.models import User
from sqlalchemy.exc import IntegrityError
from typing import Optional

from ...models.mobile import MobileSecurity
from ...services import mobile as service, keylog, outbox, actions
from ..utils import admit
from ...schemas.v1 import MobileKeys, MobileLogin


def _status(device: Optional[MobileSecurity], state: dict) -> dict:
    data = {
        "account": state["account"],
        "keylog": { "seq": state["seq"], "head": state["head"], "broken": state["broken"],
                    "recovery": state["recovery"] is not None }
    }
    if not device:
        return { "enrolled": False, "enc_pubkey": None, "sig_pubkey": None, **data }

    return {
        "enrolled": True,
        "enc_pubkey": device.enc_pubkey,
        "sig_pubkey": device.sig_pubkey,
        **data
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


def _matches(envelope: dict, keys: MobileKeys) -> bool:
    statement = (envelope or {}).get("statement") or {}
    return statement.get("type") == "device.bind" and statement.get("keys") == {
        "sig": keys.sig_pubkey, "enc": keys.enc_pubkey
    }


async def _bind(user: User, keys: MobileKeys, allowed: tuple) -> dict:
    envelope = keys.keylog
    if envelope is None:
        envelope = await keylog.host_statement(user.id, "device.bind",
                                               { "sig": keys.sig_pubkey, "enc": keys.enc_pubkey }, keys.reset)
        allow_host = True
    else:
        if not _matches(envelope, keys):
            raise HTTPException(status_code=400, detail="KEYLOG_MISMATCH")
        if (envelope.get("statement") or {}).get("authority") not in allowed:
            raise HTTPException(status_code=400, detail="AUTHORITY_NOT_ALLOWED")
        allow_host = False
    try:
        result = await keylog.append(user.id, envelope, allow_host=allow_host)
    except keylog.KeylogError as exc:
        status = 409 if exc.code in ("KEYLOG_CONFLICT", "MOBILE_ENROLLED") else 400
        raise HTTPException(status_code=status, detail=exc.code)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="KEYLOG_CONFLICT")
    await outbox.flush()
    return result


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
    state = await keylog.anchors(user.id)
    return _status(await service.device(user.id), state)


async def keylog_request(user: User = s.user_service.require_2fa):
    state = await keylog.anchors(user.id)
    return {
        "account": state["account"],
        "origin": keylog.origin(),
        "state": state,
        "consistent": await keylog.consistent(user.id),
        "statements": await keylog.history(user.id)
    }


async def actions_request(user: User = s.user_service.require_2fa):
    return {
        "account": keylog.handle(user.id),
        "devices": await actions.heads(user.id),
        "recent": await actions.history(user.id, 100)
    }


async def register_request(
        request: Request, keys: MobileKeys,
        user: User = s.user_service.require_2fa
):
    if await service.device(user.id):
        raise HTTPException(status_code=409, detail="MOBILE_ALREADY_ENROLLED")

    await _verify_keys(user, keys)
    result = await _bind(user, keys, ("self", "recovery"))
    return { "status": "ok", "keylog": { "seq": result["seq"], "hash": result["hash"], "flags": result["flags"] } }


async def replace_request(
        request: Request, keys: MobileKeys,
        user: User = s.user_service.require_2fa
):
    if request.session.get("mobile"):
        raise HTTPException(status_code=403, detail="REAUTHENTICATION_REQUIRED")

    await _verify_keys(user, keys)

    state = await keylog.anchors(user.id)
    if state["device"] == { "sig": keys.sig_pubkey, "enc": keys.enc_pubkey }:
        restored = not await keylog.consistent(user.id)
        if restored:
            async with db.async_executor(model=MobileSecurity) as e:
                await keylog._mirror(e, user.id, state)
        return { "status": "ok", "replaced": False, "restored": restored }

    result = await _bind(user, keys, ("device", "recovery"))
    _trigger_replaced(user.id)
    return { "status": "ok", "replaced": True,
             "keylog": { "seq": result["seq"], "hash": result["hash"], "flags": result["flags"] } }


async def login_request(request: Request, login: MobileLogin):
    await admit("device")
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
