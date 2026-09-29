"""Bloqueo de cuentas por intentos fallidos (compartido entre API y portal)."""

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User


def now() -> datetime:
    return datetime.now(timezone.utc)


def is_locked(user: User) -> bool:
    """La cuenta está bloqueada mientras locked_until siga en el futuro."""
    return user.locked_until is not None and user.locked_until > now()


def lock_minutes_left(user: User) -> int:
    if not is_locked(user):
        return 0
    remaining = user.locked_until - now()
    return max(1, int(remaining.total_seconds() // 60) + 1)


async def register_failed_attempt(db: AsyncSession, user: User) -> bool:
    """Suma un intento fallido; bloquea la cuenta al llegar al límite."""
    attempts = (user.failed_login_attempts or 0) + 1
    locked = attempts >= settings.login_max_attempts
    if locked:
        user.failed_login_attempts = 0
        user.locked_until = now() + timedelta(minutes=settings.login_lock_minutes)
    else:
        user.failed_login_attempts = attempts
    await db.flush()
    return locked


async def reset_failed_attempts(db: AsyncSession, user: User) -> None:
    user.failed_login_attempts = 0
    user.locked_until = None
    await db.flush()
