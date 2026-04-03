from fastapi import APIRouter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from webfluid import Additive

v1 = APIRouter(prefix="/v1")


def setup(a: "Additive"):
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
    v1.get("/users/login")(login_available)
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
    v1.get("/users/confirm/resend")(resend_confirmation)

    from .update import handle_request as update_user
    v1.post("/users/update")(update_user)

    a.api.include_router(v1)
