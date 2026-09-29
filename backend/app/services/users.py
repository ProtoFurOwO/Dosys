"""Cuentas de pacientes y personal del hospital.

Reglas compartidas: la contraseña siempre se guarda con Argon2 y la política
mínima se valida aquí para que la cumpla cualquier formulario.
"""

import secrets
import re
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.role import Role
from app.models.user import User

PASSWORD_MIN_LENGTH = 8
# Sin caracteres confundibles al dictar o escribir a mano.
_DIGITS = "23456789"
_UPPER = "ABCDEFGHJKLMNPQRSTUVWXYZ"
_LOWER = "abcdefghijkmnpqrstuvwxyz"

CURP_PATTERN = re.compile(r"^[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d$")
USERNAME_PATTERN = re.compile(r"^[a-z0-9._-]{3,64}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AccountError(ValueError):
    """Error de negocio mostrable al usuario del portal."""


def password_policy_error(password: str, confirm: str) -> str | None:
    if len(password) < PASSWORD_MIN_LENGTH:
        return f"La contraseña debe tener al menos {PASSWORD_MIN_LENGTH} caracteres."
    if not any(char.isalpha() for char in password) or not any(char.isdigit() for char in password):
        return "La contraseña debe incluir letras y números."
    if password != confirm:
        return "Las dos contraseñas no coinciden."
    return None


def generate_temp_password() -> str:
    """Contraseña temporal legible que ya cumple la política (letra y número)."""
    chars = (
        [secrets.choice(_DIGITS) for _ in range(2)]
        + [secrets.choice(_UPPER) for _ in range(4)]
        + [secrets.choice(_LOWER) for _ in range(4)]
    )
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


async def _ensure_username_free(db: AsyncSession, username: str) -> None:
    existing = await db.scalar(select(User).where(User.username == username))
    if existing is not None:
        raise AccountError("Ese usuario ya está en uso. Elige otro.")


async def _role_id(db: AsyncSession, code: str) -> int:
    role = await db.scalar(select(Role).where(Role.code == code))
    if role is None:
        raise AccountError("Falta configurar el rol base en el sistema.")
    return role.id


async def create_patient_account(
    db: AsyncSession,
    *,
    full_name: str,
    curp: str,
    birth_date: date | None,
    blood_type: str | None,
    emergency_contact: str | None,
    email: str | None,
    username: str,
    password: str,
) -> tuple[User, Patient]:
    await _ensure_username_free(db, username)
    duplicated = await db.scalar(select(Patient).where(Patient.curp == curp))
    if duplicated is not None:
        raise AccountError("Ya existe un paciente con esa CURP.")

    user = User(
        username=username,
        password_hash=hash_password(password),
        role_id=await _role_id(db, "patient"),
    )
    db.add(user)
    await db.flush()

    patient = Patient(
        user_id=user.id,
        full_name=full_name,
        curp=curp,
        blood_type=blood_type or None,
        birth_date=birth_date,
        emergency_contact=emergency_contact or None,
        email=email or None,
    )
    db.add(patient)
    await db.flush()
    return user, patient


async def create_doctor_account(
    db: AsyncSession,
    *,
    full_name: str,
    specialty: str,
    username: str,
    password: str,
) -> tuple[User, Doctor]:
    await _ensure_username_free(db, username)

    user = User(
        username=username,
        password_hash=hash_password(password),
        role_id=await _role_id(db, "doctor"),
    )
    db.add(user)
    await db.flush()

    doctor = Doctor(user_id=user.id, full_name=full_name, specialty=specialty)
    db.add(doctor)
    await db.flush()
    return user, doctor


async def set_user_active(db: AsyncSession, user: User, active: bool) -> None:
    user.is_active = active
    await db.flush()


async def reset_user_password(db: AsyncSession, user: User) -> str:
    new_password = generate_temp_password()
    user.password_hash = hash_password(new_password)
    await db.flush()
    return new_password


def account_created_detail(username: str, role_code: str) -> str:
    return f"username={username} role={role_code} at={datetime.now(timezone.utc).isoformat(timespec='seconds')}"
