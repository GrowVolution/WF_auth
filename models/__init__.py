from webfluid.core.constants import EXECUTION

if not EXECUTION:
    from .token import Token

    from webfluid.core.context import FluidContext
    ctx = FluidContext.current()
    bind = ctx.fluid.config.get("SECURITY_MODELS_DB_BIND")
    if bind: Token.set_bind(bind)

__all__ = ["token"]
