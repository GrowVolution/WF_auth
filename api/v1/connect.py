from fastapi import Request, HTTPException
from webfluid.core.ext import db, security as s
from webfluid.extensions.security.models import (
    User, Identity
)
from sqlalchemy import select


async def oauth_request(
        request: Request, provider: str,
        client = s.oauth_service.client,
        _ = s.user_service.require_2fa,
        __ = s.oauth_service.prepare_session
):
    from ... import additive
    redirect_uri = request.url_for(
        additive.unique_name("connect_callback"),
        provider=provider
    )
    return await client.authorize_redirect(request, redirect_uri)


async def callback_request(
        request: Request, provider: str,
        userinfo = s.oauth_service.userinfo,
        current_user: User = s.user_service.require_2fa,
):
    async with db.ensured_async_executor(model=Identity) as e:
        identities = await e.exec(select(Identity).where(
            Identity.sub == str(userinfo["sub"]),
            Identity.provider == provider
        ))
        if identities.first():
            raise HTTPException(status_code=400, detail="ALREADY_CONNECTED")

        await e.insert(Identity(
            user_id=current_user.id,
            sub=str(userinfo["sub"]),
            provider=provider
        ))

    device = request.session.pop("device", "mobile")
    return s.oauth_service.authorize_response(request, provider, device)
