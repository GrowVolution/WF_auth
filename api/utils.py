from fastapi import Request, HTTPException
from sqlalchemy import select
from webfluid.core.ext import security as s
from webfluid.extensions.security.models import User
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi.params import Depends as DependsParam


def resolver(grant: str) -> Any["DependsParam"]:
    return s.user_service.requirement_and_grant(
        {"requirement": "is_admin"}, grant
    )


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
