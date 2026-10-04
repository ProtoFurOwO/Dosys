from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, examples=["paciente"])
    password: str = Field(min_length=8, max_length=128, examples=["Paciente123!"])


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int
    role: str


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=20)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
    new_password_confirm: str = Field(min_length=8, max_length=128)


class PasswordForgotRequest(BaseModel):
    identifier: str = Field(min_length=3, max_length=160, examples=["paciente", "paciente@correo.com"])


class PasswordForgotResponse(BaseModel):
    message: str = "Si la cuenta existe, generamos un enlace de restablecimiento."
    delivery: str = "simulated"
    preview_url: str | None = None


class PasswordResetRequest(BaseModel):
    token: str = Field(min_length=20)
    new_password: str = Field(min_length=8, max_length=128)
    new_password_confirm: str = Field(min_length=8, max_length=128)


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
