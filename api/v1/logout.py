from fastapi import Request, HTTPException
from webfluid.core.ext import security as s
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from webfluid.extensions.security.models import User


async def default_request(
        request: Request,
        current_user: Optional["User"] = s.user_service.current_user
):
    if not current_user:
        raise HTTPException(status_code=400, detail="NOT_LOGGED_IN")

    request.session.clear()
    return { "status": "ok" }
