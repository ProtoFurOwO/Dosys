"""Esquemas de la API de administración."""

from pydantic import BaseModel, Field


class AdminUserResponse(BaseModel):
    id: int
    username: str
    email: str | None
    role_code: str
    role_name: str
    is_active: bool


class AdminRoleResponse(BaseModel):
    id: int
    code: str
    name: str
    description: str | None
    is_system: bool
    permissions: list[str]
    users: int


class UserRoleUpdateRequest(BaseModel):
    role_code: str = Field(min_length=2, max_length=40, examples=["doctor"])


class RoleUpdateRequest(BaseModel):
    name: str = Field(min_length=3, max_length=80)
    description: str | None = Field(default=None, max_length=200)
    permissions: list[str] = Field(default_factory=list)
