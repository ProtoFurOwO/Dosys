"""Administración del portal: personal del hospital, credenciales y bitácora."""

import re
import unicodedata

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User
from app.portal import deps
from app.portal.labels import ROLE_LABELS, action_label
from app.portal.routes import forbidden, portal_staff
from app.portal.templating import credential_context, templates
from app.services import login_security, two_factor
from app.services.audit import write_audit_event
from app.services.email import delivery_enabled, send_email
from app.services.permissions import has_permission
from app.services.users import (
    EMAIL_PATTERN,
    USERNAME_PATTERN,
    AccountError,
    create_staff_account,
    password_policy_error,
    reset_user_password,
    set_user_active,
)

router = APIRouter(prefix="/portal", tags=["Portal clínico"], include_in_schema=False)

STAFF_LOGIN_ACTIONS = ("portal_login_success", "login_success")


def normalize(text: str) -> str:
    """Búsqueda sin acentos ni mayúsculas ("medico" encuentra "Médico")."""
    lowered = unicodedata.normalize("NFKD", text.lower())
    return "".join(char for char in lowered if not unicodedata.combining(char))


def login_redirect() -> RedirectResponse:
    return RedirectResponse("/portal/login", status_code=status.HTTP_303_SEE_OTHER)


def users_redirect(aviso: str | None = None) -> RedirectResponse:
    target = "/portal/usuarios" if not aviso else f"/portal/usuarios?aviso={aviso}"
    return RedirectResponse(target, status_code=status.HTTP_303_SEE_OTHER)


async def require_staff(
    request: Request, db: AsyncSession
) -> tuple[User, Doctor | object] | None:
    user = await deps.current_doctor(request, db)
    if user is None:
        return None
    return user, await portal_staff(db, user)


def doctor_form_context(
    doctor_name: str,
    *,
    mode: str,
    user: User | None,
    values: dict,
    errors: dict,
    roles: list[Role] | None = None,
    is_doctor: bool = True,
) -> dict:
    return {
        "doctor_name": doctor_name,
        "active": "usuarios",
        "mode": mode,
        "user": user,
        "values": values,
        "errors": errors,
        "roles": roles or [],
        "is_doctor": is_doctor,
    }


# ── Personal del hospital ─────────────────────────────────────────────────────


@router.get("/usuarios", response_class=HTMLResponse)
async def users_page(request: Request, aviso: str = "", db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    session = await require_staff(request, db)
    if session is None:
        return login_redirect()
    current_user, doctor = session
    if not has_permission(current_user, "users:manage"):
        return forbidden(request, doctor.full_name, "Tu rol no puede gestionar usuarios.")

    rows = (
        await db.execute(
            select(User, Doctor, Patient)
            .outerjoin(Doctor, Doctor.user_id == User.id)
            .outerjoin(Patient, Patient.user_id == User.id)
            .order_by(User.username.asc())
        )
    ).all()
    last_access_rows = await db.execute(
        select(AuditLog.user_id, func.max(AuditLog.created_at))
        .where(AuditLog.action.in_(STAFF_LOGIN_ACTIONS))
        .group_by(AuditLog.user_id)
    )
    last_access = {user_id: moment for user_id, moment in last_access_rows.all()}
    roles = list((await db.scalars(select(Role).order_by(Role.code.asc()))).all())

    staff = [
        {
            "id": account.id,
            "username": account.username,
            "role_code": account.role.code,
            "role_label": account.role.name,
            "active": account.is_active,
            # El nombre viene de la ficha (médico o paciente) o de la propia cuenta.
            "full_name": account.full_name or (profile.full_name if profile else (patient.full_name if patient else account.username)),
            "specialty": profile.specialty if profile else ("Paciente" if patient else None),
            "last_access": last_access.get(account.id),
            "is_self": account.id == current_user.id,
            "totp_enabled": account.totp_enabled,
            "locked": login_security.is_locked(account),
            "lock_minutes": login_security.lock_minutes_left(account),
        }
        for account, profile, patient in rows
    ]

    return templates.TemplateResponse(
        request,
        "users.html",
        {
            "doctor_name": doctor.full_name,
            "active": "usuarios",
            "staff": staff,
            "roles_catalog": roles,
            "aviso": aviso,
        },
    )


@router.get("/usuarios/nuevo", response_class=HTMLResponse)
async def doctor_new_page(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    session = await require_staff(request, db)
    if session is None:
        return login_redirect()
    _, doctor = session

    roles = list(
        (await db.scalars(select(Role).where(Role.code != "patient").order_by(Role.name.asc()))).all()
    )
    return templates.TemplateResponse(
        request,
        "doctor_form.html",
        doctor_form_context(
            doctor.full_name,
            mode="create",
            user=None,
            values={"full_name": "", "specialty": "", "username": "", "role_code": "doctor", "email": ""},
            errors={},
            roles=roles,
        ),
    )


@router.post("/usuarios/nuevo", response_class=HTMLResponse)
async def doctor_new_submit(
    request: Request,
    full_name: str = Form(""),
    role_code: str = Form("doctor"),
    specialty: str = Form(""),
    email: str = Form(""),
    username: str = Form(""),
    password: str = Form(""),
    password_confirm: str = Form(""),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    session = await require_staff(request, db)
    if session is None:
        return login_redirect()
    current_user, doctor = session

    roles = list(
        (await db.scalars(select(Role).where(Role.code != "patient").order_by(Role.name.asc()))).all()
    )
    role = next((item for item in roles if item.code == role_code.strip().lower()), None)

    values = {
        "full_name": full_name.strip(),
        "role_code": role.code if role else role_code.strip().lower(),
        "specialty": specialty.strip(),
        "email": email.strip().lower(),
        "username": username.strip().lower(),
    }
    errors: dict[str, str] = {}

    if role is None:
        errors["role_code"] = "Selecciona un rol válido."
    if not 5 <= len(values["full_name"]) <= 160:
        errors["full_name"] = "Escribe el nombre completo (mínimo 5 caracteres)."
    if role is not None and role.code == "doctor" and not 3 <= len(values["specialty"]) <= 120:
        errors["specialty"] = "Escribe la especialidad (mínimo 3 caracteres)."
    if values["email"] and not EMAIL_PATTERN.match(values["email"]):
        errors["email"] = "Escribe un correo válido o déjalo vacío."
    if not USERNAME_PATTERN.match(values["username"]):
        errors["username"] = (
            "El usuario debe tener entre 3 y 64 caracteres: letras minúsculas, números, punto, guion o guion bajo."
        )
    password_error = password_policy_error(password, password_confirm)
    if password_error:
        errors["password"] = password_error

    if errors:
        return templates.TemplateResponse(
            request,
            "doctor_form.html",
            doctor_form_context(doctor.full_name, mode="create", user=None, values=values, errors=errors, roles=roles),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    try:
        account, profile = await create_staff_account(
            db,
            full_name=values["full_name"],
            role_code=role.code if role else "doctor",
            username=values["username"],
            password=password,
            email=values["email"] or None,
            specialty=values["specialty"],
        )
    except AccountError as error:
        errors["general"] = str(error)
        return templates.TemplateResponse(
            request,
            "doctor_form.html",
            doctor_form_context(doctor.full_name, mode="create", user=None, values=values, errors=errors, roles=roles),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    await write_audit_event(
        db,
        user=current_user,
        action="portal_create_doctor" if account.role.code == "doctor" else "portal_create_staff",
        entity_type="user",
        entity_id=account.id,
        request=request,
        detail=f"username={account.username} role={account.role.code}",
    )
    await db.commit()

    return templates.TemplateResponse(
        request,
        "credential.html",
        credential_context(
            doctor_name=doctor.full_name,
            person_name=account.full_name or account.username,
            role_label=account.role.name,
            username=account.username,
            password=password,
            email=values["email"] or None,
            user_id=account.id,
            back_url="/portal/usuarios",
            back_label="Volver a usuarios",
        ),
        status_code=status.HTTP_201_CREATED,
    )


@router.get("/usuarios/{user_id:int}/editar", response_class=HTMLResponse)
async def doctor_edit_page(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    session = await require_staff(request, db)
    if session is None:
        return login_redirect()
    _, doctor = session

    account = await db.get(User, user_id)
    if account is None:
        return templates.TemplateResponse(
            request, "not_found.html", {"doctor_name": doctor.full_name}, status_code=status.HTTP_404_NOT_FOUND
        )
    profile = await db.scalar(select(Doctor).where(Doctor.user_id == user_id))

    return templates.TemplateResponse(
        request,
        "doctor_form.html",
        doctor_form_context(
            doctor.full_name,
            mode="edit",
            user=account,
            values={
                "full_name": account.full_name or (profile.full_name if profile else account.username),
                "specialty": profile.specialty if profile else "",
                "username": account.username,
            },
            errors={},
            is_doctor=profile is not None,
        ),
    )


@router.post("/usuarios/{user_id:int}/editar", response_class=HTMLResponse)
async def doctor_edit_submit(
    user_id: int,
    request: Request,
    full_name: str = Form(""),
    specialty: str = Form(""),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    session = await require_staff(request, db)
    if session is None:
        return login_redirect()
    current_user, doctor = session

    account = await db.get(User, user_id)
    if account is None:
        return templates.TemplateResponse(
            request, "not_found.html", {"doctor_name": doctor.full_name}, status_code=status.HTTP_404_NOT_FOUND
        )
    profile = await db.scalar(select(Doctor).where(Doctor.user_id == user_id))

    values = {
        "full_name": full_name.strip(),
        "specialty": specialty.strip() if profile else "",
        "username": account.username,
    }
    errors: dict[str, str] = {}
    if not 5 <= len(values["full_name"]) <= 160:
        errors["full_name"] = "Escribe el nombre completo (mínimo 5 caracteres)."
    if profile is not None and not 3 <= len(values["specialty"]) <= 120:
        errors["specialty"] = "Escribe la especialidad (mínimo 3 caracteres)."

    if errors:
        return templates.TemplateResponse(
            request,
            "doctor_form.html",
            doctor_form_context(
                doctor.full_name,
                mode="edit",
                user=account,
                values=values,
                errors=errors,
                is_doctor=profile is not None,
            ),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    account.full_name = values["full_name"]
    if profile is not None:
        profile.full_name = values["full_name"]
        profile.specialty = values["specialty"]
    await db.flush()

    await write_audit_event(
        db,
        user=current_user,
        action="portal_update_doctor" if profile is not None else "portal_update_staff",
        entity_type="user",
        entity_id=account.id,
        request=request,
    )
    await db.commit()
    return users_redirect()


@router.post("/usuarios/{user_id:int}/estado")
async def user_toggle_state(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    session = await require_staff(request, db)
    if session is None:
        return login_redirect()
    current_user, _ = session
    if not has_permission(current_user, "users:manage"):
        return users_redirect("permiso")

    account = await db.get(User, user_id)
    if account is None:
        return users_redirect("no-encontrado")
    if account.id == current_user.id:
        return users_redirect("propio")

    await set_user_active(db, account, not account.is_active)
    await write_audit_event(
        db,
        user=current_user,
        action="portal_user_activated" if account.is_active else "portal_user_deactivated",
        entity_type="user",
        entity_id=account.id,
        request=request,
        detail=f"username={account.username}",
    )
    await db.commit()
    return users_redirect()


@router.post("/usuarios/{user_id:int}/desbloquear")
async def user_unlock(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Quita el bloqueo por intentos fallidos (para soporte y para la demo)."""
    session = await require_staff(request, db)
    if session is None:
        return login_redirect()
    current_user, _ = session
    if not has_permission(current_user, "users:manage"):
        return users_redirect("permiso")

    account = await db.get(User, user_id)
    if account is None:
        return users_redirect("no-encontrado")

    await login_security.reset_failed_attempts(db, account)
    await write_audit_event(
        db,
        user=current_user,
        action="account_unlocked",
        entity_type="user",
        entity_id=account.id,
        request=request,
        detail=f"username={account.username}",
    )
    await db.commit()
    return users_redirect()


@router.post("/usuarios/{user_id:int}/reset-2fa")
async def user_reset_two_factor(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Apaga el segundo factor de otra cuenta (soporte: perdió el teléfono y los códigos)."""
    session = await require_staff(request, db)
    if session is None:
        return login_redirect()
    current_user, _ = session
    if not has_permission(current_user, "users:manage"):
        return users_redirect("permiso")

    account = await db.get(User, user_id)
    if account is None:
        return users_redirect("no-encontrado")

    await two_factor.clear_two_factor(db, account)
    await write_audit_event(
        db,
        user=current_user,
        action="portal_reset_two_factor",
        entity_type="user",
        entity_id=account.id,
        request=request,
        detail=f"username={account.username}",
    )
    await db.commit()
    return users_redirect()


@router.post("/usuarios/{user_id:int}/reset", response_class=HTMLResponse)
async def user_reset_password(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    session = await require_staff(request, db)
    if session is None:
        return login_redirect()
    current_user, doctor = session
    if not has_permission(current_user, "users:manage"):
        return forbidden(request, doctor.full_name, "Tu rol no puede gestionar usuarios.")

    account = await db.get(User, user_id)
    if account is None:
        return templates.TemplateResponse(
            request, "not_found.html", {"doctor_name": doctor.full_name}, status_code=status.HTTP_404_NOT_FOUND
        )

    profile = await db.scalar(select(Doctor).where(Doctor.user_id == account.id))
    new_password = await reset_user_password(db, account)
    await write_audit_event(
        db,
        user=current_user,
        action="portal_reset_password",
        entity_type="user",
        entity_id=account.id,
        request=request,
        detail=f"username={account.username}",
    )
    await db.commit()

    return templates.TemplateResponse(
        request,
        "credential.html",
        credential_context(
            doctor_name=doctor.full_name,
            person_name=profile.full_name if profile else account.username,
            role_label=ROLE_LABELS.get(account.role.code, account.role.name),
            username=account.username,
            password=new_password,
            email=None,
            user_id=account.id,
            back_url="/portal/usuarios",
            back_label="Volver a usuarios",
        ),
        status_code=status.HTTP_200_OK,
    )


# ── Roles y permisos ──────────────────────────────────────────────────────────


def roles_context(doctor_name: str, *, roles: list, permissions: list, error: str | None = None) -> dict:
    return {
        "doctor_name": doctor_name,
        "active": "roles",
        "roles": roles,
        "permissions": permissions,
        "error": error,
    }


def role_form_context(
    doctor_name: str,
    *,
    mode: str,
    role: Role | None,
    values: dict,
    permissions: list,
    selected: list[str],
    error: str | None = None,
) -> dict:
    return {
        "doctor_name": doctor_name,
        "active": "roles",
        "mode": mode,
        "role": role,
        "values": values,
        "permissions": permissions,
        "selected": selected,
        "error": error,
    }


async def permission_catalog(db: AsyncSession) -> list[Permission]:
    return list((await db.scalars(select(Permission).order_by(Permission.area.asc(), Permission.action.asc()))).all())


@router.get("/roles", response_class=HTMLResponse)
async def roles_page(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    session = await require_staff(request, db)
    if session is None:
        return login_redirect()
    current_user, doctor = session
    if not has_permission(current_user, "roles:manage"):
        return forbidden(request, doctor.full_name, "Tu rol no puede gestionar roles.")

    roles = list((await db.scalars(select(Role).order_by(Role.code.asc()))).all())
    counts = (await db.execute(select(User.role_id, func.count(User.id)).group_by(User.role_id))).all()
    context = roles_context(doctor.full_name, roles=roles, permissions=await permission_catalog(db))
    context["user_counts"] = {role_id: total for role_id, total in counts}
    return templates.TemplateResponse(request, "roles.html", context)


@router.get("/roles/nuevo", response_class=HTMLResponse)
async def role_new_page(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    session = await require_staff(request, db)
    if session is None:
        return login_redirect()
    current_user, doctor = session
    if not has_permission(current_user, "roles:manage"):
        return forbidden(request, doctor.full_name, "Tu rol no puede gestionar roles.")

    return templates.TemplateResponse(
        request,
        "role_form.html",
        role_form_context(
            doctor.full_name,
            mode="create",
            role=None,
            values={"code": "", "name": "", "description": ""},
            permissions=await permission_catalog(db),
            selected=[],
        ),
    )


@router.post("/roles/nuevo", response_class=HTMLResponse)
async def role_new_submit(
    request: Request,
    code: str = Form(""),
    name: str = Form(""),
    description: str = Form(""),
    permissions: list[str] = Form([]),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    session = await require_staff(request, db)
    if session is None:
        return login_redirect()
    current_user, doctor = session
    if not has_permission(current_user, "roles:manage"):
        return forbidden(request, doctor.full_name, "Tu rol no puede gestionar roles.")

    values = {"code": code.strip().lower(), "name": name.strip(), "description": description.strip()}
    catalog = await permission_catalog(db)
    valid = {permission.code for permission in catalog}
    selected = [item for item in permissions if item in valid]
    error = None

    if not re.fullmatch(r"[a-z0-9_]{3,40}", values["code"]):
        error = "El código del rol solo admite minúsculas, números y guion bajo (3 a 40 caracteres)."
    elif not 3 <= len(values["name"]) <= 80:
        error = "Escribe el nombre del rol (3 a 80 caracteres)."
    elif await db.scalar(select(Role).where(Role.code == values["code"])) is not None:
        error = "Ya existe un rol con ese código."

    if error:
        return templates.TemplateResponse(
            request,
            "role_form.html",
            role_form_context(
                doctor.full_name,
                mode="create",
                role=None,
                values=values,
                permissions=catalog,
                selected=selected,
                error=error,
            ),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    role = Role(code=values["code"], name=values["name"], description=values["description"] or None, is_system=False)
    role.permissions = [permission for permission in catalog if permission.code in selected]
    db.add(role)
    await db.flush()
    await write_audit_event(
        db,
        user=current_user,
        action="portal_create_role",
        entity_type="role",
        entity_id=role.id,
        request=request,
        detail=f"code={role.code} permisos={len(selected)}",
    )
    await db.commit()
    return RedirectResponse("/portal/roles", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/roles/{role_id:int}/editar", response_class=HTMLResponse)
async def role_edit_page(
    role_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    session = await require_staff(request, db)
    if session is None:
        return login_redirect()
    current_user, doctor = session
    if not has_permission(current_user, "roles:manage"):
        return forbidden(request, doctor.full_name, "Tu rol no puede gestionar roles.")

    role = await db.get(Role, role_id)
    if role is None:
        return templates.TemplateResponse(
            request, "not_found.html", {"doctor_name": doctor.full_name}, status_code=status.HTTP_404_NOT_FOUND
        )

    return templates.TemplateResponse(
        request,
        "role_form.html",
        role_form_context(
            doctor.full_name,
            mode="edit",
            role=role,
            values={"code": role.code, "name": role.name, "description": role.description or ""},
            permissions=await permission_catalog(db),
            selected=[permission.code for permission in role.permissions],
        ),
    )


@router.post("/roles/{role_id:int}/editar", response_class=HTMLResponse)
async def role_edit_submit(
    role_id: int,
    request: Request,
    name: str = Form(""),
    description: str = Form(""),
    permissions: list[str] = Form([]),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    session = await require_staff(request, db)
    if session is None:
        return login_redirect()
    current_user, doctor = session
    if not has_permission(current_user, "roles:manage"):
        return forbidden(request, doctor.full_name, "Tu rol no puede gestionar roles.")

    role = await db.get(Role, role_id)
    if role is None:
        return templates.TemplateResponse(
            request, "not_found.html", {"doctor_name": doctor.full_name}, status_code=status.HTTP_404_NOT_FOUND
        )

    catalog = await permission_catalog(db)
    valid = {permission.code for permission in catalog}
    selected = [item for item in permissions if item in valid]
    values = {"code": role.code, "name": name.strip(), "description": description.strip()}
    error = None

    if not 3 <= len(values["name"]) <= 80:
        error = "Escribe el nombre del rol (3 a 80 caracteres)."
    elif role.code == "admin" and "users:manage" not in selected:
        error = "El rol Administrador debe conservar la gestión de usuarios."

    if error:
        return templates.TemplateResponse(
            request,
            "role_form.html",
            role_form_context(
                doctor.full_name,
                mode="edit",
                role=role,
                values=values,
                permissions=catalog,
                selected=selected,
                error=error,
            ),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    role.name = values["name"]
    role.description = values["description"] or None
    role.permissions = [permission for permission in catalog if permission.code in selected]
    await db.flush()
    await write_audit_event(
        db,
        user=current_user,
        action="portal_update_role",
        entity_type="role",
        entity_id=role.id,
        request=request,
        detail=f"code={role.code} permisos={len(selected)}",
    )
    await db.commit()
    return RedirectResponse("/portal/roles", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/usuarios/{user_id:int}/rol")
async def user_assign_role(
    user_id: int,
    request: Request,
    role_id: int = Form(...),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    session = await require_staff(request, db)
    if session is None:
        return login_redirect()
    current_user, _ = session
    if not has_permission(current_user, "users:manage"):
        return users_redirect("permiso")

    account = await db.get(User, user_id)
    role = await db.get(Role, role_id)
    if account is None or role is None:
        return users_redirect("no-encontrado")
    if account.id == current_user.id:
        return users_redirect("propio")

    account.role_id = role.id
    await db.flush()
    await write_audit_event(
        db,
        user=current_user,
        action="portal_assign_role",
        entity_type="user",
        entity_id=account.id,
        request=request,
        detail=f"username={account.username} role={role.code}",
    )
    await db.commit()
    return users_redirect()


# ── Envío simulado de credenciales ────────────────────────────────────────────


@router.post("/credencial/correo", response_class=HTMLResponse)
async def send_credentials_email(
    request: Request,
    user_id: int = Form(0),
    person_name: str = Form(""),
    role_label: str = Form(""),
    username: str = Form(""),
    password: str = Form(""),
    email: str = Form(""),
    back_url: str = Form("/portal/usuarios"),
    back_label: str = Form("Volver"),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    session = await require_staff(request, db)
    if session is None:
        return login_redirect()
    current_user, doctor = session

    clean_email = email.strip().lower()
    if not EMAIL_PATTERN.match(clean_email):
        context = credential_context(
            doctor_name=doctor.full_name,
            person_name=person_name,
            role_label=role_label,
            username=username,
            password=password,
            email=email.strip(),
            user_id=user_id,
            back_url=back_url,
            back_label=back_label,
        )
        context["errors"] = {"email": "Escribe un correo válido para enviar la credencial."}
        return templates.TemplateResponse(request, "credential.html", context, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

    body = (
        f"Hola {person_name}:\n\n"
        "Tu cuenta del hospital ya está lista. Descarga la app D.O.S.Y.S e inicia sesión con estos datos:\n\n"
        f"Usuario: {username}\n"
        f"Contraseña temporal: {password}\n\n"
        "Por seguridad, no compartas este mensaje y cambia la contraseña después de tu primer acceso.\n"
    )
    sent, reason = await send_email(to=clean_email, subject="Tu acceso a D.O.S.Y.S", text=body)
    send_error = reason if not sent and delivery_enabled() else None

    await write_audit_event(
        db,
        user=current_user,
        action="portal_send_credentials",
        entity_type="user",
        entity_id=user_id or None,
        request=request,
        detail=f"to={clean_email} delivery={'email' if sent else 'simulated'}",
    )
    await db.commit()

    return templates.TemplateResponse(
        request,
        "email_mockup.html",
        {
            "doctor_name": doctor.full_name,
            "active": "usuarios",
            "to": clean_email,
            "person_name": person_name,
            "role_label": role_label,
            "username": username,
            "password": password,
            "back_url": back_url,
            "back_label": back_label,
            "sender": settings.email_from,
            "sent": sent,
            "send_error": send_error,
        },
    )


# ── Bitácora ──────────────────────────────────────────────────────────────────


@router.get("/actividad", response_class=HTMLResponse)
async def activity_page(
    request: Request,
    accion: str = "",
    usuario: str = "",
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    session = await require_staff(request, db)
    if session is None:
        return login_redirect()
    current_user, doctor = session
    if not has_permission(current_user, "audit:read"):
        return forbidden(request, doctor.full_name, "Tu rol no puede consultar la bitácora.")

    query = (
        select(AuditLog, User)
        .outerjoin(User, AuditLog.user_id == User.id)
        .order_by(desc(AuditLog.created_at))
        .limit(300)
    )
    if usuario.strip():
        query = query.where(User.username.ilike(f"%{usuario.strip()}%"))

    rows = (await db.execute(query)).all()
    search = normalize(accion.strip())
    entries = [
        {
            "created_at": log.created_at,
            "username": account.username if account else "—",
            "action": log.action,
            "label": action_label(log.action),
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "ip": log.ip_address or "—",
            "detail": log.detail,
        }
        for log, account in rows
    ]
    if search:
        entries = [
            entry
            for entry in entries
            if search in normalize(entry["label"]) or search in normalize(entry["action"])
        ]
    entries = entries[:100]

    return templates.TemplateResponse(
        request,
        "activity.html",
        {
            "doctor_name": doctor.full_name,
            "active": "actividad",
            "entries": entries,
            "accion": accion,
            "usuario": usuario,
        },
    )
