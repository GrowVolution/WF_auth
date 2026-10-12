from datetime import datetime, UTC
from pathlib import Path
import hashlib

SCRIPT = Path(__file__).resolve().parent.parent / "static" / "js" / "utils.js"


async def provide(_) -> list[dict]:
    from .. import additive
    served = SCRIPT.read_bytes()
    version = str(additive.version)
    return [{
        "id": "auth_utils_js",
        "additive": additive.id,
        "type": "script",
        "algorithm": "sha256",
        "hash": hashlib.sha256(served).hexdigest(),
        "size": len(served),
        "version": version,
        "served_version": version,
        "url": f"{additive.prefix}/static/js/utils.js",
        "served": True,
        "computed_at": datetime.now(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "label": "Request and CSRF helpers of the auth additive (self-reported)",
        "provenance": { "status": "unsigned" }
    }]
