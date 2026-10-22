from webfluid.core.ext import db, events, cache
from sqlalchemy import select, delete
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, UTC, timedelta
from typing import TYPE_CHECKING

from .models.token import Token

if TYPE_CHECKING:
    from webfluid import Fluid


def get_watcher(fluid: "Fluid"):
    from . import additive
    deadline_days = fluid.config["AUTH_TOKEN_EXPIRY_EVENT_DEADLINE"]

    async def watcher():
        now = datetime.now(UTC)
        deadline = now + timedelta(days=deadline_days)

        async with db.async_executor(model=Token) as e:
            result = await e.exec(select(Token).where(Token.exp <= deadline))
            try:
                for token in result.all():
                    if token.revoked: continue
                    events.trigger(
                        additive.unique_name("token:expires"), {
                            "username": token.owner.username,
                            "email": token.owner.email,
                            "token": token.name,
                            "exp": token.exp,
                            "iat": token.iat
                        }
                    )
            except ValueError: pass

            await e.exec(delete(Token).where(Token.exp <= now), False)

    return watcher


async def cache_revoked():
    now = datetime.now(UTC)
    try:
        async with db.async_executor(model=Token) as e:
            result = await e.exec(select(Token).where(Token.revoked == True))
            revoked = result.all()
    except SQLAlchemyError as exc:
        raise RuntimeError(
            "Cannot load token revocations. Run migrations and restore database "
            "access before enabling auth."
        ) from exc

    for token in revoked:
        seconds = int((token.exp.replace(tzinfo=UTC) - now).total_seconds())
        if seconds > 0: await cache.aset(f"jwt:revoked:{token.id}", "1", seconds)
