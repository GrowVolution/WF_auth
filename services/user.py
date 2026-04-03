from fastapi import Request, Depends, HTTPException
from webfluid.core.ext import db
from sqlalchemy import select
from typing import TYPE_CHECKING, Optional, AsyncGenerator, Any, Callable

if TYPE_CHECKING:
    from .token import TokenService
    from ..models.user import User


class UserService:
    _TokenService: type["TokenService"]
    current_user: type[Depends]
    require_user: type[Depends]
    require_admin: type[Depends]

    @classmethod
    def setup(cls):
        from .token import TokenService
        cls._TokenService = TokenService
        cls.current_user = Depends(cls._current_user())
        cls.require_user = Depends(cls._require_user())
        cls.require_admin = Depends(cls._require_admin())

    @classmethod
    def _current_user(cls) -> Callable:
        async def _wrapped(
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
        return _wrapped

    @classmethod
    def _require_user(cls) -> Callable:
        async def _wrapped(
                user: "User" = cls.current_user,
                _ = cls._TokenService.csrf_protect
        ) -> AsyncGenerator[Optional["User"]]:
            if not user:
                raise HTTPException(status_code=401, detail="Not authenticated")

            if "pending_email" in request.session \
                    and user.email == request.session["pending_email"]:
                request.session.pop("pending_email")

            yield user
        return _wrapped

    @classmethod
    def _require_admin(cls) -> Callable:
        async def _wrapped(
                user: "User" = cls.require_user
        ) -> AsyncGenerator[Optional["User"]]:
            for role in user.roles:
                if role.is_admin:
                    yield user
                    return
            raise HTTPException(status_code=403, detail="Not authorized")
        return _wrapped

    @classmethod
    def require_any_role(cls, *roles: str) -> Any[Depends, AsyncGenerator[Optional["User"]]]:
        async def wrapped(user: "User" = cls.require_user) -> AsyncGenerator[Optional["User"]]:
            for role in user.roles:
                if role.name in roles:
                    yield user
                    return
            raise HTTPException(status_code=403, detail="Not authorized")

        return Depends(wrapped)

    @classmethod
    def require_roles(cls, *roles: str) -> Any[Depends, AsyncGenerator[Optional["User"]]]:
        async def wrapped(user: "User" = cls.require_user) -> AsyncGenerator[Optional["User"]]:
            for role in user.roles:
                if role.name not in roles:
                    raise HTTPException(status_code=403, detail="Not authorized")
            yield user

        return Depends(wrapped)
