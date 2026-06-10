from fastapi import HTTPException
from sqlalchemy import select
from webfluid.core.ext import db
from webfluid.extensions.security.models import Permission

from ..utils import resolver
from ...schemas.v1 import AdminCreatePermission


def _serialize(permission: Permission) -> dict:
    return {
        "id": permission.id,
        "name": permission.name,
        "role_count": len(permission.roles)
    }


async def list_request(_ = resolver("permissions:read")):
    e = db.current_async_executor
    result = await e.exec(select(Permission).order_by(Permission.name))
    return [_serialize(permission) for permission in result.all()]


async def create_request(create: AdminCreatePermission, _ = resolver("permissions:write")):
    e = db.current_async_executor

    result = await e.exec(
        select(Permission).where(Permission.name == create.name).limit(1)
    )
    if result.first():
        raise HTTPException(status_code=409, detail="PERMISSION_EXISTS")

    permission = await e.insert(Permission(create.name), True)
    return _serialize(permission)


async def delete_request(permission_id: int, _ = resolver("permissions:write")):
    e = db.current_async_executor
    result = await e.exec(select(Permission).where(Permission.id == permission_id))
    permission = result.first()
    if not permission:
        raise HTTPException(status_code=404, detail="UNKNOWN_PERMISSION")

    await e.delete(permission)
    return {"status": "ok"}
