from webfluid.core.constants import EXECUTION

if not EXECUTION:
    from .token import Token
    from .mobile import MobileSecurity
    from .keylog import KeyStatement, ActionLog

    from webfluid.core.context import FluidContext
    ctx = FluidContext.try_current()
    bind = ctx.fluid.config.get("SECURITY_MODELS_DB_BIND") if ctx is not None and ctx.fluid is not None else None
    if bind:
        Token.set_bind(bind)
        MobileSecurity.set_bind(bind)
        KeyStatement.set_bind(bind)
        ActionLog.set_bind(bind)

__all__ = ["token", "mobile", "keylog"]
