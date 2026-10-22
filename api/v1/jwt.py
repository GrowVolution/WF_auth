from webfluid.core.ext import security as s, jwt, db, cache
from webfluid.core.context import FluidContext
from webfluid.extensions.security.models import User
from fastapi import Request
from fastapi.exceptions import HTTPException
from datetime import datetime, UTC, timedelta
from sqlalchemy import select

from ...schemas.v1 import CreateToken, UpdateToken
from ...models.token import Token

NAME_LENGTH = 64
GRANT_LENGTH = 128
GRANT_COUNT = 256


def _name(value) -> str:
    name = value.strip() if isinstance(value, str) else ""
    if not name or len(name) > NAME_LENGTH:
        raise HTTPException(status_code=400, detail="INVALID_TOKEN_NAME")
    return name


def _payload(payload: dict) -> dict:
    if set(payload) - { "permissions" }:
        raise HTTPException(status_code=400, detail="INVALID_TOKEN_PAYLOAD")
    grants = payload.get("permissions", [])
    if not isinstance(grants, list) or len(grants) > GRANT_COUNT or not all(
        isinstance(grant, str) and 0 < len(grant) <= GRANT_LENGTH for grant in grants
    ):
        raise HTTPException(status_code=400, detail="INVALID_TOKEN_PAYLOAD")
    return { "permissions": list(dict.fromkeys(grants)) }


def _days(expires) -> int:
    config = FluidContext.current().fluid.config
    if expires is None: return int(config["JWT_EXPIRY_DAYS"])
    if isinstance(expires, bool) or not 0 < expires <= int(config["AUTH_JWT_MAX_DAYS"]):
        raise HTTPException(status_code=400, detail="INVALID_EXPIRY")
    return expires


def _iat(value: str) -> datetime:
    try: return datetime.fromisoformat(value)
    except (TypeError, ValueError): raise HTTPException(status_code=400, detail="UNKNOWN_TOKEN")


async def _owned(e, user_id: int, iat: datetime) -> Token:
    result = await e.exec(select(Token).where(
        Token.uid == user_id,
        Token.iat == iat,
        Token.revoked == False
    ))
    token = result.first()
    if not token: raise HTTPException(status_code=400, detail="UNKNOWN_TOKEN")
    return token


async def create_request(
        create: CreateToken, user = s.user_service.require_2fa
):
    name = _name(create.name)
    payload = _payload(create.payload)
    days = _days(create.expires)

    async with db.ensured_async_executor(model=Token) as e:
        result = await e.exec(select(Token).where(
            Token.uid == user.id,
            Token.name == name,
            Token.revoked == False
        ))
        if result.first(): raise HTTPException(status_code=400, detail="TOKEN_EXISTS")

        t = await e.insert(Token(
            user.id, name, datetime.now(UTC) + timedelta(days=days)
        ), True)

        payload["sub"] = str(user.id)
        payload["jti"] = str(t.id)

    token = await jwt.aencode(payload, expire=days)
    return { "token": token }


async def list_request(user = s.user_service.require_2fa):
    async with db.ensured_async_executor(model=Token) as e:
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
    name = _name(patch.name)
    iat = _iat(patch.iat)

    async with db.ensured_async_executor(model=Token) as e:
        token = await _owned(e, user.id, iat)

        result = await e.exec(select(Token).where(
            Token.uid == user.id,
            Token.name == name,
            Token.revoked == False,
            Token.id != token.id
        ))
        if result.first(): raise HTTPException(status_code=400, detail="TOKEN_EXISTS")

        token.name = name

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
    iat = _iat(delete.iat)

    async with db.ensured_async_executor(model=Token) as e:
        token = await _owned(e, user.id, iat)
        token.revoked = True
        token_id, delta = token.id, token.exp.replace(tzinfo=UTC) - datetime.now(UTC)

    seconds = int(delta.total_seconds())
    if seconds > 0: await cache.aset(f"jwt:revoked:{token_id}", "1", seconds)
    return { "status": "ok" }
