from fastapi import Request, HTTPException
from webfluid.core.ext import db, security as s
from webfluid.extensions.security.models import User
from sqlalchemy import select
from urllib.parse import urlencode

from ..utils import admit
from ...schemas.v1 import SsoAppStart, SsoAppExchange
from ...services import approval as approvals, mobile as devices, sso_app


async def start_request(
        request: Request, provider: str, body: SsoAppStart,
        _ = s.oauth_service.client
):
    await admit("app-sso", provider)
    try: ticket, lifetime = await sso_app.open_ticket(provider, body.redirect, body.challenge)
    except sso_app.SsoAppError as exc:
        raise HTTPException(status_code=400, detail=exc.code)

    from ... import additive
    url = request.url_for(additive.unique_name("oauth_login"), provider=provider)
    return {
        "ticket": ticket,
        "url": f"{url}?{urlencode({ 'device': 'mobile', 'app': ticket })}",
        "expires": lifetime
    }


async def exchange_request(request: Request, provider: str, body: SsoAppExchange):
    await admit("app-sso", provider)
    try: state = await sso_app.redeem(provider, body.code, body.verifier)
    except sso_app.SsoAppError as exc:
        raise HTTPException(status_code=400, detail=exc.code)

    async with db.async_executor(model=User) as e:
        result = await e.exec(select(User).where(User.id == state["user_id"]))
        user = result.first()
    if not user:
        raise HTTPException(status_code=400, detail="INVALID_CODE")

    phone = await devices.device(user.id) if state.get("existing") else None
    if phone: return await approvals.begin(request, user, phone)

    request.session.clear()
    request.session["user_id"] = user.id
    return s.token_service.csrf_response(request)
