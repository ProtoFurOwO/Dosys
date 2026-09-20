from pydantic import BaseModel, Field

from app.models.enums import UserRole


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, examples=["paciente"])
    password: str = Field(min_length=8, max_length=128, examples=["Paciente123!"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: UserRole
