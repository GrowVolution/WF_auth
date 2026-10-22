from fastapi import Depends, Request, HTTPException
from sqlalchemy import select
from webfluid.core.ext import events, security as s
from webfluid.extensions.security.models import User
from webfluid.utils.logging import factory as log_factory
from typing import TYPE_CHECKING, Any, Optional
import re

if TYPE_CHECKING:
    from fastapi.params import Depends as DependsParam

_REFUSAL = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")


def _mobile_client(request: Request):
    from ..services import client
    code = client.refusal(request)
    if code: raise HTTPException(status_code=401, detail=code)


MOBILE_CLIENT = [Depends(_mobile_client)]


async def _gate(query: str, payload: dict, refused: str, failed: str):
    from .. import additive
    name = additive.unique_name(query)

    try: answers = await events.request(name, payload)
    except Exception as exc:
        if isinstance(exc, ValueError) and str(exc) == f"Query '{name}' does not exist.": return
        log_factory.exception(exc, f"[auth] A {name} handler failed, the request is refused.")
        raise HTTPException(status_code=503, detail=failed)

    for answer in answers if isinstance(answers, list) else [answers]:
        if answer is None or answer is True: continue
        detail = answer if isinstance(answer, str) and _REFUSAL.match(answer) else refused
        raise HTTPException(status_code=403, detail=detail)


async def admit(method: str, provider: Optional[str] = None):
    payload = { "method": method }
    if provider is not None: payload["provider"] = provider
    await _gate("login:admit", payload, "LOGIN_NOT_ADMITTED", "LOGIN_GATE_FAILED")


async def admit_credential(credential: str, user_id: int):
    await _gate(
        "credentials:admit", { "credential": credential, "user_id": user_id },
        "CREDENTIAL_NOT_ADMITTED", "CREDENTIAL_GATE_FAILED"
    )


def resolver(grant: str) -> Any["DependsParam"]:
    return s.user_service.requirement_and_grant(
        {"requirement": "is_admin"}, grant
    )


def role_update(user_ids):
    for user_id in dict.fromkeys(user_ids):
        events.trigger("user:role-update", user_id)


async def attached_user(user: User, e, *options) -> User:
    stmt = select(User).where(User.id == user.id)
    if options: stmt = stmt.options(*options)

    result = await e.exec(stmt)
    attached = result.first()
    if not attached:
        raise HTTPException(status_code=404, detail="UNKNOWN_USER")
    return attached


def session_verified(request: Request) -> bool:
    return bool(request.session.get("2fa_verified"))


def require_verified_session(request: Request, user: User):
    if s.user_service.has_2fa(user) and not session_verified(request):
        raise HTTPException(status_code=401, detail="TWO_FA_REQUIRED")


def require_verified_email(user: User):
    if not s.user_service.email_verified(user):
        raise HTTPException(status_code=401, detail="EMAIL_NOT_VERIFIED")


def escalate(request: Request, user: User):
    require_verified_email(user)
    require_verified_session(request, user)
