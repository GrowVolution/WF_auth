from fastapi import Request
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse
from webfluid.core.ext import db, events, security as s
from webfluid.extensions.babel.utils import get_locale
from webfluid.extensions.security.models import User
from sqlalchemy import select
from typing import Callable


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
            HTTPException(status_code=400, detail="MISSING_TOKEN")
        )

    try: token_data = await s.token_service.validate_token(token, "confirm")
    except HTTPException as e:
        if e.detail == "TOKEN_EXPIRED":
            return await _render_or_raise(_confirmation_page, e)
        return await _render_or_raise(_invalid_page, e)

    user_id = token_data.get("user_id")
    if not user_id:
        return await _render_or_raise(
            _invalid_page,
            HTTPException(status_code=400, detail="INVALID_TOKEN")
        )

    async with db.async_executor(model=User) as e:
        users = await e.exec(select(User).where(
            User.id == user_id
        ).limit(1))
        user = users.first()
        if not user:
            return await _render_or_raise(
                _invalid_page,
                HTTPException(status_code=400, detail="UNKNOWN_USER")
            )

        elif user.email_verified:
            if not user.pending_email:
                return await _render_or_raise(
                    _confirmation_page,
                    HTTPException(status_code=400, detail="ALREADY_CONFIRMED")
                )
            user.email = user.pending_email
            user.pending_email = None

        else:
            from ... import additive
            user.email_verified = True
            events.trigger(additive.unique_name("user_confirmed"), user.id)

        try: return await _confirmation_page()
        except ValueError: return { "status": "ok" }


async def resend_request(
        request: Request,
        user: User = s.user_service.require_user
):
    if not user.email:
        raise HTTPException(status_code=400, detail="NO_EMAIL")

    elif user.email_verified:
        if not user.pending_email:
            raise HTTPException(status_code=400, detail="ALREADY_CONFIRMED")
        msg_type = "CHANGE"

    else:
        msg_type = "REGISTRATION"

    from ... import additive
    base_url = str(request.base_url).rstrip("/")

    token_data = { "user_id": user.id }
    token = s.token_service.generate_token(token_data, "confirm")

    try:
        events.trigger(additive.unique_name("resend_confirmation"), {
            "type": msg_type,
            "username": user.username,
            "email": user.email,
            "link": f"{base_url}{additive.prefix}/api/v1/users/confirm?token={token}",
            "locale": get_locale()
        })
    except ValueError:
        raise HTTPException(status_code=400, detail="NO_HANDLER")

    return { "status": "ok" }
