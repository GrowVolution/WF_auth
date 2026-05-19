from fastapi import Request, Depends, HTTPException
from webfluid.core.ext import db
from sqlalchemy import select
from typing import TYPE_CHECKING, Optional, AsyncGenerator, Callable, Any

if TYPE_CHECKING:
    from fastapi.params import Depends as DependsParam
    from .token import TokenService
    from ..models.user import User


class UserService:
    _TokenService: type["TokenService"]
    current_user: Any["DependsParam"]
    require_user: Any["DependsParam"]
    require_admin: Any["DependsParam"]
    require_roles_v1: Any["DependsParam"]
    require_any_role_v1: Any["DependsParam"]
    require_permissions_v1: Any["DependsParam"]
    require_any_permission_v1: Any["DependsParam"]

    @classmethod
    def setup(cls):
        from .token import TokenService
        cls._TokenService = TokenService
        cls.current_user = Depends(cls._current_user())
        cls.require_user = Depends(cls._require_user())
        cls.require_admin = Depends(cls._require_admin())
        cls.require_roles_v1 = Depends(cls._require_roles_v1())
        cls.require_any_role_v1 = Depends(cls._require_any_role_v1())
        cls.require_permissions_v1 = Depends(cls._require_permissions_v1())
        cls.require_any_permission_v1 = Depends(cls._require_any_permission_v1())

    @classmethod
    def _current_user(cls) -> Callable:
        async def wrapped(
                request: Request
        ) -> AsyncGenerator[Optional["User"]]:
            if "user_id" not in request.session:
                yield None
                return

            from ..models.user import User
            async with db.async_executor(model=User) as e:
                results = await e.exec(
                    select(User).where(
                        User.id == request.session["user_id"]
                    )
                )
                yield results.first()
        return wrapped

    @classmethod
    def _require_user(cls) -> Callable:
        async def wrapped(
                request: Request,
                user: "User" = cls.current_user,
                _ = cls._TokenService.csrf_protect
        ) -> AsyncGenerator["User"]:
            if not user:
                raise HTTPException(status_code=401, detail="Not authenticated")

            if "pending_email" in request.session \
                    and user.email == request.session["pending_email"]:
                request.session.pop("pending_email")

            yield user
        return wrapped

    @classmethod
    def _require_admin(cls) -> Callable:
        async def wrapped(
                user: "User" = cls.require_user
        ) -> AsyncGenerator[Optional["User"]]:
            for role in user.roles:
                if role.is_admin:
                    yield user
                    return
            raise HTTPException(status_code=403, detail="Not authorized")
        return wrapped

    @classmethod
    def _require_roles_v1(cls) -> Callable:
        from ..schemas.v1 import AuthorizeRequest

        async def wrapped(
                authorize: AuthorizeRequest,
                user: "User" = cls.require_user
        ) -> AsyncGenerator["User"]:
            if not authorize.roles:
                raise HTTPException(status_code=400, detail="No roles specified")

            required_roles = set(authorize.roles)
            for role in user.roles:
                if role.name in authorize.roles:
                    required_roles.remove(role.name)

            if len(required_roles) > 0:
                raise HTTPException(status_code=403, detail="Not authorized")

            yield user
        return wrapped

    @classmethod
    def _require_any_role_v1(cls) -> Callable:
        from ..schemas.v1 import AuthorizeRequest

        async def wrapped(
                authorize: AuthorizeRequest,
                user: "User" = cls.require_user
        ) -> AsyncGenerator["User"]:
            if not authorize.roles:
                raise HTTPException(status_code=400, detail="No roles specified")

            for role in user.roles:
                if role.name in authorize.roles:
                    yield user
                    return

            raise HTTPException(status_code=403, detail="Not authorized")
        return wrapped

    @classmethod
    def _require_permissions_v1(cls) -> Callable:
        from ..schemas.v1 import AuthorizeRequest

        async def wrapped(
                authorize: AuthorizeRequest,
                user: "User" = cls.require_user
        ) -> AsyncGenerator["User"]:
            if not authorize.permissions:
                raise HTTPException(status_code=400, detail="No permissions specified")

            required_permissions = set(authorize.permissions)
            for role in user.roles:
                for perm in role.permissions:
                    if perm.name in authorize.permissions:
                        required_permissions.remove(perm.name)

                if len(required_permissions) == 0:
                    yield user
                    return

            raise HTTPException(status_code=403, detail="Not authorized")
        return wrapped

    @classmethod
    def _require_any_permission_v1(cls) -> Callable:
        from ..schemas.v1 import AuthorizeRequest

        async def wrapped(
                authorize: AuthorizeRequest,
                user: "User" = cls.require_user
        ) -> AsyncGenerator["User"]:
            if not authorize.permissions:
                raise HTTPException(status_code=400, detail="No permissions specified")

            for role in user.roles:
                for perm in role.permissions:
                    if perm.name in authorize.permissions:
                        yield user
                        return

            raise HTTPException(status_code=403, detail="Not authorized")
        return wrapped
