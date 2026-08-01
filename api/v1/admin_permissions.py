from fastapi import HTTPException
from sqlalchemy import select, func
from webfluid.core.ext import db
from webfluid.extensions.security.models import Permission
from webfluid.extensions.security.models.user import role_permissions

from ..utils import resolver
from ...schemas.v1 import AdminCreatePermission


def _serialize(permission: Permission, role_count: int = 0) -> dict:
    return {
        "id": permission.id,
        "name": permission.name,
        "role_count": role_count
    }


async def _role_counts(permission_ids: list[int], e) -> dict[int, int]:
    if not permission_ids: return {}
    result = await e.exec(
        select(role_permissions.c.permission_id, func.count())
        .where(role_permissions.c.permission_id.in_(permission_ids))
        .group_by(role_permissions.c.permission_id),
        scalars=False
    )
    return {row[0]: row[1] for row in result.all()}


async def list_request(_ = resolver("permissions:read")):
    async with db.ensured_async_executor(model=Permission) as e:
        result = await e.exec(select(Permission).order_by(Permission.name))

        permissions = list(result.all())
        counts = await _role_counts([p.id for p in permissions], e)
        return [
            _serialize(permission, counts.get(permission.id, 0))
            for permission in permissions
        ]


async def create_request(create: AdminCreatePermission, _ = resolver("permissions:write")):
    async with db.ensured_async_executor(model=Permission) as e:
        result = await e.exec(
            select(Permission).where(Permission.name == create.name).limit(1)
        )
        if result.first():
            raise HTTPException(status_code=409, detail="PERMISSION_EXISTS")

        permission = await e.insert(Permission(create.name), True)
        return _serialize(permission)


async def delete_request(permission_id: int, _ = resolver("permissions:write")):
    async with db.ensured_async_executor(model=Permission) as e:
        result = await e.exec(select(Permission).where(Permission.id == permission_id))
        permission = result.first()
        if not permission:
            raise HTTPException(status_code=404, detail="UNKNOWN_PERMISSION")

        await e.delete(permission)

    return {"status": "ok"}
