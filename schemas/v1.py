from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional

from ..utils import validate_username, validate_password


class RoleSchema(BaseModel):
    name: str
    permissions: list[str] = Field(default_factory=list)


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
    email: Optional[EmailStr] = None
    confirmed: bool
    is_admin: bool


class ResetRequest(BaseModel):
    email: EmailStr


class ResetPassword(BaseModel):
    password: str
    _validate_password = field_validator("password")(validate_password)


class AuthorizeRequest(BaseModel):
    action: str
    action_id: str

    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
