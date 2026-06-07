from webfluid.core.config import register_config


class DefaultConfig:
    AUTH_TOKEN_EXPIRY_EVENT_DEADLINE = 5


@register_config()
class Config(DefaultConfig): pass