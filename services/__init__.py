from webfluid.core.ext import scheduler
from apscheduler.triggers.cron import CronTrigger
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from webfluid import Fluid


def setup(f: "Fluid"):
    from .token import get_watcher
    scheduler.add_job(get_watcher(f), CronTrigger(hour=0))
