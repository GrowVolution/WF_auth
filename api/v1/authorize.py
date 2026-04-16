from webfluid.core.ext import events
from webfluid.utils.logging import factory as log_factory

from ...models.user import User
from ...schemas.v1 import AuthorizeRequest
from ...services import UserService


async def _authorize_event(action: str, auth_info: dict):
    from ... import additive
    try: await events.trigger(additive.unique_name(f"authorize_{action}"), auth_info)
    except ValueError:
        log_factory.warning(f"[{additive.name}] No event handlers for: authorize_{action}")


async def default_request(
        authorize: AuthorizeRequest,
        user: User = UserService.require_user
):
    await _authorize_event(
        authorize.action, {
            "action_id": authorize.uuid,
            "user_id": user.id,
            "type": "default",
            "requested_roles": [],
            "requested_permissions": []
        })
    return { "status": "ok" }


async def admin_request(
        authorize: AuthorizeRequest,
        user: User = UserService.require_admin
):
    await _authorize_event(
        authorize.action, {
            "action_id": authorize.uuid,
            "user_id": user.id,
            "type": "admin",
            "requested_roles": [],
            "requested_permissions": []
        })
    return { "status": "ok" }


async def roles_request(
        authorize: AuthorizeRequest,
        user: User = UserService.require_roles_v1
):
    await _authorize_event(
        authorize.action, {
            "action_id": authorize.uuid,
            "user_id": user.id,
            "type": "roles",
            "requested_roles": authorize.roles,
            "requested_permissions": []
        }
    )
    return { "status": "ok" }


async def any_role_request(
        authorize: AuthorizeRequest,
        user: User = UserService.require_any_role_v1
):
    await _authorize_event(
        authorize.action, {
            "action_id": authorize.uuid,
            "user_id": user.id,
            "type": "any_role",
            "requested_roles": authorize.roles,
            "requested_permissions": []
        }
    )
    return { "status": "ok" }


async def permissions_request(
        authorize: AuthorizeRequest,
        user: User = UserService.require_permissions_v1
):
    await _authorize_event(
        authorize.action, {
            "action_id": authorize.uuid,
            "user_id": user.id,
            "type": "permissions",
            "requested_roles": [],
            "requested_permissions": authorize.permissions
        }
    )
    return { "status": "ok" }


async def any_permission_request(
        authorize: AuthorizeRequest,
        user: User = UserService.require_any_permission_v1
):
    await _authorize_event(
        authorize.action, {
            "action_id": authorize.uuid,
            "user_id": user.id,
            "type": "any_permission",
            "requested_roles": [],
            "requested_permissions": authorize.permissions
        }
    )
    return { "status": "ok" }
