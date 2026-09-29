from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import ACCESS_PURPOSE, decode_token
from app.db.session import get_db
from app.models.user import User
from app.services.permissions import has_any_permission


bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticación requerida",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # Solo se aceptan tokens de acceso: un token de desafío 2FA no sirve aquí.
        payload = decode_token(credentials.credentials, purpose=ACCESS_PURPOSE)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no disponible")
    return user


def require_roles(*allowed_roles: str) -> Callable[..., User]:
    """Dependencia por rol: la autorización siempre ocurre en el servidor."""

    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role.code not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para esta operación",
            )
        return current_user

    return role_checker


def require_permission(*codes: str) -> Callable[..., User]:
    """Dependencia por permiso: basta con tener uno de los indicados."""

    async def permission_checker(current_user: User = Depends(get_current_user)) -> User:
        if not has_any_permission(current_user, *codes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para esta operación",
            )
        return current_user

    return permission_checker
