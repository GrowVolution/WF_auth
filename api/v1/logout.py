from fastapi import Request, HTTPException
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ...models.user import User

from ...services import UserService


async def default_request(
        request: Request,
        current_user: Optional["User"] = UserService.current_user
):
    if not current_user:
        raise HTTPException(status_code=400, detail="Not logged in")

    request.session.clear()
    return { "status": "ok" }
