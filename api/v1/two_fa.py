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
import io, json, base64, secrets, pyotp, qrcode

from ...schemas.v1 import (
    TOTPVerify, BackupCodeVerify,
    WebAuthnRegister, WebAuthnVerify, WebAuthnDelete
)

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
    e = db.current_async_executor

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
        "verified": bool(request.session.get("2fa_verified")),
    }



async def request_totp(user: User = s.user_service.require_user):
    issuer, *_ = _config()
    e = db.current_async_executor

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

    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr = base64.b64encode(buf.getvalue()).decode()

    return { "secret": secret, "uri": uri, "qr": qr }


async def verify_totp(request: Request, verify: TOTPVerify,
                      user: User = s.user_service.require_user):
    e = db.current_async_executor
    result = await e.exec(select(TOTPSecret).where(
        TOTPSecret.user_id == user.id
    ))
    totp = result.first()
    if not totp:
        raise HTTPException(status_code=400, detail="TWO_FA_NOT_SETUP")

    if not pyotp.TOTP(totp.secret).verify(verify.code, valid_window=1):
        raise HTTPException(status_code=401, detail="INVALID_OTP")

    totp.confirmed = True
    _mark_verified(request)
    return { "status": "ok" }


async def delete_totp(user: User = s.user_service.require_2fa):
    e = db.current_async_executor
    result = await e.exec(select(TOTPSecret).where(
        TOTPSecret.user_id == user.id
    ))
    totp = result.first()
    if not totp:
        raise HTTPException(status_code=400, detail="TWO_FA_NOT_SETUP")

    await e.delete(totp)
    return { "status": "ok" }



async def register_webauthn(request: Request, user: User = s.user_service.require_user):
    _, rp_id, rp_name, _ = _config()
    e = db.current_async_executor
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

    e = db.current_async_executor
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
    e = db.current_async_executor
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

    e = db.current_async_executor
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


async def delete_webauthn(delete: WebAuthnDelete,
                          user: User = s.user_service.require_2fa):
    e = db.current_async_executor
    result = await e.exec(select(WebAuthnCredential).where(
        WebAuthnCredential.user_id == user.id,
        WebAuthnCredential.credential_id == delete.credential_id
    ))
    credential = result.first()
    if not credential:
        raise HTTPException(status_code=400, detail="UNKNOWN_CREDENTIAL")

    await e.delete(credential)
    return { "status": "ok" }



async def request_backup(user: User = s.user_service.require_user):
    cfg = FluidContext.current().fluid.config
    count = cfg.get("AUTH_2FA_BACKUP_CODE_COUNT", 10)
    digits = cfg.get("AUTH_2FA_BACKUP_CODE_DIGITS", 8)

    e = db.current_async_executor
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
        await e.insert(BackupCode(user.id, s.hash_service.hash(code)))

    return { "codes": codes }


async def verify_backup(request: Request, verify: BackupCodeVerify,
                        user: User = s.user_service.require_user):
    e = db.current_async_executor
    result = await e.exec(select(BackupCode).where(
        BackupCode.user_id == user.id,
        BackupCode.used == False
    ))

    for code in result.all():
        if s.hash_service.verify(code.code_hash, verify.code):
            code.used = True
            _mark_verified(request)
            return { "status": "ok" }

    raise HTTPException(status_code=401, detail="INVALID_BACKUP_CODE")


async def delete_backup(user: User = s.user_service.require_2fa):
    e = db.current_async_executor
    result = await e.exec(select(BackupCode).where(
        BackupCode.user_id == user.id
    ))
    for code in result.all():
        await e.delete(code)

    return { "status": "ok" }
