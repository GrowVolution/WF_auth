from webfluid.core.config import register_config
from webfluid.core.constants import EXECUTION
from webfluid.exceptions import AdditiveException
import os, secrets

try: from ._my_config import MyConfig
except ImportError:
    class MyConfig: pass


class DefaultConfig:
    AUTH_TOKEN_EXPIRY_EVENT_DEADLINE = 5

    AUTH_2FA_ISSUER = "WebFluid"
    AUTH_2FA_BACKUP_CODE_COUNT = 10
    AUTH_2FA_BACKUP_CODE_DIGITS = 8

    AUTH_2FA_WEBAUTHN_RP_ID = "localhost"
    AUTH_2FA_WEBAUTHN_RP_NAME = "WebFluid"
    AUTH_2FA_WEBAUTHN_ORIGIN = "http://localhost:8000"

    AUTH_ADMIN_ROLE_REQUIRES_2FA = True

    AUTH_LEDGER_FLUSH_INTERVAL = 60

    AUTH_PROVIDER_APP_REDIRECTS = []
    AUTH_PROVIDER_APP_TTL = 600

    AUTH_JWT_MAX_DAYS = 365


@register_config()
class Config(MyConfig, DefaultConfig):
    AUTH_MOBILE_SECRET = os.getenv("MOBILE_SECRET")

    if EXECUTION:
        if not AUTH_MOBILE_SECRET:
            raise AdditiveException("Missing MOBILE_SECRET")


setup = {
    "MOBILE_SECRET": {
        "type": "auto", "value": secrets.token_hex(32)
    }
}
