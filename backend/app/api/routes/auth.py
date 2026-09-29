from datetime import datetime, timezone

import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
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
    TokenResponse,
    TwoFactorChallengeResponse,
    TwoFactorConfirmRequest,
    TwoFactorDisableRequest,
    TwoFactorEnableResponse,
    TwoFactorSetupResponse,
    TwoFactorStatusResponse,
    TwoFactorVerifyRequest,
)
from app.services import login_security, two_factor
from app.services.audit import write_audit_event
from app.services.permissions import permission_codes

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/login", response_model=TokenResponse | TwoFactorChallengeResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Autentica a un usuario; si tiene 2FA activo devuelve un token de desafío.

    El mensaje es deliberadamente genérico para no revelar si un usuario existe.
    """
    user = await db.scalar(select(User).where(User.username == payload.username.strip().lower()))

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
    await write_audit_event(
        db,
        user=user,
        action="login_success",
        entity_type="authentication",
        entity_id=user.id,
        request=request,
    )
    await db.commit()
    return TokenResponse(access_token=token, expires_in=expires_in, role=user.role.code)


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
    await write_audit_event(
        db,
        user=user,
        action="login_2fa_success",
        entity_type="authentication",
        entity_id=user.id,
        request=request,
    )
    await db.commit()
    return TokenResponse(access_token=token, expires_in=expires_in, role=user.role.code)


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
