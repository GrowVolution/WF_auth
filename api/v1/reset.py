from fastapi import Request
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse
from webfluid.core.ext import db, events, security as s
from webfluid.extensions.security.models import User
from sqlalchemy import select
from typing import Callable

from ...schemas.v1 import ResetRequest, ResetPassword


async def _reset_page(request: Request) -> HTMLResponse:
    from ... import additive
    html = await events.request(
        additive.unique_name("page:reset")
    )
    response = HTMLResponse(html)

    csrf = s.token_service.csrf_response(request)
    for header in csrf.raw_headers:
        if header[0].lower() == b"set-cookie":
            response.raw_headers.append(header)

    return response


async def _invalid_page() -> HTMLResponse:
    from ... import additive
    html = await events.request(
        additive.unique_name("page:invalid")
    )
    return HTMLResponse(html)


async def _render_or_raise(render: Callable, exc: HTTPException) -> HTMLResponse:
    try: return await render()
    except ValueError: raise exc


async def ui_request(request: Request):
    token = request.query_params.get("token")
    if not token:
        return await _render_or_raise(
            _invalid_page,
            HTTPException(status_code=400, detail="MISSING_TOKEN")
        )

    try: token_data = await s.token_service.validate_token(token, "reset")
    except HTTPException as e: return await _render_or_raise(_invalid_page, e)

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

        try:
            request.session.clear()
            request.session["reset_user"] = user.id
            return await _reset_page(request)
        except ValueError:
            raise HTTPException(status_code=400, detail="NO_HANDLER")


async def reset_request(request: Request, reset: ResetRequest):
    async with db.async_executor(model=User) as e:
        users = await e.exec(select(User).where(
                User.email == reset.email
        ).limit(1))
        user = users.first()
        if not user:
            raise HTTPException(status_code=400, detail="UNKNOWN_EMAIL")

        from ... import additive
        base_url = str(request.base_url).rstrip("/")

        token_data = { "user_id": user.id }
        token = s.token_service.generate_token(token_data, "reset")

        try:
            events.trigger(additive.unique_name("send:reset"), {
                "username": user.username,
                "email": user.email,
                "link": f"{base_url}{additive.prefix}/api/v1/users/reset?token={token}"
            })
        except ValueError:
            raise HTTPException(status_code=400, detail="NO_HANDLER")

    return { "status": "ok" }


async def reset_password(request: Request, reset: ResetPassword,
                         _ = s.token_service.csrf_protect):
    user_id = request.session.pop("reset_user", None)
    if not user_id:
        raise HTTPException(status_code=400, detail="INVALID_SESSION")

    async with db.async_executor(model=User) as e:
        users = await e.exec(select(User).where(
                User.id == user_id
        ).limit(1))
        user = users.first()
        if not user:
            raise HTTPException(status_code=400, detail="UNKNOWN_USER")

        user.psw_hash = s.hash_service.hash(reset.password)

    request.session.clear()
    return { "status": "ok" }
