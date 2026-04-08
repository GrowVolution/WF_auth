from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from webfluid.core.ext import db
from sqlalchemy import select
from argon2.exceptions import VerifyMismatchError

from ...models.user import User, Identity
from ...schemas.v1 import LoginUser
from ...services import TokenService, UserService, HashService, OAuthService


async def default_request(request: Request, login: LoginUser,
                          current_user = UserService.current_user):
    if current_user:
        raise HTTPException(status_code=400, detail="Already logged in")

    async with db.async_executor(model=User) as e:
        users = await e.exec(select(User).where(
            User.username == login.username
        ))
        user = users.first()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        if not user.psw_hash:
            raise HTTPException(status_code=400, detail="Must login with provider")

        try:
            if not HashService.verify(user.psw_hash, login.password):
                raise HTTPException(status_code=401, detail="Invalid credentials")
        except VerifyMismatchError:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        request.session.clear()
        request.session["user_id"] = user.id
        return TokenService.csrf_response(request)


async def login_available(user = UserService.current_user):
    return { "available": user is None }


async def oauth_request(
        request: Request, provider: str,
        client = OAuthService.client,
        _ = OAuthService.prepare_session
):
    from ... import additive
    redirect_uri = request.url_for(
        additive.unique_name("oauth_callback"), provider=provider
    )
    return await client.authorize_redirect(request, redirect_uri)


async def callback_request(request: Request, provider: str, userinfo = OAuthService.userinfo):
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
            email = userinfo.get("email")

            username = base_username
            i = 1

            while True:
                exists = await e.exec(select(User).where(
                    User.username == username
                ))
                if not exists.first(): break
                username = f"{base_username}_{i}"
                i += 1

            user = await e.insert(User(
                username=username,
                email=email
            ), True)
            await e.insert(Identity(
                user_id=user.id, sub=sub,
                provider=provider
            ))

        else:
            user = identity.user

        request.session.clear()
        request.session["user_id"] = user.id
        token_res = TokenService.csrf_response(request)
        return await OAuthService.authorize_response(
            request, provider, token_res
        )
