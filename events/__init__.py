from webfluid.core.ext import events
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from webfluid import Additive


def setup(a: "Additive"):
    events.create_signal(a.unique_name("user_confirmed"))

    from .autodelete import handle_event as autodelete_event
    events.event(a.unique_name("autodelete_unconfirmed"))(autodelete_event)
