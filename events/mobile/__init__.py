from webfluid.core.ext import events
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from webfluid import Additive


def setup(a: "Additive"):
    events.create_signal(a.unique_name("mobile:approval"))

    from .encrypt import handle_query as user_encrypt
    events.query(a.unique_name("user-encrypt"))(user_encrypt)

    from .signature import handle_query as verify_signature
    events.query(a.unique_name("verify-signature"))(verify_signature)

    from .approval import state_query, resolve_query, fingerprint_query
    events.query(a.unique_name("mobile:approval-state"))(state_query)
    events.query(a.unique_name("mobile:resolve"))(resolve_query)
    events.query(a.unique_name("mobile:fingerprint"))(fingerprint_query)

    from .keylog import state_query, append_query, accept_query, result_query, flush_query
    events.query(a.unique_name("keylog:state"))(state_query)
    events.query(a.unique_name("keylog:append"))(append_query)
    events.query(a.unique_name("action:accept"))(accept_query)
    events.query(a.unique_name("action:result"))(result_query)
    events.query(a.unique_name("ledger:flush"))(flush_query)
