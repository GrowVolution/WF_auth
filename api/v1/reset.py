from fastapi import Request
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse
from webfluid.core.ext import db, events
from webfluid.extensions.utils.babel import get_locale
from sqlalchemy import select
from typing import Callable

from ...models.user import User
from ...schemas.v1 import ResetRequest, ResetPassword
from ...services import TokenService, HashService


async def _reset_page(request: Request) -> HTMLResponse:
    from ... import additive
    html = await events.request(
        additive.unique_name("reset_page"),
        get_locale()
    )
    response = HTMLResponse(html)

    csrf = TokenService.csrf_response(request)
    for header in csrf.raw_headers:
        if header[0].lower() == b"set-cookie":
            response.raw_headers.append(header)

    return response


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


async def ui_request(request: Request):
    token = request.query_params.get("token")
    if not token:
        return await _render_or_raise(
            _invalid_page,
            HTTPException(status_code=400, detail="Missing token")
        )

    try: token_data = await TokenService.validate_token(token, "reset")
    except HTTPException as e: return await _render_or_raise(_invalid_page, e)

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

        try:
            request.session.clear()
            request.session["reset_user"] = user.id
            return await _reset_page(request)
        except ValueError:
            raise HTTPException(status_code=400, detail="No reset handler")


async def reset_request(request: Request, reset: ResetRequest):
    async with db.async_executor(model=User) as e:
        users = await e.exec(select(User).where(
                User.email == reset.email
        ).limit(1))
        user = users.first()
        if not user:
            raise HTTPException(status_code=400, detail="Unknown email")

        from ... import additive
        base_url = str(request.base_url).rstrip("/")

        token_data = { "user_id": user.id }
        token = TokenService.generate_token(token_data, "reset")

        try:
            await events.trigger(additive.unique_name("user_forgot_password"), {
                "username": user.username,
                "email": user.email,
                "link": f"{base_url}{additive.prefix}/api/v1/users/reset?token={token}",
                "locale": get_locale()
            })
        except ValueError:
            raise HTTPException(status_code=400, detail="No reset handler")

    return { "status": "ok" }


async def reset_password(request: Request, reset: ResetPassword,
                         _ = TokenService.csrf_protect):
    user_id = request.session.pop("reset_user", None)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid session")

    async with db.async_executor(model=User) as e:
        users = await e.exec(select(User).where(
                User.id == user_id
        ).limit(1))
        user = users.first()
        if not user:
            raise HTTPException(status_code=400, detail="Unknown user")

        user.psw_hash = HashService.hash(reset.password)

    request.session.clear()
    return { "status": "ok" }
