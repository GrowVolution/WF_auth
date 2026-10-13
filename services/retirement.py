from webfluid.core.ext import db, cache
from sqlalchemy import select
from datetime import datetime, UTC

from ..models.token import Token
from . import keylog, outbox


async def _revoke_tokens(user_id: int):
    now = datetime.now(UTC)
    async with db.async_executor(model=Token) as e:
        result = await e.exec(select(Token).where(Token.uid == user_id, Token.revoked == False))
        live = []
        for token in result.all():
            token.revoked = True
            live.append((token.id, token.exp.replace(tzinfo=UTC) - now))

    for token_id, delta in live:
        seconds = int(delta.total_seconds())
        if seconds > 0: await cache.aset(f"jwt:revoked:{token_id}", "1", seconds)


async def retire(user_id: int):
    await _revoke_tokens(user_id)
    if await keylog.close(user_id): await outbox.flush()
