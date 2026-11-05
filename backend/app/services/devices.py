"""Dispositivos de confianza y transferencia de sesión entre dispositivos.

El servidor es solo un enrutador: nunca genera, compara ni registra el código
de 6 dígitos. El dispositivo activo (A) lo genera localmente, lo compara con
tiempo constante y aprueba con un token criptográfico. Aquí se concentran el
registro de dispositivos, las propuestas de código y la resolución de la
transferencia, siempre dentro de una transacción.

El token de aprobación se deriva con HMAC-SHA256 del identificador de la
transferencia y un secreto del servidor, de modo que la base guarda únicamente
su hash y el servidor puede entregarlo otra vez solo al dispositivo activo
autenticado (nunca al dispositivo nuevo ni por FCM).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token
from app.models.device_transfer import DeviceTransfer
from app.models.enums import DeviceTransferStatus
from app.models.session_token import RefreshToken
from app.models.user import User
from app.models.user_device import UserDevice
from app.services.permissions import permission_codes

logger = logging.getLogger(__name__)

_ACTIVE_STATUSES = (DeviceTransferStatus.PENDING, DeviceTransferStatus.CODE_SUBMITTED)
_REFRESH_BYTES = 48


class DeviceTransferError(Exception):
    """Error de negocio que la ruta traduce a una respuesta HTTP."""

    def __init__(self, message: str, status_code: int = 409):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _now() -> datetime:
    return datetime.now(timezone.utc)


def hash_device_id(device_id: str) -> str:
    """Hash SHA-256 del identificador aleatorio que genera la app."""
    return hashlib.sha256(device_id.strip().encode("utf-8")).hexdigest()


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def normalize_name(name: str | None) -> str:
    clean = " ".join((name or "").split())
    return clean[:120] or "Dispositivo desconocido"


def derive_approval_token(transfer_id: str, user_id: int, new_device_hash: str | None) -> str:
    """Token que solo el servidor puede reconstruir para entregarlo a A."""
    message = f"{transfer_id}:{user_id}:{new_device_hash or ''}".encode("utf-8")
    digest = hmac.new(settings.jwt_secret_key.encode("utf-8"), message, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def verify_approval_token(transfer: DeviceTransfer, token: str) -> bool:
    return hmac.compare_digest(transfer.approval_token_hash, hash_token(token))


def matches_device(device: UserDevice | None, device_id: str | None) -> bool:
    if device is None or not device_id:
        return False
    return hmac.compare_digest(device.device_hash, hash_device_id(device_id))


# ── Dispositivos ──────────────────────────────────────────────────────────────


async def active_device(db: AsyncSession, user_id: int) -> UserDevice | None:
    return await db.scalar(
        select(UserDevice)
        .where(UserDevice.user_id == user_id, UserDevice.is_active.is_(True))
        .limit(1)
    )


async def find_device(db: AsyncSession, user_id: int, device_id: str) -> UserDevice | None:
    return await db.scalar(
        select(UserDevice).where(
            UserDevice.user_id == user_id,
            UserDevice.device_hash == hash_device_id(device_id),
        )
    )


async def register_or_touch(
    db: AsyncSession,
    user: User,
    *,
    device_id: str,
    name: str | None,
    fcm_token: str | None = None,
    activate: bool = True,
) -> UserDevice:
    """Registra o actualiza el dispositivo; si se activa, desactiva los demás."""
    device_hash = hash_device_id(device_id)
    if activate:
        await db.execute(
            update(UserDevice)
            .where(
                UserDevice.user_id == user.id,
                UserDevice.is_active.is_(True),
                UserDevice.device_hash != device_hash,
            )
            .values(is_active=False)
        )

    device = await db.scalar(
        select(UserDevice)
        .where(UserDevice.user_id == user.id, UserDevice.device_hash == device_hash)
        .with_for_update()
    )
    if device is None:
        device = UserDevice(
            user_id=user.id,
            device_hash=device_hash,
            name=normalize_name(name),
            is_active=activate,
            last_seen_at=_now(),
        )
        db.add(device)
    else:
        if name:
            device.name = normalize_name(name)
        device.last_seen_at = _now()
        if activate:
            device.is_active = True
    if fcm_token is not None:
        device.fcm_token = fcm_token.strip()[:255] or None
    await db.flush()
    return device


async def activate_device_hash(
    db: AsyncSession, user: User, device_hash: str | None, name: str | None
) -> UserDevice | None:
    """Activa un dispositivo a partir de su hash (login ya validado)."""
    if not device_hash:
        await db.execute(
            update(UserDevice)
            .where(UserDevice.user_id == user.id, UserDevice.is_active.is_(True))
            .values(is_active=False)
        )
        await db.flush()
        return None

    await db.execute(
        update(UserDevice)
        .where(
            UserDevice.user_id == user.id,
            UserDevice.is_active.is_(True),
            UserDevice.device_hash != device_hash,
        )
        .values(is_active=False)
    )
    device = await db.scalar(
        select(UserDevice)
        .where(UserDevice.user_id == user.id, UserDevice.device_hash == device_hash)
        .with_for_update()
    )
    if device is None:
        device = UserDevice(
            user_id=user.id,
            device_hash=device_hash,
            name=normalize_name(name),
            is_active=True,
            last_seen_at=_now(),
        )
        db.add(device)
    else:
        device.is_active = True
        device.last_seen_at = _now()
        if name:
            device.name = normalize_name(name)
    await db.flush()
    return device


async def find_device_by_id(db: AsyncSession, device_id: int) -> UserDevice | None:
    return await db.get(UserDevice, device_id)


async def clear_fcm_token(db: AsyncSession, device: UserDevice) -> None:
    device.fcm_token = None
    await db.flush()


async def release_device(db: AsyncSession, user: User) -> bool:
    """Libera el dispositivo de confianza y revoca las sesiones ligadas a él."""
    released = await db.scalar(
        select(func.count(UserDevice.id)).where(
            UserDevice.user_id == user.id, UserDevice.is_active.is_(True)
        )
    )
    await db.execute(
        update(UserDevice)
        .where(UserDevice.user_id == user.id, UserDevice.is_active.is_(True))
        .values(is_active=False)
    )
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )
    await db.flush()
    return bool(released)


async def release_device_by_id(db: AsyncSession, device_id: int) -> bool:
    device = await db.get(UserDevice, device_id)
    if device is None or not device.is_active:
        return False
    device.is_active = False
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.device_id == device_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )
    await db.flush()
    return True


# ── Transferencias ────────────────────────────────────────────────────────────


async def _lock_transfer(db: AsyncSession, transfer_id: str) -> DeviceTransfer | None:
    # populate_existing fuerza a leer la fila bloqueada, no la copia en caché de
    # la sesión: evita que dos sondeos simultáneos emitan tokens dos veces.
    return await db.scalar(
        select(DeviceTransfer)
        .where(DeviceTransfer.id == transfer_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


async def expire_if_needed(db: AsyncSession, transfer: DeviceTransfer) -> bool:
    """Expiración perezosa: sin tareas en segundo plano."""
    if transfer.status in _ACTIVE_STATUSES and transfer.expires_at <= _now():
        transfer.status = DeviceTransferStatus.EXPIRED
        transfer.resolved_at = _now()
        transfer.submitted_code = None
        await db.flush()
        return True
    return False


def seconds_left(transfer: DeviceTransfer) -> int:
    remaining = (transfer.expires_at - _now()).total_seconds()
    return max(0, int(remaining))


async def pending_transfer(db: AsyncSession, user_id: int) -> DeviceTransfer | None:
    transfer = await db.scalar(
        select(DeviceTransfer)
        .where(
            DeviceTransfer.user_id == user_id,
            DeviceTransfer.status.in_(_ACTIVE_STATUSES),
        )
        .order_by(DeviceTransfer.created_at.desc())
        .limit(1)
    )
    if transfer is not None and await expire_if_needed(db, transfer):
        return None
    return transfer


async def create_transfer(
    db: AsyncSession,
    user: User,
    *,
    device_id: str | None,
    device_name: str | None,
) -> tuple[DeviceTransfer, str]:
    """Crea la solicitud. Una nueva sustituye a la pendiente anterior."""
    since = _now() - timedelta(hours=1)
    recent = await db.scalar(
        select(func.count(DeviceTransfer.id)).where(
            DeviceTransfer.user_id == user.id, DeviceTransfer.created_at >= since
        )
    )
    if int(recent or 0) >= settings.device_transfer_max_per_hour:
        raise DeviceTransferError(
            "Demasiadas solicitudes de transferencia. Espera una hora e intenta de nuevo.",
            status_code=429,
        )

    await db.execute(
        update(DeviceTransfer)
        .where(
            DeviceTransfer.user_id == user.id,
            DeviceTransfer.status.in_(_ACTIVE_STATUSES),
        )
        .values(
            status=DeviceTransferStatus.EXPIRED,
            resolved_at=_now(),
            submitted_code=None,
        )
    )

    transfer_id = str(uuid4())
    new_hash = hash_device_id(device_id) if device_id else None
    approval_token = derive_approval_token(transfer_id, user.id, new_hash)
    transfer = DeviceTransfer(
        id=transfer_id,
        user_id=user.id,
        new_device_hash=new_hash,
        new_device_name=normalize_name(device_name),
        status=DeviceTransferStatus.PENDING,
        approval_token_hash=hash_token(approval_token),
        code_submissions=0,
        created_at=_now(),
        expires_at=_now() + timedelta(seconds=settings.device_transfer_ttl_seconds),
    )
    db.add(transfer)
    await db.flush()
    return transfer, approval_token


async def get_transfer(db: AsyncSession, transfer_id: str) -> DeviceTransfer | None:
    return await db.get(DeviceTransfer, transfer_id)


async def submit_code(
    db: AsyncSession, transfer: DeviceTransfer, code: str
) -> tuple[int, bool]:
    """Guarda la propuesta de B. Devuelve (restantes, acaba de expirar)."""
    locked = await _lock_transfer(db, transfer.id)
    if locked is None:
        raise DeviceTransferError("La solicitud ya no está disponible.")
    transfer = locked
    if await expire_if_needed(db, transfer):
        return 0, True
    if transfer.status == DeviceTransferStatus.FAILED:
        raise DeviceTransferError(
            "Se agotaron los intentos de esta solicitud. Inicia sesión otra vez."
        )
    if transfer.status not in _ACTIVE_STATUSES:
        raise DeviceTransferError("La solicitud ya no está disponible.")
    if transfer.submitted_code is not None:
        raise DeviceTransferError(
            "Ya hay un código esperando aprobación en tu otro dispositivo. "
            "Espera a que lo revises."
        )
    if transfer.code_submissions >= settings.device_transfer_max_code_submissions:
        transfer.status = DeviceTransferStatus.FAILED
        transfer.resolved_at = _now()
        await db.flush()
        raise DeviceTransferError("Se agotaron los intentos de esta solicitud.")

    transfer.submitted_code = code
    transfer.code_submissions += 1
    transfer.status = DeviceTransferStatus.CODE_SUBMITTED
    await db.flush()
    remaining = max(0, settings.device_transfer_max_code_submissions - transfer.code_submissions)
    return remaining, False


async def approve_transfer(
    db: AsyncSession,
    user: User,
    device: UserDevice,
    *,
    transfer_id: str,
    approval_token: str,
) -> DeviceTransfer:
    transfer = await _lock_transfer(db, transfer_id)
    if transfer is None or transfer.user_id != user.id:
        raise DeviceTransferError("No encontramos esa solicitud.", status_code=404)
    if await expire_if_needed(db, transfer):
        raise DeviceTransferError("La solicitud expiró. Inicia sesión otra vez.")
    if transfer.status not in _ACTIVE_STATUSES:
        raise DeviceTransferError("La solicitud ya no está disponible.")
    if not device.is_active:
        raise DeviceTransferError("Este dispositivo ya no es el activo.", status_code=403)
    if not verify_approval_token(transfer, approval_token):
        raise DeviceTransferError("El token de aprobación no es válido.", status_code=403)

    transfer.status = DeviceTransferStatus.APPROVED
    transfer.resolved_at = _now()
    transfer.submitted_code = None

    # B pasa a ser el único dispositivo activo; A queda fuera de inmediato
    # porque su claim ``did`` deja de coincidir con el dispositivo activo.
    await db.execute(
        update(UserDevice)
        .where(UserDevice.user_id == user.id, UserDevice.is_active.is_(True))
        .values(is_active=False)
    )
    if transfer.new_device_hash:
        new_device = await db.scalar(
            select(UserDevice)
            .where(
                UserDevice.user_id == user.id,
                UserDevice.device_hash == transfer.new_device_hash,
            )
            .with_for_update()
        )
        if new_device is None:
            new_device = UserDevice(
                user_id=user.id,
                device_hash=transfer.new_device_hash,
                name=transfer.new_device_name,
                is_active=True,
                last_seen_at=_now(),
            )
            db.add(new_device)
        else:
            new_device.is_active = True
            new_device.name = transfer.new_device_name
            new_device.last_seen_at = _now()

    # Todas las sesiones renovables de A quedan revocadas.
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )
    await db.flush()
    return transfer


async def reject_transfer(
    db: AsyncSession, transfer_id: str, reason: str
) -> DeviceTransfer:
    transfer = await _lock_transfer(db, transfer_id)
    if transfer is None:
        raise DeviceTransferError("No encontramos esa solicitud.", status_code=404)

    if reason == "expired":
        if transfer.status in _ACTIVE_STATUSES:
            transfer.status = DeviceTransferStatus.EXPIRED
            transfer.resolved_at = _now()
            transfer.submitted_code = None
            await db.flush()
        return transfer

    if await expire_if_needed(db, transfer):
        return transfer
    if transfer.status not in _ACTIVE_STATUSES:
        raise DeviceTransferError("La solicitud ya no está disponible.")

    if reason == "not_me":
        transfer.status = DeviceTransferStatus.REJECTED
        transfer.resolved_at = _now()
        transfer.submitted_code = None
    elif reason == "mismatch":
        transfer.submitted_code = None
        if transfer.code_submissions >= settings.device_transfer_max_code_submissions:
            transfer.status = DeviceTransferStatus.FAILED
            transfer.resolved_at = _now()
        else:
            transfer.status = DeviceTransferStatus.PENDING
    else:
        raise DeviceTransferError("Motivo de rechazo no válido.", status_code=422)
    await db.flush()
    return transfer


async def cancel_transfer(db: AsyncSession, transfer: DeviceTransfer) -> None:
    """El dispositivo nuevo desiste; la solicitud termina sin aprobación."""
    if await expire_if_needed(db, transfer):
        return
    if transfer.status in _ACTIVE_STATUSES:
        transfer.status = DeviceTransferStatus.REJECTED
        transfer.resolved_at = _now()
        transfer.submitted_code = None
        await db.flush()


async def reject_pending_for_fallback(db: AsyncSession, transfer: DeviceTransfer) -> None:
    if transfer.status in _ACTIVE_STATUSES:
        transfer.status = DeviceTransferStatus.REJECTED
        transfer.resolved_at = _now()
        transfer.submitted_code = None
        await db.flush()


async def issue_tokens_for_approved(
    db: AsyncSession, transfer: DeviceTransfer, user: User
) -> tuple[str, str, int] | None:
    """Entrega los tokens a B una sola vez (``consumed_at``)."""
    locked = await _lock_transfer(db, transfer.id)
    if locked is None or locked.status != DeviceTransferStatus.APPROVED or locked.consumed_at is not None:
        return None
    transfer = locked

    device = None
    if transfer.new_device_hash:
        device = await db.scalar(
            select(UserDevice).where(
                UserDevice.user_id == user.id,
                UserDevice.device_hash == transfer.new_device_hash,
                UserDevice.is_active.is_(True),
            )
        )
    device_hash = device.device_hash if device else None
    access, expires_in = create_access_token(
        user.id,
        user.role.code,
        sorted(permission_codes(user)),
        device_hash=device_hash,
    )
    refresh = secrets.token_urlsafe(_REFRESH_BYTES)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(refresh),
            expires_at=_now() + timedelta(days=settings.refresh_token_expire_days),
            device_id=device.id if device else None,
        )
    )
    transfer.consumed_at = _now()
    if device is not None:
        device.last_seen_at = _now()
    await db.flush()
    return access, refresh, expires_in
