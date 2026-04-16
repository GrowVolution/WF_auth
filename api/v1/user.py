from fastapi import Request
from webfluid.core.ext import db
from sqlalchemy import delete

from ...models.user import User
from ...services import UserService


async def available_request(user: User = UserService.current_user):
    return { "available": user is not None }


async def get_request(user: User = UserService.require_user):
    roles = []
    is_admin = False
    for role in user.roles:
        roles.append({
            "name": role.name,
            "permissions": [
                perm.name for perm in role.permissions
            ]
        })
        if role.is_admin: is_admin = True

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "confirmed": user.confirmed,
        "roles": roles,
        "is_admin": is_admin
    }


async def delete_request(request: Request, user: User = UserService.require_user):
    async with db.async_executor(model=User) as e:
        await e.exec(delete(User).where(User.id == user.id))

    request.session.clear()
    return { "status": "ok" }
