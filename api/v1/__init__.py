from fastapi import APIRouter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from webfluid import Additive, Fluid

v1 = APIRouter(prefix="/v1")


def setup(a: "Additive", f: "Fluid"):
    from .create import (
        setup_request as initial_setup,
        setup_available,
        admin_request as create_user_admin,
        default_request as create_user
    )
    v1.get("/dev/setup")(setup_available)
    v1.post("/dev/setup")(initial_setup)
    v1.post("/admin/users/create")(create_user_admin)
    v1.post("/users/create")(create_user)

    from .login import (
        default_request as login_user,
        login_available,
        oauth_request as oauth_login,
        callback_request as oauth_callback
    )
    v1.post("/users/login/available")(login_available)
    v1.post("/users/login")(login_user)
    v1.get("/{provider}/login")(oauth_login)
    v1.api_route(
        "/{provider}/login/callback",
        methods=["GET", "POST"],
        name=a.unique_name("oauth_callback")
    )(oauth_callback)

    from .logout import (
        default_request as logout_user
    )
    v1.get("/users/logout")(logout_user)

    from .connect import (
        oauth_request as connect_oauth,
        callback_request as connect_callback
    )
    v1.get("/{provider}/connect")(connect_oauth)
    v1.api_route(
        "/{provider}/connect/callback",
        methods=["GET", "POST"],
        name=a.unique_name("connect_callback")
    )(connect_callback)

    from .confirm import (
        default_request as confirm_user,
        resend_request as resend_confirmation
    )
    v1.get("/users/confirm")(confirm_user)
    v1.post("/users/confirm/resend")(f.limit("2/hour")(resend_confirmation))

    from .reset import (
        reset_request,
        ui_request as reset_page,
        reset_password
    )
    v1.post("/users/reset/request")(f.limit("2/hour")(reset_request))
    v1.get("/users/reset")(reset_page)
    v1.post("/users/reset")(reset_password)

    from .user import (
        available_request as user_available,
        get_request as get_user,
        update_request as update_user,
        delete_request as delete_user
    )
    from ...schemas.v1 import UserResponse
    v1.get("/users/me/available")(user_available)
    v1.get("/users/me", response_model=UserResponse)(get_user)
    v1.patch("/users/me")(update_user)
    v1.delete("/users/me")(delete_user)

    from .authorize import (
        default_request as authorize_user,
        admin_request as authorize_admin,
        roles_request as authorize_roles,
        any_role_request as authorize_any_role,
        permissions_request as authorize_permissions,
        any_permission_request as authorize_any_permission
    )
    v1.post("/authorize/user")(authorize_user)
    v1.post("/authorize/admin")(authorize_admin)
    v1.post("/authorize/roles")(authorize_roles)
    v1.post("/authorize/any-role")(authorize_any_role)
    v1.post("/authorize/permissions")(authorize_permissions)
    v1.post("/authorize/any-permission")(authorize_any_permission)

    a.api.include_router(v1)
