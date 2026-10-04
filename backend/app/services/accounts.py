"""Sesiones renovables y recuperación de contraseña.

Los tokens de renovación y de restablecimiento se generan con ``secrets`` y se
guardan únicamente como hash SHA-256: la base de datos nunca almacena el token
utilizable. Cada uso de un token de renovación lo rota (revoca el anterior).
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.models.patient import Patient
from app.models.session_token import PasswordResetToken, RefreshToken
from app.models.user import User
from app.services.users import AccountError, password_policy_error

_RESET_BYTES = 32
_REFRESH_BYTES = 48


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def reset_link(token: str) -> str:
    return f"{settings.public_base_url.rstrip('/')}/portal/restablecer?token={token}"


async def find_user_by_identifier(db: AsyncSession, identifier: str) -> User | None:
    """Permite iniciar sesión con el usuario o con el correo registrado."""
    value = identifier.strip().lower()
    if not value:
        return None
    user = await db.scalar(select(User).where(User.username == value))
    if user is not None:
        return user
    if "@" not in value:
        return None
    user = await db.scalar(select(User).where(func.lower(User.email) == value))
    if user is not None:
        return user
    # El correo de la ficha del paciente también sirve para entrar a la app.
    return await db.scalar(
        select(User).join(Patient, Patient.user_id == User.id).where(func.lower(Patient.email) == value)
    )


# ── Sesión renovable ──────────────────────────────────────────────────────────


async def issue_refresh_token(db: AsyncSession, user: User) -> str:
    token = secrets.token_urlsafe(_REFRESH_BYTES)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=_digest(token),
            expires_at=_now() + timedelta(days=settings.refresh_token_expire_days),
        )
    )
    await db.flush()
    return token


async def rotate_refresh_token(db: AsyncSession, token: str) -> tuple[User, str] | None:
    """Valida el token, lo revoca y entrega uno nuevo junto con su usuario."""
    if not token:
        return None
    record = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == _digest(token)))
    if record is None or record.revoked_at is not None or record.expires_at <= _now():
        return None
    user = await db.get(User, record.user_id)
    if user is None or not user.is_active:
        return None
    record.revoked_at = _now()
    new_token = await issue_refresh_token(db, user)
    await db.flush()
    return user, new_token


async def revoke_refresh_token(db: AsyncSession, token: str) -> None:
    if not token:
        return
    record = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == _digest(token)))
    if record is not None and record.revoked_at is None:
        record.revoked_at = _now()
        await db.flush()


async def revoke_user_sessions(db: AsyncSession, user: User) -> None:
    """Cierra todas las sesiones renovables de la cuenta (tras cambiar contraseña)."""
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


# ── Recuperación de contraseña ────────────────────────────────────────────────


async def create_password_reset(db: AsyncSession, user: User) -> str:
    """Genera un token de un solo uso e invalida los anteriores."""
    await db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=_now())
    )
    token = secrets.token_urlsafe(_RESET_BYTES)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=_digest(token),
            expires_at=_now() + timedelta(minutes=settings.password_reset_expire_minutes),
        )
    )
    await db.flush()
    return token


async def consume_password_reset(db: AsyncSession, token: str) -> User | None:
    if not token:
        return None
    record = await db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == _digest(token)))
    if record is None or record.used_at is not None or record.expires_at <= _now():
        return None
    user = await db.get(User, record.user_id)
    if user is None or not user.is_active:
        return None
    record.used_at = _now()
    await db.flush()
    return user


# ── Contraseña ────────────────────────────────────────────────────────────────


async def change_password(db: AsyncSession, user: User, *, current: str, new: str, confirm: str) -> None:
    """Cambio propio: exige la contraseña actual y cierra las demás sesiones."""
    if not verify_password(current, user.password_hash):
        raise AccountError("La contraseña actual no coincide.")
    error = password_policy_error(new, confirm)
    if error is not None:
        raise AccountError(error)
    user.password_hash = hash_password(new)
    await revoke_user_sessions(db, user)
    await db.flush()


async def replace_password(db: AsyncSession, user: User, *, new: str, confirm: str) -> None:
    """Restablecimiento con token: no pide la contraseña anterior."""
    error = password_policy_error(new, confirm)
    if error is not None:
        raise AccountError(error)
    user.password_hash = hash_password(new)
    await revoke_user_sessions(db, user)
    await db.flush()
