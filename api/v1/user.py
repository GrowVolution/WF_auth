from fastapi import Request
from fastapi.exceptions import HTTPException
from webfluid.core.ext import db, events, security as s
from webfluid.extensions.security.models import User, Role
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..utils import attached_user, admit_credential
from ...services import mobile as devices
from ...schemas.v1 import UpdateUser


async def available_request(request: Request, user: User = s.user_service.current_user):
    return {
        "available": user is not None,
        "mobile_2fa": user is None and "mobile_approval" in request.session
    }


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
            "has_2fa": s.user_service.has_2fa(user),
            "has_mobile": await devices.device(user.id) is not None
        }


async def update_request(
        request: Request, update: UpdateUser,
        user: User = s.user_service.require_2fa
):
    if update.new_password:
        await admit_credential("password", user.id)

    if user.psw_hash:
        if update.new_password and not update.current_password:
            raise HTTPException(status_code=400, detail="MISSING_CURRENT_PASSWORD")

        elif update.current_password and not await s.hash_service.averify(
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
            user.psw_hash = await s.hash_service.ahash(update.new_password)

    return { "status": "ok" }


async def purge(user_id: int) -> bool:
    from ... import additive
    from ...services.retirement import retire
    try:
        results = await events.request(additive.unique_name("user:delete"), {
            "user_id": user_id
        })
    except ValueError:
        results = []

    if not all(result is not None for result in results): return False
    await retire(user_id)
    return True


async def delete_request(request: Request, user: User = s.user_service.require_2fa):
    from ...services import actions, outbox
    try:
        envelope = actions.from_header(request.headers.get(actions.HEADER))
    except actions.ActionError as exc:
        raise HTTPException(status_code=400, detail=exc.code)
    if request.session.get("mobile") or envelope is not None:
        if envelope is None:
            raise HTTPException(status_code=401, detail="ACTION_SIGNATURE_REQUIRED")
        try:
            await actions.accept(user.id, envelope, "auth:account.delete", "auth:account", {})
        except actions.ActionError as exc:
            raise HTTPException(status_code=401, detail=exc.code)
        await outbox.flush()

    if not await purge(user.id):
        raise HTTPException(status_code=500, detail="DELETION_INCOMPLETE")

    async with db.ensured_async_executor(model=User) as e:
        await e.delete(await attached_user(user, e))

    request.session.clear()
    return { "status": "ok" }
