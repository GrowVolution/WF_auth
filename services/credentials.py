from webfluid.core.ext import cache, security as s
from typing import Optional
import secrets

ATTEMPTS = 10
WINDOW = 900

_decoy: dict = {}


async def verify(password_hash: Optional[str], password: str) -> bool:
    if not password_hash:
        if "hash" not in _decoy: _decoy["hash"] = await s.hash_service.ahash(secrets.token_urlsafe(32))
        await s.hash_service.averify(_decoy["hash"], password)
        return False
    return await s.hash_service.averify(password_hash, password)


def _key(scope: str, user_id: int) -> str:
    from .. import additive
    return f"{additive.id}:attempts:{scope}:{user_id}"


async def exhausted(scope: str, user_id: int) -> bool:
    count = await cache.aget(_key(scope, user_id))
    try: return int(count or 0) >= ATTEMPTS
    except (TypeError, ValueError): return False


async def failed(scope: str, user_id: int):
    key = _key(scope, user_id)
    count = await cache.aget(key)
    try: count = int(count or 0)
    except (TypeError, ValueError): count = 0
    await cache.aset(key, str(count + 1), timeout=WINDOW)


async def cleared(scope: str, user_id: int):
    await cache.adelete(_key(scope, user_id))


async def fresh_step(user_id: int, step: int) -> bool:
    key = _key("totp-step", user_id)
    last = await cache.aget(key)
    try: last = int(last) if last is not None else None
    except (TypeError, ValueError): last = None
    if last is not None and step <= last: return False
    await cache.aset(key, str(step), timeout=WINDOW)
    return True
