from webfluid.core.ext import security as s, jwt, db
from webfluid.core.context import FluidContext
from fastapi.exceptions import HTTPException
from datetime import datetime, UTC, timedelta
from sqlalchemy import select

from ...schemas.v1 import CreateToken, Token as DeleteToken
from ...models.token import Token


async def create_request(
        create: CreateToken, user = s.user_service.require_user
):
    ctx = FluidContext.current()
    e = db.current_async_executor
    result = await e.exec(select(Token).where(Token.name == create.name))
    if result.first(): raise HTTPException(status_code=400, detail="TOKEN_EXISTS")

    await e.insert(Token(
        user.id, create.name,
        datetime.now(UTC) + timedelta(
            days=create.expires or ctx.fluid.config.get("JWT_EXPIRY_DAYS", 30)
        )
    ))
    token = await jwt.aencode(create.payload, expire=create.expires)
    return { "token": token }


async def list_request(user = s.user_service.require_user):
    e = db.current_async_executor
    result = await e.exec(select(Token).where(Token.uid == user.id))
    return [ {
        "name": t.name,
        "exp": t.exp.isoformat(),
        "iat": t.iat.isoformat()
    } for t in result.all() ]


async def delete_request(delete: DeleteToken, user = s.user_service.require_user):
    e = db.current_async_executor
    result = await e.exec(select(Token).where(Token.name == delete.name))
    token = result.first()
    if not token: raise HTTPException(status_code=400, detail="UNKNOWN_TOKEN")
    if token.owner != user: raise HTTPException(status_code=403, detail="FORBIDDEN")
    await e.delete(token)
    return { "status": "ok" }
