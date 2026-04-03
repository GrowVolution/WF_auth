from fastapi import Request
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse
from webfluid.core.ext import db, events
from sqlalchemy import select

from ...models.user import User
from ...services import TokenService, UserService


async def default_request(request: Request):
    token = request.query_params.get("token")
    if not token:
        raise HTTPException(status_code=400, detail="Missing token")

    token_data = TokenService.validate_token(token, "confirm")
    user_id = token_data.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid token")

    async with db.async_executor(model=User) as e:
        users = await e.exec(select(User).where(
            User.id == user_id
        ).limit(1))
        user = users.first()
        if not user:
            raise HTTPException(status_code=400, detail="Unknown user")

        elif user.confirmed:
            new_mail = token_data.get("email")
            if not new_mail or new_mail == user.email:
                raise HTTPException(status_code=400, detail="Already confirmed")
            user.email = new_mail

        user.confirmed = True
        try:
            from ... import additive
            html = await events.query(
                additive.unique_name("confirmation_page")
            )
            return HTMLResponse(html)

        except ValueError:
            return { "status": "ok" }


async def resend_request(request: Request, user = UserService.require_user):
    if user.confirmed:
        new_mail = request.session.get("pending_email")
        if not new_mail or new_mail == user.email:
            raise HTTPException(status_code=400, detail="Already confirmed")
        msg_type = "CHANGE"
    else:
        new_mail = None
        msg_type = "REGISTRATION"

    from ... import additive
    base_url = str(request.base_url).rstrip("/")

    token_data = { "user_id": user.id }
    if new_mail: token_data["email"] = new_mail
    token = TokenService.generate_token(token_data, "confirm")

    try:
        await events.trigger(additive.unique_name("resend_confirmation"), {
            "type": msg_type,
            "username": user.username,
            "email": user.email,
            "link": f"{base_url}{additive.prefix}/api/v1/users/confirm?token={token}"
        })
    except ValueError:
        raise HTTPException(status_code=400, detail="No confirmation handler")

    return { "status": "ok" }
