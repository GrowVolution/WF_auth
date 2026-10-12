from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
from webfluid.core.ext import db, events, security as s
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload
from webfluid.extensions.security.models import (
    User, Identity
)
from typing import Optional

from .create import _trigger
from ..utils import normalized_claims
from ...schemas.v1 import LoginUser
from ...services import approval as approvals, mobile as devices, sso_app


async def available_request(_ = s.user_service.require_user):
    return { "available": False }


async def default_request(request: Request, login: LoginUser,
                          current_user = s.user_service.current_user):
    if current_user:
        raise HTTPException(status_code=400, detail="ALREADY_LOGGED_IN")

    async with db.async_executor(model=User) as e:
        users = await e.exec(select(User).where(or_(
            User.username == login.username,
            User.email == login.username
        )))
        user = users.first()
        if not user:
            raise HTTPException(status_code=401, detail="INVALID_CREDENTIALS")

        if not user.psw_hash:
            raise HTTPException(status_code=400, detail="PROVIDER_ONLY")

        if not s.hash_service.verify(user.psw_hash, login.password):
            raise HTTPException(status_code=401, detail="INVALID_CREDENTIALS")

        phone = await devices.device(user.id)
        if phone: return await approvals.begin(request, user, phone)

        request.session.clear()
        request.session["user_id"] = user.id
        return s.token_service.csrf_response(request)


async def oauth_request(
        request: Request, provider: str,
        app: Optional[str] = None,
        client = s.oauth_service.client,
        _ = s.oauth_service.prepare_session
):
    from ... import additive
    if app is not None:
        if not await sso_app.ticket(provider, app):
            raise HTTPException(status_code=400, detail="SSO_APP_EXPIRED")
        request.session["sso_app"] = app

    redirect_uri = request.url_for(
        additive.unique_name("oauth_callback"),
        provider=provider
    )
    return await client.authorize_redirect(request, redirect_uri)


def _trigger_first_callback(user_id: int, provider: str, sub: str, userinfo):
    from ... import additive
    try:
        events.trigger(additive.unique_name("oauth:first-callback"), {
            "user_id": user_id,
            "provider": provider,
            "sub": sub,
            "claims": normalized_claims(userinfo)
        })
    except ValueError: pass


async def callback_request(
        request: Request, provider: str,
        userinfo = s.oauth_service.userinfo
):
    sub = str(userinfo["sub"])

    app = request.session.pop("sso_app", None)
    if app is not None and not await sso_app.ticket(provider, app):
        request.session.clear()
        raise HTTPException(status_code=400, detail="SSO_APP_EXPIRED")

    async with db.async_executor(model=User) as e:
        identities = await e.exec(select(Identity).options(
            selectinload(Identity.user)
        ).where(
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
            _trigger_first_callback(user.id, provider, sub, userinfo)

        else:
            user = identity.user

        if app is not None:
            request.session.clear()
            try: target = await sso_app.issue(provider, app, user.id, identity is not None)
            except sso_app.SsoAppError as exc:
                raise HTTPException(status_code=400, detail=exc.code)
            return RedirectResponse(target, status_code=303)

        device = request.session.pop("device", "mobile")
        phone = await devices.device(user.id) if identity else None
        if phone:
            await approvals.begin(request, user, phone)
            return s.oauth_service.authorize_response(request, provider, device)

        request.session.clear()
        request.session["user_id"] = user.id
        token_res = s.token_service.csrf_response(request)
        return s.oauth_service.authorize_response(
            request, provider, device, token_res
        )
