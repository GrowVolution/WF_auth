from fastapi import Request
from fastapi.exceptions import HTTPException
from webfluid.core.ext import db, events
from webfluid.extensions.utils.babel import get_locale
from sqlalchemy import select, delete

from ...models.user import User
from ...schemas.v1 import UpdateUser
from ...services import UserService, HashService, TokenService


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


async def update_request(
        request: Request,
        update: UpdateUser,
        user: User = UserService.require_user
):
    if user.psw_hash:
        if update.new_password and not update.current_password:
            raise HTTPException(status_code=400, detail="Missing current password")

        elif update.current_password and not HashService.verify(user.psw_hash, update.current_password):
            raise HTTPException(status_code=401, detail="Invalid credentials")

    if user.username != update.username:
        async with db.async_executor(model=User) as e:
            users = await e.exec(select(User).where(
                User.username == update.username
            ).limit(1))
            if users.first():
                raise HTTPException(status_code=400, detail="Username already taken")

        user.username = update.username

    if update.new_password:
        user.psw_hash = HashService.hash(update.new_password)

    if user.email != update.email:
        async with db.async_executor(model=User) as e:
            users = await e.exec(select(User).where(
                User.email == update.email
            ).limit(1))
            if users.first():
                raise HTTPException(status_code=400, detail="Email already taken")

        from ... import additive
        base_url = str(request.base_url).rstrip("/")

        try:
            if user.email:
                token = TokenService.generate_token({
                    "user_id": user.id,
                    "email": update.email
                }, "confirm")
                event = "user_changed_mail"
                event_type = "CHANGE"
                request.session["pending_email"] = update.email

            else:
                token = TokenService.generate_token({
                    "user_id": user.id
                }, "confirm")
                event = "user_registered"
                event_type = "REGISTRATION"
                user.email = update.email

            await events.trigger(additive.unique_name(event), {
                "type": event_type,
                "username": user.username,
                "email": update.email,
                "link": f"{base_url}{additive.prefix}/api/v1/users/confirm?token={token}",
                "locale": get_locale()
            })

        except ValueError:
            user.email = update.email

    return { "status": "ok" }


async def delete_request(request: Request, user: User = UserService.require_user):
    async with db.async_executor(model=User) as e:
        await e.exec(delete(User).where(User.id == user.id))

    request.session.clear()
    return { "status": "ok" }
