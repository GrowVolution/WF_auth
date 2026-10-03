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
