from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select, or_
from webfluid.core.ext import db, events, security as s
from webfluid.core.constants import DEBUG
from webfluid.core.context import FluidContext
from webfluid.utils.logging import factory as log_factory
from webfluid.extensions.security.models import (
    User, Role, Permission
)
from typing import Optional

from ...schemas.v1 import CreateUser, InitialSetup


async def _create_user(create: CreateUser, e) -> User:
    users = await e.exec(
        select(User).where(
            or_(
                User.username == create.username,
                User.email == create.email
            )
        )
    )
    if users.first():
        raise HTTPException(
            status_code=409,
            detail="CREDENTIALS_TAKEN"
        )

    return await e.insert(User(
        username=create.username,
        email=create.email,
        psw_hash=s.hash_service.hash(create.password)
    ), True)


def _trigger(request: Request, user: User):
    from ... import additive
    from .verification import confirmation_link, locale
    token = s.token_service.generate_token({ "user_id": user.id }, "confirm")
    try:
        events.trigger(additive.unique_name("user:created"), {
            "type": "REGISTRATION",
            "username": user.username,
            "email": user.email,
            "link": confirmation_link(request, token),
            "locale": locale()
        })
    except ValueError:
        log_factory.warning(f"[{additive.name}] No confirmation handler.")
        user.email_verified = True


async def _make_response_and_trigger(
        request: Request, user: User
) -> JSONResponse:
    _trigger(request, user)
    request.session.clear()
    request.session["user_id"] = user.id
    return s.token_service.csrf_response(request)


async def setup_available(user: Optional[User] = s.user_service.current_user):
    if not DEBUG or user: return { "available": False }

    async with db.async_executor(model=User) as e:
        users = await e.exec(select(User).limit(1))
        roles = await e.exec(select(Role).limit(1))
        return { "available": not (users.first() or roles.first()) }


async def setup_request(
        request: Request, setup: InitialSetup,
        current_user: Optional[User] = s.user_service.current_user
):
    if not DEBUG:
        raise HTTPException(
            status_code=403,
            detail="PRODUCTION_MODE"
        )

    if current_user:
        raise HTTPException(
            status_code=403,
            detail="SETUP_ALREADY_PERFORMED"
        )

    async with db.async_executor(model=User) as e:
        users = await e.exec(select(User).limit(1))
        if users.first():
            raise HTTPException(
                status_code=403,
                detail="SETUP_ALREADY_PERFORMED"
            )

        roles = await e.exec(select(Role).limit(1))
        if roles.first():
            raise HTTPException(
                status_code=403,
                detail="SETUP_ALREADY_PERFORMED"
            )

        ctx = FluidContext.current()
        admin_role = setup.admin_role.name
        role = await e.insert(Role(
            admin_role,
            ctx.fluid.config.get(
                "AUTH_ADMIN_ROLE_REQUIRES_2FA", True
            )
        ))
        role.is_admin = True

        for permission_name in setup.admin_role.permissions:
            permissions = await e.exec(
                select(Permission).where(
                    Permission.name == permission_name
                )
            )
            permission = permissions.first()
            if not permission:
                permission = await e.insert(Permission(permission_name))
            elif permission in role.permissions: continue
            role.permissions.append(permission)

        userdata = setup.admin_user
        user = await e.insert(User(
            userdata.username,
            userdata.email,
            s.hash_service.hash(userdata.password)
        ), True)
        user.roles.append(role)

        response = await _make_response_and_trigger(request, user)
        return response


async def default_request(request: Request, create: CreateUser):
    if create.roles:
        raise HTTPException(
            status_code=400,
            detail="ROLES_NOT_ALLOWED"
        )

    async with db.async_executor(model=User) as e:
        user = await _create_user(create, e)
        response = await _make_response_and_trigger(request, user)

    return response
