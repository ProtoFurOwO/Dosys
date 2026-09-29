from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, examples=["paciente"])
    password: str = Field(min_length=8, max_length=128, examples=["Paciente123!"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: str


class TwoFactorChallengeResponse(BaseModel):
    """Respuesta cuando la contraseña es correcta pero falta el segundo factor."""

    requires_2fa: bool = True
    challenge_token: str
    message: str = "Escribe el código de 6 dígitos de tu app autenticadora."


class TwoFactorVerifyRequest(BaseModel):
    challenge_token: str = Field(min_length=20)
    code: str = Field(min_length=6, max_length=16, examples=["123456"])


class TwoFactorSetupResponse(BaseModel):
    secret: str
    otpauth_uri: str
    issuer: str


class TwoFactorConfirmRequest(BaseModel):
    code: str = Field(min_length=6, max_length=16)


class TwoFactorEnableResponse(BaseModel):
    enabled: bool
    recovery_codes: list[str]


class TwoFactorStatusResponse(BaseModel):
    enabled: bool
    recovery_codes_remaining: int


class TwoFactorDisableRequest(BaseModel):
    password: str = Field(min_length=8, max_length=128)
