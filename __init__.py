from webfluid import Additive, Fluid
from webfluid.core.ext import babel, db, scheduler
from webfluid.core.constants import EXT_MAIL, EXT_SCHEDULING
from webfluid.exceptions import AdditiveException

additive = Additive(
    __name__,
	required_extensions=[
		"sqlalchemy",
		"babel",
        "events"
    ]
)


@additive.before_enable
def before_enable(fluid: Fluid):
    from .services import TokenService, HashService, OAuthService, UserService

    TokenService.setup(
        fluid.config["AUTH_SECRET"],
        fluid.config.get("AUTH_TOKEN_MAX_AGE", 3600)
    )

    HashService.setup(
        fluid.config.get("AUTH_HASH_TIME_COST", 3),
        fluid.config.get("AUTH_HASH_MEMORY_COST", 65536),
        fluid.config.get("AUTH_HASH_PARALLELISM", 4)
    )

    OAuthService.setup(fluid.config.get("AUTH_OAUTH_CLIENTS", {}))

    UserService.setup()


    bind = fluid.config.get("AUTH_MODELS_DB_BIND")
    if bind:
        from .models.user import User, Identity, Role, Permission
        User.set_bind(bind)
        Identity.set_bind(bind)
        Role.set_bind(bind)
        Permission.set_bind(bind)


    from .api import health, setup_v1
    additive.api.get("/health")(health)
    setup_v1(additive)


    from .events import setup
    setup(additive)


    from .i18n import translations
    babel.register_domain(additive.id)
    babel.update_translations(additive.id, translations)
