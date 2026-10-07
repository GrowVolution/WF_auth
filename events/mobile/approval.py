from typing import Optional

from ...services import approval as approvals, mobile as devices


def _int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


async def state_query(data: dict) -> Optional[dict]:
    approval = (data or {}).get("approval")
    if not isinstance(approval, str):
        raise TypeError("Expected { approval: str }.")

    state = await approvals.load(approval)
    if not state: return None

    return {
        "user_id": state["user_id"],
        "device": state["device"],
        "state": state["state"],
        "delegated": bool(state.get("delegated")),
        "expires": approvals.remaining(state)
    }


async def resolve_query(data: dict) -> bool:
    approval = (data or {}).get("approval")
    user_id = (data or {}).get("user_id")
    approved = (data or {}).get("approved")
    if not isinstance(approval, str) or not _int(user_id) or not isinstance(approved, bool):
        raise TypeError("Expected { approval: str, user_id: int, approved: bool }.")

    return await approvals.resolve(approval, user_id, approved)


async def fingerprint_query(data: dict) -> Optional[str]:
    user_id = (data or {}).get("user_id")
    if not _int(user_id):
        raise TypeError("Expected { user_id: int }.")

    device = await devices.device(user_id)
    return approvals.fingerprint(device.sig_pubkey) if device else None
