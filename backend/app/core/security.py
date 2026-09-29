from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from pwdlib import PasswordHash

from app.core.config import settings


password_hash = PasswordHash.recommended()

ACCESS_PURPOSE = "access"
TWO_FACTOR_PURPOSE = "2fa"


def hash_password(password: str) -> str:
    """Genera un hash Argon2; las contraseñas nunca se guardan en texto plano."""
    return password_hash.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    return password_hash.verify(password, stored_hash)


def _encode(payload: dict[str, Any], expires_in: int) -> str:
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: int, role_code: str, permissions: list[str]) -> tuple[str, int]:
    """Crea un JWT breve con identidad, rol y permisos, sin información clínica."""
    expires_in = settings.jwt_access_token_expire_minutes * 60
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role_code,
        "permissions": permissions,
        "purpose": ACCESS_PURPOSE,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    return _encode(payload, expires_in), expires_in


def create_challenge_token(user_id: int) -> tuple[str, int]:
    """Token temporal (5 min) que solo sirve para completar el segundo factor."""
    expires_in = settings.two_factor_challenge_minutes * 60
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "purpose": TWO_FACTOR_PURPOSE,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    return _encode(payload, expires_in), expires_in


def decode_token(token: str, *, purpose: str) -> dict[str, Any]:
    """Decodifica y exige que el token sea del tipo esperado (access o 2fa)."""
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    if payload.get("purpose") != purpose:
        raise jwt.InvalidTokenError("Propósito del token inválido")
    return payload
