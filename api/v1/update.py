from fastapi import Request
from fastapi.exceptions import HTTPException
from webfluid.core.ext import db, events
from sqlalchemy import select

from ...models.user import User
from ...schemas.v1 import UpdateUser
from ...services import UserService, HashService, TokenService


async def handle_request(
        request: Request,
        update: UpdateUser,
        user = UserService.require_user
):
    if not HashService.verify(user.psw_hash, update.current_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if user.username != update.username:
        async with db.async_executor(model=User) as e:
            users = await e.exec(select(User).where(
                User.username == update.username
            ).limit(1))
            if users.first():
                raise HTTPException(status_code=400, detail="Username already taken")

        user.username = update.username

    if update.new_password:
        user.psw_hash = HashService.hash(update.new_password)

    if user.email != update.email:
        from ... import additive

        base_url = str(request.base_url).rstrip("/")
        token = TokenService.generate_token({
            "user_id": user.id,
            "email": update.email
        }, "confirm")

        try:
            await events.trigger(additive.unique_name("user_changed_mail"), {
                "type": "CHANGE",
                "username": user.username,
                "email": user.email,
                "link": f"{base_url}{additive.prefix}/api/v1/users/confirm?token={token}"
            })
            request.session["pending_email"] = update.email

        except ValueError:
            user.email = update.email

    return { "status": "ok" }
