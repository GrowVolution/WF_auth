from webfluid.utils import async_result
from datetime import datetime, UTC


async def handle_request():
    return await async_result({
        "status": "ok",
        "timestamp": datetime.now(UTC).isoformat()
    })
