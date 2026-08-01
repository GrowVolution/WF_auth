from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from webfluid.core.ext import db, security as s
from webfluid.core.context import FluidContext
from webfluid.extensions.security.models import User, Role, Permission
from webfluid.extensions.security.models.user import user_roles

from ..utils import resolver
from ...schemas.v1 import (
    AdminCreateRole, AdminUpdateRole, AdminRolePermission, AdminRoleMember
)


def _serialize(role: Role, user_count: int = 0) -> dict:
    return {
        "id": role.id,
        "name": role.name,
        "is_admin": role.is_admin,
        "requires_2fa": role.requires_2fa,
        "permissions": [perm.name for perm in role.permissions],
        "user_count": user_count
    }


async def _user_counts(role_ids: list[int], e) -> dict[int, int]:
    if not role_ids: return {}
    result = await e.exec(
        select(user_roles.c.role_id, func.count())
        .where(user_roles.c.role_id.in_(role_ids))
        .group_by(user_roles.c.role_id),
        scalars=False
    )
    return {row[0]: row[1] for row in result.all()}


async def _user_count(role_id: int, e) -> int:
    return (await _user_counts([role_id], e)).get(role_id, 0)


def _resolve_requires_2fa(is_admin: bool, requires_2fa: bool) -> bool:
    if is_admin and FluidContext.current().fluid.config.get(
            "AUTH_ADMIN_ROLE_REQUIRES_2FA", True
    ):
        return True
    return requires_2fa


async def _get_role(role_id: int, e) -> Role:
    result = await e.exec(select(Role).options(
        selectinload(Role.permissions)
    ).where(Role.id == role_id))
    role = result.first()
    if not role:
        raise HTTPException(status_code=404, detail="UNKNOWN_ROLE")
    return role


async def _get_permission(name: str, e) -> Permission:
    result = await e.exec(select(Permission).where(Permission.name == name))
    permission = result.first()
    if not permission:
        raise HTTPException(status_code=404, detail="UNKNOWN_PERMISSION")
    return permission


async def config_request(_ = resolver("roles:read")):
    cfg = FluidContext.current().fluid.config
    return {
        "admin_role_requires_2fa": cfg.get("AUTH_ADMIN_ROLE_REQUIRES_2FA", True)
    }


async def list_request(_ = resolver("roles:read")):
    async with db.ensured_async_executor(model=Role) as e:
        result = await e.exec(select(Role).options(
            selectinload(Role.permissions)
        ).order_by(Role.name))

        roles = list(result.all())
        counts = await _user_counts([role.id for role in roles], e)
        return [_serialize(role, counts.get(role.id, 0)) for role in roles]


async def create_request(create: AdminCreateRole, _ = resolver("roles:write")):
    async with db.ensured_async_executor(model=Role) as e:
        result = await e.exec(select(Role).where(Role.name == create.name).limit(1))
        if result.first():
            raise HTTPException(status_code=409, detail="ROLE_EXISTS")

        role = await e.insert(Role(create.name))
        role.is_admin = create.is_admin
        role.requires_2fa = _resolve_requires_2fa(create.is_admin, create.requires_2fa)

        for name in create.permissions:
            role.permissions.append(await _get_permission(name, e))

        await e.flush()
        return _serialize(role)


async def update_request(
        role_id: int, update: AdminUpdateRole, _ = resolver("roles:write")
):
    async with db.ensured_async_executor(model=Role) as e:
        role = await _get_role(role_id, e)

        if update.name is not None and update.name != role.name:
            result = await e.exec(select(Role).where(Role.name == update.name).limit(1))
            if result.first():
                raise HTTPException(status_code=409, detail="ROLE_EXISTS")
            role.name = update.name

        is_admin = role.is_admin if update.is_admin is None else update.is_admin
        requires_2fa = (
            role.requires_2fa if update.requires_2fa is None else update.requires_2fa
        )
        role.is_admin = is_admin
        role.requires_2fa = _resolve_requires_2fa(is_admin, requires_2fa)

        if update.permissions is not None:
            resolved = []
            for name in update.permissions:
                resolved.append(await _get_permission(name, e))
            role.permissions = resolved

        await e.flush()
        return _serialize(role, await _user_count(role.id, e))


async def delete_request(role_id: int, _ = resolver("roles:write")):
    async with db.ensured_async_executor(model=Role) as e:
        role = await _get_role(role_id, e)
        await e.delete(role)

    return {"status": "ok"}


async def add_permission_request(
        role_id: int, body: AdminRolePermission, _ = resolver("roles:write")
):
    async with db.ensured_async_executor(model=Role) as e:
        role = await _get_role(role_id, e)
        permission = await _get_permission(body.permission, e)

        if permission in role.permissions:
            raise HTTPException(status_code=409, detail="PERMISSION_ALREADY_ON_ROLE")

        role.permissions.append(permission)

    return {"status": "ok"}


async def remove_permission_request(
        role_id: int, permission_id: int, _ = resolver("roles:write")
):
    async with db.ensured_async_executor(model=Role) as e:
        role = await _get_role(role_id, e)

        for permission in role.permissions:
            if permission.id == permission_id:
                role.permissions.remove(permission)
                return {"status": "ok"}

    raise HTTPException(status_code=404, detail="PERMISSION_NOT_ON_ROLE")


async def add_member_request(
        role_id: int, body: AdminRoleMember, _ = resolver("roles:write")
):
    async with db.ensured_async_executor(model=Role) as e:
        role = await _get_role(role_id, e)

        result = await e.exec(select(User).options(
            selectinload(User.roles)
        ).where(User.id == body.user_id))
        user = result.first()
        if not user:
            raise HTTPException(status_code=404, detail="UNKNOWN_USER")

        if role in user.roles:
            raise HTTPException(status_code=409, detail="USER_ALREADY_IN_ROLE")

        user.roles.append(role)

    return {"status": "ok"}


async def remove_member_request(
        role_id: int, user_id: int, admin: User = resolver("roles:write")
):
    async with db.ensured_async_executor(model=Role) as e:
        role = await _get_role(role_id, e)

        result = await e.exec(select(User).options(
            selectinload(User.roles)
        ).where(User.id == user_id))
        user = result.first()
        if not user:
            raise HTTPException(status_code=404, detail="UNKNOWN_USER")

        if admin and user.id == admin.id and role.is_admin \
                and await s.user_service.is_admin(user):
            remaining_admin = any(
                r.is_admin for r in user.roles if r.id != role.id
            )
            if not remaining_admin:
                raise HTTPException(status_code=400, detail="CANNOT_REVOKE_OWN_ADMIN")

        if role not in user.roles:
            raise HTTPException(status_code=404, detail="USER_NOT_IN_ROLE")

        user.roles.remove(role)

    return {"status": "ok"}
