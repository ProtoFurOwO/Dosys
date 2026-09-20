from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse
from app.services.audit import write_audit_event


router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Autentica a un usuario y devuelve un JWT breve.

    El mensaje es deliberadamente genérico para no revelar si un usuario existe.
    """
    user = await db.scalar(select(User).where(User.username == payload.username.strip().lower()))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
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

    token, expires_in = create_access_token(user.id, user.role)
    await write_audit_event(
        db,
        user=user,
        action="login_success",
        entity_type="authentication",
        entity_id=user.id,
        request=request,
    )
    await db.commit()
    return TokenResponse(access_token=token, expires_in=expires_in, role=user.role)
