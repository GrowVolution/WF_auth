from ...services import mobile as service


async def handle_query(data: dict) -> bool:
    user_id = (data or {}).get("user_id")
    message = (data or {}).get("message")
    signature = (data or {}).get("signature")
    if not isinstance(user_id, int) or isinstance(user_id, bool) \
            or not isinstance(message, str) or not isinstance(signature, str):
        raise TypeError("Expected { user_id: int, message: str, signature: str }.")

    device = await service.device(user_id)
    if not device: return False
    return service.verify(device.sig_pubkey, message, signature)
