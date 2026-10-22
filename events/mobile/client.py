from webfluid.core.context import FluidContext
from typing import Optional

from ...services import client


async def handle_query(_) -> Optional[str]:
    ctx = FluidContext.try_current()
    return client.refusal(ctx.request if ctx is not None else None)
