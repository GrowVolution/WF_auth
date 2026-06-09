from webfluid.core.ext import scheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, UTC, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from webfluid import Fluid


def setup(f: "Fluid"):
    from .token import get_watcher, cache_revoked
    scheduler.add_job(get_watcher(f), CronTrigger(hour=0))
    scheduler.add_job(
        cache_revoked, DateTrigger(
            run_date=datetime.now(UTC) + timedelta(seconds=5),
            timezone=UTC
        )
    )
