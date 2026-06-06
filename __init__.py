from webfluid import Additive, Fluid
from webfluid.core.ext import babel

additive = Additive(
    __name__,
	required_extensions=[
        "scheduling",
		"sqlalchemy",
        "security",
        "events"
    ]
)


@additive.before_enable
def before_enable(fluid: Fluid):
    from .api import health, setup_v1
    additive.api.get("/health")(health)
    setup_v1(additive, fluid)

    from .events import setup
    setup(additive)

    from .i18n import translations
    babel.update_translations("messages", translations)
