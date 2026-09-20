from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.user import User


def client_ip(request: Request) -> str | None:
    """No se confía en X-Forwarded-For hasta configurar proxies confiables en VPS."""
    return request.client.host if request.client else None


async def write_audit_event(
    db: AsyncSession,
    *,
    user: User | None,
    action: str,
    entity_type: str,
    entity_id: int | str | None,
    request: Request,
    detail: str | None = None,
) -> None:
    """Registra quién accedió a qué entidad, sin almacenar datos clínicos."""
    db.add(
        AuditLog(
            user_id=user.id if user else None,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            ip_address=client_ip(request),
            detail=detail,
        )
    )
    await db.flush()
