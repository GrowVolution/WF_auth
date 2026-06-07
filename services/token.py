from webfluid.core.ext import db, events
from sqlalchemy import select
from datetime import datetime, UTC, timedelta
from typing import TYPE_CHECKING

from ..models.token import Token

if TYPE_CHECKING:
    from webfluid import Fluid


def get_watcher(fluid: "Fluid"):
    from .. import additive
    deadline_days = fluid.config.get("AUTH_TOKEN_EXPIRY_EVENT_DEADLINE", 5)

    async def watcher():
        deadline = datetime.now(UTC) + timedelta(days=deadline_days)

        async with db.async_executor(model=Token) as e:
            result = await e.exec(select(Token).where(Token.exp <= deadline))
            try:
                for token in result.all(): events.trigger(
                    additive.unique_name("token:expires"), {
                        "username": token.owner.username,
                        "email": token.owner.email,
                        "token": token.name,
                        "exp": token.exp,
                        "iat": token.iat
                    }
                )
            except ValueError: pass

    return watcher
