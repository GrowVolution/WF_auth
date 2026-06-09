from webfluid.core.ext import db, events, cache
from sqlalchemy import select, delete
from datetime import datetime, UTC, timedelta
from typing import TYPE_CHECKING

from ..models.token import Token

if TYPE_CHECKING:
    from webfluid import Fluid


def get_watcher(fluid: "Fluid"):
    from .. import additive
    deadline_days = fluid.config.get("AUTH_TOKEN_EXPIRY_EVENT_DEADLINE", 5)

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

            await e.exec(delete(Token).where(Token.exp <= now))

    return watcher


async def cache_revoked():
    now = datetime.now(UTC)
    async with db.async_executor(model=Token) as e:
        result = await e.exec(select(Token).where(Token.revoked == True))

        for token in result.all():
            delta = token.exp.replace(tzinfo=UTC) - now
            await cache.aset(
                f"jwt:revoked:{token.id}", "1",
                max(0, int(delta.total_seconds()))
            )
