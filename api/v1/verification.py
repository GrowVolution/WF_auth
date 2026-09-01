from fastapi import Request
from fastapi.exceptions import HTTPException
from webfluid.core.constants import EXT_BABEL
from webfluid.core.ext import db, events, security as s
from webfluid.extensions.security.models import User
from webfluid.utils.logging import factory as log_factory
from sqlalchemy import select, or_

from ..utils import attached_user, escalate
from ...schemas.v1 import SetEmail


def locale():
    if not EXT_BABEL: return None
    from webfluid.extensions.babel import get_locale
    return str(get_locale())


def confirmation_link(request: Request, token: str) -> str:
    from ... import additive
    base_url = str(request.base_url).rstrip("/")
    return f"{base_url}{additive.prefix}/api/v1/users/confirm?token={token}"


def send_confirmation(msg_type: str, username: str, email: str,
                      link: str, lc: str | None = None) -> bool:
    from ... import additive
    try:
        events.trigger(additive.unique_name("send:confirm"), {
            "type": msg_type,
            "username": username,
            "email": email,
            "link": link,
            "locale": lc or locale()
        })
        return True
    except ValueError:
        log_factory.warning(f"[{additive.name}] No confirmation handler.")
        return False


def _pending(user: User) -> tuple[str, str]:
    if not user.email:
        raise HTTPException(status_code=400, detail="NO_EMAIL")

    if not user.email_verified:
        return "REGISTRATION", user.email

    if not user.pending_email:
        raise HTTPException(status_code=400, detail="ALREADY_CONFIRMED")

    return "CHANGE", user.pending_email


async def _taken(e, email: str, user_id: int) -> bool:
    result = await e.exec(select(User).where(
        or_(User.email == email, User.pending_email == email),
        User.id != user_id
    ).limit(1))
    return result.first() is not None


async def email_request(user: User = s.user_service.require_user):
    if user.email and user.email_verified:
        return { "email": None, "verified": True }

    return { "email": user.email, "verified": user.email_verified }


async def set_email_request(
        request: Request, update: SetEmail,
        user: User = s.user_service.require_user
):
    if user.email and user.email_verified:
        escalate(request, user)

    async with db.ensured_async_executor(model=User) as e:
        user = await attached_user(user, e)

        if user.email == update.email:
            if not user.email_verified:
                raise HTTPException(status_code=400, detail="CONFIRMATION_PENDING")

            user.pending_email = None
            return { "status": "ok", "type": "CANCELLED" }

        if await _taken(e, update.email, user.id):
            raise HTTPException(status_code=400, detail="EMAIL_TAKEN")

        if user.email_verified:
            msg_type = "CHANGE"
            token = s.token_service.generate_token({
                "user_id": user.id,
                "email": update.email
            }, "confirm")

        else:
            msg_type = "REGISTRATION"
            token = s.token_service.generate_token({
                "user_id": user.id
            }, "confirm")

        if not send_confirmation(
                msg_type, user.username, update.email,
                confirmation_link(request, token)
        ):
            user.email = update.email
            user.pending_email = None
            user.email_verified = True
            return { "status": "ok", "type": "VERIFIED" }

        if msg_type == "CHANGE":
            user.pending_email = update.email
        else:
            user.email = update.email
            user.pending_email = None

        return { "status": "ok", "type": msg_type }


async def resend_request(
        request: Request, user: User = s.user_service.require_user
):
    msg_type, email = _pending(user)
    if msg_type == "CHANGE":
        escalate(request, user)

    payload = { "user_id": user.id }
    if msg_type == "CHANGE": payload["email"] = email

    token = s.token_service.generate_token(payload, "confirm")
    if not send_confirmation(
            msg_type, user.username, email,
            confirmation_link(request, token)
    ):
        raise HTTPException(status_code=400, detail="NO_HANDLER")

    return { "status": "ok", "type": msg_type }
