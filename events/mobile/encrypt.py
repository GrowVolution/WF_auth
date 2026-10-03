from typing import Optional

from ...services import mobile as service


async def handle_query(data: dict) -> Optional[str]:
    user_id = (data or {}).get("user_id")
    payload = (data or {}).get("data")
    if not isinstance(user_id, int) or isinstance(user_id, bool) \
            or not isinstance(payload, str):
        raise TypeError("Expected { user_id: int, data: str }.")

    try: raw = service.b64decode(payload)
    except ValueError: raise TypeError("data must be base64url encoded.")

    device = await service.device(user_id)
    if not device: return None
    return service.wrap(device.enc_pubkey, raw)
