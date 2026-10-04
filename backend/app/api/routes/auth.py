from datetime import datetime, timezone

import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.security import (
    TWO_FACTOR_PURPOSE,
    create_access_token,
    create_challenge_token,
    decode_token,
    verify_password,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    PasswordChangeRequest,
    PasswordForgotRequest,
    PasswordForgotResponse,
    PasswordResetRequest,
    RefreshRequest,
    TokenResponse,
    TwoFactorChallengeResponse,
    TwoFactorConfirmRequest,
    TwoFactorDisableRequest,
    TwoFactorEnableResponse,
    TwoFactorSetupResponse,
    TwoFactorStatusResponse,
    TwoFactorVerifyRequest,
)
from app.services import accounts, email, login_security, rate_limit, two_factor
from app.services.audit import write_audit_event
from app.services.permissions import permission_codes
from app.services.users import AccountError, password_policy_error

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/login", response_model=TokenResponse | TwoFactorChallengeResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Autentica a un usuario; si tiene 2FA activo devuelve un token de desafío.

    El mensaje es deliberadamente genérico para no revelar si un usuario existe.
    Acepta el nombre de usuario o el correo registrado.
    """
    if rate_limit.exceeded("api-login", request):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos desde esta red. Espera un minuto.",
            headers={"Retry-After": "60"},
        )

    user = await accounts.find_user_by_identifier(db, payload.username)

    if user is not None and login_security.is_locked(user):
        await write_audit_event(
            db,
            user=user,
            action="login_blocked",
            entity_type="authentication",
            entity_id=user.id,
            request=request,
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=(
                "Cuenta bloqueada temporalmente por intentos fallidos. "
                f"Intenta de nuevo en {login_security.lock_minutes_left(user)} minutos."
            ),
        )

    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        if user is not None and user.is_active:
            locked = await login_security.register_failed_attempt(db, user)
            if locked:
                await write_audit_event(
                    db,
                    user=user,
                    action="account_locked",
                    entity_type="authentication",
                    entity_id=user.id,
                    request=request,
                    detail=f"intentos={settings.login_max_attempts} bloqueo_min={settings.login_lock_minutes}",
                )
        await write_audit_event(
            db,
            user=None,
            action="login_failed",
            entity_type="authentication",
            entity_id=None,
            request=request,
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    await login_security.reset_failed_attempts(db, user)

    if user.totp_enabled and user.totp_secret:
        challenge, _ = create_challenge_token(user.id)
        await write_audit_event(
            db,
            user=user,
            action="login_2fa_challenge",
            entity_type="authentication",
            entity_id=user.id,
            request=request,
        )
        await db.commit()
        return TwoFactorChallengeResponse(challenge_token=challenge)

    token, expires_in = create_access_token(user.id, user.role.code, sorted(permission_codes(user)))
    refresh_token = await accounts.issue_refresh_token(db, user)
    await write_audit_event(
        db,
        user=user,
        action="login_success",
        entity_type="authentication",
        entity_id=user.id,
        request=request,
    )
    await db.commit()
    return TokenResponse(
        access_token=token, refresh_token=refresh_token, expires_in=expires_in, role=user.role.code
    )


@router.post("/2fa/verify", response_model=TokenResponse)
async def verify_two_factor(
    payload: TwoFactorVerifyRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Completa el inicio de sesión con el código TOTP o un código de recuperación."""
    try:
        decoded = decode_token(payload.challenge_token, purpose=TWO_FACTOR_PURPOSE)
        user_id = int(decoded["sub"])
    except (pyjwt.PyJWTError, KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El proceso de verificación expiró. Vuelve a iniciar sesión.",
        ) from None

    user = await db.get(User, user_id)
    if user is None or not user.is_active or not user.totp_enabled or not user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El proceso de verificación expiró. Vuelve a iniciar sesión.",
        )

    used_recovery = False
    valid = two_factor.verify_code(user.totp_secret, payload.code)
    if not valid:
        used_recovery = await two_factor.consume_recovery_code(db, user, payload.code)
        valid = used_recovery

    if not valid:
        await write_audit_event(
            db,
            user=user,
            action="login_2fa_failed",
            entity_type="authentication",
            entity_id=user.id,
            request=request,
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Código incorrecto. Revisa tu app autenticadora e intenta de nuevo.",
        )

    if used_recovery:
        await write_audit_event(
            db,
            user=user,
            action="recovery_code_used",
            entity_type="authentication",
            entity_id=user.id,
            request=request,
        )

    token, expires_in = create_access_token(user.id, user.role.code, sorted(permission_codes(user)))
    refresh_token = await accounts.issue_refresh_token(db, user)
    await write_audit_event(
        db,
        user=user,
        action="login_2fa_success",
        entity_type="authentication",
        entity_id=user.id,
        request=request,
    )
    await db.commit()
    return TokenResponse(
        access_token=token, refresh_token=refresh_token, expires_in=expires_in, role=user.role.code
    )


@router.get("/2fa/status", response_model=TwoFactorStatusResponse)
async def two_factor_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TwoFactorStatusResponse:
    return TwoFactorStatusResponse(
        enabled=current_user.totp_enabled,
        recovery_codes_remaining=await two_factor.recovery_codes_remaining(db, current_user),
    )


@router.post("/2fa/setup", response_model=TwoFactorSetupResponse)
async def two_factor_setup(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TwoFactorSetupResponse:
    """Genera un secreto nuevo (pendiente de confirmar con un código)."""
    if current_user.totp_enabled:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El segundo factor ya está activo.")

    secret = two_factor.generate_secret()
    current_user.totp_secret = secret
    await db.flush()
    await db.commit()

    return TwoFactorSetupResponse(
        secret=secret,
        otpauth_uri=two_factor.provisioning_uri(secret, current_user.username),
        issuer=settings.totp_issuer,
    )


@router.post("/2fa/confirm", response_model=TwoFactorEnableResponse)
async def two_factor_confirm(
    payload: TwoFactorConfirmRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TwoFactorEnableResponse:
    if not current_user.totp_secret:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Primero genera el código QR.")
    if not two_factor.verify_code(current_user.totp_secret, payload.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El código no coincide. Revisa la hora de tu teléfono e intenta otra vez.",
        )

    codes = two_factor.generate_recovery_codes()
    await two_factor.store_recovery_codes(db, current_user, codes)
    current_user.totp_enabled = True
    current_user.totp_confirmed_at = datetime.now(timezone.utc)
    await write_audit_event(
        db,
        user=current_user,
        action="two_factor_enabled",
        entity_type="authentication",
        entity_id=current_user.id,
        request=request,
    )
    await db.commit()
    return TwoFactorEnableResponse(enabled=True, recovery_codes=codes)


@router.post("/2fa/disable", response_model=TwoFactorStatusResponse)
async def two_factor_disable(
    payload: TwoFactorDisableRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TwoFactorStatusResponse:
    if not verify_password(payload.password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Contraseña incorrecta.")

    await two_factor.clear_two_factor(db, current_user)
    await write_audit_event(
        db,
        user=current_user,
        action="two_factor_disabled",
        entity_type="authentication",
        entity_id=current_user.id,
        request=request,
    )
    await db.commit()
    return TwoFactorStatusResponse(enabled=False, recovery_codes_remaining=0)


# ── Sesión renovable ──────────────────────────────────────────────────────────


@router.post("/refresh", response_model=TokenResponse)
async def refresh_session(
    payload: RefreshRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Rota el token de renovación y entrega un acceso nuevo sin pedir credenciales."""
    if rate_limit.exceeded("api-refresh", request):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas solicitudes. Espera un minuto.",
            headers={"Retry-After": "60"},
        )

    rotated = await accounts.rotate_refresh_token(db, payload.refresh_token)
    if rotated is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La sesión expiró. Inicia sesión de nuevo.",
        )
    user, new_refresh = rotated
    token, expires_in = create_access_token(user.id, user.role.code, sorted(permission_codes(user)))
    await write_audit_event(
        db,
        user=user,
        action="session_refreshed",
        entity_type="authentication",
        entity_id=user.id,
        request=request,
    )
    await db.commit()
    return TokenResponse(access_token=token, refresh_token=new_refresh, expires_in=expires_in, role=user.role.code)


@router.post("/logout")
async def logout(
    payload: LogoutRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Revoca el token de renovación de esta sesión."""
    await accounts.revoke_refresh_token(db, payload.refresh_token)
    await db.commit()
    return {"detail": "Sesión cerrada."}


# ── Contraseñas ───────────────────────────────────────────────────────────────


@router.post("/password/change")
async def change_own_password(
    payload: PasswordChangeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Cambio de contraseña propio: exige la actual y cierra las demás sesiones."""
    try:
        await accounts.change_password(
            db,
            current_user,
            current=payload.current_password,
            new=payload.new_password,
            confirm=payload.new_password_confirm,
        )
    except AccountError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from None

    await write_audit_event(
        db,
        user=current_user,
        action="password_changed",
        entity_type="authentication",
        entity_id=current_user.id,
        request=request,
    )
    await db.commit()
    return {"detail": "Contraseña actualizada. Las demás sesiones se cerraron."}


@router.post("/password/forgot", response_model=PasswordForgotResponse)
async def forgot_password(
    payload: PasswordForgotRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> PasswordForgotResponse:
    """Solicita un enlace de restablecimiento (la respuesta no revela si la cuenta existe)."""
    if rate_limit.exceeded("api-forgot", request):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas solicitudes. Espera un minuto.",
            headers={"Retry-After": "60"},
        )

    user = await accounts.find_user_by_identifier(db, payload.identifier)
    delivery = "simulated"
    preview_url: str | None = None

    if user is not None and user.is_active:
        token = await accounts.create_password_reset(db, user)
        link = accounts.reset_link(token)
        if user.email:
            sent, _ = await email.send_email(
                to=user.email,
                subject="D.O.S.Y.S · Restablece tu contraseña",
                text=(
                    "Recibimos una solicitud para restablecer tu contraseña.\n\n"
                    f"Abre este enlace (válido {settings.password_reset_expire_minutes} minutos):\n{link}\n\n"
                    "Si no fuiste tú, ignora este mensaje."
                ),
            )
            delivery = "email" if sent else "simulated"
        if settings.app_env == "development":
            # Sin proveedor de correo en desarrollo se permite probar el flujo completo.
            preview_url = link
        await write_audit_event(
            db,
            user=user,
            action="password_reset_requested",
            entity_type="authentication",
            entity_id=user.id,
            request=request,
            detail=f"delivery={delivery}",
        )

    await db.commit()
    return PasswordForgotResponse(delivery=delivery, preview_url=preview_url)


@router.post("/password/reset")
async def reset_password(
    payload: PasswordResetRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Restablece la contraseña con un token de un solo uso."""
    if rate_limit.exceeded("api-reset", request):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas solicitudes. Espera un minuto.",
            headers={"Retry-After": "60"},
        )

    # Validar la política antes de consumir el token evita quemarlo por un error de forma.
    policy_error = password_policy_error(payload.new_password, payload.new_password_confirm)
    if policy_error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=policy_error)

    user = await accounts.consume_password_reset(db, payload.token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El enlace no es válido o ya expiró. Solicita uno nuevo.",
        )

    try:
        await accounts.replace_password(
            db, user, new=payload.new_password, confirm=payload.new_password_confirm
        )
    except AccountError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from None

    await write_audit_event(
        db,
        user=user,
        action="password_reset",
        entity_type="authentication",
        entity_id=user.id,
        request=request,
    )
    await db.commit()
    return {"detail": "Contraseña restablecida. Inicia sesión con la nueva."}
