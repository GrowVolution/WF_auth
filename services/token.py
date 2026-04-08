from fastapi import Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from itsdangerous import URLSafeTimedSerializer
from itsdangerous.exc import BadSignature, SignatureExpired
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import delete, select
from secrets import token_urlsafe
from datetime import timedelta, datetime, UTC
from typing import Callable
import hmac

from webfluid.core.ext import scheduler, db
from webfluid.core.constants import DEBUG
from webfluid.utils.logging import factory as log_factory

class TokenService:
    _serializer: URLSafeTimedSerializer
    _max_age: int
    _csrf_cookie: str
    _csrf_secure: bool
    csrf_protect: type[Depends]

    @classmethod
    def setup(cls, secret: str, max_age: int, csrf_cookie: str, csrf_secure: bool):
        cls._serializer = URLSafeTimedSerializer(secret)
        cls._max_age = max_age
        cls._csrf_cookie = csrf_cookie
        cls._csrf_secure = csrf_secure
        cls.csrf_protect = Depends(cls._csrf_protect())

        async def db_cleaner():
            from ..models.token import ExpiredToken
            async with db.async_executor(model=ExpiredToken) as e:
                time_diff = datetime.now(UTC) - timedelta(seconds=max_age)
                await e.exec(delete(ExpiredToken).where(
                    ExpiredToken.created_at < time_diff
                ))

        scheduler.add_job(db_cleaner, IntervalTrigger(days=15))

        if not csrf_secure and not DEBUG:
            from .. import additive
            log_factory.warning(f"[{additive.name}] CSRF cookies are not secure. "
                                 "Consider setting AUTH_CSRF_COOKIE_SECURE=True")

    @classmethod
    def generate_token(cls, data: dict, salt: str = "csrf") -> str:
        return cls._serializer.dumps(data, salt=salt)

    @classmethod
    async def validate_token(cls, token: str, salt: str = "csrf") -> dict:
        try:
            if salt == "csrf":
                return cls._serializer.loads(token, salt=salt, max_age=cls._max_age)

            from ..models.token import ExpiredToken
            async with db.async_executor(model=ExpiredToken) as e:
                expired = await e.exec(select(ExpiredToken).where(
                    ExpiredToken.token == token
                ))
                if expired.first():
                    raise HTTPException(status_code=403, detail="Token expired")

                data = cls._serializer.loads(token, salt=salt, max_age=cls._max_age)
                await e.insert(ExpiredToken(token))
                return data

        except SignatureExpired:
            raise HTTPException(status_code=403, detail="Token expired")

        except BadSignature:
            raise HTTPException(status_code=403, detail="Invalid token")

    @classmethod
    def csrf_response(cls, request: Request) -> JSONResponse:
        raw = token_urlsafe(32)
        csrf_token = TokenService.generate_token(
            { "csrf": raw }
        )
        request.session["csrf_token"] = raw

        response = JSONResponse(
            content={ "status": "ok" }
        )
        response.set_cookie(
            key="csrf_token",
            value=csrf_token,
            httponly=False,
            secure=cls._csrf_secure,
            samesite="lax",
            path="/"
        )
        return response

    @classmethod
    def _csrf_protect(cls) -> Callable:
        async def wrapped(request: Request):
            if request.method in {"GET", "HEAD", "OPTIONS"}:
                return

            csrf_cookie = request.cookies.get("csrf_token")
            csrf_header = request.headers.get("X-CSRF-Token")
            csrf_session = request.session.get("csrf_token", "")

            if not csrf_cookie or not csrf_header or not csrf_session:
                raise HTTPException(status_code=403, detail="Missing CSRF token")

            cookie_data = await cls.validate_token(csrf_cookie)
            header_data = await cls.validate_token(csrf_header)
            cookie_val = cookie_data.get("csrf", "")
            header_val = header_data.get("csrf", "")


            if not (cookie_val and header_val):
                raise HTTPException(status_code=403, detail="Invalid CSRF token")

            if not (
                    hmac.compare_digest(cookie_val, csrf_session) and
                    hmac.compare_digest(header_val, csrf_session)
            ):
                raise HTTPException(status_code=403, detail="CSRF mismatch")

        return wrapped
