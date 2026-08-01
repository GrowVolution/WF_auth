from fastapi import Request
from fastapi.exceptions import HTTPException
from webfluid.core.ext import db, events, security as s
from webfluid.extensions.babel import get_locale
from webfluid.extensions.security.models import User, Role
from webfluid.utils.logging import factory as log_factory
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..utils import attached_user
from ...schemas.v1 import UpdateUser


async def available_request(user: User = s.user_service.current_user):
    return { "available": user is not None }


async def get_request(user: User = s.user_service.require_2fa):
    async with db.ensured_async_executor(model=User) as e:
        user = await attached_user(
            user, e, selectinload(User.roles).selectinload(Role.permissions)
        )

        roles = []
        is_admin = False
        for role in user.roles:
            roles.append({
                "name": role.name,
                "permissions": [
                    perm.name for perm in role.permissions
                ],
                "requires_2fa": role.requires_2fa
            })
            if role.is_admin: is_admin = True

        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "pending_email": user.pending_email,
            "email_verified": user.email_verified,
            "roles": roles,
            "is_admin": is_admin,
            "has_2fa": s.user_service.has_2fa(user)
        }


async def update_request(
        request: Request,
        update: UpdateUser,
        user: User = s.user_service.require_2fa
):
    if user.psw_hash:
        if update.new_password and not update.current_password:
            raise HTTPException(status_code=400, detail="MISSING_CURRENT_PASSWORD")

        elif update.current_password and not s.hash_service.verify(
                user.psw_hash, update.current_password
        ):
            raise HTTPException(status_code=401, detail="INVALID_CREDENTIALS")

    async with db.ensured_async_executor(model=User) as e:
        user = await attached_user(user, e)

        if user.username != update.username:
            users = await e.exec(select(User).where(
                User.username == update.username
            ).limit(1))
            if users.first():
                raise HTTPException(status_code=400, detail="USERNAME_TAKEN")

            user.username = update.username

        if update.new_password:
            user.psw_hash = s.hash_service.hash(update.new_password)

        if user.email != update.email:
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
                    event_type = "CHANGE"
                    user.pending_email = update.email

                else:
                    token = s.token_service.generate_token({
                        "user_id": user.id
                    }, "confirm")
                    event_type = "REGISTRATION"
                    user.email = update.email

                events.trigger(additive.unique_name("send:confirm"), {
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


async def delete_request(request: Request, user: User = s.user_service.require_2fa):
    async with db.ensured_async_executor(model=User) as e:
        await e.delete(await attached_user(user, e))

    request.session.clear()
    return { "status": "ok" }
