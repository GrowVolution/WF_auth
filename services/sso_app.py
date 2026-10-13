from webfluid.core.ext import cache
from webfluid.core.context import FluidContext
from urllib.parse import urlencode
from typing import Optional
import asyncio, hashlib, hmac, json, re, secrets, time

from ..utils.crypto import b64encode

CODE_TTL = 120

_TICKET = re.compile(r"^[A-Za-z0-9_-]{32}$")
_CODE = re.compile(r"^[A-Za-z0-9_-]{43}$")
_CHALLENGE = re.compile(r"^[A-Za-z0-9_-]{43}$")
_VERIFIER = re.compile(r"^[A-Za-z0-9._~-]{43,128}$")

_exchange = asyncio.Lock()


class SsoAppError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _key(kind: str, value: str) -> str:
    from .. import additive
    return f"{additive.id}:sso:app:{kind}:{value}"


def redirects() -> list[str]:
    configured = FluidContext.current().fluid.config.get("AUTH_SSO_APP_REDIRECTS") or []
    return [value for value in configured if isinstance(value, str) and value]


def ttl() -> int:
    return int(FluidContext.current().fluid.config.get("AUTH_SSO_APP_TTL") or 600)


def challenge_of(verifier: str) -> str:
    return b64encode(hashlib.sha256(verifier.encode("ascii")).digest())


async def _load(key: str) -> Optional[dict]:
    value = await cache.aget(key)
    if value is None: return None
    if isinstance(value, (bytes, bytearray)): value = value.decode("utf-8", "replace")
    if isinstance(value, str):
        try: value = json.loads(value)
        except ValueError: return None
    if not isinstance(value, dict) or value.get("expires_at", 0) < time.time(): return None
    return value


async def open_ticket(provider: str, redirect: str, challenge: str) -> tuple[str, int]:
    allowed = redirects()
    if not allowed: raise SsoAppError("SSO_APP_DISABLED")
    if redirect not in allowed: raise SsoAppError("INVALID_REDIRECT")
    if not isinstance(challenge, str) or not _CHALLENGE.match(challenge):
        raise SsoAppError("INVALID_CODE_CHALLENGE")

    lifetime = ttl()
    ticket = secrets.token_urlsafe(24)
    state = {
        "provider": provider, "redirect": redirect, "challenge": challenge,
        "expires_at": time.time() + lifetime
    }
    await cache.aset(_key("ticket", ticket), json.dumps(state), timeout=lifetime)
    return ticket, lifetime


async def ticket(provider: str, value) -> Optional[dict]:
    if not isinstance(value, str) or not _TICKET.match(value): return None
    state = await _load(_key("ticket", value))
    if not state or state.get("provider") != provider: return None
    return state


async def issue(provider: str, value: str, user_id: int, existing: bool) -> str:
    state = await ticket(provider, value)
    if not state: raise SsoAppError("SSO_APP_EXPIRED")
    await cache.adelete(_key("ticket", value))

    code = secrets.token_urlsafe(32)
    await cache.aset(_key("code", code), json.dumps({
        "provider": provider, "user_id": user_id, "existing": existing,
        "challenge": state["challenge"], "expires_at": time.time() + CODE_TTL
    }), timeout=CODE_TTL)

    separator = "&" if "?" in state["redirect"] else "?"
    return state["redirect"] + separator + urlencode({ "code": code, "ticket": value })


async def redeem(provider: str, code, verifier) -> dict:
    if not isinstance(code, str) or not _CODE.match(code): raise SsoAppError("INVALID_CODE")
    if not isinstance(verifier, str) or not _VERIFIER.match(verifier): raise SsoAppError("INVALID_CODE")

    async with _exchange:
        key = _key("code", code)
        state = await _load(key)
        await cache.adelete(key)

    if not state or state.get("provider") != provider: raise SsoAppError("INVALID_CODE")
    if not hmac.compare_digest(challenge_of(verifier), str(state.get("challenge"))):
        raise SsoAppError("INVALID_CODE")
    return state
