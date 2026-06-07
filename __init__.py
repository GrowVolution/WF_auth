from webfluid import Additive, Fluid
from webfluid.core.ext import babel

additive = Additive(
    __name__,
	required_extensions=[
        "scheduling",
		"sqlalchemy",
        "security",
        "events",
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

    from .services import setup as setup_services
    setup_services(fluid)

    from .i18n import translations
    babel.update_translations("messages", translations)
