"""Segundo factor TOTP (RFC 6238) y códigos de recuperación."""

import secrets
from datetime import datetime, timezone

import pyotp
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.models.recovery_code import RecoveryCode
from app.models.user import User

RECOVERY_CODE_COUNT = 8
# Sin caracteres confundibles al transcribir a mano.
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(secret: str, username: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name=settings.totp_issuer)


def verify_code(secret: str, code: str) -> bool:
    """Acepta el código de 6 dígitos con una ventana de ±30 segundos."""
    clean = "".join(char for char in code if char.isalnum())
    if len(clean) != 6 or not clean.isdigit():
        return False
    return pyotp.TOTP(secret).verify(clean, valid_window=1)


def generate_recovery_codes(count: int = RECOVERY_CODE_COUNT) -> list[str]:
    codes = []
    for _ in range(count):
        raw = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))
        codes.append(f"{raw[:4]}-{raw[4:]}")
    return codes


async def store_recovery_codes(db: AsyncSession, user: User, codes: list[str]) -> None:
    """Reemplaza los códigos anteriores por los nuevos (también al regenerar)."""
    for existing in (await db.scalars(select(RecoveryCode).where(RecoveryCode.user_id == user.id))).all():
        await db.delete(existing)
    for code in codes:
        db.add(RecoveryCode(user_id=user.id, code_hash=hash_password(code)))
    await db.flush()


async def consume_recovery_code(db: AsyncSession, user: User, code: str) -> bool:
    clean = "".join(char for char in code.strip().upper() if char.isalnum())
    if len(clean) == 8:
        clean = f"{clean[:4]}-{clean[4:]}"
    rows = (
        await db.scalars(
            select(RecoveryCode).where(RecoveryCode.user_id == user.id, RecoveryCode.used_at.is_(None))
        )
    ).all()
    for row in rows:
        if verify_password(clean, row.code_hash):
            row.used_at = datetime.now(timezone.utc)
            await db.flush()
            return True
    return False


async def recovery_codes_remaining(db: AsyncSession, user: User) -> int:
    total = await db.scalar(
        select(func.count(RecoveryCode.id)).where(
            RecoveryCode.user_id == user.id,
            RecoveryCode.used_at.is_(None),
        )
    )
    return int(total or 0)


async def clear_two_factor(db: AsyncSession, user: User) -> None:
    """Apaga el 2FA y borra secreto y códigos de recuperación."""
    user.totp_enabled = False
    user.totp_secret = None
    user.totp_confirmed_at = None
    for existing in (await db.scalars(select(RecoveryCode).where(RecoveryCode.user_id == user.id))).all():
        await db.delete(existing)
    await db.flush()
