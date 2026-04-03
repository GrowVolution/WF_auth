from fastapi import Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from itsdangerous import URLSafeTimedSerializer
from itsdangerous.exc import BadSignature, SignatureExpired
from secrets import token_urlsafe
from typing import Callable
import hmac


class TokenService:
    _serializer: URLSafeTimedSerializer
    _max_age: int
    csrf_protect: type[Depends]

    @classmethod
    def setup(cls, secret: str, max_age: int):
        cls._serializer = URLSafeTimedSerializer(secret)
        cls._max_age = max_age
        cls.csrf_protect = Depends(cls._csrf_protect())

    @classmethod
    def generate_token(cls, data: dict, salt: str = "csrf") -> str:
        return cls._serializer.dumps(data, salt=salt)

    @classmethod
    def validate_token(cls, token: str, salt: str = "csrf") -> dict:
        try:
            return cls._serializer.loads(token, salt=salt, max_age=cls._max_age)
        except (BadSignature, SignatureExpired):
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
            secure=True,
            samesite="lax",
            path="/"
        )
        return response

    @classmethod
    def _csrf_protect(cls) -> Callable:
        def wrapped(request: Request):
            if request.method in {"GET", "HEAD", "OPTIONS"}:
                return

            csrf_cookie = request.cookies.get("csrf_token")
            csrf_header = request.headers.get("X-CSRF-Token")
            csrf_session = request.session.get("csrf_token", "")

            if not csrf_cookie or not csrf_header or not csrf_session:
                raise HTTPException(status_code=403, detail="Missing CSRF token")

            cookie_data = cls.validate_token(csrf_cookie)
            header_data = cls.validate_token(csrf_header)
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
