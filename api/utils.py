from fastapi import Request, HTTPException
from sqlalchemy import select
from webfluid.core.ext import security as s
from webfluid.extensions.security.models import User
from typing import TYPE_CHECKING, Any, Mapping, Optional

if TYPE_CHECKING:
    from fastapi.params import Depends as DependsParam


def resolver(grant: str) -> Any["DependsParam"]:
    return s.user_service.requirement_and_grant(
        {"requirement": "is_admin"}, grant
    )


async def attached_user(user: User, e, *options) -> User:
    stmt = select(User).where(User.id == user.id)
    if options: stmt = stmt.options(*options)

    result = await e.exec(stmt)
    attached = result.first()
    if not attached:
        raise HTTPException(status_code=404, detail="UNKNOWN_USER")
    return attached


def session_verified(request: Request) -> bool:
    return bool(request.session.get("2fa_verified"))


def require_verified_session(request: Request, user: User):
    if s.user_service.has_2fa(user) and not session_verified(request):
        raise HTTPException(status_code=401, detail="TWO_FA_REQUIRED")


def require_verified_email(user: User):
    if not s.user_service.email_verified(user):
        raise HTTPException(status_code=401, detail="EMAIL_NOT_VERIFIED")


def escalate(request: Request, user: User):
    require_verified_email(user)
    require_verified_session(request, user)


_CLAIM_SOURCES: dict[str, tuple[str, ...]] = {
    "full_name": (
        "name", "full_name", "fullName", "fullname",
        "display_name", "displayName", "displayname", "cn"
    ),
    "first_name": (
        "given_name", "givenName", "givenname",
        "first_name", "firstName", "firstname"
    ),
    "last_name": (
        "family_name", "familyName", "familyname",
        "last_name", "lastName", "lastname",
        "surname", "sn"
    ),
    "middle_name": ("middle_name", "middleName", "middlename"),
    "nickname": (
        "nickname", "preferred_username", "preferredUsername",
        "username", "login"
    ),
    "email": ("email", "mail", "email_address", "emailAddress", "upn"),
    "picture": (
        "picture", "avatar", "avatar_url", "avatarUrl",
        "photo", "photoURL", "thumbnailPhotoUrl"
    ),
    "locale": ("locale", "lang", "language"),
    "timezone": ("zoneinfo", "timezone", "tz"),
    "phone": ("phone_number", "phoneNumber", "phone", "mobile")
}

_ROLE_SOURCES = (
    "roles", "role", "groups", "group",
    "memberOf", "member_of", "memberof",
    "authorities"
)

_NESTED_ROLE_SOURCES = (
    ("realm_access", "roles"),
    ("resource_access", None)
)


def _text(value: Any) -> Optional[str]:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return None


def _first_text(claims: Mapping[str, Any], names: tuple[str, ...]) -> Optional[str]:
    for name in names:
        text = _text(claims.get(name))
        if text: return text
    return None


def _as_roles(value: Any) -> list[str]:
    if isinstance(value, str):
        parts = value.replace(",", " ").split()
        return [part for part in parts if part]
    if isinstance(value, (list, tuple, set, frozenset)):
        collected = []
        for entry in value:
            text = _text(entry)
            if text: collected.append(text)
            elif isinstance(entry, Mapping):
                nested = _first_text(entry, ("name", "id", "slug", "title"))
                if nested: collected.append(nested)
        return collected
    return []


def _roles(claims: Mapping[str, Any]) -> list[str]:
    collected: list[str] = []

    for name in _ROLE_SOURCES:
        collected.extend(_as_roles(claims.get(name)))

    for outer, inner in _NESTED_ROLE_SOURCES:
        nested = claims.get(outer)
        if not isinstance(nested, Mapping): continue
        if inner:
            collected.extend(_as_roles(nested.get(inner)))
            continue
        for entry in nested.values():
            if isinstance(entry, Mapping):
                collected.extend(_as_roles(entry.get("roles")))

    seen = set()
    unique = []
    for role in collected:
        if role in seen: continue
        seen.add(role)
        unique.append(role)
    return unique


def normalized_claims(userinfo: Mapping[str, Any]) -> dict:
    normalized = {}

    for field, names in _CLAIM_SOURCES.items():
        value = _first_text(userinfo, names)
        if value: normalized[field] = value

    roles = _roles(userinfo)
    if roles: normalized["roles"] = roles

    if "full_name" not in normalized:
        parts = [
            normalized.get("first_name"),
            normalized.get("middle_name"),
            normalized.get("last_name")
        ]
        joined = " ".join(part for part in parts if part)
        if joined and normalized.get("first_name") and normalized.get("last_name"):
            normalized["full_name"] = joined

    return normalized
