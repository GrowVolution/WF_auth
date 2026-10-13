from fastapi import Request, HTTPException
from sqlalchemy import select
from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
    options_to_json,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    UserVerificationRequirement,
    PublicKeyCredentialDescriptor,
)

from webfluid.core.ext import db, security as s
from webfluid.core.context import FluidContext
from webfluid.extensions.security.models import (
    User, TOTPSecret, WebAuthnCredential, BackupCode
)
from webfluid.utils.logging import factory as log_factory
import io, json, secrets, pyotp, segno, time

from ..utils import require_verified_session, admit_credential
from ...schemas.v1 import (
    TOTPVerify, BackupCodeVerify,
    WebAuthnRegister, WebAuthnVerify, WebAuthnDelete,
    MobileApproval, MobileDenial
)
from ...services import approval as approvals, mobile as devices, credentials

_REG_CHALLENGE = "webauthn_reg_challenge"
_AUTH_CHALLENGE = "webauthn_auth_challenge"


def _config():
    cfg = FluidContext.current().fluid.config
    return (
        cfg.get("AUTH_2FA_ISSUER", "WebFluid"),
        cfg.get("AUTH_2FA_WEBAUTHN_RP_ID", "localhost"),
        cfg.get("AUTH_2FA_WEBAUTHN_RP_NAME", "WebFluid"),
        cfg.get("AUTH_2FA_WEBAUTHN_ORIGIN", "http://localhost:8000"),
    )


def _mark_verified(request: Request):
    request.session["2fa_verified"] = True


async def _throttled(scope: str, user_id: int):
    if await credentials.exhausted(scope, user_id):
        raise HTTPException(status_code=429, detail="TOO_MANY_ATTEMPTS")


def _timecode(totp: pyotp.TOTP, code: str):
    for offset in (-1, 0, 1):
        moment = time.time() + offset * totp.interval
        if secrets.compare_digest(totp.at(moment), str(code)): return int(moment // totp.interval)
    return None


async def _has_confirmed_totp(e, user: User) -> bool:
    result = await e.exec(select(TOTPSecret).where(
        TOTPSecret.user_id == user.id,
        TOTPSecret.confirmed == True
    ))
    return result.first() is not None


async def _credentials(e, user: User) -> list[WebAuthnCredential]:
    result = await e.exec(select(WebAuthnCredential).where(
        WebAuthnCredential.user_id == user.id
    ))
    return list(result.all())



async def status(request: Request, user: User = s.user_service.require_user):
    async with db.ensured_async_executor(model=TOTPSecret) as e:
        result = await e.exec(select(TOTPSecret).where(
            TOTPSecret.user_id == user.id,
            TOTPSecret.confirmed == True
        ))
        totp = result.first()

        credentials = await _credentials(e, user)

        result = await e.exec(select(BackupCode).where(
            BackupCode.user_id == user.id,
            BackupCode.used == False
        ))
        backup_codes = len(list(result.all()))

        return {
            "totp": totp is not None,
            "webauthn": [
                { "id": c.credential_id, "name": c.name }
                for c in credentials
            ],
            "backup_codes": backup_codes,
            "mobile": await devices.device(user.id) is not None,
            "verified": bool(request.session.get("2fa_verified")),
        }



async def request_totp(request: Request, user: User = s.user_service.require_user):
    require_verified_session(request, user)
    await admit_credential("totp", user.id)
    issuer, *_ = _config()

    async with db.ensured_async_executor(model=TOTPSecret) as e:
        result = await e.exec(select(TOTPSecret).where(
            TOTPSecret.user_id == user.id
        ))
        existing = result.first()
        if existing and existing.confirmed:
            raise HTTPException(status_code=400, detail="TWO_FA_ALREADY_SETUP")

        secret = pyotp.random_base32()
        if existing:
            existing.secret = secret
        else:
            await e.insert(TOTPSecret(user.id, secret))

    uri = pyotp.TOTP(secret).provisioning_uri(
        name=user.email or user.username,
        issuer_name=issuer
    )

    buf = io.BytesIO()
    segno.make(uri, error="m").save(
        buf, kind="svg", scale=3, border=2,
        dark="#e2e8f0", light=None, svgclass=None
    )

    return { "secret": secret, "uri": uri, "qr": buf.getvalue() }


async def verify_totp(request: Request, verify: TOTPVerify,
                      user: User = s.user_service.require_user):
    async with db.ensured_async_executor(model=TOTPSecret) as e:
        result = await e.exec(select(TOTPSecret).where(
            TOTPSecret.user_id == user.id
        ))
        totp = result.first()
        if not totp:
            raise HTTPException(status_code=400, detail="TWO_FA_NOT_SETUP")

        if not totp.confirmed:
            require_verified_session(request, user)
            await admit_credential("totp", user.id)

        await _throttled("totp", user.id)
        step = _timecode(pyotp.TOTP(totp.secret), verify.code)
        if step is None or not await credentials.fresh_step(user.id, step):
            await credentials.failed("totp", user.id)
            raise HTTPException(status_code=401, detail="INVALID_OTP")

        await credentials.cleared("totp", user.id)
        totp.confirmed = True

    _mark_verified(request)
    return { "status": "ok" }


async def delete_totp(request: Request, user: User = s.user_service.require_user):
    require_verified_session(request, user)
    await admit_credential("totp", user.id)
    async with db.ensured_async_executor(model=TOTPSecret) as e:
        result = await e.exec(select(TOTPSecret).where(
            TOTPSecret.user_id == user.id
        ))
        totp = result.first()
        if not totp:
            raise HTTPException(status_code=400, detail="TWO_FA_NOT_SETUP")

        await e.delete(totp)

    return { "status": "ok" }



async def register_webauthn(request: Request, user: User = s.user_service.require_user):
    require_verified_session(request, user)
    await admit_credential("webauthn", user.id)
    _, rp_id, rp_name, _ = _config()

    async with db.ensured_async_executor(model=WebAuthnCredential) as e:
        credentials = await _credentials(e, user)

    options = generate_registration_options(
        rp_id=rp_id,
        rp_name=rp_name,
        user_id=str(user.id).encode(),
        user_name=user.username,
        user_display_name=user.username,
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=base64url_to_bytes(c.credential_id))
            for c in credentials
        ],
        authenticator_selection=AuthenticatorSelectionCriteria(
            user_verification=UserVerificationRequirement.PREFERRED
        ),
    )

    request.session[_REG_CHALLENGE] = bytes_to_base64url(options.challenge)
    return json.loads(options_to_json(options))


async def verify_webauthn_register(request: Request, register: WebAuthnRegister,
                                   user: User = s.user_service.require_user):
    require_verified_session(request, user)
    await admit_credential("webauthn", user.id)
    _, rp_id, _, origin = _config()
    challenge = request.session.pop(_REG_CHALLENGE, None)
    if not challenge:
        raise HTTPException(status_code=400, detail="NO_CHALLENGE")

    try:
        verification = verify_registration_response(
            credential=json.dumps(register.credential),
            expected_challenge=base64url_to_bytes(challenge),
            expected_rp_id=rp_id,
            expected_origin=origin,
        )
    except Exception as exc:
        log_factory.debug(f"[auth] WebAuthn registration rejected: {exc}")
        raise HTTPException(status_code=400, detail="WEBAUTHN_FAILED")

    async with db.ensured_async_executor(model=WebAuthnCredential) as e:
        await e.insert(WebAuthnCredential(
            user_id=user.id,
            credential_id=bytes_to_base64url(verification.credential_id),
            public_key=bytes_to_base64url(verification.credential_public_key),
            sign_count=verification.sign_count,
            name=register.name,
        ))

    _mark_verified(request)
    return { "status": "ok" }


async def authenticate_webauthn(request: Request, user: User = s.user_service.require_user):
    _, rp_id, _, _ = _config()

    async with db.ensured_async_executor(model=WebAuthnCredential) as e:
        credentials = await _credentials(e, user)

    if not credentials:
        raise HTTPException(status_code=400, detail="TWO_FA_NOT_SETUP")

    options = generate_authentication_options(
        rp_id=rp_id,
        allow_credentials=[
            PublicKeyCredentialDescriptor(id=base64url_to_bytes(c.credential_id))
            for c in credentials
        ],
        user_verification=UserVerificationRequirement.PREFERRED,
    )

    request.session[_AUTH_CHALLENGE] = bytes_to_base64url(options.challenge)
    return json.loads(options_to_json(options))


async def verify_webauthn(request: Request, verify: WebAuthnVerify,
                          user: User = s.user_service.require_user):
    _, rp_id, _, origin = _config()
    challenge = request.session.pop(_AUTH_CHALLENGE, None)
    if not challenge:
        raise HTTPException(status_code=400, detail="NO_CHALLENGE")

    async with db.ensured_async_executor(model=WebAuthnCredential) as e:
        credentials = await _credentials(e, user)
        raw_id = verify.credential.get("id")
        matching = next((c for c in credentials if c.credential_id == raw_id), None)
        if not matching:
            raise HTTPException(status_code=400, detail="UNKNOWN_CREDENTIAL")

        try:
            verification = verify_authentication_response(
                credential=json.dumps(verify.credential),
                expected_challenge=base64url_to_bytes(challenge),
                expected_rp_id=rp_id,
                expected_origin=origin,
                credential_public_key=base64url_to_bytes(matching.public_key),
                credential_current_sign_count=matching.sign_count,
            )
        except Exception as exc:
            log_factory.debug(f"[auth] WebAuthn authentication rejected: {exc}")
            raise HTTPException(status_code=401, detail="WEBAUTHN_FAILED")

        matching.sign_count = verification.new_sign_count

    _mark_verified(request)
    return { "status": "ok" }


async def delete_webauthn(request: Request, delete: WebAuthnDelete,
                          user: User = s.user_service.require_user):
    require_verified_session(request, user)
    await admit_credential("webauthn", user.id)
    async with db.ensured_async_executor(model=WebAuthnCredential) as e:
        result = await e.exec(select(WebAuthnCredential).where(
            WebAuthnCredential.user_id == user.id,
            WebAuthnCredential.credential_id == delete.credential_id
        ))
        credential = result.first()
        if not credential:
            raise HTTPException(status_code=400, detail="UNKNOWN_CREDENTIAL")

        await e.delete(credential)

    return { "status": "ok" }



async def request_backup(request: Request, user: User = s.user_service.require_user):
    require_verified_session(request, user)
    await admit_credential("backup_codes", user.id)
    cfg = FluidContext.current().fluid.config
    count = cfg.get("AUTH_2FA_BACKUP_CODE_COUNT", 10)
    digits = cfg.get("AUTH_2FA_BACKUP_CODE_DIGITS", 8)

    async with db.ensured_async_executor(model=BackupCode) as e:
        if not (await _has_confirmed_totp(e, user) or await _credentials(e, user)):
            raise HTTPException(status_code=400, detail="TWO_FA_NOT_SETUP")

        existing = await e.exec(select(BackupCode).where(
            BackupCode.user_id == user.id
        ))
        for code in existing.all():
            await e.delete(code)

        codes = []
        for _ in range(count):
            code = "".join(secrets.choice("0123456789") for _ in range(digits))
            codes.append(code)
            await e.insert(BackupCode(user.id, await s.hash_service.ahash(code)))

    return { "codes": codes }


async def verify_backup(request: Request, verify: BackupCodeVerify,
                        user: User = s.user_service.require_user):
    await _throttled("backup", user.id)
    async with db.ensured_async_executor(model=BackupCode) as e:
        result = await e.exec(select(BackupCode).where(
            BackupCode.user_id == user.id,
            BackupCode.used == False
        ))

        matching = None
        for code in result.all():
            if await s.hash_service.averify(code.code_hash, verify.code):
                matching = code
                break

        if not matching:
            await credentials.failed("backup", user.id)
            raise HTTPException(status_code=401, detail="INVALID_BACKUP_CODE")

        matching.used = True
    await credentials.cleared("backup", user.id)

    _mark_verified(request)
    return { "status": "ok" }


async def delete_backup(request: Request, user: User = s.user_service.require_user):
    require_verified_session(request, user)
    await admit_credential("backup_codes", user.id)
    async with db.ensured_async_executor(model=BackupCode) as e:
        result = await e.exec(select(BackupCode).where(
            BackupCode.user_id == user.id
        ))
        for code in result.all():
            await e.delete(code)

    return { "status": "ok" }



def _sign_in(request: Request, user_id: int, verified: bool):
    request.session.clear()
    request.session["user_id"] = user_id
    if verified: _mark_verified(request)
    return s.token_service.csrf_response(request)


async def _approval(request: Request) -> tuple[str, dict]:
    approval = request.session.get("mobile_approval")
    state = await approvals.load(approval)
    if not state:
        request.session.pop("mobile_approval", None)
        raise HTTPException(status_code=401, detail="MOBILE_APPROVAL_EXPIRED")
    return approval, state


async def _pending(approval: str, user_id: int) -> dict:
    state = await approvals.load(approval)
    if not state or state.get("state") != "pending" or state.get("user_id") != user_id             or state.get("delegated"):
        raise HTTPException(status_code=409, detail="MOBILE_APPROVAL_UNAVAILABLE")
    return state


async def _verify_device(user_id: int, message: str, signature: str):
    device = await devices.device(user_id)
    if not device or not devices.verify(device.sig_pubkey, message, signature):
        raise HTTPException(status_code=401, detail="INVALID_SIGNATURE")


async def mobile_state(request: Request):
    approval = request.session.get("mobile_approval")
    if not approval: return { "pending": False }

    state = await approvals.load(approval)
    if not state: return { "pending": True, "state": "expired" }

    response = {
        "pending": True,
        "state": state["state"],
        "number": state["number"],
        "fallback": state["fallback"],
        "delegated": bool(state.get("delegated")),
        "expires": approvals.remaining(state)
    }
    if state.get("delegated"): response["approval"] = approval
    return response


async def complete_mobile(request: Request):
    approval, state = await _approval(request)
    if state["state"] == "pending":
        raise HTTPException(status_code=409, detail="MOBILE_APPROVAL_PENDING")
    if state["state"] != "approved":
        raise HTTPException(status_code=401, detail="MOBILE_APPROVAL_DENIED")

    state["state"] = "used"
    await approvals.store(approval, state)
    return _sign_in(request, state["user_id"], True)


async def fallback_mobile(request: Request):
    approval, state = await _approval(request)
    if state["state"] not in ("pending", "approved"):
        raise HTTPException(status_code=401, detail="MOBILE_APPROVAL_DENIED")
    if not state["fallback"]:
        raise HTTPException(status_code=400, detail="TWO_FA_NOT_SETUP")

    state["state"] = "cancelled"
    await approvals.store(approval, state)
    approvals.push(state, approval)
    return _sign_in(request, state["user_id"], False)


async def cancel_mobile(request: Request):
    approval = request.session.get("mobile_approval")
    state = await approvals.load(approval)
    if state and state["state"] == "pending":
        state["state"] = "cancelled"
        await approvals.store(approval, state)
        approvals.push(state, approval)

    request.session.clear()
    return { "status": "ok" }


async def pending_mobile(user: User = s.user_service.require_2fa):
    found = await approvals.pending(user.id)
    if not found: return { "approval": None }

    approval, state = found
    return { "approval": approval, "expires": approvals.remaining(state) }


async def approve_mobile(request: Request, approval: MobileApproval):
    state = await _pending(approval.approval, approval.user_id)
    await _verify_device(
        approval.user_id,
        approvals.approve_message(approval.user_id, approval.approval, approval.number),
        approval.signature
    )

    if approval.number != state["number"]:
        state["attempts"] += 1
        if state["attempts"] >= approvals.APPROVAL_ATTEMPTS:
            state["state"] = "denied"
            await approvals.store(approval.approval, state)
            approvals.push(state, approval.approval)
            raise HTTPException(status_code=409, detail="MOBILE_APPROVAL_DENIED")

        await approvals.store(approval.approval, state)
        raise HTTPException(status_code=400, detail="WRONG_NUMBER")

    state["state"] = "approved"
    await approvals.store(approval.approval, state)
    approvals.push(state, approval.approval)
    return { "status": "ok" }


async def deny_mobile(request: Request, denial: MobileDenial):
    state = await _pending(denial.approval, denial.user_id)
    await _verify_device(
        denial.user_id,
        approvals.deny_message(denial.user_id, denial.approval),
        denial.signature
    )

    state["state"] = "denied"
    await approvals.store(denial.approval, state)
    approvals.push(state, denial.approval)
    return { "status": "ok" }
