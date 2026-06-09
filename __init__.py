from webfluid import Additive, Fluid
from webfluid.core.ext import babel
from webfluid.core.constants import EXT_BABEL

additive = Additive(
    __name__,
	required_extensions=[
        "scheduling",
		"sqlalchemy",
        "security",
        "events",
        "cache",
        "jwt"
    ]
)


@additive.before_enable
def before_enable(fluid: Fluid):
    from .api import health, setup_v1
    additive.api.get("/health")(health)
    setup_v1(additive, fluid)

    from .events import setup as setup_events
    setup_events(additive)

    bind = fluid.config.get("SECURITY_MODELS_DB_BIND")
    if bind:
        from .models.token import Token
        Token.set_bind(bind)

    from .jobs import setup as setup_jobs
    setup_jobs(fluid)

    if EXT_BABEL:
        from .i18n import translations
        babel.update_translations("messages", translations)
