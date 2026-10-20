from webfluid import Additive, Fluid
from webfluid.core.ext import scheduler, babel
from webfluid.core.constants import EXT_BABEL
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timedelta, UTC


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
async def before_enable(fluid: Fluid):
    fluid.add_source(
        f'<script src="{additive.prefix}/static/js/utils.js" type="module"></script>',
        priority=5
    )

    from .services.keylog import configure as configure_keylog
    configure_keylog(fluid.config["BASE_URL"])

    from .api import health, setup_v1
    additive.api.get("/health")(health)
    setup_v1(additive, fluid)

    from .events import setup as setup_events
    setup_events(additive)

    bind = fluid.config.get("SECURITY_MODELS_DB_BIND")
    if bind:
        from .models.token import Token
        from .models.mobile import MobileSecurity
        from .models.keylog import KeyStatement, ActionLog
        Token.set_bind(bind)
        MobileSecurity.set_bind(bind)
        KeyStatement.set_bind(bind)
        ActionLog.set_bind(bind)

    from .jobs import get_watcher, cache_revoked
    scheduler.add_job(get_watcher(fluid), CronTrigger(hour=0))
    await cache_revoked()

    from .services import outbox
    scheduler.add_job(outbox.import_all, DateTrigger(run_date=datetime.now(UTC) + timedelta(seconds=10)),
                      misfire_grace_time=None)
    scheduler.add_job(outbox.flush, IntervalTrigger(seconds=fluid.config.get("AUTH_LEDGER_FLUSH_INTERVAL", 60)))

    if EXT_BABEL:
        from .i18n import translations
        babel.update_translations("messages", translations)
