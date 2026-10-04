"""API REST de administración de usuarios y roles.

Es el mismo dominio que administra el portal clínico, expuesto con los verbos
GET, PUT y DELETE para cualquier cliente HTTP autorizado. Cada operación exige
el permiso correspondiente y queda registrada en la bitácora.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User
from app.schemas.admin import (
    AdminRoleResponse,
    AdminUserResponse,
    RoleUpdateRequest,
    UserRoleUpdateRequest,
)
from app.services.audit import write_audit_event
from app.services.permissions import BASE_ROLES

router = APIRouter(prefix="/admin", tags=["Administración"])

_BASE_CODES = {code for code, _, _ in BASE_ROLES}


def _user_response(user: User) -> AdminUserResponse:
    return AdminUserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role_code=user.role.code,
        role_name=user.role.name,
        is_active=user.is_active,
    )


def _role_response(role: Role, users: int) -> AdminRoleResponse:
    return AdminRoleResponse(
        id=role.id,
        code=role.code,
        name=role.name,
        description=role.description,
        is_system=role.is_system or role.code in _BASE_CODES,
        permissions=sorted(permission.code for permission in role.permissions),
        users=users,
    )


@router.get("/users", response_model=list[AdminUserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("users:manage")),
) -> list[AdminUserResponse]:
    """Lista las cuentas con su rol y estado."""
    users = (await db.scalars(select(User).order_by(User.id))).all()
    return [_user_response(user) for user in users]


@router.put("/users/{user_id}/role", response_model=AdminUserResponse)
async def update_user_role(
    user_id: int,
    payload: UserRoleUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("users:manage")),
) -> AdminUserResponse:
    """Asigna un rol distinto a la cuenta indicada."""
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="La cuenta no existe.")

    role = await db.scalar(select(Role).where(Role.code == payload.role_code.strip().lower()))
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El rol indicado no existe.")

    if user.role_id == role.id:
        return _user_response(user)

    # Nunca dejar al sistema sin administradores activos.
    if user.role.code == "admin" and role.code != "admin":
        active_admins = await db.scalar(
            select(func.count(User.id)).where(User.role_id == user.role_id, User.is_active.is_(True))
        )
        if (active_admins or 0) <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No puedes quitar el rol administrador a la última cuenta activa.",
            )

    previous = user.role.code
    user.role_id = role.id
    await db.flush()
    await write_audit_event(
        db,
        user=current_user,
        action="admin_user_role_updated",
        entity_type="user",
        entity_id=user.id,
        request=request,
        detail=f"role={previous}->{role.code}",
    )
    await db.commit()
    await db.refresh(user)
    return _user_response(user)


@router.get("/roles", response_model=list[AdminRoleResponse])
async def list_roles(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("roles:manage")),
) -> list[AdminRoleResponse]:
    """Lista los roles con sus permisos y cuántas cuentas los usan."""
    roles = (await db.scalars(select(Role).order_by(Role.id))).all()
    counts = dict(
        (await db.execute(select(User.role_id, func.count(User.id)).group_by(User.role_id))).all()
    )
    return [_role_response(role, counts.get(role.id, 0)) for role in roles]


@router.put("/roles/{role_id}", response_model=AdminRoleResponse)
async def update_role(
    role_id: int,
    payload: RoleUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("roles:manage")),
) -> AdminRoleResponse:
    """Actualiza el nombre, la descripción y los permisos de un rol."""
    role = await db.get(Role, role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El rol no existe.")

    wanted = {code.strip().lower() for code in payload.permissions if code.strip()}
    permissions = (
        (await db.scalars(select(Permission).where(Permission.code.in_(wanted)))).all() if wanted else []
    )
    unknown = wanted - {permission.code for permission in permissions}
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Permisos desconocidos: {', '.join(sorted(unknown))}",
        )

    # Un rol de sistema no puede quedarse sin acceso al portal si ya lo tenía.
    if ("portal:access" in {p.code for p in role.permissions}) and "portal:access" not in wanted:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El rol debe conservar el permiso portal:access.",
        )

    role.name = payload.name.strip()
    role.description = (payload.description or "").strip() or None
    role.permissions = list(permissions)
    await db.flush()
    await write_audit_event(
        db,
        user=current_user,
        action="admin_role_updated",
        entity_type="role",
        entity_id=role.id,
        request=request,
        detail=f"code={role.code} permisos={len(permissions)}",
    )
    await db.commit()
    await db.refresh(role)
    count = await db.scalar(select(func.count(User.id)).where(User.role_id == role.id))
    return _role_response(role, count or 0)


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("roles:manage")),
) -> Response:
    """Elimina un rol personalizado que no tenga cuentas asignadas."""
    role = await db.get(Role, role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El rol no existe.")
    if role.is_system or role.code in _BASE_CODES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Los roles base del sistema no se eliminan; se editan sus permisos.",
        )

    in_use = await db.scalar(select(func.count(User.id)).where(User.role_id == role.id))
    if (in_use or 0) > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El rol tiene cuentas asignadas. Reasígnalas antes de eliminarlo.",
        )

    role_code = role.code
    await db.delete(role)
    await write_audit_event(
        db,
        user=current_user,
        action="admin_role_deleted",
        entity_type="role",
        entity_id=role_id,
        request=request,
        detail=f"code={role_code}",
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
