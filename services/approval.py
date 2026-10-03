from fastapi import Request
from webfluid.core.ext import cache, events, security as s
from webfluid.extensions.security.models import User
from typing import Optional
import hashlib, json, re, secrets, time

from .crypto import b64decode, b64encode
from ..models.mobile import MobileSecurity

APPROVAL_TTL = 120
APPROVAL_ATTEMPTS = 3

_APPROVAL = re.compile(r"^[A-Za-z0-9_-]{22}$")


def _name(name: str) -> str:
    from .. import additive
    return additive.unique_name(name)


def _key(approval: str) -> str:
    from .. import additive
    return f"{additive.id}:mobile:approval:{approval}"


def _user_key(user_id: int) -> str:
    from .. import additive
    return f"{additive.id}:mobile:approval:user:{user_id}"


def fingerprint(sig_pubkey: str) -> str:
    return b64encode(hashlib.sha256(b64decode(sig_pubkey)).digest()[:16])


def approve_message(user_id: int, approval: str, number: int) -> str:
    return "\n".join((_name("mobile:approve"), str(user_id), approval, str(number)))


def deny_message(user_id: int, approval: str) -> str:
    return "\n".join((_name("mobile:deny"), str(user_id), approval))


def remaining(state: dict) -> int:
    return max(0, int(state.get("expires_at", 0) - time.time()))


async def load(approval) -> Optional[dict]:
    if not isinstance(approval, str) or not _APPROVAL.match(approval):
        return None

    cached = await cache.aget(_key(approval))
    if cached is None: return None
    if isinstance(cached, (bytes, bytearray)):
        cached = cached.decode("utf-8", "replace")
    if isinstance(cached, str):
        try: cached = json.loads(cached)
        except ValueError: return None
    if not isinstance(cached, dict) or not remaining(cached): return None
    return cached


async def store(approval: str, state: dict):
    timeout = remaining(state)
    if timeout: await cache.aset(_key(approval), json.dumps(state), timeout=timeout)


async def pending(user_id: int) -> Optional[tuple[str, dict]]:
    approval = await cache.aget(_user_key(user_id))
    if isinstance(approval, (bytes, bytearray)):
        approval = approval.decode("utf-8", "replace")

    state = await load(approval)
    if not state or state.get("state") != "pending" or state.get("user_id") != user_id:
        return None
    return approval, state


def push(state: dict, approval: str):
    try:
        events.trigger(_name("mobile:approval"), {
            "device": state["device"],
            "approval": approval,
            "state": state["state"],
            "expires": remaining(state)
        })
    except ValueError: pass


async def begin(request: Request, user: User, device: MobileSecurity) -> dict:
    approval = secrets.token_urlsafe(16)
    state = {
        "user_id": user.id,
        "device": fingerprint(device.sig_pubkey),
        "number": secrets.randbelow(90) + 10,
        "state": "pending",
        "attempts": 0,
        "fallback": s.user_service.has_2fa(user),
        "expires_at": time.time() + APPROVAL_TTL
    }

    await store(approval, state)
    await cache.aset(_user_key(user.id), approval, timeout=APPROVAL_TTL)

    request.session.clear()
    request.session["mobile_approval"] = approval
    push(state, approval)

    return {
        "status": "mobile_2fa",
        "number": state["number"],
        "expires": APPROVAL_TTL,
        "fallback": state["fallback"]
    }
