from webfluid.core.ext import db, cache
from sqlalchemy import select
from typing import Optional
import re, secrets

from .crypto import b64decode, valid_keys, wrap, verify
from ..models.mobile import MobileSecurity

CHALLENGE_TTL = 120

_CHALLENGE = re.compile(r"^[A-Za-z0-9_-]{43}$")

__all__ = [
    "CHALLENGE_TTL", "b64decode", "valid_keys", "wrap", "verify",
    "login_message", "register_message",
    "issue_challenge", "consume_challenge", "device"
]


def _purpose(name: str) -> str:
    from .. import additive
    return additive.unique_name(name)


def login_message(user_id: int, challenge: str) -> str:
    return "\n".join((_purpose("mobile:login"), str(user_id), challenge))


def register_message(user_id: int, enc_pubkey: str,
                     sig_pubkey: str, challenge: str) -> str:
    return "\n".join((
        _purpose("mobile:register"), str(user_id),
        enc_pubkey, sig_pubkey, challenge
    ))


def _challenge_key(challenge: str) -> str:
    from .. import additive
    return f"{additive.id}:mobile:challenge:{challenge}"


async def issue_challenge() -> str:
    challenge = secrets.token_urlsafe(32)
    await cache.aset(_challenge_key(challenge), "1", timeout=CHALLENGE_TTL)
    return challenge


async def consume_challenge(challenge) -> bool:
    if not isinstance(challenge, str) or not _CHALLENGE.match(challenge):
        return False

    key = _challenge_key(challenge)
    if await cache.aget(key) is None: return False
    await cache.adelete(key)
    return True


async def device(user_id: int) -> Optional[MobileSecurity]:
    async with db.async_executor(model=MobileSecurity) as e:
        result = await e.exec(select(MobileSecurity).where(
            MobileSecurity.uid == user_id
        ))
        return result.first()
