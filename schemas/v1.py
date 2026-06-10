from pydantic import BaseModel, EmailStr, Field, field_validator
from webfluid.extensions.security.utils import (
    validate_username, validate_password
)
from typing import Optional


class RoleSchema(BaseModel):
    name: str
    permissions: list[str] = Field(default_factory=list)
    is_admin: bool = False
    requires_2fa: bool = False


class UserSchema(BaseModel):
    username: str
    email: EmailStr
    roles: list[RoleSchema] = Field(default_factory=list)


class CreateUser(UserSchema):
    password: str

    _validate_username = field_validator("username")(validate_username)
    _validate_password = field_validator("password")(validate_password)


class UpdateUser(UserSchema):
    current_password: Optional[str] = None
    new_password: Optional[str] = None

    _validate_username = field_validator("username")(validate_username)

    @field_validator("new_password")
    @classmethod
    def _validate_new_password(cls, v):
        if v is not None:
            return validate_password(v)
        return v


class InitialSetup(BaseModel):
    admin_user: CreateUser
    admin_role: RoleSchema


class LoginUser(BaseModel):
    username: str
    password: str


class UserResponse(UserSchema):
    id: int
    email: Optional[EmailStr]
    pending_email: Optional[EmailStr]
    email_verified: bool
    is_admin: bool
    has_2fa: bool


class AdminUpdateUser(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    new_password: Optional[str] = None
    roles: Optional[list[str]] = None

    @field_validator("username")
    @classmethod
    def _validate_username(cls, v):
        if v is not None:
            return validate_username(v)
        return v

    @field_validator("new_password")
    @classmethod
    def _validate_new_password(cls, v):
        if v is not None:
            return validate_password(v)
        return v


class AdminCreateRole(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    is_admin: bool = False
    requires_2fa: bool = False
    permissions: list[str] = Field(default_factory=list)


class AdminUpdateRole(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    is_admin: Optional[bool] = None
    requires_2fa: Optional[bool] = None
    permissions: Optional[list[str]] = None


class AdminCreatePermission(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class AdminRolePermission(BaseModel):
    permission: str


class AdminRoleMember(BaseModel):
    user_id: int


class AdminUserResponse(BaseModel):
    id: int
    username: str
    email: Optional[EmailStr]
    email_verified: bool
    is_admin: bool
    has_2fa: bool
    sso: bool
    roles: list[str]


class AdminPermissionResponse(BaseModel):
    id: int
    name: str
    role_count: int


class AdminRoleResponse(BaseModel):
    id: int
    name: str
    is_admin: bool
    requires_2fa: bool
    permissions: list[str]
    user_count: int


class AdminConfigResponse(BaseModel):
    admin_role_requires_2fa: bool


class ResetRequest(BaseModel):
    email: EmailStr


class ResetPassword(BaseModel):
    password: str
    _validate_password = field_validator("password")(validate_password)


class Token(BaseModel):
    name: str
    exp: Optional[str] = None
    iat: Optional[str] = None


class CreateToken(Token):
    payload: dict
    expires: Optional[int] = None


class UpdateToken(Token):
    name: Optional[str] = None
    iat: str


class Tokens(BaseModel):
    tokens: list[Token]


class TOTPSetupResponse(BaseModel):
    secret: str
    uri: str
    qr: str


class TOTPVerify(BaseModel):
    code: str


class BackupCodesResponse(BaseModel):
    codes: list[str]


class BackupCodeVerify(BaseModel):
    code: str


class WebAuthnOptions(BaseModel):
    options: dict


class WebAuthnRegister(BaseModel):
    credential: dict
    name: Optional[str] = None


class WebAuthnVerify(BaseModel):
    credential: dict


class WebAuthnDelete(BaseModel):
    credential_id: str
