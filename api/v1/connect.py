from fastapi import Request, HTTPException
from webfluid.core.ext import db
from sqlalchemy import select

from ...models.user import User, Identity
from ...services import UserService, OAuthService


async def oauth_request(
        request: Request, provider: str,
        client = OAuthService.client,
        _ = UserService.require_user,
        __ = OAuthService.prepare_session
):
    from ... import additive
    redirect_uri = request.url_for(
        additive.unique_name("connect_callback"), provider=provider
    )
    return await client.authorize_redirect(request, redirect_uri)


async def callback_request(
        request: Request, provider: str,
        userinfo = OAuthService.userinfo,
        current_user = UserService.require_user,
):
    async with db.async_executor(model=User) as e:
        identities = await e.exec(select(Identity).where(
            Identity.sub == str(userinfo["sub"]),
            Identity.provider == provider
        ))
        if identities.first():
            raise HTTPException(status_code=400, detail="Already connected")

        await e.insert(Identity(
            user_id=current_user.id,
            sub=str(userinfo["sub"]),
            provider=provider
        ))

        return await OAuthService.authorize_response(request, provider)
