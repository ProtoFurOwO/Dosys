"""Portal clínico del personal médico (HTML servido por el mismo backend).

Seguridad: cookie de sesión HttpOnly con el mismo JWT de la API, rol médico
validado en el servidor en cada petición, y bitácora de todos los accesos.
"""

from datetime import datetime, timezone
import re
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    TWO_FACTOR_PURPOSE,
    create_access_token,
    create_challenge_token,
    decode_token,
    verify_password,
)
from app.db.session import get_db
from app.models.appointment import Appointment
from app.models.consultation import Consultation
from app.models.doctor import Doctor
from app.models.document import Document
from app.models.enums import AppointmentStatus
from app.models.patient import Patient
from app.models.user import User
from app.portal import deps
from app.portal.labels import ROLE_LABELS
from app.portal.qr import qr_svg
from app.portal.templating import credential_context, templates
from app.services import login_security, two_factor
from app.services.appointments import create_appointment
from app.services.audit import write_audit_event
from app.services.consultations import create_consultation
from app.services.documents import (
    CATEGORIES,
    DocumentError,
    check_integrity,
    document_path,
    human_size,
    store_document,
)
from app.services.permissions import has_permission, permission_codes
from app.services.users import (
    CURP_PATTERN,
    EMAIL_PATTERN,
    USERNAME_PATTERN,
    AccountError,
    create_patient_account,
    password_policy_error,
)

router = APIRouter(prefix="/portal", tags=["Portal clínico"], include_in_schema=False)

TWO_FACTOR_COOKIE = "dosys_2fa"

REASON_MIN, REASON_MAX = 3, 300
DIAGNOSIS_MIN, DIAGNOSIS_MAX = 3, 500
NOTES_MAX = 4000
SPECIALTY_MIN, SPECIALTY_MAX = 3, 120
LOCATION_MIN, LOCATION_MAX = 3, 160

STATUS_LABELS = {
    AppointmentStatus.SCHEDULED: "Agendada",
    AppointmentStatus.CONFIRMED: "Confirmada",
    AppointmentStatus.ATTENDED: "Atendida",
    AppointmentStatus.CANCELLED: "Cancelada",
}

BLOOD_TYPES = ("O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-")


def login_redirect() -> RedirectResponse:
    return RedirectResponse("/portal/login", status_code=status.HTTP_303_SEE_OTHER)


async def doctor_profile(db: AsyncSession, user: User) -> Doctor | None:
    return await db.scalar(select(Doctor).where(Doctor.user_id == user.id))


class StaffDisplay:
    """Perfil mostrable para cuentas sin ficha de médico (administración, etc.)."""

    def __init__(self, user: User) -> None:
        self.id = 0
        self.full_name = user.username
        self.specialty = ""


async def portal_staff(db: AsyncSession, user: User) -> Doctor | StaffDisplay:
    return await doctor_profile(db, user) or StaffDisplay(user)


def forbidden(request: Request, doctor_name: str, detail: str) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "forbidden.html",
        {"doctor_name": doctor_name, "active": "", "detail": detail},
        status_code=status.HTTP_403_FORBIDDEN,
    )


def render_login(request: Request, *, error: str | None, username: str = "", code: int = 200) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "login.html",
        {"error": error, "username": username},
        status_code=code,
    )


def set_session_cookie(response: RedirectResponse, token: str, expires_in: int) -> RedirectResponse:
    response.set_cookie(
        deps.COOKIE_NAME,
        token,
        max_age=expires_in,
        httponly=True,
        secure=settings.app_env != "development",
        samesite="lax",
        path="/portal",
    )
    return response


# ── Sesión ────────────────────────────────────────────────────────────────────


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    if await deps.current_doctor(request, db) is not None:
        return RedirectResponse("/portal", status_code=status.HTTP_303_SEE_OTHER)
    return render_login(request, error=None)


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    user = await db.scalar(select(User).where(User.username == username.strip().lower()))

    # Cuenta bloqueada por intentos fallidos: ni la contraseña correcta entra.
    if user is not None and login_security.is_locked(user):
        await write_audit_event(
            db,
            user=user,
            action="login_blocked",
            entity_type="authentication",
            entity_id=user.id,
            request=request,
        )
        await db.commit()
        return render_login(
            request,
            error=(
                "Cuenta bloqueada temporalmente por intentos fallidos. "
                f"Intenta de nuevo en {login_security.lock_minutes_left(user)} minutos."
            ),
            username=username.strip(),
            code=status.HTTP_423_LOCKED,
        )

    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        if user is not None and user.is_active:
            locked = await login_security.register_failed_attempt(db, user)
            if locked:
                await write_audit_event(
                    db,
                    user=user,
                    action="account_locked",
                    entity_type="authentication",
                    entity_id=user.id,
                    request=request,
                    detail=f"intentos={settings.login_max_attempts} bloqueo_min={settings.login_lock_minutes}",
                )
        await write_audit_event(
            db,
            user=None,
            action="portal_login_failed",
            entity_type="authentication",
            entity_id=None,
            request=request,
        )
        await db.commit()
        return render_login(
            request,
            error="Usuario o contraseña incorrectos.",
            username=username.strip(),
            code=status.HTTP_401_UNAUTHORIZED,
        )

    if not has_permission(user, "portal:access"):
        await write_audit_event(
            db,
            user=user,
            action="portal_login_denied",
            entity_type="authentication",
            entity_id=user.id,
            request=request,
            detail=f"role={user.role.code}",
        )
        await db.commit()
        return render_login(
            request,
            error="Este portal es para personal autorizado.",
            username=username.strip(),
            code=status.HTTP_403_FORBIDDEN,
        )

    await login_security.reset_failed_attempts(db, user)

    # Segundo factor: no se entrega la sesión hasta verificar el código.
    if user.totp_enabled and user.totp_secret:
        challenge, challenge_ttl = create_challenge_token(user.id)
        await write_audit_event(
            db,
            user=user,
            action="login_2fa_challenge",
            entity_type="authentication",
            entity_id=user.id,
            request=request,
        )
        await db.commit()
        response = RedirectResponse("/portal/2fa", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(
            TWO_FACTOR_COOKIE,
            challenge,
            max_age=challenge_ttl,
            httponly=True,
            secure=settings.app_env != "development",
            samesite="lax",
            path="/portal",
        )
        return response

    token, expires_in = create_access_token(user.id, user.role.code, sorted(permission_codes(user)))
    await write_audit_event(
        db,
        user=user,
        action="portal_login_success",
        entity_type="authentication",
        entity_id=user.id,
        request=request,
    )
    await db.commit()

    return set_session_cookie(RedirectResponse("/portal", status_code=status.HTTP_303_SEE_OTHER), token, expires_in)


# ── Segundo factor del portal ─────────────────────────────────────────────────


async def _pending_two_factor_user(request: Request, db: AsyncSession) -> User | None:
    token = request.cookies.get(TWO_FACTOR_COOKIE)
    if not token:
        return None
    try:
        decoded = decode_token(token, purpose=TWO_FACTOR_PURPOSE)
        user_id = int(decoded["sub"])
    except Exception:
        return None
    user = await db.get(User, user_id)
    if user is None or not user.is_active or not user.totp_enabled or not user.totp_secret:
        return None
    return user


@router.get("/2fa", response_class=HTMLResponse)
async def two_factor_page(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    user = await _pending_two_factor_user(request, db)
    if user is None:
        return login_redirect()
    return templates.TemplateResponse(
        request,
        "two_factor.html",
        {"error": None, "username": user.username},
    )


@router.post("/2fa", response_class=HTMLResponse)
async def two_factor_submit(
    request: Request,
    code: str = Form(""),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    user = await _pending_two_factor_user(request, db)
    if user is None:
        return login_redirect()

    used_recovery = False
    valid = two_factor.verify_code(user.totp_secret, code)
    if not valid:
        used_recovery = await two_factor.consume_recovery_code(db, user, code)
        valid = used_recovery

    if not valid:
        await write_audit_event(
            db,
            user=user,
            action="login_2fa_failed",
            entity_type="authentication",
            entity_id=user.id,
            request=request,
        )
        await db.commit()
        return templates.TemplateResponse(
            request,
            "two_factor.html",
            {"error": "Código incorrecto. Revisa tu app autenticadora e intenta de nuevo.", "username": user.username},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    if used_recovery:
        await write_audit_event(
            db,
            user=user,
            action="recovery_code_used",
            entity_type="authentication",
            entity_id=user.id,
            request=request,
        )

    token, expires_in = create_access_token(user.id, user.role.code, sorted(permission_codes(user)))
    await write_audit_event(
        db,
        user=user,
        action="login_2fa_success",
        entity_type="authentication",
        entity_id=user.id,
        request=request,
    )
    await db.commit()

    response = RedirectResponse("/portal", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(TWO_FACTOR_COOKIE, path="/portal")
    return set_session_cookie(response, token, expires_in)


@router.post("/2fa/cancelar")
async def two_factor_cancel() -> RedirectResponse:
    response = RedirectResponse("/portal/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(TWO_FACTOR_COOKIE, path="/portal")
    return response


# ── Mi seguridad (2FA del médico) ─────────────────────────────────────────────


def security_context(
    doctor_name: str,
    *,
    user: User,
    enabled: bool,
    remaining: int,
    otpauth_uri: str | None = None,
    secret: str | None = None,
    recovery_codes: list[str] | None = None,
    error: str | None = None,
) -> dict:
    return {
        "doctor_name": doctor_name,
        "active": "seguridad",
        "enabled": enabled,
        "remaining": remaining,
        "otpauth_uri": otpauth_uri,
        "qr": qr_svg(otpauth_uri) if otpauth_uri else None,
        "secret": secret,
        "recovery_codes": recovery_codes,
        "error": error,
        "username": user.username,
    }


@router.get("/seguridad", response_class=HTMLResponse)
async def security_page(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    doctor = await portal_staff(db, user)

    enabled = user.totp_enabled
    pending = bool(user.totp_secret) and not enabled
    return templates.TemplateResponse(
        request,
        "security.html",
        security_context(
            doctor.full_name,
            user=user,
            enabled=enabled,
            remaining=await two_factor.recovery_codes_remaining(db, user) if enabled else 0,
            otpauth_uri=two_factor.provisioning_uri(user.totp_secret, user.username) if pending else None,
            secret=user.totp_secret if pending else None,
        ),
    )


@router.post("/seguridad/iniciar")
async def security_start(request: Request, db: AsyncSession = Depends(get_db)) -> RedirectResponse:
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    if not user.totp_enabled:
        user.totp_secret = two_factor.generate_secret()
        await db.flush()
        await db.commit()
    return RedirectResponse("/portal/seguridad", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/seguridad/confirmar", response_class=HTMLResponse)
async def security_confirm(
    request: Request,
    code: str = Form(""),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    doctor = await portal_staff(db, user)

    if not user.totp_secret:
        return RedirectResponse("/portal/seguridad", status_code=status.HTTP_303_SEE_OTHER)

    if not two_factor.verify_code(user.totp_secret, code):
        return templates.TemplateResponse(
            request,
            "security.html",
            security_context(
                doctor.full_name,
                user=user,
                enabled=False,
                remaining=0,
                otpauth_uri=two_factor.provisioning_uri(user.totp_secret, user.username),
                secret=user.totp_secret,
                error="El código no coincide. Revisa la hora de tu teléfono e intenta otra vez.",
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    codes = two_factor.generate_recovery_codes()
    await two_factor.store_recovery_codes(db, user, codes)
    user.totp_enabled = True
    user.totp_confirmed_at = datetime.now(timezone.utc)
    await write_audit_event(
        db,
        user=user,
        action="two_factor_enabled",
        entity_type="authentication",
        entity_id=user.id,
        request=request,
    )
    await db.commit()

    return templates.TemplateResponse(
        request,
        "security.html",
        security_context(
            doctor.full_name,
            user=user,
            enabled=True,
            remaining=len(codes),
            recovery_codes=codes,
        ),
    )


@router.post("/seguridad/desactivar", response_class=HTMLResponse)
async def security_disable(
    request: Request,
    password: str = Form(""),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    doctor = await portal_staff(db, user)

    if not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request,
            "security.html",
            security_context(
                doctor.full_name,
                user=user,
                enabled=user.totp_enabled,
                remaining=await two_factor.recovery_codes_remaining(db, user),
                error="Contraseña incorrecta. No se desactivó el segundo factor.",
            ),
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    await two_factor.clear_two_factor(db, user)
    await write_audit_event(
        db,
        user=user,
        action="two_factor_disabled",
        entity_type="authentication",
        entity_id=user.id,
        request=request,
    )
    await db.commit()
    return RedirectResponse("/portal/seguridad", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/salir")
async def logout() -> RedirectResponse:
    response = RedirectResponse("/portal/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(deps.COOKIE_NAME, path="/portal")
    return response


# ── Pacientes ─────────────────────────────────────────────────────────────────


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    q: str = "",
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    doctor = await portal_staff(db, user)
    if not has_permission(user, "patients:read"):
        return forbidden(request, doctor.full_name, "Tu rol no puede consultar pacientes.")

    search = q.strip()
    query = select(Patient).order_by(Patient.full_name.asc())
    if search:
        pattern = f"%{search}%"
        query = query.where(or_(Patient.full_name.ilike(pattern), Patient.curp.ilike(pattern)))
    patients = list((await db.scalars(query)).all())

    latest_rows = await db.execute(
        select(Consultation.patient_id, func.max(Consultation.created_at)).group_by(Consultation.patient_id)
    )
    latest_by_patient = {patient_id: last for patient_id, last in latest_rows.all()}

    stats = {
        "patients": await db.scalar(select(func.count(Patient.id))) or 0,
        "consultations": await db.scalar(select(func.count(Consultation.id))) or 0,
        "today": await db.scalar(
            select(func.count(Consultation.id)).where(Consultation.created_at >= deps.start_of_today_utc())
        )
        or 0,
    }

    await write_audit_event(
        db,
        user=user,
        action="portal_read_patients",
        entity_type="patient",
        entity_id=None,
        request=request,
        detail=f"search={search}" if search else None,
    )
    await db.commit()

    return templates.TemplateResponse(
        request,
        "patients.html",
        {
            "doctor_name": doctor.full_name,
            "active": "pacientes",
            "patients": patients,
            "latest_by_patient": latest_by_patient,
            "search": search,
            "stats": stats,
        },
    )


@router.get("/pacientes/{patient_id:int}", response_class=HTMLResponse)
async def patient_detail(
    patient_id: int,
    request: Request,
    creada: int | None = None,
    documento: int | None = None,
    documento_error: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    doctor = await portal_staff(db, user)
    if not has_permission(user, "patients:read"):
        return forbidden(request, doctor.full_name, "Tu rol no puede consultar expedientes.")

    patient = await db.get(Patient, patient_id)
    if patient is None:
        return templates.TemplateResponse(
            request, "not_found.html", {"doctor_name": doctor.full_name}, status_code=status.HTTP_404_NOT_FOUND
        )

    account = await db.scalar(select(User).where(User.id == patient.user_id))
    rows = (
        await db.execute(
            select(Consultation, Doctor)
            .join(Doctor, Consultation.doctor_id == Doctor.id)
            .where(Consultation.patient_id == patient.id)
            .order_by(Consultation.created_at.desc())
        )
    ).all()
    consultations = [
        {
            "id": consultation.id,
            "created_at": consultation.created_at,
            "doctor_name": doctor_row.full_name,
            "specialty": doctor_row.specialty,
            "reason": consultation.reason,
            "diagnosis": consultation.diagnosis,
            "notes": consultation.notes,
        }
        for consultation, doctor_row in rows
    ]
    created = next((item for item in consultations if item["id"] == creada), None)
    documents = (
        await db.scalars(
            select(Document).where(Document.patient_id == patient.id).order_by(Document.created_at.desc())
        )
    ).all()

    await write_audit_event(
        db,
        user=user,
        action="portal_read_patient",
        entity_type="patient",
        entity_id=patient.id,
        request=request,
    )
    await db.commit()

    return templates.TemplateResponse(
        request,
        "patient_detail.html",
        {
            "doctor_name": doctor.full_name,
            "active": "pacientes",
            "patient": patient,
            "consultations": consultations,
            "created": created,
            "locked": login_security.is_locked(account) if account else False,
            "lock_minutes": login_security.lock_minutes_left(account) if account else 0,
            "totp_enabled": bool(account.totp_enabled) if account else False,
            "documents": documents,
            "categories": CATEGORIES,
            "documento": documento,
            "documento_error": documento_error,
        },
    )


@router.post("/pacientes/{patient_id:int}/desbloquear")
async def patient_unlock(
    patient_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Levanta el bloqueo del acceso del paciente (lo pide en consulta o recepción)."""
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()

    patient = await db.get(Patient, patient_id)
    if patient is None:
        return RedirectResponse("/portal", status_code=status.HTTP_303_SEE_OTHER)

    account = await db.scalar(select(User).where(User.id == patient.user_id))
    if account is not None:
        await login_security.reset_failed_attempts(db, account)
        await write_audit_event(
            db,
            user=user,
            action="account_unlocked",
            entity_type="user",
            entity_id=account.id,
            request=request,
            detail=f"username={account.username}",
        )
        await db.commit()

    return RedirectResponse(f"/portal/pacientes/{patient.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/pacientes/{patient_id:int}/reiniciar-2fa")
async def patient_reset_two_factor(
    patient_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Apaga el 2FA del paciente (soporte: perdió el teléfono y sus códigos de recuperación)."""
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()

    patient = await db.get(Patient, patient_id)
    if patient is None:
        return RedirectResponse("/portal", status_code=status.HTTP_303_SEE_OTHER)

    account = await db.scalar(select(User).where(User.id == patient.user_id))
    if account is not None:
        await two_factor.clear_two_factor(db, account)
        await write_audit_event(
            db,
            user=user,
            action="portal_reset_two_factor",
            entity_type="user",
            entity_id=account.id,
            request=request,
            detail=f"username={account.username}",
        )
        await db.commit()

    return RedirectResponse(f"/portal/pacientes/{patient.id}", status_code=status.HTTP_303_SEE_OTHER)


# ── Citas ─────────────────────────────────────────────────────────────────────


@router.get("/citas", response_class=HTMLResponse)
async def appointments_page(
    request: Request,
    creada: int | None = None,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    doctor = await portal_staff(db, user)
    if not has_permission(user, "appointments:read"):
        return forbidden(request, doctor.full_name, "Tu rol no puede consultar la agenda.")

    rows = (
        await db.execute(
            select(Appointment, Patient, Doctor)
            .join(Patient, Appointment.patient_id == Patient.id)
            .outerjoin(Doctor, Appointment.doctor_id == Doctor.id)
            .order_by(Appointment.scheduled_at.desc())
        )
    ).all()

    appointments = []
    for appointment, patient, doctor_row in rows:
        code = appointment.checkin_code
        appointments.append(
            {
                "id": appointment.id,
                "patient_name": patient.full_name,
                "specialty": appointment.specialty,
                "doctor_name": doctor_row.full_name if doctor_row else None,
                "scheduled_at": appointment.scheduled_at,
                "location": appointment.location,
                "status": appointment.status.value,
                "status_label": STATUS_LABELS.get(appointment.status, appointment.status.value),
                "checked_in_at": appointment.checked_in_at,
                "checkin_code": code,
                "qr_svg": qr_svg(f"DOSYS-CHECKIN|{appointment.id}|{code}") if code else None,
            }
        )

    await write_audit_event(
        db,
        user=user,
        action="portal_read_appointments",
        entity_type="appointment",
        entity_id=None,
        request=request,
    )
    await db.commit()

    created = next((item for item in appointments if item["id"] == creada), None)

    return templates.TemplateResponse(
        request,
        "appointments.html",
        {"doctor_name": doctor.full_name, "active": "citas", "appointments": appointments, "created": created},
    )


# ── Registro y edición de pacientes ──────────────────────────────────────────


def patient_form_context(
    doctor_name: str,
    *,
    mode: str,
    patient: Patient | None,
    values: dict,
    errors: dict,
) -> dict:
    return {
        "doctor_name": doctor_name,
        "active": "pacientes",
        "mode": mode,
        "patient": patient,
        "values": values,
        "errors": errors,
        "blood_types": BLOOD_TYPES,
    }


@router.get("/pacientes/nuevo", response_class=HTMLResponse)
async def patient_new_page(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    doctor = await portal_staff(db, user)
    if not has_permission(user, "patients:write"):
        return forbidden(request, doctor.full_name, "Tu rol no puede registrar pacientes.")

    return templates.TemplateResponse(
        request,
        "patient_form.html",
        patient_form_context(
            doctor.full_name,
            mode="create",
            patient=None,
            values={
                "full_name": "",
                "curp": "",
                "birth_date": "",
                "blood_type": "",
                "emergency_contact": "",
                "email": "",
                "username": "",
            },
            errors={},
        ),
    )


@router.post("/pacientes/nuevo", response_class=HTMLResponse)
async def patient_new_submit(
    request: Request,
    full_name: str = Form(""),
    curp: str = Form(""),
    birth_date: str = Form(""),
    blood_type: str = Form(""),
    emergency_contact: str = Form(""),
    email: str = Form(""),
    username: str = Form(""),
    password: str = Form(""),
    password_confirm: str = Form(""),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    doctor = await portal_staff(db, user)

    values = {
        "full_name": full_name.strip(),
        "curp": curp.strip().upper(),
        "birth_date": birth_date.strip(),
        "blood_type": blood_type.strip().upper(),
        "emergency_contact": emergency_contact.strip(),
        "email": email.strip().lower(),
        "username": username.strip().lower(),
    }
    errors: dict[str, str] = {}
    parsed_birth = None

    if not 5 <= len(values["full_name"]) <= 160:
        errors["full_name"] = "Escribe el nombre completo (mínimo 5 caracteres)."
    if not CURP_PATTERN.match(values["curp"]):
        errors["curp"] = "La CURP debe tener 18 caracteres con el formato oficial (ej. MAAJ010415HCSRRN09)."
    if values["birth_date"]:
        try:
            parsed_birth = datetime.strptime(values["birth_date"], "%Y-%m-%d").date()
            if parsed_birth >= deps.clinic_now().date():
                errors["birth_date"] = "La fecha de nacimiento debe ser anterior a hoy."
        except ValueError:
            errors["birth_date"] = "Elige una fecha válida."
    if values["blood_type"] and values["blood_type"] not in BLOOD_TYPES:
        errors["blood_type"] = "Elige un tipo de sangre de la lista."
    if len(values["emergency_contact"]) > 160:
        errors["emergency_contact"] = "El contacto de emergencia es demasiado largo."
    if values["email"] and not EMAIL_PATTERN.match(values["email"]):
        errors["email"] = "Escribe un correo válido."
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
            "patient_form.html",
            patient_form_context(doctor.full_name, mode="create", patient=None, values=values, errors=errors),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    try:
        account, patient = await create_patient_account(
            db,
            full_name=values["full_name"],
            curp=values["curp"],
            birth_date=parsed_birth,
            blood_type=values["blood_type"] or None,
            emergency_contact=values["emergency_contact"] or None,
            email=values["email"] or None,
            username=values["username"],
            password=password,
        )
    except AccountError as error:
        errors["general"] = str(error)
        return templates.TemplateResponse(
            request,
            "patient_form.html",
            patient_form_context(doctor.full_name, mode="create", patient=None, values=values, errors=errors),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    await write_audit_event(
        db,
        user=user,
        action="portal_create_patient",
        entity_type="patient",
        entity_id=patient.id,
        request=request,
        detail=f"username={account.username}",
    )
    await db.commit()

    return templates.TemplateResponse(
        request,
        "credential.html",
        credential_context(
            doctor_name=doctor.full_name,
            person_name=patient.full_name,
            role_label=ROLE_LABELS["patient"],
            username=account.username,
            password=password,
            email=patient.email,
            user_id=account.id,
            back_url=f"/portal/pacientes/{patient.id}",
            back_label="Ir al expediente del paciente",
        ),
        status_code=status.HTTP_201_CREATED,
    )


@router.get("/pacientes/{patient_id:int}/editar", response_class=HTMLResponse)
async def patient_edit_page(
    patient_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    doctor = await portal_staff(db, user)
    if not has_permission(user, "patients:write"):
        return forbidden(request, doctor.full_name, "Tu rol no puede editar pacientes.")

    patient = await db.get(Patient, patient_id)
    if patient is None:
        return templates.TemplateResponse(
            request, "not_found.html", {"doctor_name": doctor.full_name}, status_code=status.HTTP_404_NOT_FOUND
        )

    account = await db.scalar(select(User).where(User.id == patient.user_id))
    return templates.TemplateResponse(
        request,
        "patient_form.html",
        patient_form_context(
            doctor.full_name,
            mode="edit",
            patient=patient,
            values={
                "full_name": patient.full_name,
                "curp": patient.curp,
                "birth_date": patient.birth_date.isoformat() if patient.birth_date else "",
                "blood_type": patient.blood_type or "",
                "emergency_contact": patient.emergency_contact or "",
                "email": patient.email or "",
                "username": account.username if account else "",
            },
            errors={},
        ),
    )


@router.post("/pacientes/{patient_id:int}/editar", response_class=HTMLResponse)
async def patient_edit_submit(
    patient_id: int,
    request: Request,
    full_name: str = Form(""),
    birth_date: str = Form(""),
    blood_type: str = Form(""),
    emergency_contact: str = Form(""),
    email: str = Form(""),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    doctor = await portal_staff(db, user)
    if not has_permission(user, "patients:read"):
        return forbidden(request, doctor.full_name, "Tu rol no puede consultar expedientes.")

    patient = await db.get(Patient, patient_id)
    if patient is None:
        return templates.TemplateResponse(
            request, "not_found.html", {"doctor_name": doctor.full_name}, status_code=status.HTTP_404_NOT_FOUND
        )

    account = await db.scalar(select(User).where(User.id == patient.user_id))
    values = {
        "full_name": full_name.strip(),
        "curp": patient.curp,
        "birth_date": birth_date.strip(),
        "blood_type": blood_type.strip().upper(),
        "emergency_contact": emergency_contact.strip(),
        "email": email.strip().lower(),
        "username": account.username if account else "",
    }
    errors: dict[str, str] = {}
    parsed_birth = None

    if not 5 <= len(values["full_name"]) <= 160:
        errors["full_name"] = "Escribe el nombre completo (mínimo 5 caracteres)."
    if values["birth_date"]:
        try:
            parsed_birth = datetime.strptime(values["birth_date"], "%Y-%m-%d").date()
            if parsed_birth >= deps.clinic_now().date():
                errors["birth_date"] = "La fecha de nacimiento debe ser anterior a hoy."
        except ValueError:
            errors["birth_date"] = "Elige una fecha válida."
    if values["blood_type"] and values["blood_type"] not in BLOOD_TYPES:
        errors["blood_type"] = "Elige un tipo de sangre de la lista."
    if len(values["emergency_contact"]) > 160:
        errors["emergency_contact"] = "El contacto de emergencia es demasiado largo."
    if values["email"] and not EMAIL_PATTERN.match(values["email"]):
        errors["email"] = "Escribe un correo válido."

    if errors:
        return templates.TemplateResponse(
            request,
            "patient_form.html",
            patient_form_context(doctor.full_name, mode="edit", patient=patient, values=values, errors=errors),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    patient.full_name = values["full_name"]
    patient.birth_date = parsed_birth
    patient.blood_type = values["blood_type"] or None
    patient.emergency_contact = values["emergency_contact"] or None
    patient.email = values["email"] or None
    await db.flush()

    await write_audit_event(
        db,
        user=user,
        action="portal_update_patient",
        entity_type="patient",
        entity_id=patient.id,
        request=request,
    )
    await db.commit()

    return RedirectResponse(
        f"/portal/pacientes/{patient.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# ── Documentos del expediente ─────────────────────────────────────────────────


@router.post("/pacientes/{patient_id:int}/documentos")
async def document_upload(
    patient_id: int,
    request: Request,
    title: str = Form(""),
    category: str = Form("estudio"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    if not has_permission(user, "documents:write"):
        return RedirectResponse(f"/portal/pacientes/{patient_id}", status_code=status.HTTP_303_SEE_OTHER)

    patient = await db.get(Patient, patient_id)
    if patient is None:
        return RedirectResponse("/portal", status_code=status.HTTP_303_SEE_OTHER)

    valid_categories = {code for code, _ in CATEGORIES}
    clean_title = title.strip() or (file.filename or "Documento")
    try:
        document = await store_document(
            db,
            patient=patient,
            uploader=user,
            title=clean_title[:160],
            category=category if category in valid_categories else "otro",
            upload=file,
        )
    except DocumentError as error:
        return RedirectResponse(
            f"/portal/pacientes/{patient.id}?documento_error={quote(str(error))}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    await write_audit_event(
        db,
        user=user,
        action="portal_upload_document",
        entity_type="document",
        entity_id=document.id,
        request=request,
        detail=f"patient_id={patient.id} sha256={document.sha256[:16]}",
    )
    await db.commit()
    return RedirectResponse(
        f"/portal/pacientes/{patient.id}?documento={document.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/documentos/{document_id:int}/archivo")
async def document_download(
    document_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    if not has_permission(user, "documents:read"):
        return forbidden(request, user.username, "Tu rol no puede descargar documentos.")

    document = await db.get(Document, document_id)
    if document is None:
        return templates.TemplateResponse(
            request, "not_found.html", {"doctor_name": user.username}, status_code=status.HTTP_404_NOT_FOUND
        )

    path = document_path(document)
    if not path.exists():
        return templates.TemplateResponse(
            request, "not_found.html", {"doctor_name": user.username}, status_code=status.HTTP_410_GONE
        )

    await write_audit_event(
        db,
        user=user,
        action="portal_download_document",
        entity_type="document",
        entity_id=document.id,
        request=request,
    )
    await db.commit()
    return FileResponse(path, media_type=document.content_type, filename=document.original_name)


@router.post("/documentos/{document_id:int}/verificar", response_class=HTMLResponse)
async def document_verify(
    document_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    if not has_permission(user, "documents:read"):
        return forbidden(request, user.username, "Tu rol no puede consultar documentos.")

    document = await db.get(Document, document_id)
    if document is None:
        return templates.TemplateResponse(
            request, "not_found.html", {"doctor_name": user.username}, status_code=status.HTTP_404_NOT_FOUND
        )

    intact, current_hash = check_integrity(document)
    patient = await db.get(Patient, document.patient_id)
    uploader = await db.get(User, document.uploaded_by_user_id) if document.uploaded_by_user_id else None

    await write_audit_event(
        db,
        user=user,
        action="portal_verify_document",
        entity_type="document",
        entity_id=document.id,
        request=request,
        detail="resultado=intacto" if intact else "resultado=alterado",
    )
    await db.commit()

    return templates.TemplateResponse(
        request,
        "document_verify.html",
        {
            "doctor_name": user.username,
            "active": "pacientes",
            "document": document,
            "patient": patient,
            "uploader": uploader,
            "intact": intact,
            "current_hash": current_hash,
            "size": human_size(document.size_bytes),
            "category_label": dict(CATEGORIES).get(document.category, document.category),
        },
    )


@router.post("/documentos/{document_id:int}/eliminar")
async def document_delete(
    document_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    if not has_permission(user, "documents:delete"):
        return RedirectResponse("/portal", status_code=status.HTTP_303_SEE_OTHER)

    document = await db.get(Document, document_id)
    if document is None:
        return RedirectResponse("/portal", status_code=status.HTTP_303_SEE_OTHER)

    patient_id = document.patient_id
    document_path(document).unlink(missing_ok=True)
    await db.delete(document)
    await write_audit_event(
        db,
        user=user,
        action="portal_delete_document",
        entity_type="document",
        entity_id=document_id,
        request=request,
        detail=f"patient_id={patient_id}",
    )
    await db.commit()
    return RedirectResponse(f"/portal/pacientes/{patient_id}", status_code=status.HTTP_303_SEE_OTHER)


# ── Agendar cita ──────────────────────────────────────────────────────────────


@router.get("/pacientes/{patient_id:int}/cita", response_class=HTMLResponse)
async def appointment_page(
    patient_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    doctor = await portal_staff(db, user)

    patient = await db.get(Patient, patient_id)
    if patient is None:
        return templates.TemplateResponse(
            request, "not_found.html", {"doctor_name": doctor.full_name}, status_code=status.HTTP_404_NOT_FOUND
        )

    return templates.TemplateResponse(
        request,
        "appointment_form.html",
        {
            "doctor_name": doctor.full_name,
            "active": "pacientes",
            "patient": patient,
            "errors": {},
            "values": {
                "specialty": "Medicina General",
                "fecha": deps.clinic_now().date().isoformat(),
                "hora": "10:00",
                "location": "Consultorio 3",
                "notes": "",
            },
        },
    )


@router.post("/pacientes/{patient_id:int}/cita", response_class=HTMLResponse)
async def appointment_submit(
    patient_id: int,
    request: Request,
    specialty: str = Form(""),
    fecha: str = Form(""),
    hora: str = Form(""),
    location: str = Form(""),
    notes: str = Form(""),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    doctor = await portal_staff(db, user)
    if not isinstance(doctor, Doctor):
        return forbidden(request, doctor.full_name, "Tu cuenta no tiene ficha de médico para agendar citas.")

    patient = await db.get(Patient, patient_id)
    if patient is None:
        return templates.TemplateResponse(
            request, "not_found.html", {"doctor_name": doctor.full_name}, status_code=status.HTTP_404_NOT_FOUND
        )

    specialty = specialty.strip()
    location = location.strip()
    notes = notes.strip()
    errors: dict[str, str] = {}
    scheduled_local: datetime | None = None

    if not SPECIALTY_MIN <= len(specialty) <= SPECIALTY_MAX:
        errors["specialty"] = "Escribe la especialidad o el servicio."
    if not LOCATION_MIN <= len(location) <= LOCATION_MAX:
        errors["location"] = "Indica el consultorio o la ubicación."
    if len(notes) > NOTES_MAX:
        errors["notes"] = f"Las notas no deben pasar de {NOTES_MAX} caracteres."

    parsed_date = None
    parsed_time = None
    try:
        parsed_date = datetime.strptime(fecha, "%Y-%m-%d").date()
    except ValueError:
        errors["fecha"] = "Elige la fecha de la cita."
    try:
        parsed_time = datetime.strptime(hora, "%H:%M").time()
    except ValueError:
        errors["hora"] = "Elige la hora de la cita."

    if parsed_date and parsed_time:
        scheduled_local = datetime.combine(parsed_date, parsed_time, tzinfo=deps.CLINIC_TIMEZONE)
        if scheduled_local < deps.clinic_now():
            errors["fecha"] = "Elige una fecha y hora futuras."

    if errors or scheduled_local is None:
        return templates.TemplateResponse(
            request,
            "appointment_form.html",
            {
                "doctor_name": doctor.full_name,
                "active": "pacientes",
                "patient": patient,
                "errors": errors,
                "values": {
                    "specialty": specialty,
                    "fecha": fecha,
                    "hora": hora,
                    "location": location,
                    "notes": notes,
                },
            },
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    appointment = await create_appointment(
        db,
        patient=patient,
        doctor=doctor,
        specialty=specialty,
        scheduled_at=scheduled_local.astimezone(timezone.utc),
        location=location,
        notes=notes or None,
    )
    await write_audit_event(
        db,
        user=user,
        action="portal_create_appointment",
        entity_type="appointment",
        entity_id=appointment.id,
        request=request,
        detail=f"patient_id={patient.id}",
    )
    await db.commit()

    return RedirectResponse(
        f"/portal/citas?creada={appointment.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# ── Consultas ─────────────────────────────────────────────────────────────────


@router.get("/pacientes/{patient_id:int}/consulta", response_class=HTMLResponse)
async def consultation_page(
    patient_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    doctor = await portal_staff(db, user)
    if not has_permission(user, "consultations:write"):
        return forbidden(request, doctor.full_name, "Tu rol no puede registrar consultas.")

    patient = await db.get(Patient, patient_id)
    if patient is None:
        return templates.TemplateResponse(
            request, "not_found.html", {"doctor_name": doctor.full_name}, status_code=status.HTTP_404_NOT_FOUND
        )

    return templates.TemplateResponse(
        request,
        "consultation_form.html",
        {
            "doctor_name": doctor.full_name,
            "active": "pacientes",
            "patient": patient,
            "errors": {},
            "values": {"reason": "", "diagnosis": "", "notes": ""},
        },
    )


@router.post("/pacientes/{patient_id:int}/consulta", response_class=HTMLResponse)
async def consultation_submit(
    patient_id: int,
    request: Request,
    reason: str = Form(""),
    diagnosis: str = Form(""),
    notes: str = Form(""),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    doctor = await portal_staff(db, user)
    if not has_permission(user, "consultations:write"):
        return forbidden(request, doctor.full_name, "Tu rol no puede registrar consultas.")

    patient = await db.get(Patient, patient_id)
    if patient is None:
        return templates.TemplateResponse(
            request, "not_found.html", {"doctor_name": doctor.full_name}, status_code=status.HTTP_404_NOT_FOUND
        )

    reason = reason.strip()
    diagnosis = diagnosis.strip()
    notes = notes.strip()
    errors: dict[str, str] = {}
    if not REASON_MIN <= len(reason) <= REASON_MAX:
        errors["reason"] = f"Escribe el motivo de la consulta ({REASON_MIN} a {REASON_MAX} caracteres)."
    if not DIAGNOSIS_MIN <= len(diagnosis) <= DIAGNOSIS_MAX:
        errors["diagnosis"] = f"Escribe el diagnóstico ({DIAGNOSIS_MIN} a {DIAGNOSIS_MAX} caracteres)."
    if len(notes) > NOTES_MAX:
        errors["notes"] = f"Las notas no deben pasar de {NOTES_MAX} caracteres."

    if errors:
        return templates.TemplateResponse(
            request,
            "consultation_form.html",
            {
                "doctor_name": doctor.full_name,
                "active": "pacientes",
                "patient": patient,
                "errors": errors,
                "values": {"reason": reason, "diagnosis": diagnosis, "notes": notes},
            },
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    consultation = await create_consultation(
        db,
        doctor=doctor,
        patient=patient,
        reason=reason,
        diagnosis=diagnosis,
        notes=notes or None,
    )
    await write_audit_event(
        db,
        user=user,
        action="portal_create_consultation",
        entity_type="consultation",
        entity_id=consultation.id,
        request=request,
        detail=f"patient_id={patient.id}",
    )
    await db.commit()

    return RedirectResponse(
        f"/portal/pacientes/{patient.id}?creada={consultation.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
