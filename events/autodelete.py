from webfluid.core.ext import db
from sqlalchemy import select
from datetime import timedelta

from ..models.user import User


async def handle_event(autodelete_after: int):
    async with db.async_executor(model=User) as e:
        users = await e.exec(select(User).where(
            User.created_at < (User.created_at + timedelta(days=autodelete_after)),
            User.confirmed == False
        ))
        for user in users.all():
            await e.delete(user)
