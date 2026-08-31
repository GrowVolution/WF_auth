from webfluid.core.ext import db
from webfluid.extensions.security.models import User
from webfluid.utils.logging import factory as log_factory
from sqlalchemy import select
from datetime import datetime, UTC, timedelta

from ..api.v1.user import purge


async def handle_event(autodelete_after: int):
    if not isinstance(autodelete_after, int) or autodelete_after < 1: return

    deadline = datetime.now(UTC).replace(tzinfo=None) - timedelta(
        days=autodelete_after
    )

    async with db.async_executor(model=User) as e:
        users = await e.exec(select(User).where(
            User.created_at < deadline,
            User.email_verified == False
        ))
        stale = [user.id for user in users.all()]

    purged = []
    for user_id in stale:
        if await purge(user_id):
            purged.append(user_id)
            continue

        from ... import additive
        log_factory.error(
            f"[{additive.name}] Keeping user {user_id}: "
            f"a {additive.unique_name('user:delete')} handler failed."
        )

    if not purged: return

    async with db.async_executor(model=User) as e:
        result = await e.exec(select(User).where(User.id.in_(purged)))
        for user in result.all(): await e.delete(user)
