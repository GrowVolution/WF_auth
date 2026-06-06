from fastapi import Request, HTTPException
from webfluid.core.ext import db, security as s
from sqlalchemy import select
from webfluid.extensions.security.models.user import (
    User, Identity
)

from .create import _trigger
from ...schemas.v1 import LoginUser


async def default_request(request: Request, login: LoginUser,
                          current_user = s.user_service.current_user):
    if current_user:
        raise HTTPException(status_code=400, detail="ALREADY_LOGGED_IN")

    async with db.async_executor(model=User) as e:
        users = await e.exec(select(User).where(
            User.username == login.username
        ))
        user = users.first()
        if not user:
            raise HTTPException(status_code=401, detail="INVALID_CREDENTIALS")

        if not user.psw_hash:
            raise HTTPException(status_code=400, detail="PROVIDER_ONLY")

        if not s.hash_service.verify(user.psw_hash, login.password):
            raise HTTPException(status_code=401, detail="INVALID_CREDENTIALS")

        request.session.clear()
        request.session["user_id"] = user.id
        return s.token_service.csrf_response(request)


async def login_available(user = s.user_service.current_user):
    return { "available": user is None }


async def oauth_request(
        request: Request, provider: str,
        client = s.oauth_service.client,
        _ = s.oauth_service.prepare_session
):
    from ... import additive
    redirect_uri = request.url_for(
        additive.unique_name("oauth_callback"),
        provider=provider
    )
    return await client.authorize_redirect(request, redirect_uri)


async def callback_request(
        request: Request, provider: str,
        userinfo = s.oauth_service.userinfo
):
    sub = str(userinfo["sub"])

    async with db.async_executor(model=User) as e:
        identities = await e.exec(select(Identity).where(
            Identity.sub == sub,
            Identity.provider == provider
        ))

        identity = identities.first()
        if not identity:
            base_username = (
                    userinfo.get("preferred_username")
                    or userinfo.get("username")
                    or userinfo.get("login")
                    or f"{provider}_user"
            )

            username = base_username
            i = 1

            while True:
                exists = await e.exec(select(User).where(
                    User.username == username
                ))
                if not exists.first(): break
                username = f"{base_username}_{i}"
                i += 1

            email = userinfo.get("email")
            if email:
                exists = await e.exec(select(User).where(
                    User.email == email
                ))
                if exists.first(): email = None

            user = await e.insert(User(
                username=username,
                email=email
            ), True)
            await e.insert(Identity(
                user_id=user.id, sub=sub,
                provider=provider
            ))

            _trigger(request, user)

        else:
            user = identity.user

        device = request.session.pop("device", "mobile")
        request.session.clear()
        request.session["user_id"] = user.id
        token_res = s.token_service.csrf_response(request)
        return s.oauth_service.authorize_response(
            request, provider, device, token_res
        )
