from fastapi import Request, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from webfluid.core.ext import db, security as s, babel
from webfluid.core.context import FluidContext
from webfluid.extensions.security.models import User, Role, Permission
from typing import Optional

from .create import _create_user, _trigger
from .user import purge
from .verification import confirmation_link, send_confirmation
from ..utils import resolver
from ...schemas.v1 import CreateUser, AdminUpdateUser


def _with_relations(stmt):
    return stmt.options(
        selectinload(User.identities),
        selectinload(User.roles)
    )


async def _serialize(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "email_verified": user.email_verified,
        "is_admin": await s.user_service.is_admin(user),
        "has_2fa": s.user_service.has_2fa(user),
        "sso": any(i.provider == "sso" for i in user.identities),
        "roles": [role.name for role in user.roles]
    }


async def _get_user(user_id: int, e) -> User:
    result = await e.exec(_with_relations(
        select(User).where(User.id == user_id)
    ))
    user = result.first()
    if not user:
        raise HTTPException(status_code=404, detail="UNKNOWN_USER")
    return user


async def create_request(
        request: Request, create: CreateUser,
        _ = resolver("users:write")
):
    async with db.ensured_async_executor(model=User) as e:
        user = await _create_user(create, e)

        for r in create.roles:
            roles = await e.exec(select(Role).options(
                selectinload(Role.permissions)
            ).where(Role.name == r.name))
            role = roles.first()

            if not role:
                ctx = FluidContext.current()
                role = await e.insert(Role(r.name))
                role.is_admin = r.is_admin
                role.requires_2fa = r.requires_2fa or ctx.fluid.config.get(
                    "AUTH_ADMIN_ROLE_REQUIRES_2FA", True
                ) if r.is_admin else r.requires_2fa

                for p in r.permissions:
                    permissions = await e.exec(select(Permission).where(Permission.name == p))
                    permission = permissions.first()
                    if not permission:
                        permission = await e.insert(Permission(p))
                    role.permissions.append(permission)

            user.roles.append(role)

        _trigger(request, user)

    return { "status": "ok" }


async def list_request(
        role: Optional[str] = None,
        permission: Optional[str] = None,
        search: Optional[str] = None,
        _ = resolver("users:read")
):
    async with db.ensured_async_executor(model=User) as e:
        stmt = select(User)
        if role:
            stmt = stmt.where(User.roles.any(Role.name == role))
        if permission:
            stmt = stmt.where(
                User.roles.any(Role.permissions.any(Permission.name == permission))
            )
        if search:
            stmt = stmt.where(User.username.ilike(f"%{search}%"))

        stmt = _with_relations(stmt.order_by(User.username))

        result = await e.exec(stmt)
        return [await _serialize(user) for user in result.all()]


async def get_request(user_id: int, _ = resolver("users:read")):
    async with db.ensured_async_executor(model=User) as e:
        user = await _get_user(user_id, e)
        return await _serialize(user)


async def update_request(
        request: Request, user_id: int, update: AdminUpdateUser,
        admin: User = resolver("users:write")
):
    async with db.ensured_async_executor(model=User) as e:
        user = await _get_user(user_id, e)

        if update.username is not None and update.username != user.username:
            result = await e.exec(select(User).where(
                User.username == update.username
            ).limit(1))
            if result.first():
                raise HTTPException(status_code=409, detail="USERNAME_TAKEN")
            user.username = update.username

        if update.email is not None and update.email != user.email:
            result = await e.exec(select(User).where(
                User.email == update.email
            ).limit(1))
            if result.first():
                raise HTTPException(status_code=409, detail="EMAIL_TAKEN")

            token = s.token_service.generate_token({
                "user_id": user.id,
                "email": update.email
            }, "confirm")

            if send_confirmation(
                    "CHANGE", user.username, update.email,
                    confirmation_link(request, token), babel.default_locale
            ):
                user.pending_email = update.email

            else:
                user.email = update.email
                user.pending_email = None
                user.email_verified = True

        if update.new_password is not None:
            user.psw_hash = s.hash_service.hash(update.new_password)

        if update.roles is not None:
            if admin and user.id == admin.id and await s.user_service.is_admin(user):
                resolved = await _resolve_roles(update.roles, e)
                if not any(role.is_admin for role in resolved):
                    raise HTTPException(status_code=400, detail="CANNOT_REVOKE_OWN_ADMIN")
                user.roles = resolved
            else:
                user.roles = await _resolve_roles(update.roles, e)

    return {"status": "ok"}


async def _resolve_roles(names: list[str], e) -> list[Role]:
    roles = []
    for name in names:
        result = await e.exec(select(Role).where(Role.name == name))
        role = result.first()
        if not role:
            raise HTTPException(status_code=404, detail="UNKNOWN_ROLE")
        roles.append(role)
    return roles


async def delete_request(user_id: int, admin: User = resolver("users:write")):
    if admin and user_id == admin.id:
        raise HTTPException(status_code=400, detail="CANNOT_DELETE_SELF")

    await purge(user_id)

    async with db.ensured_async_executor(model=User) as e:
        user = await _get_user(user_id, e)
        await e.delete(user)

    return {"status": "ok"}
