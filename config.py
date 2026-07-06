from webfluid.core.config import register_config

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


@register_config()
class Config(MyConfig, DefaultConfig): pass