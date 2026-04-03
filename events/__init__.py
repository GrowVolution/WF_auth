from webfluid.core.ext import events
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from webfluid import Additive


def setup(a: "Additive"):
    from .autodelete import handle_event as autodelete_event
    events.event(a.unique_name("autodelete_unconfirmed"))(autodelete_event)

    from .unconfirm import handle_event as unconfirm_event
    events.event(a.unique_name("unconfirm_user"))(unconfirm_event)
