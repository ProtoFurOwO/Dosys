from datetime import datetime, timezone

import hmac

import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.security import (
    DEVICE_TRANSFER_PURPOSE,
    TWO_FACTOR_PURPOSE,
    create_access_token,
    create_challenge_token,
    create_device_transfer_token,
    decode_token,
    verify_password,
)
from app.db.session import get_db
from app.models.device_transfer import DeviceTransfer
from app.models.enums import DeviceTransferStatus, UserRole
from app.models.user import User
from app.schemas.auth import (
    DeviceTransferChallengeResponse,
    DeviceTransferCodeRequest,
    DeviceTransferCodeResponse,
    DeviceTransferStatusRequest,
    DeviceTransferStatusResponse,
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
from app.services import accounts, devices, email, login_security, push, rate_limit, two_factor
from app.services.audit import write_audit_event
from app.services.permissions import permission_codes
from app.services.users import AccountError, password_policy_error

router = APIRouter(prefix="/auth", tags=["Autenticación"])

_TRANSFER_EXPIRED_MESSAGE = "La solicitud de transferencia expiró. Inicia sesión otra vez."


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


async def _transfer_from_challenge(
    db: AsyncSession, transfer_id: str, challenge_token: str
) -> tuple[DeviceTransfer, int]:
    """Autentica al dispositivo nuevo con su token de desafío (nunca con JWT)."""
    try:
        decoded = decode_token(challenge_token, purpose=DEVICE_TRANSFER_PURPOSE)
        user_id = int(decoded["sub"])
    except (pyjwt.PyJWTError, KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=_TRANSFER_EXPIRED_MESSAGE
        ) from None

    if decoded.get("transfer") != transfer_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=_TRANSFER_EXPIRED_MESSAGE
        )
    transfer = await devices.get_transfer(db, transfer_id)
    if transfer is None or transfer.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=_TRANSFER_EXPIRED_MESSAGE
        )
    return transfer, user_id


@router.post(
    "/login",
    response_model=TokenResponse | TwoFactorChallengeResponse | DeviceTransferChallengeResponse,
)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    _no_store(response)
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
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Cuenta bloqueada temporalmente por intentos fallidos. "
                f"Intenta de nuevo en {login_security.lock_minutes_left(user)} minutos."
            ),
            headers={"Retry-After": str(login_security.lock_minutes_left(user) * 60)},
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

    # ── Dispositivo de confianza (solo pacientes) ─────────────────────────────
    # Un dispositivo activo distinto exige transferencia de sesión. Para
    # pacientes, ``device_id`` es obligatorio: sin él no se emite ningún token.
    device = None
    if user.role.code == UserRole.PATIENT.value:
        if not payload.device_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Actualiza la app e inicia sesión de nuevo: este dispositivo "
                    "no tiene identificador de confianza."
                ),
            )
        active = await devices.active_device(db, user.id)
        if active is not None and not devices.matches_device(active, payload.device_id):
            if rate_limit.exceeded("api-device-transfer", request):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Demasiadas solicitudes de transferencia. Espera un minuto.",
                    headers={"Retry-After": "60"},
                )
            try:
                transfer, _ = await devices.create_transfer(
                    db,
                    user,
                    device_id=payload.device_id,
                    device_name=payload.device_name,
                )
            except devices.DeviceTransferError as error:
                raise HTTPException(
                    status_code=error.status_code, detail=error.message
                ) from None
            challenge_token, expires_in = create_device_transfer_token(
                transfer.id, user.id, transfer.new_device_hash
            )
            await write_audit_event(
                db,
                user=user,
                action="device_transfer_requested",
                entity_type="device_transfer",
                entity_id=transfer.id,
                request=request,
                detail=f"dispositivo={transfer.new_device_name}",
            )
            sent, reason = await push.notify_device_transfer(active.fcm_token, transfer.id)
            if not sent and reason == "token inválido" and active.fcm_token:
                await devices.clear_fcm_token(db, active)
            await db.commit()
            return DeviceTransferChallengeResponse(
                transfer_id=transfer.id,
                challenge_token=challenge_token,
                expires_in=expires_in,
            )

        # Si hay 2FA, el dispositivo se registra/activa después de verificar el
        # segundo factor. Así una contraseña sola no puede ocupar el slot activo.
        if not (user.totp_enabled and user.totp_secret):
            device = await devices.register_or_touch(
                db,
                user,
                device_id=payload.device_id,
                name=payload.device_name,
                activate=True,
            )
            if active is None:
                await write_audit_event(
                    db,
                    user=user,
                    action="device_registered",
                    entity_type="device",
                    entity_id=device.id,
                    request=request,
                    detail=f"nombre={device.name}",
                )

    if user.totp_enabled and user.totp_secret:
        extra_claims: dict[str, object] = {}
        if user.role.code == UserRole.PATIENT.value and payload.device_id:
            # El hash del dispositivo viaja en el challenge; se activa al
            # verificar el 2FA, nunca antes.
            extra_claims["did"] = (
                device.device_hash
                if device is not None
                else devices.hash_device_id(payload.device_id)
            )
            extra_claims["device_name"] = (
                device.name
                if device is not None
                else devices.normalize_name(payload.device_name)
            )
            extra_claims["epoch"] = user.device_epoch or 0
        challenge, _ = create_challenge_token(user.id, extra_claims or None)
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

    device_hash = device.device_hash if device else None
    token, expires_in = create_access_token(
        user.id, user.role.code, sorted(permission_codes(user)), device_hash=device_hash
    )
    refresh_token = await accounts.issue_refresh_token(
        db, user, device_id=device.id if device else None
    )
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
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    _no_store(response)
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

    # Un challenge emitido antes de transferir/liberar el dispositivo no puede
    # reactivarlo: el epoch cambia con cada cambio de dispositivo de confianza.
    is_patient = user.role.code == UserRole.PATIENT.value
    device_hash = decoded.get("did")
    device_name = decoded.get("device_name")
    fallback_transfer_id = decoded.get("transfer")
    active = None
    if is_patient:
        if not device_hash:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Actualiza la app e inicia sesión de nuevo para vincular este dispositivo.",
            )
        epoch = decoded.get("epoch")
        if epoch is None or int(epoch) != (user.device_epoch or 0):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="La sesión cambió de dispositivo. Vuelve a iniciar sesión.",
            )
        active = await devices.active_device(db, user.id)
        if (
            not fallback_transfer_id
            and active is not None
            and not hmac.compare_digest(active.device_hash, str(device_hash))
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Esta sesión se transfirió a otro dispositivo. Inicia sesión de nuevo.",
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

    # El desafío puede conservar el dispositivo (login normal con 2FA) o la
    # transferencia (alternativa "no tengo mi dispositivo anterior").
    device = None
    if is_patient:
        if fallback_transfer_id:
            transfer = await devices.get_transfer(db, str(fallback_transfer_id))
            if transfer is None or transfer.user_id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="La solicitud de transferencia ya no está disponible.",
                )
            await devices.reject_pending_for_fallback(db, transfer)
            await accounts.revoke_user_sessions(db, user)
            await write_audit_event(
                db,
                user=user,
                action="device_transfer_fallback",
                entity_type="device_transfer",
                entity_id=transfer.id,
                request=request,
                detail="2fa=correcto",
            )
            device = await devices.activate_device_hash(
                db,
                user,
                str(device_hash),
                device_name if isinstance(device_name, str) else None,
            )
        elif active is not None:
            # El dispositivo sigue siendo el activo: no se reactiva nada.
            device = active
        else:
            # Primer login con 2FA: recién aquí se activa el dispositivo.
            device = await devices.activate_device_hash(
                db,
                user,
                str(device_hash),
                device_name if isinstance(device_name, str) else None,
            )
            if device is not None:
                await write_audit_event(
                    db,
                    user=user,
                    action="device_registered",
                    entity_type="device",
                    entity_id=device.id,
                    request=request,
                    detail=f"nombre={device.name}",
                )
        if device is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No se pudo vincular este dispositivo. Inicia sesión de nuevo.",
            )

    token, expires_in = create_access_token(
        user.id,
        user.role.code,
        sorted(permission_codes(user)),
        device_hash=device.device_hash if device else None,
    )
    refresh_token = await accounts.issue_refresh_token(
        db, user, device_id=device.id if device else None
    )
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
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    _no_store(response)
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
    user, new_refresh, device_hash = rotated
    token, expires_in = create_access_token(
        user.id, user.role.code, sorted(permission_codes(user)), device_hash=device_hash
    )
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
    """Revoca el token de renovación y libera el dispositivo de esa sesión."""
    revoked = await accounts.revoke_refresh_token(db, payload.refresh_token)
    if revoked is not None:
        user_id, device_id = revoked
        if device_id is not None:
            device = await devices.find_device_by_id(db, device_id)
            released = await devices.release_device_by_id(db, device_id)
            if released:
                author = await db.get(User, user_id)
                await write_audit_event(
                    db,
                    user=author,
                    action="device_released",
                    entity_type="device",
                    entity_id=device_id,
                    request=request,
                    detail=f"nombre={device.name if device else 'dispositivo'}",
                )
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

    had_device = (
        user.role.code == UserRole.PATIENT.value
        and await devices.active_device(db, user.id) is not None
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
    if had_device:
        await write_audit_event(
            db,
            user=user,
            action="device_released",
            entity_type="device",
            entity_id=user.id,
            request=request,
            detail="motivo=restablecimiento_de_contrasena",
        )
    await db.commit()
    return {"detail": "Contraseña restablecida. Inicia sesión con la nueva."}


# ── Transferencia de sesión: dispositivo nuevo (B) ────────────────────────────
# Se autentican con el ``challenge_token`` (propósito device_transfer), nunca
# con un access token. El servidor no compara el código: solo lo enruta a A.


@router.post(
    "/device-transfer/{transfer_id}/code",
    response_model=DeviceTransferCodeResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_device_transfer_code(
    transfer_id: str,
    payload: DeviceTransferCodeRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> DeviceTransferCodeResponse:
    _no_store(response)
    """Deja la propuesta de código disponible para el dispositivo activo."""
    if rate_limit.exceeded("api-transfer-code", request):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas solicitudes. Espera un minuto.",
            headers={"Retry-After": "60"},
        )

    transfer, user_id = await _transfer_from_challenge(
        db, transfer_id, payload.challenge_token
    )
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=_TRANSFER_EXPIRED_MESSAGE
        )

    try:
        remaining, expired = await devices.submit_code(db, transfer, payload.code)
    except devices.DeviceTransferError as error:
        await db.commit()
        raise HTTPException(status_code=error.status_code, detail=error.message) from None

    if expired:
        await write_audit_event(
            db,
            user=user,
            action="device_transfer_expired",
            entity_type="device_transfer",
            entity_id=transfer.id,
            request=request,
            detail="servidor",
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=_TRANSFER_EXPIRED_MESSAGE
        )

    await write_audit_event(
        db,
        user=user,
        action="device_transfer_code_submitted",
        entity_type="device_transfer",
        entity_id=transfer.id,
        request=request,
        detail=f"propuesta={transfer.code_submissions}",
    )
    await db.commit()
    return DeviceTransferCodeResponse(submissions_left=remaining)


@router.post(
    "/device-transfer/{transfer_id}/status", response_model=DeviceTransferStatusResponse
)
async def device_transfer_status(
    transfer_id: str,
    payload: DeviceTransferStatusRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> DeviceTransferStatusResponse:
    _no_store(response)
    """Sondeo del dispositivo nuevo; entrega los tokens una sola vez."""
    # El sondeo es cada ~2 s: un límite propio más alto evita falsos 429.
    if rate_limit.exceeded("api-transfer-status", request, limit=180):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas solicitudes. Espera un momento.",
            headers={"Retry-After": "30"},
        )

    transfer, user_id = await _transfer_from_challenge(
        db, transfer_id, payload.challenge_token
    )
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=_TRANSFER_EXPIRED_MESSAGE
        )

    if await devices.expire_if_needed(db, transfer):
        await write_audit_event(
            db,
            user=user,
            action="device_transfer_expired",
            entity_type="device_transfer",
            entity_id=transfer.id,
            request=request,
            detail="servidor",
        )

    tokens = None
    if (
        transfer.status is DeviceTransferStatus.APPROVED
        and transfer.consumed_at is None
    ):
        issued = await devices.issue_tokens_for_approved(db, transfer, user)
        if issued is not None:
            access, refresh, expires_in = issued
            tokens = TokenResponse(
                access_token=access,
                refresh_token=refresh,
                expires_in=expires_in,
                role=user.role.code,
            )

    await db.commit()
    return DeviceTransferStatusResponse(
        status=transfer.status,
        expires_in=devices.seconds_left(transfer),
        submissions_left=max(
            0, settings.device_transfer_max_code_submissions - transfer.code_submissions
        ),
        tokens=tokens,
    )


@router.post("/device-transfer/{transfer_id}/cancel")
async def cancel_device_transfer(
    transfer_id: str,
    payload: DeviceTransferStatusRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    if rate_limit.exceeded("api-transfer-cancel", request):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas solicitudes. Espera un minuto.",
            headers={"Retry-After": "60"},
        )
    transfer, user_id = await _transfer_from_challenge(
        db, transfer_id, payload.challenge_token
    )
    await devices.cancel_transfer(db, transfer)
    user = await db.get(User, user_id)
    await write_audit_event(
        db,
        user=user,
        action="device_transfer_rejected",
        entity_type="device_transfer",
        entity_id=transfer.id,
        request=request,
        detail="motivo=cancelado_desde_dispositivo_nuevo",
    )
    await db.commit()
    return {"detail": "Solicitud cancelada."}


@router.post(
    "/device-transfer/{transfer_id}/fallback",
    response_model=TwoFactorChallengeResponse,
)
async def device_transfer_fallback(
    transfer_id: str,
    payload: DeviceTransferStatusRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TwoFactorChallengeResponse:
    _no_store(response)
    """Alternativa si el paciente ya no tiene el dispositivo anterior."""
    if rate_limit.exceeded("api-transfer-fallback", request):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas solicitudes. Espera un minuto.",
            headers={"Retry-After": "60"},
        )

    transfer, user_id = await _transfer_from_challenge(
        db, transfer_id, payload.challenge_token
    )
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=_TRANSFER_EXPIRED_MESSAGE
        )

    if await devices.expire_if_needed(db, transfer):
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=_TRANSFER_EXPIRED_MESSAGE
        )
    if transfer.status not in (
        DeviceTransferStatus.PENDING,
        DeviceTransferStatus.CODE_SUBMITTED,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La solicitud ya no está disponible.",
        )

    if user.totp_enabled and user.totp_secret:
        challenge, _ = create_challenge_token(
            user.id,
            {
                "transfer": transfer.id,
                "fallback": True,
                "did": transfer.new_device_hash,
                "device_name": transfer.new_device_name,
                "epoch": user.device_epoch or 0,
            },
        )
        await devices.reject_pending_for_fallback(db, transfer)
        await write_audit_event(
            db,
            user=user,
            action="device_transfer_fallback",
            entity_type="device_transfer",
            entity_id=transfer.id,
            request=request,
            detail="2fa=disponible",
        )
        await db.commit()
        return TwoFactorChallengeResponse(challenge_token=challenge)

    await write_audit_event(
        db,
        user=user,
        action="device_transfer_fallback",
        entity_type="device_transfer",
        entity_id=transfer.id,
        request=request,
        detail="2fa=no_disponible",
    )
    await db.commit()
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            "No tienes un segundo factor activo. Restablece tu contraseña desde el "
            "inicio de sesión para recuperar tu cuenta."
        ),
    )
