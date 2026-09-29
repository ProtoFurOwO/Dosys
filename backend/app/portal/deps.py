"""Sesión del portal clínico y utilidades de presentación."""

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

import jwt
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import ACCESS_PURPOSE, decode_token
from app.models.enums import UserRole
from app.models.user import User

COOKIE_NAME = "dosys_portal"
CLINIC_TIMEZONE = ZoneInfo("America/Mexico_City")

MESES = (
    "ene",
    "feb",
    "mar",
    "abr",
    "may",
    "jun",
    "jul",
    "ago",
    "sep",
    "oct",
    "nov",
    "dic",
)


async def current_doctor(request: Request, db: AsyncSession) -> User | None:
    """Devuelve al médico autenticado o None; la cookie viaja solo en /portal."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        # Solo tokens de acceso: el token temporal del 2FA no abre el portal.
        payload = decode_token(token, purpose=ACCESS_PURPOSE)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        return None

    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None or not user.is_active or user.role is not UserRole.DOCTOR:
        return None
    return user


def clinic_now() -> datetime:
    return datetime.now(CLINIC_TIMEZONE)


def start_of_today_utc() -> datetime:
    """Medianoche del hospital convertida a UTC, para contar las consultas de hoy."""
    today = clinic_now().date()
    return datetime.combine(today, time.min, tzinfo=CLINIC_TIMEZONE).astimezone(timezone.utc)


def _local(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(CLINIC_TIMEZONE)


def format_datetime(value: datetime | None) -> str:
    if value is None:
        return "Sin registros"
    local = _local(value)
    return f"{local.day} {MESES[local.month - 1]} {local.year}, {local:%H:%M} h"


def format_date(value: datetime | None) -> str:
    if value is None:
        return "Sin registros"
    local = _local(value)
    return f"{local.day} {MESES[local.month - 1]} {local.year}"


def format_last_visit(value: datetime | None) -> str:
    if value is None:
        return "Sin consultas"
    local = _local(value)
    days = (clinic_now().date() - local.date()).days
    if days == 0:
        return "Hoy"
    if days == 1:
        return "Ayer"
    return format_date(value)


def format_time(value: datetime | None) -> str:
    if value is None:
        return "Sin registros"
    return f"{_local(value):%H:%M} h"
