from webfluid.core.ext import security as s
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi.params import Depends as DependsParam


def resolver(grant: str) -> Any["DependsParam"]:
    return s.user_service.requirement_and_grant(
        {"requirement": "is_admin"}, grant
    )
