from pydantic import BaseModel, Field

from app.models.enums import DeviceTransferStatus


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, examples=["paciente"])
    password: str = Field(min_length=8, max_length=128, examples=["Paciente123!"])
    # Opcionales y retrocompatibles: la app identifica el dispositivo de confianza.
    device_id: str | None = Field(default=None, max_length=64)
    device_name: str | None = Field(default=None, max_length=120)


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


class DeviceTransferChallengeResponse(BaseModel):
    """La cuenta ya tiene un dispositivo activo y este es distinto."""

    requires_device_transfer: bool = True
    transfer_id: str
    challenge_token: str
    expires_in: int
    message: str = (
        "Enviamos una solicitud al dispositivo de confianza. Escribe ahí el código de 6 dígitos."
    )


class DeviceTransferCodeRequest(BaseModel):
    challenge_token: str = Field(min_length=20)
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$", examples=["482913"])


class DeviceTransferStatusRequest(BaseModel):
    challenge_token: str = Field(min_length=20)


class DeviceTransferCodeResponse(BaseModel):
    submissions_left: int
    detail: str = "Código enviado al dispositivo de confianza."


class DeviceTransferStatusResponse(BaseModel):
    status: DeviceTransferStatus
    expires_in: int = 0
    submissions_left: int = 0
    # Solo aparece una vez, al aprobarse la transferencia.
    tokens: TokenResponse | None = None


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
