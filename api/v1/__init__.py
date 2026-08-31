from fastapi import APIRouter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from webfluid import Additive, Fluid

v1 = APIRouter(prefix="/v1")


def setup(a: "Additive", f: "Fluid"):
    from .create import (
        setup_request as initial_setup,
        setup_available,
        default_request as create_user
    )
    v1.get("/dev/setup")(setup_available)
    v1.post("/dev/setup")(initial_setup)
    v1.post("/users/create")(create_user)

    from .login import (
        available_request as login_available,
        default_request as login_user,
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
        default_request as confirm_user
    )
    v1.get("/users/confirm")(confirm_user)

    from .verification import (
        email_request as email_verification,
        set_email_request as set_email,
        resend_request as resend_confirmation
    )
    v1.get("/verification/email")(email_verification)
    v1.post("/verification/email")(f.limit("6/hour")(set_email))
    v1.post("/verification/email/resend")(f.limit("2/hour")(resend_confirmation))

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

    from .jwt import (
        create_request as create_jwt,
        list_request as list_jwts,
        patch_request as update_jwt,
        delete_request as delete_jwt,
        metadata_request as jwt_metadata
    )
    v1.post("/users/jwt")(create_jwt)
    v1.get("/users/jwts")(list_jwts)
    v1.get("/users/jwt/metadata")(jwt_metadata)
    v1.patch("/users/jwt")(update_jwt)
    v1.delete("/users/jwt")(delete_jwt)

    from .two_fa import (
        status as two_fa_status,
        request_totp,
        verify_totp,
        delete_totp,
        register_webauthn,
        verify_webauthn_register,
        authenticate_webauthn,
        verify_webauthn,
        delete_webauthn,
        request_backup,
        verify_backup,
        delete_backup
    )
    from ...schemas.v1 import (
        AdminUserResponse, AdminRoleResponse,
        AdminPermissionResponse, AdminConfigResponse
    )

    from .admin_users import (
        create_request as admin_create_user,
        list_request as admin_list_users,
        get_request as admin_get_user,
        update_request as admin_update_user,
        delete_request as admin_delete_user
    )
    v1.post("/admin/users")(admin_create_user)
    v1.get("/admin/users", response_model=list[AdminUserResponse])(admin_list_users)
    v1.get("/admin/users/{user_id}", response_model=AdminUserResponse)(admin_get_user)
    v1.patch("/admin/users/{user_id}")(admin_update_user)
    v1.delete("/admin/users/{user_id}")(admin_delete_user)

    from .admin_roles import (
        config_request as admin_config,
        list_request as admin_list_roles,
        create_request as admin_create_role,
        update_request as admin_update_role,
        delete_request as admin_delete_role,
        add_permission_request as admin_add_role_permission,
        remove_permission_request as admin_remove_role_permission,
        add_member_request as admin_add_role_member,
        remove_member_request as admin_remove_role_member
    )
    v1.get("/admin/config", response_model=AdminConfigResponse)(admin_config)
    v1.get("/admin/roles", response_model=list[AdminRoleResponse])(admin_list_roles)
    v1.post("/admin/roles")(admin_create_role)
    v1.patch("/admin/roles/{role_id}")(admin_update_role)
    v1.delete("/admin/roles/{role_id}")(admin_delete_role)
    v1.post("/admin/roles/{role_id}/permissions")(admin_add_role_permission)
    v1.delete("/admin/roles/{role_id}/permissions/{permission_id}")(admin_remove_role_permission)
    v1.post("/admin/roles/{role_id}/users")(admin_add_role_member)
    v1.delete("/admin/roles/{role_id}/users/{user_id}")(admin_remove_role_member)

    from .admin_permissions import (
        list_request as admin_list_permissions,
        create_request as admin_create_permission,
        delete_request as admin_delete_permission
    )
    v1.get("/admin/permissions", response_model=list[AdminPermissionResponse])(admin_list_permissions)
    v1.post("/admin/permissions")(admin_create_permission)
    v1.delete("/admin/permissions/{permission_id}")(admin_delete_permission)

    from ...schemas.v1 import TOTPSetupResponse, BackupCodesResponse
    v1.get("/users/2fa")(two_fa_status)
    v1.post("/users/2fa/totp", response_model=TOTPSetupResponse)(request_totp)
    v1.post("/users/2fa/totp/verify")(verify_totp)
    v1.delete("/users/2fa/totp")(delete_totp)
    v1.post("/users/2fa/webauthn/register")(register_webauthn)
    v1.post("/users/2fa/webauthn/register/verify")(verify_webauthn_register)
    v1.post("/users/2fa/webauthn/verify")(authenticate_webauthn)
    v1.post("/users/2fa/webauthn/verify/complete")(verify_webauthn)
    v1.delete("/users/2fa/webauthn")(delete_webauthn)
    v1.post("/users/2fa/backup", response_model=BackupCodesResponse)(request_backup)
    v1.post("/users/2fa/backup/verify")(verify_backup)
    v1.delete("/users/2fa/backup")(delete_backup)

    a.api.include_router(v1)
