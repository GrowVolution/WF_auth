from fastapi import Request
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse
from webfluid.core.ext import db, events
from webfluid.extensions.utils.babel import get_locale
from sqlalchemy import select
from typing import Callable

from ...models.user import User
from ...services import TokenService, UserService


async def _confirmation_page() -> HTMLResponse:
    from ... import additive
    html = await events.request(
        additive.unique_name("confirmation_page"),
        get_locale()
    )
    return HTMLResponse(html)


async def _invalid_page() -> HTMLResponse:
    from ... import additive
    html = await events.request(
        additive.unique_name("invalid_page"),
        get_locale()
    )
    return HTMLResponse(html)


async def _render_or_raise(render: Callable, exc: HTTPException) -> HTMLResponse:
    try: return await render()
    except ValueError: raise exc


async def default_request(request: Request):
    token = request.query_params.get("token")
    if not token:
        return await _render_or_raise(
            _invalid_page,
            HTTPException(status_code=400, detail="Missing token")
        )

    try: token_data = await TokenService.validate_token(token, "confirm")
    except HTTPException as e:
        if e.detail == "Token expired":
            return await _render_or_raise(_confirmation_page, e)
        return await _render_or_raise(_invalid_page, e)

    user_id = token_data.get("user_id")
    if not user_id:
        return await _render_or_raise(
            _invalid_page,
            HTTPException(status_code=400, detail="Invalid token")
        )

    async with db.async_executor(model=User) as e:
        users = await e.exec(select(User).where(
            User.id == user_id
        ).limit(1))
        user = users.first()
        if not user:
            return await _render_or_raise(
                _invalid_page,
                HTTPException(status_code=400, detail="Unknown user")
            )

        elif user.confirmed:
            new_mail = token_data.get("email")
            if not new_mail or new_mail == user.email:
                return await _render_or_raise(
                    _confirmation_page,
                    HTTPException(status_code=400, detail="Already confirmed")
                )
            user.email = new_mail

        else:
            from ... import additive
            user.confirmed = True
            await events.trigger(additive.unique_name("user_confirmed"), user.id)

        try: return await _confirmation_page()
        except ValueError: return { "status": "ok" }


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
            "link": f"{base_url}{additive.prefix}/api/v1/users/confirm?token={token}",
            "locale": get_locale()
        })
    except ValueError:
        raise HTTPException(status_code=400, detail="No confirmation handler")

    return { "status": "ok" }
