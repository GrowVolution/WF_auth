from webfluid.core.ext import db
from sqlalchemy import select

from ..models.user import User


async def handle_event(username: str):
    async with db.async_executor(model=User) as e:
        users = await e.exec(select(User).where(
            User.username == username
        ).limit(1))

        user = users.first()
        if user: user.confirmed = False
