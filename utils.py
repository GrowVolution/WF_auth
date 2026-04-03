from webfluid.core.context import FluidContext
from webfluid.core.ext import babel
import string, re

from .config import DefaultConfig


def validate_username(username: str) -> str:
    if not re.match(r"^[a-zA-Z0-9_-]{3,30}$", username):
        from . import additive
        t = babel.domain_context(additive.id)(babel.gettext)
        raise ValueError(t("INVALID_USERNAME"))
    return username


def validate_password(password: str) -> str:
    min_len, requirements = FluidContext.get_ctx_data(
        DefaultConfig,
        "AUTH_PASSWORD_MIN_LENGTH",
        "AUTH_PASSWORD_REQUIREMENTS"
    )

    from . import additive
    t = babel.domain_context(additive.id)(babel.gettext)
    tn = babel.domain_context(additive.id)(babel.ngettext)
    errors = []

    if len(password) < min_len:
        errors.append(t("MIN_PSW_LEN", len=min_len))

    lower = upper = digits = special = 0
    for c in password:
        if c.islower():
            lower += 1
        elif c.isupper():
            upper += 1
        elif c.isdigit():
            digits += 1
        elif c in string.punctuation:
            special += 1

    min_lower = requirements.get("lower", 1)
    if lower < min_lower:
        errors.append(tn("MIN_LOWER", "", min_lower))

    min_upper = requirements.get("upper", 1)
    if upper < min_upper:
        errors.append(tn("MIN_UPPER", "", min_upper))

    min_digits = requirements.get("digits", 1)
    if digits < min_digits:
        errors.append(tn("MIN_DIGITS", "", min_digits))

    min_special = requirements.get("special", 1)
    if special < min_special:
        errors.append(tn("MIN_SPECIAL", "", min_special))

    if len(errors) > 0:
        exc = ValueError()
        exc.errors = errors
        raise exc

    return password
