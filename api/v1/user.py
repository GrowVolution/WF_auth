from fastapi import Request
from fastapi.exceptions import HTTPException
from webfluid.core.ext import db, events, security as s
from webfluid.extensions.babel.utils import get_locale
from webfluid.extensions.security.models.user import User
from webfluid.utils.logging import factory as log_factory
from sqlalchemy import select, delete

from ...schemas.v1 import UpdateUser


async def available_request(user: User = s.user_service.current_user):
    return { "available": user is not None }


async def get_request(user: User = s.user_service.require_user):
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
        "pending_email": user.pending_email,
        "email_verified": user.email_verified,
        "roles": roles,
        "is_admin": is_admin
    }


async def update_request(
        request: Request,
        update: UpdateUser,
        user: User = s.user_service.require_user
):
    if user.psw_hash:
        if update.new_password and not update.current_password:
            raise HTTPException(status_code=400, detail="MISSING_CURRENT_PASSWORD")

        elif update.current_password and not s.hash_service.verify(
                user.psw_hash, update.current_password
        ):
            raise HTTPException(status_code=401, detail="INVALID_CREDENTIALS")

    if user.username != update.username:
        async with db.async_executor(model=User) as e:
            users = await e.exec(select(User).where(
                User.username == update.username
            ).limit(1))
            if users.first():
                raise HTTPException(status_code=400, detail="USERNAME_TAKEN")

        user.username = update.username

    if update.new_password:
        user.psw_hash = s.hash_service.hash(update.new_password)

    if user.email != update.email:
        async with db.async_executor(model=User) as e:
            users = await e.exec(select(User).where(
                User.email == update.email
            ).limit(1))
            if users.first():
                raise HTTPException(status_code=400, detail="EMAIL_TAKEN")

        from ... import additive
        base_url = str(request.base_url).rstrip("/")

        try:
            if user.email:
                token = s.token_service.generate_token({
                    "user_id": user.id,
                    "email": update.email
                }, "confirm")
                event = "user_changed_mail"
                event_type = "CHANGE"
                user.pending_email = update.email

            else:
                token = s.token_service.generate_token({
                    "user_id": user.id
                }, "confirm")
                event = "user_registered"
                event_type = "REGISTRATION"
                user.email = update.email

            events.trigger(additive.unique_name(event), {
                "type": event_type,
                "username": user.username,
                "email": update.email,
                "link": f"{base_url}{additive.prefix}/api/v1/users/confirm?token={token}",
                "locale": get_locale()
            })

        except ValueError:
            log_factory.warning(f"[{additive.name}] No confirmation handler.")
            user.email = update.email
            user.pending_email = None

    return { "status": "ok" }


async def delete_request(request: Request, user: User = s.user_service.require_user):
    async with db.async_executor(model=User) as e:
        await e.exec(delete(User).where(User.id == user.id))

    request.session.clear()
    return { "status": "ok" }
