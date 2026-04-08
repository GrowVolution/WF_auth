from webfluid.core.config import register_config
from webfluid.core.constants import DEBUG, EXECUTION
from webfluid.exceptions import AdditiveException
from secrets import token_hex
import os

from ._my_config import MyConfig


class DefaultConfig:
    AUTH_SECRET: str

    AUTH_TOKEN_MAX_AGE = 3600
    AUTH_CSRF_COOKIE_NAME = "csrf_token"
    AUTH_CSRF_COOKIE_SECURE = True

    AUTH_HASHER_TIME_COST = 3
    AUTH_HASHER_MEMORY_COST = 65536
    AUTH_HASHER_PARALLELISM = 4

    AUTH_PASSWORD_MIN_LENGTH = 8
    AUTH_PASSWORD_REQUIREMENTS = {
        "lower": 1,
        "upper": 1,
        "digits": 1,
        "special": 1
    }

    AUTH_OAUTH_CLIENTS = {}

    AUTH_MODELS_DB_BIND = None


@register_config()
class Config(MyConfig, DefaultConfig):
    AUTH_SECRET = os.getenv("AUTH_SECRET")
    if DEBUG and not AUTH_SECRET:
        AUTH_SECRET = token_hex(16)
    elif EXECUTION and not AUTH_SECRET:
        raise AdditiveException("Missing AUTH_SECRET in environment.")


setup = {
    "AUTH_SECRET": {
        "type": "auto",
        "value": token_hex(32),
    }
}
