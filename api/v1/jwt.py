from webfluid.core.ext import security as s, jwt, db, cache
from webfluid.core.context import FluidContext
from webfluid.extensions.security.models import User
from fastapi import Request
from fastapi.exceptions import HTTPException
from datetime import datetime, UTC, timedelta
from sqlalchemy import select

from ...schemas.v1 import CreateToken, UpdateToken
from ...models.token import Token


async def create_request(
        create: CreateToken, user = s.user_service.require_2fa
):
    ctx = FluidContext.current()
    e = db.current_async_executor
    result = await e.exec(select(Token).where(
        Token.uid == user.id,
        Token.name == create.name,
        Token.revoked == False
    ))
    if result.first(): raise HTTPException(status_code=400, detail="TOKEN_EXISTS")

    t = await e.insert(Token(
        user.id, create.name,
        datetime.now(UTC) + timedelta(
            days=create.expires or ctx.fluid.config.get("JWT_EXPIRY_DAYS", 30)
        )
    ), True)

    payload = create.payload
    payload["sub"] = str(user.id)
    payload["jti"] = str(t.id)
    token = await jwt.aencode(payload, expire=create.expires)
    return { "token": token }


async def list_request(user = s.user_service.require_2fa):
    e = db.current_async_executor
    result = await e.exec(select(Token).where(
        Token.uid == user.id,
        Token.revoked == False
    ))
    return [ {
        "name": t.name,
        "exp": t.exp.isoformat(),
        "iat": t.iat.isoformat()
    } for t in result.all() ]


async def patch_request(patch: UpdateToken, user = s.user_service.require_2fa):
    e = db.current_async_executor

    iat = datetime.fromisoformat(patch.iat)
    result = await e.exec(select(Token).where(
        Token.uid == user.id,
        Token.name == patch.name,
        Token.iat != iat
    ))
    if result.first(): raise HTTPException(status_code=400, detail="TOKEN_EXISTS")

    result = await e.exec(select(Token).where(
        Token.iat == iat,
        Token.revoked == False
    ))
    token = result.first()
    if not token: raise HTTPException(status_code=400, detail="UNKNOWN_TOKEN")
    if token.owner != user: raise HTTPException(status_code=403, detail="FORBIDDEN")

    token.name = patch.name
    return { "status": "ok" }


async def metadata_request(request: Request):
    scheme, _, raw = request.headers.get("Authorization", "").partition(" ")
    raw = raw.strip()
    if scheme.lower() != "bearer" or not raw:
        raise HTTPException(status_code=401, detail="INVALID_TOKEN")

    try: payload = await jwt.adecode(raw)
    except Exception: raise HTTPException(status_code=401, detail="INVALID_TOKEN")

    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(status_code=401, detail="INVALID_TOKEN")

    async with db.async_executor(model=User) as e:
        result = await e.exec(select(User).where(User.id == int(sub)))
        user = result.first()
        if not user:
            raise HTTPException(status_code=404, detail="UNKNOWN_USER")

        exp = payload.get("exp")
        valid_days = None
        if exp:
            remaining = datetime.fromtimestamp(exp, UTC) - datetime.now(UTC)
            valid_days = max(0, remaining.days)

        return { "username": user.username, "valid_days": valid_days, "exp": exp }


async def delete_request(delete: UpdateToken, user = s.user_service.require_2fa):
    e = db.current_async_executor
    result = await e.exec(select(Token).where(
        Token.iat == datetime.fromisoformat(delete.iat)
    ))
    token = result.first()
    if not token: raise HTTPException(status_code=400, detail="UNKNOWN_TOKEN")
    if token.owner != user: raise HTTPException(status_code=403, detail="FORBIDDEN")
    token.revoked = True
    delta = token.exp.replace(tzinfo=UTC) - datetime.now(UTC)
    await cache.aset(
        f"jwt:revoked:{token.id}", "1",
        max(0, int(delta.total_seconds()))
    )
    return { "status": "ok" }
