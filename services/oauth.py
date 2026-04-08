from fastapi import Request, Depends
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.exceptions import HTTPException
from authlib.integrations.starlette_client import OAuth
from authlib.integrations.base_client import MismatchingStateError
from typing import Callable, Optional


class OAuthService:
    _client = OAuth()
    _allowed_providers = set()
    client: type[Depends]
    prepare_session: type[Depends]
    userinfo: type[Depends]

    @classmethod
    def setup(cls, clients: dict):
        for name, client in clients.items():
            cls._client.register(name, **client)
            cls._allowed_providers.add(name)

        cls.client = Depends(cls._resolve_client())
        cls.prepare_session = Depends(cls._prepare_session())
        cls.userinfo = Depends(cls._userinfo())

    @classmethod
    def _resolve_client(cls) -> Callable:
        async def wrapped(provider: str):
            if provider not in cls._allowed_providers:
                raise HTTPException(status_code=400, detail="Unknown provider")
            return cls._client.create_client(provider)
        return wrapped

    @classmethod
    def _prepare_session(cls):
        async def wrapped(request: Request):
            device = request.query_params.get("device", "mobile")
            if device not in ("mobile", "desktop"):
                raise HTTPException(status_code=400, detail="Invalid device")

            if device == "mobile":
                redirect_path = request.query_params.get("redirect", "/")
                request.session["redirect_path"] = redirect_path

            request.session["device"] = device
        return wrapped

    @classmethod
    def _userinfo(cls):
        async def wrapped(request: Request, provider: str):
            if provider not in cls._allowed_providers:
                raise HTTPException(status_code=400, detail="Unknown provider")

            error = request.query_params.get("error")
            if error: raise HTTPException(status_code=400, detail=error)

            try:
                client = cls._client.create_client(provider)
                token = await client.authorize_access_token(request)
            except MismatchingStateError:
                raise HTTPException(status_code=400, detail="Invalid state")

            userinfo = token.get("userinfo")
            if not userinfo:
                userinfo = await client.userinfo(token=token)

            return userinfo
        return wrapped

    @classmethod
    async def authorize_response(
            cls, request: Request, provider: str,
            csrf: Optional[JSONResponse] = None
    ):
        device = request.session.pop("device", "mobile")

        if device == "desktop":
            from .. import additive
            response = HTMLResponse(
                await additive.render(
                    "desktop_callback.html",
                    provider=provider,
                    origin=str(request.base_url).rstrip("/")
                )
            )

        else:
            response = RedirectResponse(
                request.session.pop("redirect_path", "/")
            )

        if csrf is not None:
            for header in csrf.raw_headers:
                if header[0].lower() == b"set-cookie":
                    response.raw_headers.append(header)

        return response
