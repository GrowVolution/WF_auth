from fastapi import HTTPException
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
