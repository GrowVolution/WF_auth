from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select, or_
from webfluid.core.ext import db, events
from webfluid.core.context import FluidContext
from webfluid.core.constants import DEBUG
from webfluid.utils.logging import factory as log_factory

from ...models.user import User, Role, Permission
from ...schemas.v1 import CreateUser, InitialSetup
from ...services import HashService, TokenService, UserService


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
            detail="Username or email already taken"
        )

    return await e.insert(User(
        username=create.username,
        email=create.email,
        psw_hash=HashService.hash(create.password)
    ), True)


async def _make_response(request: Request, user: User) -> JSONResponse:
    from ... import additive

    base_url = str(request.base_url).rstrip("/")
    token = TokenService.generate_token({ "user_id": user.id }, "confirm")
    try:
        await events.trigger(additive.unique_name("user_registered"), {
            "type": "REGISTRATION",
            "username": user.username,
            "email": user.email,
            "link": f"{base_url}{additive.prefix}/api/v1/users/confirm?token={token}"
        })
    except ValueError:
        log_factory.warning(f"[{additive.name}] No confirmation handler")

    request.session["user_id"] = user.id
    return TokenService.csrf_response(request)


async def setup_request(request: Request, setup: InitialSetup,
                        current_user = UserService.current_user):
    if not DEBUG:
        raise HTTPException(
            status_code=403,
            detail="Not allowed in production"
        )

    if current_user:
        raise HTTPException(
            status_code=403,
            detail="Initial setup already performed"
        )

    async with db.async_executor(model=User) as e:
        users = await e.exec(select(User).limit(1))
        if users.first():
            raise HTTPException(
                status_code=403,
                detail="Initial setup already performed"
            )

        roles = await e.exec(select(Role).limit(1))
        if roles.first():
            raise HTTPException(
                status_code=403,
                detail="Initial setup already performed"
            )

        admin_role = setup.admin_role.name
        role = await e.insert(Role(admin_role))
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
            HashService.hash(userdata.password)
        ), True)
        user.roles.append(role)

        return await _make_response(request, user)


async def setup_available(user = UserService.current_user):
    if not DEBUG or user: return { "available": False }

    async with db.async_executor(model=User) as e:
        users = await e.exec(select(User).limit(1))
        roles = await e.exec(select(Role).limit(1))
        return { "available": not (users.first() and roles.first()) }


async def admin_request(create: CreateUser, _ = UserService.require_admin):
    async with db.async_executor(model=User) as e:
        user = await _create_user(create, e)

        for r in create.roles:
            roles = await e.exec(select(Role).where(Role.name == r.name))
            role = roles.first()
            if not role:
                role = await e.insert(Role(r.name))

            for p in r.permissions:
                permissions = await e.exec(select(Permission).where(Permission.name == p))
                permission = permissions.first()
                if not permission:
                    permission = await e.insert(Permission(p))
                role.permissions.append(permission)

            user.roles.append(role)

        ctx = FluidContext.current()
        if ctx.fluid.config.get("AUTH_EMAIL_CONFIRM"):
            user.confirmed = False

        return { "status": "ok" }


async def default_request(request: Request, create: CreateUser):
    if create.roles:
        raise HTTPException(
            status_code=400,
            detail="Roles are not allowed for default registration"
        )

    async with db.async_executor(model=User) as e:
        user = await _create_user(create, e)
        return await _make_response(request, user)
