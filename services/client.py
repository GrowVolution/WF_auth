from fastapi import Request
from typing import Optional
import hmac, re

HEADER = "X-Client-Ident"
AGENT = re.compile(r"^[a-z][a-z0-9_.-]{0,63}/[0-9][a-z0-9.+_-]{0,31} \((?:android|ios)(?:; [^()]{1,128})?\)$", re.I)

_secret = b""

__all__ = ["HEADER", "AGENT", "configure", "refusal"]


def configure(secret: Optional[str]):
    global _secret
    _secret = (secret or "").encode("utf-8")


def refusal(request: Optional[Request]) -> Optional[str]:
    if request is None: return "INVALID_CLIENT"

    presented = request.headers.get(HEADER, "").encode("utf-8")
    if not _secret or not hmac.compare_digest(presented, _secret):
        return "INVALID_CLIENT"

    if not AGENT.match(request.headers.get("user-agent", "")):
        return "INVALID_USER_AGENT"

    return None
