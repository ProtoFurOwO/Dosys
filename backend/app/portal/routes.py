"""Portal clínico del personal médico (HTML servido por el mismo backend).

Seguridad: cookie de sesión HttpOnly con el mismo JWT de la API, rol médico
validado en el servidor en cada petición, y bitácora de todos los accesos.
"""

from datetime import date, datetime, time, timedelta, timezone
import re
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.crypto import CryptoConfigError, public_key_fingerprint
from app.core.security import (
    TWO_FACTOR_PURPOSE,
    create_access_token,
    create_challenge_token,
    decode_token,
    verify_password,
)
from app.db.session import get_db
from app.models.appointment import Appointment
from app.models.audit_log import AuditLog
from app.models.consultation import Consultation
from app.models.doctor import Doctor
from app.models.document import Document
from app.models.enums import AppointmentStatus, StudyOrderStatus
from app.models.lab_study import LabStudy
from app.models.patient import Patient
from app.models.prescription import Prescription, PrescriptionItem
from app.models.study_order import StudyOrder
from app.models.user import User
from app.portal import deps
from app.portal.labels import ROLE_LABELS, action_label
from app.portal.qr import qr_svg
from app.portal.templating import credential_context, templates
from app.services import accounts, checkin, email, login_security, rate_limit, two_factor
from app.services.appointments import (
    AppointmentError,
    create_appointment,
    ensure_available,
    generate_checkin_code,
)
from app.services.audit import write_audit_event
from app.services.consultations import create_consultation
from app.services.documents import (
    CATEGORIES,
    DocumentError,
    document_path,
    human_size,
    store_document,
    store_document_bytes,
    verify_document,
)
from app.services.lab import LabError, complete_order, create_orders
from app.services.permissions import has_permission, permission_codes
from app.services.reports import build_consultation_pdf, build_prescription_pdf
from app.services.users import (
    CURP_PATTERN,
    EMAIL_PATTERN,
    USERNAME_PATTERN,
    AccountError,
    create_patient_account,
    password_policy_error,
    set_user_email,
)

router = APIRouter(prefix="/portal", tags=["Portal clínico"], include_in_schema=False)

TWO_FACTOR_COOKIE = "dosys_2fa"
REFRESH_COOKIE = "dosys_portal_refresh"

REASON_MIN, REASON_MAX = 3, 300
DIAGNOSIS_MIN, DIAGNOSIS_MAX = 3, 500
NOTES_MAX = 4000
CLINICAL_MAX = 2000
SPECIALTY_MIN, SPECIALTY_MAX = 3, 120
LOCATION_MIN, LOCATION_MAX = 3, 160

STATUS_LABELS = {
    AppointmentStatus.SCHEDULED: "Agendada",
    AppointmentStatus.CONFIRMED: "Confirmada",
    AppointmentStatus.ATTENDED: "Atendida",
    AppointmentStatus.CANCELLED: "Cancelada",
}

BLOOD_TYPES = ("O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-")

BP_PATTERN = re.compile(r"^\d{2,3}/\d{2,3}$")


def _optional_int(
    raw: str, *, key: str, label: str, minimum: int, maximum: int, errors: dict[str, str]
) -> int | None:
    clean = raw.strip()
    if not clean:
        return None
    try:
        value = int(clean)
    except ValueError:
        errors[key] = f"{label}: usa un número entero."
        return None
    if not minimum <= value <= maximum:
        errors[key] = f"{label}: debe estar entre {minimum} y {maximum}."
        return None
    return value


def _optional_float(
    raw: str, *, key: str, label: str, minimum: float, maximum: float, errors: dict[str, str]
) -> float | None:
    clean = raw.strip()
    if not clean:
        return None
    try:
        value = float(clean)
    except ValueError:
        errors[key] = f"{label}: usa un número válido."
        return None
    if not minimum <= value <= maximum:
        errors[key] = f"{label}: debe estar entre {minimum:g} y {maximum:g}."
        return None
    return round(value, 2)


def _parse_vitals(values: dict[str, str], errors: dict[str, str]) -> dict:
    """Valida y convierte el bloque objetivo del SOAP."""
    blood_pressure = values["blood_pressure"].strip()
    if blood_pressure and not BP_PATTERN.match(blood_pressure):
        errors["blood_pressure"] = "Presión arterial: usa el formato 120/80."
    physical_exam = values["physical_exam"].strip()
    if len(physical_exam) > NOTES_MAX:
        errors["physical_exam"] = f"La exploración física no debe pasar de {NOTES_MAX} caracteres."
    return {
        "blood_pressure": blood_pressure or None,
        "heart_rate": _optional_int(
            values["heart_rate"], key="heart_rate", label="Frecuencia cardiaca", minimum=30, maximum=220, errors=errors
        ),
        "respiratory_rate": _optional_int(
            values["respiratory_rate"],
            key="respiratory_rate",
            label="Frecuencia respiratoria",
            minimum=5,
            maximum=80,
            errors=errors,
        ),
        "temperature_c": _optional_float(
            values["temperature_c"],
            key="temperature_c",
            label="Temperatura",
            minimum=30,
            maximum=45,
            errors=errors,
        ),
        "oxygen_saturation": _optional_int(
            values["oxygen_saturation"],
            key="oxygen_saturation",
            label="Saturación de oxígeno",
            minimum=50,
            maximum=100,
            errors=errors,
        ),
        "weight_kg": _optional_float(
            values["weight_kg"], key="weight_kg", label="Peso", minimum=1, maximum=400, errors=errors
        ),
        "height_cm": _optional_float(
            values["height_cm"], key="height_cm", label="Talla", minimum=30, maximum=250, errors=errors
        ),
        "physical_exam": physical_exam or None,
    }

ROOMS = ("Consultorio 1", "Consultorio 2", "Consultorio 3", "Consultorio 4")


def agenda_room_name(raw: str | None) -> str:
    """Normaliza la ubicación de una cita sin perder consultorios fuera de 1–4."""
    if not raw or not raw.strip():
        return "Sin consultorio"
    text = raw.strip()
    for room in ROOMS:
        if text.lower() == room.lower():
            return room
    match = re.search(r"consultorio\s*(\d+)", text, re.IGNORECASE)
    if match:
        return f"Consultorio {int(match.group(1))}"
    if "hospital" in text.lower():
        return "Sin consultorio"
    return text[:40]


STUDY_STATUS_LABELS = {
    StudyOrderStatus.REQUESTED: "Solicitado",
    StudyOrderStatus.IN_PROGRESS: "En proceso",
    StudyOrderStatus.COMPLETED: "Listo",
    StudyOrderStatus.CANCELLED: "Cancelado",
}


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


def render_login(
    request: Request,
    *,
    error: str | None,
    username: str = "",
    notice: str | None = None,
    code: int = 200,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "login.html",
        {"error": error, "username": username, "notice": notice},
        status_code=code,
    )


def set_session_cookie(
    response: RedirectResponse,
    token: str,
    expires_in: int,
    refresh_token: str | None = None,
) -> RedirectResponse:
    response.set_cookie(
        deps.COOKIE_NAME,
        token,
        max_age=expires_in,
        httponly=True,
        secure=settings.app_env != "development",
        samesite="lax",
        path="/portal",
    )
    if refresh_token:
        # Sesión renovable: permite seguir trabajando sin volver a pedir credenciales.
        response.set_cookie(
            REFRESH_COOKIE,
            refresh_token,
            max_age=settings.refresh_token_expire_days * 86400,
            httponly=True,
            secure=settings.app_env != "development",
            samesite="lax",
            path="/portal",
        )
    return response


# ── Sesión ────────────────────────────────────────────────────────────────────


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    restablecida: int = 0,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    if await deps.current_doctor(request, db) is not None:
        return RedirectResponse("/portal/inicio", status_code=status.HTTP_303_SEE_OTHER)

    # Sesión renovable: si el acceso expiró pero el token de renovación sigue
    # vivo, se emite un acceso nuevo sin pedir credenciales otra vez.
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    if refresh_token:
        rotated = await accounts.rotate_refresh_token(db, refresh_token)
        if rotated is not None:
            user, new_refresh, _device_hash = rotated
            await db.commit()
            token, expires_in = create_access_token(user.id, user.role.code, sorted(permission_codes(user)))
            response = RedirectResponse("/portal/inicio", status_code=status.HTTP_303_SEE_OTHER)
            return set_session_cookie(response, token, expires_in, new_refresh)

    notice = "Tu contraseña quedó actualizada. Inicia sesión con la nueva." if restablecida else None
    return render_login(request, error=None, notice=notice)


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    if rate_limit.exceeded("portal-login", request):
        return render_login(
            request,
            error="Demasiadas solicitudes desde esta red. Espera un minuto e intenta de nuevo.",
            username=username.strip(),
            code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    user = await accounts.find_user_by_identifier(db, username)

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
            code=status.HTTP_429_TOO_MANY_REQUESTS,
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
    refresh_token = await accounts.issue_refresh_token(db, user)
    await write_audit_event(
        db,
        user=user,
        action="portal_login_success",
        entity_type="authentication",
        entity_id=user.id,
        request=request,
    )
    await db.commit()

    return set_session_cookie(
        RedirectResponse("/portal/inicio", status_code=status.HTTP_303_SEE_OTHER), token, expires_in, refresh_token
    )


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
    refresh_token = await accounts.issue_refresh_token(db, user)
    await write_audit_event(
        db,
        user=user,
        action="login_2fa_success",
        entity_type="authentication",
        entity_id=user.id,
        request=request,
    )
    await db.commit()

    response = RedirectResponse("/portal/inicio", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(TWO_FACTOR_COOKIE, path="/portal")
    return set_session_cookie(response, token, expires_in, refresh_token)


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
    notice: str | None = None,
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
        "notice": notice,
        "username": user.username,
        "account_email": user.email,
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


@router.post("/seguridad/contrasena", response_class=HTMLResponse)
async def security_change_password(
    request: Request,
    current_password: str = Form(""),
    new_password: str = Form(""),
    new_password_confirm: str = Form(""),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Cambio de contraseña propio desde el portal."""
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    doctor = await portal_staff(db, user)

    try:
        await accounts.change_password(
            db,
            user,
            current=current_password,
            new=new_password,
            confirm=new_password_confirm,
        )
    except AccountError as error:
        return templates.TemplateResponse(
            request,
            "security.html",
            security_context(
                doctor.full_name,
                user=user,
                enabled=user.totp_enabled,
                remaining=await two_factor.recovery_codes_remaining(db, user) if user.totp_enabled else 0,
                error=str(error),
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    await write_audit_event(
        db,
        user=user,
        action="password_changed",
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
            enabled=user.totp_enabled,
            remaining=await two_factor.recovery_codes_remaining(db, user) if user.totp_enabled else 0,
            notice="Contraseña actualizada. Las sesiones renovables se cerraron por seguridad.",
        ),
    )


@router.post("/seguridad/correo", response_class=HTMLResponse)
async def security_update_email(
    request: Request,
    email: str = Form(""),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Registra el correo de la cuenta (sirve para recuperar la contraseña)."""
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    doctor = await portal_staff(db, user)

    try:
        await set_user_email(db, user, email)
    except AccountError as error:
        return templates.TemplateResponse(
            request,
            "security.html",
            security_context(
                doctor.full_name,
                user=user,
                enabled=user.totp_enabled,
                remaining=await two_factor.recovery_codes_remaining(db, user) if user.totp_enabled else 0,
                error=str(error),
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    await write_audit_event(
        db,
        user=user,
        action="account_email_updated",
        entity_type="user",
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
            enabled=user.totp_enabled,
            remaining=await two_factor.recovery_codes_remaining(db, user) if user.totp_enabled else 0,
            notice="Correo de la cuenta guardado.",
        ),
    )


@router.post("/salir")
async def logout(request: Request, db: AsyncSession = Depends(get_db)) -> RedirectResponse:
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    if refresh_token:
        await accounts.revoke_refresh_token(db, refresh_token)
        await db.commit()
    response = RedirectResponse("/portal/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(deps.COOKIE_NAME, path="/portal")
    response.delete_cookie(REFRESH_COOKIE, path="/portal")
    return response


# ── Recuperación de contraseña ────────────────────────────────────────────────


@router.get("/recuperar", response_class=HTMLResponse)
async def forgot_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "forgot.html", {"error": None, "identifier": ""}
    )


@router.post("/recuperar", response_class=HTMLResponse)
async def forgot_submit(
    request: Request,
    identifier: str = Form(""),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Genera un enlace de un solo uso; la respuesta no revela si la cuenta existe."""
    if rate_limit.exceeded("portal-forgot", request):
        return templates.TemplateResponse(
            request,
            "forgot.html",
            {
                "error": "Demasiadas solicitudes desde esta red. Espera un minuto e intenta de nuevo.",
                "identifier": identifier.strip(),
            },
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    user = await accounts.find_user_by_identifier(db, identifier)
    link: str | None = None
    destination = identifier.strip()
    send_error: str | None = None

    if user is not None and user.is_active:
        token = await accounts.create_password_reset(db, user)
        link = accounts.reset_link(token)
        destination = user.email or destination
        sent = False
        if user.email:
            sent, reason = await email.send_email(
                to=user.email,
                subject="D.O.S.Y.S · Restablece tu contraseña",
                text=(
                    "Recibimos una solicitud para restablecer tu contraseña.\n\n"
                    f"Abre este enlace (válido {settings.password_reset_expire_minutes} minutos):\n{link}\n\n"
                    "Si no fuiste tú, ignora este mensaje."
                ),
            )
            if not sent and email.delivery_enabled():
                send_error = reason
        if sent:
            link = None
        await write_audit_event(
            db,
            user=user,
            action="portal_password_reset_requested",
            entity_type="authentication",
            entity_id=user.id,
            request=request,
            detail=f"delivery={'email' if sent else 'simulated'}",
        )
        await db.commit()

    return templates.TemplateResponse(
        request,
        "email_reset.html",
        {
            "to": destination,
            "link": link,
            "minutes": settings.password_reset_expire_minutes,
            "sender": settings.email_from,
            "send_error": send_error,
        },
    )


@router.get("/restablecer", response_class=HTMLResponse)
async def reset_page(request: Request, token: str = "") -> HTMLResponse:
    return templates.TemplateResponse(request, "reset.html", {"error": None, "token": token})


@router.post("/restablecer", response_class=HTMLResponse)
async def reset_submit(
    request: Request,
    token: str = Form(""),
    password: str = Form(""),
    password_confirm: str = Form(""),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    policy_error = password_policy_error(password, password_confirm)
    if policy_error:
        return templates.TemplateResponse(
            request,
            "reset.html",
            {"error": policy_error, "token": token},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    user = await accounts.consume_password_reset(db, token)
    if user is None:
        return templates.TemplateResponse(
            request,
            "reset.html",
            {"error": "El enlace no es válido o ya expiró. Solicita uno nuevo.", "token": ""},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    await accounts.replace_password(db, user, new=password, confirm=password_confirm)
    await write_audit_event(
        db,
        user=user,
        action="password_reset",
        entity_type="authentication",
        entity_id=user.id,
        request=request,
    )
    await db.commit()
    return RedirectResponse("/portal/login?restablecida=1", status_code=status.HTTP_303_SEE_OTHER)


# ── Inicio clínico (dashboard por rol) ────────────────────────────────────────


@router.get("/inicio", response_class=HTMLResponse)
async def clinical_dashboard(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    """Vista de inicio distinta por rol: agenda, espera, laboratorio y actividad."""
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    doctor = await portal_staff(db, user)

    perms = request.state.permissions or set()
    can_patients = "patients:read" in perms
    can_appointments = "appointments:read" in perms
    can_consultations = "consultations:read" in perms
    can_studies = "studies:read" in perms
    can_audit = "audit:read" in perms
    can_users = "users:manage" in perms

    clinic_today = deps.clinic_now().date()
    day_start = datetime.combine(clinic_today, time.min, tzinfo=deps.CLINIC_TIMEZONE).astimezone(timezone.utc)
    day_end = datetime.combine(clinic_today, time.max, tzinfo=deps.CLINIC_TIMEZONE).astimezone(timezone.utc)
    now_utc = datetime.now(timezone.utc)

    appointments_today: list[dict] = []
    if can_appointments:
        rows = (
            await db.execute(
                select(Appointment, Patient, Doctor)
                .join(Patient, Appointment.patient_id == Patient.id)
                .outerjoin(Doctor, Appointment.doctor_id == Doctor.id)
                .where(Appointment.scheduled_at >= day_start, Appointment.scheduled_at <= day_end)
                .order_by(Appointment.scheduled_at.asc())
                .limit(30)
            )
        ).all()
        appointments_today = [
            {
                "id": appointment.id,
                "time": deps.format_time(appointment.scheduled_at),
                "patient_name": patient.full_name,
                "patient_id": patient.id,
                "specialty": appointment.specialty,
                "status": appointment.status.value,
                "status_label": STATUS_LABELS.get(appointment.status, appointment.status.value),
                "room": appointment.room or appointment.location,
                "checked_in": appointment.checked_in_at is not None,
            }
            for appointment, patient, _doctor in rows
        ]

    waiting: list[dict] = []
    if can_appointments:
        rows = (
            await db.execute(
                select(Appointment, Patient, Doctor)
                .join(Patient, Appointment.patient_id == Patient.id)
                .outerjoin(Doctor, Appointment.doctor_id == Doctor.id)
                .where(Appointment.checked_in_at.is_not(None), Appointment.status != AppointmentStatus.ATTENDED)
                .order_by(Appointment.checked_in_at.asc())
                .limit(20)
            )
        ).all()
        waiting = [
            {
                "id": appointment.id,
                "patient_name": patient.full_name,
                "patient_id": patient.id,
                "room": appointment.room or "Sin asignar",
                "specialty": appointment.specialty,
                "waited": max(0, int((now_utc - appointment.checked_in_at).total_seconds() // 60)),
                "checked_in": deps.format_time(appointment.checked_in_at),
            }
            for appointment, patient, _doctor in rows
        ]

    pending_studies: list[dict] = []
    if can_studies:
        rows = (
            await db.execute(
                select(StudyOrder, Patient, LabStudy)
                .join(Patient, StudyOrder.patient_id == Patient.id)
                .join(LabStudy, StudyOrder.study_id == LabStudy.id)
                .where(
                    StudyOrder.status.in_([StudyOrderStatus.REQUESTED, StudyOrderStatus.IN_PROGRESS])
                )
                .order_by(StudyOrder.requested_at.asc())
                .limit(12)
            )
        ).all()
        pending_studies = [
            {
                "id": order.id,
                "patient_name": patient.full_name,
                "patient_id": patient.id,
                "study": study.name,
                "status": order.status.value,
                "status_label": STUDY_STATUS_LABELS.get(order.status, order.status.value),
                "requested": deps.format_time(order.requested_at),
            }
            for order, patient, study in rows
        ]

    recent_consultations: list[dict] = []
    if can_consultations:
        rows = (
            await db.execute(
                select(Consultation, Patient, Doctor)
                .join(Patient, Consultation.patient_id == Patient.id)
                .join(Doctor, Consultation.doctor_id == Doctor.id)
                .order_by(Consultation.created_at.desc())
                .limit(6)
            )
        ).all()
        recent_consultations = [
            {
                "id": consultation.id,
                "patient_name": patient.full_name,
                "patient_id": patient.id,
                "diagnosis": consultation.diagnosis,
                "doctor_name": doctor_row.full_name,
                "at": deps.format_time(consultation.created_at),
            }
            for consultation, patient, doctor_row in rows
        ]

    recent_activity: list[dict] = []
    if can_audit:
        rows = (
            await db.execute(
                select(AuditLog, User)
                .outerjoin(User, AuditLog.user_id == User.id)
                .order_by(AuditLog.id.desc())
                .limit(8)
            )
        ).all()
        recent_activity = [
            {
                "label": action_label(log.action),
                "actor": actor.username if actor else "Sistema",
                "at": deps.format_time(log.created_at),
                "entity": log.entity_type,
            }
            for log, actor in rows
        ]

    stats = {
        "appointments": len(appointments_today),
        "waiting": len(waiting),
        "pending_studies": len(pending_studies),
        "consultations": 0,
        "patients": 0,
        "users": 0,
    }
    if can_consultations:
        stats["consultations"] = (
            await db.scalar(
                select(func.count(Consultation.id)).where(Consultation.created_at >= day_start)
            )
            or 0
        )
    if can_patients:
        stats["patients"] = await db.scalar(select(func.count(Patient.id))) or 0
    if can_users:
        stats["users"] = await db.scalar(select(func.count(User.id))) or 0

    hour = deps.clinic_now().hour
    if hour < 12:
        greeting = "Buenos días"
    elif hour < 19:
        greeting = "Buenas tardes"
    else:
        greeting = "Buenas noches"

    await write_audit_event(
        db,
        user=user,
        action="portal_read_dashboard",
        entity_type="system",
        entity_id=None,
        request=request,
    )
    await db.commit()

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "doctor_name": doctor.full_name,
            "active": "inicio",
            "greeting": greeting,
            "today_label": deps.format_date(deps.clinic_now()),
            "role_name": request.state.role_name,
            "appointments_today": appointments_today,
            "waiting": waiting,
            "pending_studies": pending_studies,
            "recent_consultations": recent_consultations,
            "recent_activity": recent_activity,
            "stats": stats,
            "can_patients": can_patients,
            "can_appointments": can_appointments,
            "can_consultations": can_consultations,
            "can_studies": can_studies,
            "can_audit": can_audit,
            "can_users": can_users,
            "can_write_patients": "patients:write" in perms,
            "can_write_appointments": "appointments:write" in perms,
            "can_perform_studies": "studies:perform" in perms,
        },
    )


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
    actualizado: int = 0,
    editada: int | None = None,
    estudio: int | None = None,
    estudio_error: str | None = None,
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
            "blood_pressure": consultation.blood_pressure,
            "heart_rate": consultation.heart_rate,
            "respiratory_rate": consultation.respiratory_rate,
            "temperature_c": consultation.temperature_c,
            "oxygen_saturation": consultation.oxygen_saturation,
            "weight_kg": consultation.weight_kg,
            "height_cm": consultation.height_cm,
            "physical_exam": consultation.physical_exam,
            "updated_at": consultation.updated_at,
        }
        for consultation, doctor_row in rows
    ]
    created = next((item for item in consultations if item["id"] == creada), None)
    edited = next((item for item in consultations if item["id"] == editada), None)

    # Separación de funciones: Recepción y Laboratorio ven los datos del paciente
    # y sus documentos, pero no el historial clínico salvo que tengan el permiso.
    can_read_consultations = has_permission(user, "consultations:read")
    can_write_consultations = has_permission(user, "consultations:write")
    is_doctor = isinstance(doctor, Doctor)
    can_write_patients = has_permission(user, "patients:write")
    can_write_appointments = has_permission(user, "appointments:write")
    can_request_studies = has_permission(user, "studies:request") and is_doctor
    if not can_read_consultations:
        consultations = []
        created = None
        edited = None

    documents = (
        await db.scalars(
            select(Document).where(Document.patient_id == patient.id).order_by(Document.created_at.desc())
        )
    ).all()

    study_orders = []
    if has_permission(user, "studies:read"):
        study_orders = list(
            (
                await db.scalars(
                    select(StudyOrder)
                    .where(StudyOrder.patient_id == patient.id)
                    .order_by(StudyOrder.requested_at.desc())
                    .limit(15)
                )
            ).all()
        )
    prescriptions = []
    if has_permission(user, "prescriptions:read"):
        prescriptions = list(
            (
                await db.scalars(
                    select(Prescription)
                    .where(Prescription.patient_id == patient.id)
                    .order_by(Prescription.created_at.desc())
                    .limit(15)
                )
            ).all()
        )

    studies_catalog: list[LabStudy] = []
    if can_request_studies:
        studies_catalog = list(
            (
                await db.scalars(
                    select(LabStudy)
                    .where(LabStudy.is_active.is_(True))
                    .order_by(LabStudy.name.asc())
                )
            ).all()
        )

    # Línea de tiempo clínica: solo roles con acceso al historial.
    timeline: list[dict] = []
    if can_read_consultations:
        for consultation in consultations:
            timeline.append(
                {
                    "kind": "consulta",
                    "at": consultation["created_at"],
                    "title": "Consulta médica",
                    "detail": consultation["diagnosis"],
                    "meta": f"{consultation['doctor_name']} · {consultation['specialty']}",
                    "url": f"/portal/pacientes/{patient.id}",
                }
            )
        for order in study_orders:
            timeline.append(
                {
                    "kind": "estudio",
                    "at": order.performed_at or order.requested_at,
                    "title": order.study.name if order.study else "Estudio",
                    "detail": STUDY_STATUS_LABELS.get(order.status, order.status.value),
                    "meta": "Resultado de laboratorio" if order.performed_at else "Orden solicitada",
                    "url": (
                        f"/portal/documentos/{order.document_id}/archivo"
                        if order.document_id
                        else "/portal/laboratorio"
                    ),
                }
            )
        for prescription in prescriptions:
            timeline.append(
                {
                    "kind": "receta",
                    "at": prescription.created_at,
                    "title": "Receta médica",
                    "detail": f"{len(prescription.items)} medicamento(s)",
                    "meta": "Documento firmado con SHA-256",
                    "url": (
                        f"/portal/documentos/{prescription.document_id}/archivo"
                        if prescription.document_id
                        else None
                    ),
                }
            )
        linked_documents = {order.document_id for order in study_orders if order.document_id}
        linked_documents |= {
            prescription.document_id for prescription in prescriptions if prescription.document_id
        }
        category_labels = dict(CATEGORIES)
        for document in documents:
            if document.id in linked_documents:
                continue
            timeline.append(
                {
                    "kind": "documento",
                    "at": document.created_at,
                    "title": document.title,
                    "detail": category_labels.get(document.category, document.category),
                    "meta": "Documento del expediente",
                    "url": f"/portal/documentos/{document.id}/archivo",
                }
            )
        timeline.sort(key=lambda item: item["at"], reverse=True)

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
            "edited": edited,
            "actualizado": actualizado,
            "estudio": estudio,
            "estudio_error": estudio_error,
            "can_read_consultations": can_read_consultations,
            "can_write_consultations": can_write_consultations,
            "can_edit_consultations": can_write_consultations and is_doctor,
            "is_doctor": is_doctor,
            "can_request_studies": can_request_studies,
            "can_write_patients": can_write_patients,
            "can_write_appointments": can_write_appointments,
            "locked": login_security.is_locked(account) if account else False,
            "lock_minutes": login_security.lock_minutes_left(account) if account else 0,
            "totp_enabled": bool(account.totp_enabled) if account else False,
            "timeline": timeline,
            "documents": documents,
            "categories": CATEGORIES,
            "documento": documento,
            "documento_error": documento_error,
            "study_orders": study_orders,
            "studies_catalog": studies_catalog,
            "study_status_labels": STUDY_STATUS_LABELS,
            "prescriptions": prescriptions,
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
    q: str = "",
    creada: int | None = None,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    doctor = await portal_staff(db, user)
    if not has_permission(user, "appointments:read"):
        return forbidden(request, doctor.full_name, "Tu rol no puede consultar la agenda.")

    search = q.strip()
    query = select(Patient).order_by(Patient.full_name.asc())
    if search:
        pattern = f"%{search}%"
        query = query.where(or_(Patient.full_name.ilike(pattern), Patient.curp.ilike(pattern)))
    patients = list((await db.scalars(query)).all())

    pending_by_patient: dict[int, dict] = {}
    past_by_patient: dict[int, dict] = {}
    if patients:
        now = datetime.now(timezone.utc)
        rows = (
            await db.execute(
                select(Appointment, Doctor)
                .outerjoin(Doctor, Appointment.doctor_id == Doctor.id)
                .where(
                    Appointment.patient_id.in_([patient.id for patient in patients]),
                    Appointment.status.in_([AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED]),
                    Appointment.scheduled_at >= now,
                )
                .order_by(Appointment.scheduled_at.asc())
            )
        ).all()
        for appointment, doctor_row in rows:
            pending_by_patient.setdefault(
                appointment.patient_id,
                {
                    "id": appointment.id,
                    "specialty": appointment.specialty,
                    "doctor_name": doctor_row.full_name if doctor_row else None,
                    "scheduled_at": appointment.scheduled_at,
                    "location": appointment.location,
                    "status_label": STATUS_LABELS.get(appointment.status, appointment.status.value),
                    "checked_in_at": appointment.checked_in_at,
                },
            )

        # Historial: la última cita que ya pasó, para no confundirla con la próxima.
        past_rows = (
            await db.execute(
                select(Appointment, Doctor)
                .outerjoin(Doctor, Appointment.doctor_id == Doctor.id)
                .where(
                    Appointment.patient_id.in_([patient.id for patient in patients]),
                    or_(
                        Appointment.scheduled_at < now,
                        Appointment.status.in_([AppointmentStatus.ATTENDED, AppointmentStatus.CANCELLED]),
                    ),
                )
                .order_by(Appointment.scheduled_at.desc())
            )
        ).all()
        for appointment, doctor_row in past_rows:
            past_by_patient.setdefault(
                appointment.patient_id,
                {
                    "id": appointment.id,
                    "specialty": appointment.specialty,
                    "doctor_name": doctor_row.full_name if doctor_row else None,
                    "scheduled_at": appointment.scheduled_at,
                    "location": appointment.location,
                    "status_label": STATUS_LABELS.get(appointment.status, appointment.status.value),
                },
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

    return templates.TemplateResponse(
        request,
        "appointments.html",
        {
            "doctor_name": doctor.full_name,
            "active": "citas",
            "patients": patients,
            "pending": pending_by_patient,
            "past": past_by_patient,
            "search": search,
            "created_id": creada,
        },
    )


# ── Agenda visual (calendario por consultorios y semanal) ────────────────────

DIAS_SEMANA = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
DIAS_CORTO = ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")
AGENDA_TIME_SLOTS = [f"{hour:02d}:{minute:02d}" for hour in range(8, 20) for minute in (0, 30)]


@router.get("/agenda", response_class=HTMLResponse)
async def agenda_page(
    request: Request,
    fecha: str = "",
    vista: str = "consultorios",
    doctor_id: int = 0,
    consultorio: str = "",
    estado: str = "",
    aviso: str = "",
    error: str = "",
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    doctor = await portal_staff(db, user)
    if not has_permission(user, "appointments:read"):
        return forbidden(request, doctor.full_name, "Tu rol no puede consultar la agenda.")

    today_date = deps.clinic_now().date()
    try:
        current_date = datetime.strptime(fecha, "%Y-%m-%d").date() if fecha else today_date
    except ValueError:
        current_date = today_date

    if vista == "consultorios":
        vista = "tablero"
    elif vista not in ("tablero", "cuadricula", "semana"):
        vista = "tablero"

    # Rango de la semana (Lunes a Domingo)
    week_start_date = current_date - timedelta(days=current_date.weekday())
    week_end_date = week_start_date + timedelta(days=6)
    range_start = datetime.combine(week_start_date, time.min, tzinfo=deps.CLINIC_TIMEZONE).astimezone(timezone.utc)
    range_end = datetime.combine(week_end_date, time.max, tzinfo=deps.CLINIC_TIMEZONE).astimezone(timezone.utc)

    # Días de la semana estructurados
    week_days = []
    for i in range(7):
        d = week_start_date + timedelta(days=i)
        week_days.append({
            "date": d,
            "date_str": d.isoformat(),
            "day_name": DIAS_SEMANA[i],
            "day_short": DIAS_CORTO[i],
            "day_number": d.day,
            "month_name": deps.MESES[d.month - 1],
            "is_today": d == today_date,
            "is_selected": d == current_date,
            "appointment_count": 0,
        })

    # Navegación
    if vista == "semana":
        prev_date_str = (current_date - timedelta(days=7)).isoformat()
        next_date_str = (current_date + timedelta(days=7)).isoformat()
    else:
        prev_date_str = (current_date - timedelta(days=1)).isoformat()
        next_date_str = (current_date + timedelta(days=1)).isoformat()

    # Catálogos para filtros y modal
    doctors = list((await db.scalars(select(Doctor).order_by(Doctor.full_name.asc()))).all())
    patients = list((await db.scalars(select(Patient).order_by(Patient.full_name.asc()))).all())

    # Consulta de citas
    query = (
        select(Appointment, Patient, Doctor)
        .join(Patient, Appointment.patient_id == Patient.id)
        .outerjoin(Doctor, Appointment.doctor_id == Doctor.id)
        .where(
            Appointment.scheduled_at >= range_start,
            Appointment.scheduled_at <= range_end,
        )
    )

    if doctor_id:
        query = query.where(Appointment.doctor_id == doctor_id)
    if consultorio:
        query = query.where(
            or_(
                Appointment.room == consultorio,
                and_(Appointment.room.is_(None), Appointment.location == consultorio),
            )
        )
    if estado:
        try:
            status_enum = AppointmentStatus(estado)
            query = query.where(Appointment.status == status_enum)
        except ValueError:
            pass

    query = query.order_by(Appointment.scheduled_at.asc())
    rows = (await db.execute(query)).all()

    appointments_list = []
    status_counts = {
        "total": 0,
        "scheduled": 0,
        "confirmed": 0,
        "attended": 0,
        "cancelled": 0,
    }

    day_counts: dict[str, int] = {d["date_str"]: 0 for d in week_days}
    room_names = list(ROOMS)

    for appointment, patient, doctor_row in rows:
        local_dt = deps._local(appointment.scheduled_at)
        apt_date = local_dt.date()
        apt_date_str = apt_date.isoformat()
        slot_minute = 0 if local_dt.minute < 30 else 30
        slot_key = f"{local_dt.hour:02d}:{slot_minute:02d}"

        raw_room = appointment.room or appointment.location
        room_name = agenda_room_name(raw_room)
        if room_name not in room_names:
            room_names.append(room_name)

        words = patient.full_name.split()
        initials = "".join(w[0] for w in words[:2]).upper() if words else "P"

        apt_dict = {
            "id": appointment.id,
            "patient_id": patient.id,
            "patient_name": patient.full_name,
            "patient_initials": initials,
            "patient_curp": patient.curp,
            "doctor_id": doctor_row.id if doctor_row else None,
            "doctor_name": doctor_row.full_name if doctor_row else "Sin médico asignado",
            "specialty": appointment.specialty,
            "location": appointment.location,
            "room": room_name,
            "status": appointment.status.value,
            "status_label": STATUS_LABELS.get(appointment.status, appointment.status.value),
            "scheduled_at": appointment.scheduled_at,
            "time_str": local_dt.strftime("%H:%M"),
            "date_str": apt_date_str,
            "slot_key": slot_key,
            "checkin_code": appointment.checkin_code,
            "checked_in_at": appointment.checked_in_at,
            "checked_in_label": deps.format_time(appointment.checked_in_at) if appointment.checked_in_at else None,
            "notes": appointment.notes or "",
        }
        appointments_list.append(apt_dict)

        if apt_date_str in day_counts:
            day_counts[apt_date_str] += 1

        st = appointment.status.value
        if st in status_counts:
            status_counts[st] += 1
        status_counts["total"] += 1

    for d in week_days:
        d["appointment_count"] = day_counts.get(d["date_str"], 0)

    preferred_rooms = [room for room in ROOMS if room in room_names]
    extra_rooms = sorted(
        room for room in room_names if room not in ROOMS and room != "Sin consultorio"
    )
    room_names = preferred_rooms + extra_rooms
    if "Sin consultorio" in room_names:
        room_names.append("Sin consultorio")

    # Citas del día seleccionado organizadas por consultorio (para la vista de Tablero)
    room_appointments = {room: [] for room in room_names}
    today_appointments = []
    for apt in appointments_list:
        if apt["date_str"] == current_date.isoformat():
            today_appointments.append(apt)
            room = apt["room"]
            if room in room_appointments:
                room_appointments[room].append(apt)

    for r in room_names:
        room_appointments[r].sort(key=lambda a: a["time_str"])
    today_appointments.sort(key=lambda a: a["time_str"])

    # Grilla por consultorios (matriz de horarios)
    grid_consultorios = {slot: {room: [] for room in room_names} for slot in AGENDA_TIME_SLOTS}
    for apt in appointments_list:
        if apt["date_str"] == current_date.isoformat():
            slot = apt["slot_key"]
            room = apt["room"]
            if slot in grid_consultorios and room in grid_consultorios[slot]:
                grid_consultorios[slot][room].append(apt)

    # Grilla semanal (para los 7 días de la semana)
    grid_week = {slot: {day["date_str"]: [] for day in week_days} for slot in AGENDA_TIME_SLOTS}
    for apt in appointments_list:
        slot = apt["slot_key"]
        day_str = apt["date_str"]
        if slot in grid_week and day_str in grid_week[slot]:
            grid_week[slot][day_str].append(apt)

    await write_audit_event(
        db,
        user=user,
        action="portal_read_agenda",
        entity_type="appointment",
        entity_id=None,
        request=request,
        detail=f"date={current_date.isoformat()} view={vista}",
    )
    await db.commit()

    return templates.TemplateResponse(
        request,
        "agenda.html",
        {
            "doctor_name": doctor.full_name,
            "active": "agenda",
            "current_date": current_date,
            "current_date_str": current_date.isoformat(),
            "today_date_str": today_date.isoformat(),
            "vista": vista,
            "week_days": week_days,
            "week_start_date": week_start_date,
            "week_end_date": week_end_date,
            "prev_date_str": prev_date_str,
            "next_date_str": next_date_str,
            "time_slots": AGENDA_TIME_SLOTS,
            "rooms": room_names,
            "room_appointments": room_appointments,
            "today_appointments": today_appointments,
            "grid_consultorios": grid_consultorios,
            "grid_week": grid_week,
            "doctors": doctors,
            "patients": patients,
            "selected_doctor_id": doctor_id,
            "selected_consultorio": consultorio,
            "selected_estado": estado,
            "status_counts": status_counts,
            "can_write_appointments": has_permission(user, "appointments:write"),
            "aviso": aviso,
            "error": error,
        },
    )


@router.post("/agenda/citas/{appointment_id:int}/estado", response_class=RedirectResponse)
async def agenda_update_status(
    appointment_id: int,
    request: Request,
    nuevo_estado: str = Form(...),
    nuevo_consultorio: str = Form(""),
    fecha: str = Form(""),
    vista: str = Form("consultorios"),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    staff = await portal_staff(db, user)
    if not has_permission(user, "appointments:write"):
        return forbidden(request, staff.full_name, "Tu rol no puede modificar citas.")

    appointment = await db.get(Appointment, appointment_id)
    if appointment is None:
        return RedirectResponse(
            f"/portal/agenda?fecha={fecha}&vista={vista}&error=Cita+no+encontrada",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    try:
        status_enum = AppointmentStatus(nuevo_estado)
    except ValueError:
        return RedirectResponse(
            f"/portal/agenda?fecha={fecha}&vista={vista}&error=Estado+no+válido",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    room_value = nuevo_consultorio.strip()
    if room_value:
        if len(room_value) > 40:
            return RedirectResponse(
                f"/portal/agenda?fecha={fecha}&vista={vista}&error=Consultorio+demasiado+largo",
                status_code=status.HTTP_303_SEE_OTHER,
            )
        valid_rooms = {agenda_room_name(room) for room in ROOMS}
        valid_rooms.add(agenda_room_name(appointment.room))
        valid_rooms.add(agenda_room_name(appointment.location))
        db_rooms = (
            await db.scalars(
                select(Appointment.room).where(Appointment.room.is_not(None)).distinct()
            )
        ).all()
        db_locations = (
            await db.scalars(
                select(Appointment.location).where(Appointment.location.is_not(None)).distinct()
            )
        ).all()
        for raw in list(db_rooms) + list(db_locations):
            if raw and raw.strip():
                valid_rooms.add(raw.strip()[:40])
                valid_rooms.add(agenda_room_name(raw))
        if room_value not in valid_rooms:
            return RedirectResponse(
                f"/portal/agenda?fecha={fecha}&vista={vista}&error=Consultorio+no+válido",
                status_code=status.HTTP_303_SEE_OTHER,
            )

    appointment.status = status_enum
    if room_value:
        appointment.room = room_value
        appointment.location = room_value

    if status_enum == AppointmentStatus.ATTENDED and appointment.checked_in_at is None:
        appointment.checked_in_at = datetime.now(timezone.utc)

    await write_audit_event(
        db,
        user=user,
        action="portal_update_appointment_status",
        entity_type="appointment",
        entity_id=appointment.id,
        request=request,
        detail=f"status={status_enum.value} room={appointment.room}",
    )
    await db.commit()

    label = STATUS_LABELS.get(status_enum, status_enum.value)
    return RedirectResponse(
        f"/portal/agenda?fecha={fecha}&vista={vista}&aviso=Cita+actualizada+a+{quote(label)}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/citas/{appointment_id:int}", response_class=HTMLResponse)
async def appointment_qr_page(
    appointment_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    doctor = await portal_staff(db, user)
    if not has_permission(user, "appointments:read"):
        return forbidden(request, doctor.full_name, "Tu rol no puede consultar la agenda.")

    row = (
        await db.execute(
            select(Appointment, Patient, Doctor)
            .join(Patient, Appointment.patient_id == Patient.id)
            .outerjoin(Doctor, Appointment.doctor_id == Doctor.id)
            .where(Appointment.id == appointment_id)
        )
    ).first()
    if row is None:
        return templates.TemplateResponse(
            request, "not_found.html", {"doctor_name": doctor.full_name}, status_code=status.HTTP_404_NOT_FOUND
        )

    appointment, patient, doctor_row = row
    code = appointment.checkin_code
    if not code:
        # Citas antiguas creadas antes del check-in: se habilita al abrir el QR.
        appointment.checkin_code = generate_checkin_code()
        await db.flush()
        code = appointment.checkin_code

    window = checkin.window_for(appointment)
    if appointment.status == AppointmentStatus.CANCELLED:
        workflow_step = 0
    elif appointment.status == AppointmentStatus.ATTENDED:
        workflow_step = 4
    elif appointment.checked_in_at is not None:
        workflow_step = 3
    elif appointment.status == AppointmentStatus.CONFIRMED:
        workflow_step = 2
    else:
        workflow_step = 1
    await write_audit_event(
        db,
        user=user,
        action="portal_read_checkin_qr",
        entity_type="appointment",
        entity_id=appointment.id,
        request=request,
        detail=f"patient_id={patient.id}",
    )
    await db.commit()

    return templates.TemplateResponse(
        request,
        "appointment_qr.html",
        {
            "doctor_name": doctor.full_name,
            "active": "citas",
            "appointment": appointment,
            "patient": patient,
            "attending": doctor_row,
            "status_label": STATUS_LABELS.get(appointment.status, appointment.status.value),
            "workflow_step": workflow_step,
            "checkin_code": code,
            "qr_svg": qr_svg(f"DOSYS-CHECKIN|{appointment.id}|{code}") if code else None,
            "checkin_window": window,
            "checkin_label": window.label(),
            "checkin_error": checkin.check_in_error(appointment),
            "rooms": ROOMS,
            "can_write_appointments": has_permission(user, "appointments:write"),
        },
    )


@router.get("/citas/{appointment_id:int}/estado")
async def appointment_checkin_state(
    appointment_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Estado del check-in para que la pantalla del QR se actualice sola."""
    user = await deps.current_doctor(request, db)
    if user is None:
        return JSONResponse({"detail": "Sesión requerida"}, status_code=status.HTTP_401_UNAUTHORIZED)
    if not has_permission(user, "appointments:read"):
        return JSONResponse({"detail": "Sin permiso"}, status_code=status.HTTP_403_FORBIDDEN)

    appointment = await db.get(Appointment, appointment_id)
    if appointment is None:
        return JSONResponse({"detail": "Cita no encontrada"}, status_code=status.HTTP_404_NOT_FOUND)

    window = checkin.window_for(appointment)
    return JSONResponse(
        {
            "checked_in": appointment.checked_in_at is not None,
            "checked_in_label": deps.format_time(appointment.checked_in_at) if appointment.checked_in_at else None,
            "status": appointment.status.value,
            "checkin_available": window.available,
            "checkin_label": window.label(),
            "checkin_reason": window.reason,
        }
    )


@router.post("/citas/{appointment_id:int}/check-in/revertir")
async def appointment_revert_checkin(
    appointment_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Reabre el check-in si recepción confirmó al paciente equivocado."""
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    doctor = await portal_staff(db, user)
    if not has_permission(user, "appointments:write"):
        return forbidden(request, doctor.full_name, "Tu rol no puede modificar el check-in.")

    appointment = await db.get(Appointment, appointment_id)
    if appointment is None:
        return RedirectResponse("/portal/citas", status_code=status.HTTP_303_SEE_OTHER)
    if appointment.checked_in_at is not None:
        appointment.checked_in_at = None
        if appointment.status == AppointmentStatus.CONFIRMED:
            appointment.status = AppointmentStatus.SCHEDULED
        await write_audit_event(
            db,
            user=user,
            action="portal_revert_checkin",
            entity_type="appointment",
            entity_id=appointment.id,
            request=request,
            detail=f"patient_id={appointment.patient_id}",
        )
        await db.commit()
    return RedirectResponse(f"/portal/citas/{appointment.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/citas/{appointment_id:int}/consultorio")
async def appointment_assign_room(
    appointment_id: int,
    request: Request,
    room: str = Form(""),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Recepción envía al paciente a un consultorio al confirmar la llegada."""
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    doctor = await portal_staff(db, user)
    if not has_permission(user, "appointments:write"):
        return forbidden(request, doctor.full_name, "Tu rol no puede modificar la agenda.")

    appointment = await db.get(Appointment, appointment_id)
    if appointment is None:
        return RedirectResponse("/portal/citas", status_code=status.HTTP_303_SEE_OTHER)

    clean = room.strip()
    appointment.room = clean if clean in ROOMS else None
    await write_audit_event(
        db,
        user=user,
        action="portal_assign_room",
        entity_type="appointment",
        entity_id=appointment.id,
        request=request,
        detail=f"room={appointment.room or 'sin asignar'}",
    )
    await db.commit()
    return RedirectResponse(f"/portal/citas/{appointment.id}", status_code=status.HTTP_303_SEE_OTHER)


# ── Sala de espera (el doctor ve quién llegó y a qué consultorio) ─────────────


def _waiting_query():
    return (
        select(Appointment, Patient, Doctor)
        .join(Patient, Appointment.patient_id == Patient.id)
        .outerjoin(Doctor, Appointment.doctor_id == Doctor.id)
        .where(Appointment.checked_in_at.is_not(None), Appointment.status != AppointmentStatus.ATTENDED)
        .order_by(Appointment.checked_in_at.asc())
    )


def _waiting_rows(rows) -> list[dict]:
    return [
        {
            "appointment_id": appointment.id,
            "patient_id": patient.id,
            "patient_name": patient.full_name,
            "curp": patient.curp,
            "room": appointment.room or "Sin asignar",
            "checked_in_label": deps.format_time(appointment.checked_in_at),
            "specialty": appointment.specialty,
            "doctor_name": doctor_row.full_name if doctor_row else None,
        }
        for appointment, patient, doctor_row in rows
    ]


@router.get("/en-espera", response_class=HTMLResponse)
async def waiting_room_page(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    doctor = await portal_staff(db, user)
    if not has_permission(user, "appointments:read"):
        return forbidden(request, doctor.full_name, "Tu rol no puede consultar la agenda.")

    rows = (await db.execute(_waiting_query())).all()
    return templates.TemplateResponse(
        request,
        "waiting_room.html",
        {
            "doctor_name": doctor.full_name,
            "active": "espera",
            "waiting": _waiting_rows(rows),
            "rooms": ROOMS,
            "can_write_consultations": has_permission(user, "consultations:write"),
        },
    )


@router.get("/en-espera/estado")
async def waiting_room_state(request: Request, db: AsyncSession = Depends(get_db)):
    """Lista viva de la sala de espera para que la pantalla se actualice sola."""
    user = await deps.current_doctor(request, db)
    if user is None:
        return JSONResponse({"detail": "Sesión requerida"}, status_code=status.HTTP_401_UNAUTHORIZED)
    if not has_permission(user, "appointments:read"):
        return JSONResponse({"detail": "Sin permiso"}, status_code=status.HTTP_403_FORBIDDEN)

    rows = (await db.execute(_waiting_query())).all()
    return JSONResponse({"waiting": _waiting_rows(rows)})


# ── Laboratorio (cola de órdenes y captura de resultados) ─────────────────────


LAB_PAGE_SIZE = 50


def _lab_search(query, search: str):
    if not search:
        return query
    pattern = f"%{search}%"
    return query.where(
        or_(
            Patient.full_name.ilike(pattern),
            Patient.curp.ilike(pattern),
            LabStudy.name.ilike(pattern),
        )
    )


async def _lab_context(
    db: AsyncSession,
    user: User,
    doctor_name: str,
    *,
    error: str | None = None,
    aviso: str | None = None,
    search: str = "",
    status_filter: str = "",
) -> dict:
    clean = search.strip()
    requested_statuses = {
        "": [StudyOrderStatus.REQUESTED, StudyOrderStatus.IN_PROGRESS],
        "pendientes": [StudyOrderStatus.REQUESTED, StudyOrderStatus.IN_PROGRESS],
        "solicitados": [StudyOrderStatus.REQUESTED],
        "en_proceso": [StudyOrderStatus.IN_PROGRESS],
    }
    done_statuses = {
        "": [StudyOrderStatus.COMPLETED, StudyOrderStatus.CANCELLED],
        "completados": [StudyOrderStatus.COMPLETED],
        "cancelados": [StudyOrderStatus.CANCELLED],
    }

    pending: list[dict] = []
    statuses = requested_statuses.get(status_filter)
    if statuses:
        query = _lab_search(
            select(StudyOrder, Patient, Doctor, LabStudy)
            .join(Patient, StudyOrder.patient_id == Patient.id)
            .join(Doctor, StudyOrder.doctor_id == Doctor.id)
            .join(LabStudy, StudyOrder.study_id == LabStudy.id)
            .where(StudyOrder.status.in_(statuses)),
            clean,
        ).order_by(StudyOrder.requested_at.asc()).limit(LAB_PAGE_SIZE)
        pending = [
            {
                "order": order,
                "patient": patient,
                "doctor": doctor_row,
                "study": study,
                "label": STUDY_STATUS_LABELS.get(order.status, order.status.value),
            }
            for order, patient, doctor_row, study in (await db.execute(query)).all()
        ]

    done: list[dict] = []
    statuses = done_statuses.get(status_filter)
    if statuses:
        query = _lab_search(
            select(StudyOrder, Patient, Doctor, LabStudy)
            .join(Patient, StudyOrder.patient_id == Patient.id)
            .join(Doctor, StudyOrder.doctor_id == Doctor.id)
            .join(LabStudy, StudyOrder.study_id == LabStudy.id)
            .where(StudyOrder.status.in_(statuses)),
            clean,
        ).order_by(StudyOrder.performed_at.desc().nullslast(), StudyOrder.requested_at.desc()).limit(LAB_PAGE_SIZE)
        done = [
            {
                "order": order,
                "patient": patient,
                "doctor": doctor_row,
                "study": study,
                "label": STUDY_STATUS_LABELS.get(order.status, order.status.value),
            }
            for order, patient, doctor_row, study in (await db.execute(query)).all()
        ]

    counts = {
        status.value: total
        for status, total in (
            await db.execute(select(StudyOrder.status, func.count(StudyOrder.id)).group_by(StudyOrder.status))
        ).all()
    }

    return {
        "doctor_name": doctor_name,
        "active": "laboratorio",
        "pending": pending,
        "done": done,
        "counts": counts,
        "search": clean,
        "status_filter": status_filter,
        "can_perform": has_permission(user, "studies:perform"),
        "can_view_patients": has_permission(user, "patients:read"),
        "error": error,
        "aviso": aviso,
    }


@router.get("/laboratorio", response_class=HTMLResponse)
async def laboratory_page(
    request: Request,
    aviso: str = "",
    q: str = "",
    estado: str = "",
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    doctor = await portal_staff(db, user)
    if not has_permission(user, "studies:read"):
        return forbidden(request, doctor.full_name, "Tu rol no puede consultar el laboratorio.")

    messages = {
        "resultado": "Resultado guardado y protegido con su huella SHA-256.",
        "cancelada": "Orden cancelada.",
        "iniciada": "Orden marcada como en proceso.",
    }
    context = await _lab_context(
        db,
        user,
        doctor.full_name,
        aviso=messages.get(aviso),
        search=q,
        status_filter=estado,
    )
    return templates.TemplateResponse(request, "laboratory.html", context)


@router.post("/laboratorio/{order_id:int}/iniciar")
async def laboratory_start(
    order_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    doctor = await portal_staff(db, user)
    if not has_permission(user, "studies:perform"):
        return forbidden(request, doctor.full_name, "Tu rol no puede iniciar estudios.")

    order = await db.get(StudyOrder, order_id)
    if order is None:
        return RedirectResponse("/portal/laboratorio", status_code=status.HTTP_303_SEE_OTHER)
    if order.status == StudyOrderStatus.REQUESTED:
        order.status = StudyOrderStatus.IN_PROGRESS
        await write_audit_event(
            db,
            user=user,
            action="portal_start_study_order",
            entity_type="study_order",
            entity_id=order.id,
            request=request,
            detail=f"patient_id={order.patient_id}",
        )
        await db.commit()
    return RedirectResponse("/portal/laboratorio?aviso=iniciada", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/laboratorio/{order_id:int}/completar", response_class=HTMLResponse)
async def laboratory_complete(
    order_id: int,
    request: Request,
    result_text: str = Form(""),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    doctor = await portal_staff(db, user)
    if not has_permission(user, "studies:perform"):
        return forbidden(request, doctor.full_name, "Tu rol no puede capturar resultados de estudios.")

    order = await db.get(StudyOrder, order_id)
    if order is None:
        return templates.TemplateResponse(
            request, "not_found.html", {"doctor_name": doctor.full_name}, status_code=status.HTTP_404_NOT_FOUND
        )

    try:
        document = await complete_order(db, order=order, performed_by=user, result_text=result_text)
    except LabError as err:
        context = await _lab_context(db, user, doctor.full_name, error=str(err))
        return templates.TemplateResponse(
            request, "laboratory.html", context, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )

    await write_audit_event(
        db,
        user=user,
        action="portal_complete_study_order",
        entity_type="study_order",
        entity_id=order.id,
        request=request,
        detail=f"patient_id={order.patient_id} document_id={document.id} sha256={document.sha256}",
    )
    await db.commit()
    return RedirectResponse("/portal/laboratorio?aviso=resultado", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/laboratorio/{order_id:int}/cancelar")
async def laboratory_cancel(
    order_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    doctor = await portal_staff(db, user)
    if not has_permission(user, "studies:perform"):
        return forbidden(request, doctor.full_name, "Tu rol no puede cancelar estudios.")

    order = await db.get(StudyOrder, order_id)
    if order is not None and order.status != StudyOrderStatus.COMPLETED:
        order.status = StudyOrderStatus.CANCELLED
        await write_audit_event(
            db,
            user=user,
            action="portal_cancel_study_order",
            entity_type="study_order",
            entity_id=order.id,
            request=request,
            detail=f"patient_id={order.patient_id}",
        )
        await db.commit()
    return RedirectResponse("/portal/laboratorio?aviso=cancelada", status_code=status.HTTP_303_SEE_OTHER)


# ── Registro y edición de pacientes ───────────────────────────────────────────


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
                "allergies": "",
                "medical_history": "",
                "chronic_conditions": "",
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
    allergies: str = Form(""),
    medical_history: str = Form(""),
    chronic_conditions: str = Form(""),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    doctor = await portal_staff(db, user)
    if not has_permission(user, "patients:write"):
        return forbidden(request, doctor.full_name, "Tu rol no puede registrar pacientes.")

    values = {
        "full_name": full_name.strip(),
        "curp": curp.strip().upper(),
        "birth_date": birth_date.strip(),
        "blood_type": blood_type.strip().upper(),
        "emergency_contact": emergency_contact.strip(),
        "email": email.strip().lower(),
        "username": username.strip().lower(),
        "allergies": allergies.strip(),
        "medical_history": medical_history.strip(),
        "chronic_conditions": chronic_conditions.strip(),
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
    if len(values["allergies"]) > CLINICAL_MAX:
        errors["allergies"] = f"Las alergias no deben pasar de {CLINICAL_MAX} caracteres."
    if len(values["medical_history"]) > CLINICAL_MAX:
        errors["medical_history"] = f"Los antecedentes no deben pasar de {CLINICAL_MAX} caracteres."
    if len(values["chronic_conditions"]) > CLINICAL_MAX:
        errors["chronic_conditions"] = f"Los diagnósticos crónicos no deben pasar de {CLINICAL_MAX} caracteres."
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
            allergies=values["allergies"] or None,
            medical_history=values["medical_history"] or None,
            chronic_conditions=values["chronic_conditions"] or None,
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
                "allergies": patient.allergies or "",
                "medical_history": patient.medical_history or "",
                "chronic_conditions": patient.chronic_conditions or "",
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
    allergies: str = Form(""),
    medical_history: str = Form(""),
    chronic_conditions: str = Form(""),
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
    values = {
        "full_name": full_name.strip(),
        "curp": patient.curp,
        "birth_date": birth_date.strip(),
        "blood_type": blood_type.strip().upper(),
        "emergency_contact": emergency_contact.strip(),
        "email": email.strip().lower(),
        "username": account.username if account else "",
        "allergies": allergies.strip(),
        "medical_history": medical_history.strip(),
        "chronic_conditions": chronic_conditions.strip(),
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
    if len(values["allergies"]) > CLINICAL_MAX:
        errors["allergies"] = f"Las alergias no deben pasar de {CLINICAL_MAX} caracteres."
    if len(values["medical_history"]) > CLINICAL_MAX:
        errors["medical_history"] = f"Los antecedentes no deben pasar de {CLINICAL_MAX} caracteres."
    if len(values["chronic_conditions"]) > CLINICAL_MAX:
        errors["chronic_conditions"] = f"Los diagnósticos crónicos no deben pasar de {CLINICAL_MAX} caracteres."

    if errors:
        return templates.TemplateResponse(
            request,
            "patient_form.html",
            patient_form_context(doctor.full_name, mode="edit", patient=patient, values=values, errors=errors),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    changes = []
    if patient.full_name != values["full_name"]:
        changes.append("full_name")
    if patient.birth_date != parsed_birth:
        changes.append("birth_date")
    if (patient.blood_type or "") != (values["blood_type"] or ""):
        changes.append("blood_type")
    if (patient.emergency_contact or "") != (values["emergency_contact"] or ""):
        changes.append("emergency_contact")
    if (patient.email or "") != (values["email"] or ""):
        changes.append("email")
    if (patient.allergies or "") != (values["allergies"] or ""):
        changes.append("allergies")
    if (patient.medical_history or "") != (values["medical_history"] or ""):
        changes.append("medical_history")
    if (patient.chronic_conditions or "") != (values["chronic_conditions"] or ""):
        changes.append("chronic_conditions")

    patient.full_name = values["full_name"]
    patient.birth_date = parsed_birth
    patient.blood_type = values["blood_type"] or None
    patient.emergency_contact = values["emergency_contact"] or None
    patient.email = values["email"] or None
    patient.allergies = values["allergies"] or None
    patient.medical_history = values["medical_history"] or None
    patient.chronic_conditions = values["chronic_conditions"] or None
    await db.flush()

    await write_audit_event(
        db,
        user=user,
        action="portal_update_patient",
        entity_type="patient",
        entity_id=patient.id,
        request=request,
        detail=f"campos={','.join(changes) if changes else 'sin_cambios'}",
    )
    await db.commit()

    return RedirectResponse(
        f"/portal/pacientes/{patient.id}?actualizado=1",
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

    verification = verify_document(document)
    intact, current_hash = verification.intact, verification.current_sha256
    patient = await db.get(Patient, document.patient_id)
    uploader = await db.get(User, document.uploaded_by_user_id) if document.uploaded_by_user_id else None
    try:
        fingerprint = public_key_fingerprint()
    except CryptoConfigError:
        fingerprint = ""

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
            "verification": verification,
            "public_key_fingerprint": fingerprint,
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
    if not has_permission(user, "appointments:read"):
        return forbidden(request, doctor.full_name, "Tu rol no puede consultar la agenda.")

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
    if not has_permission(user, "appointments:write"):
        return forbidden(request, doctor.full_name, "Tu rol no puede agendar citas.")
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

    try:
        appointment = await create_appointment(
            db,
            patient=patient,
            doctor=doctor,
            specialty=specialty,
            scheduled_at=scheduled_local.astimezone(timezone.utc),
            location=location,
            notes=notes or None,
        )
    except AppointmentError as error:
        return templates.TemplateResponse(
            request,
            "appointment_form.html",
            {
                "doctor_name": doctor.full_name,
                "active": "pacientes",
                "patient": patient,
                "errors": {"general": str(error)},
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
    cita: int = 0,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    doctor = await portal_staff(db, user)
    if not has_permission(user, "consultations:write"):
        return forbidden(request, doctor.full_name, "Tu rol no puede registrar consultas.")
    if not isinstance(doctor, Doctor):
        return forbidden(
            request,
            doctor.full_name,
            "Tu cuenta no tiene ficha de médico. Asigna el rol Médico a una cuenta con especialidad para registrar consultas.",
        )

    patient = await db.get(Patient, patient_id)
    if patient is None:
        return templates.TemplateResponse(
            request, "not_found.html", {"doctor_name": doctor.full_name}, status_code=status.HTTP_404_NOT_FOUND
        )

    appointment = await db.get(Appointment, cita) if cita else None
    if appointment is not None and appointment.patient_id != patient.id:
        appointment = None

    studies_catalog = list(
        (await db.scalars(select(LabStudy).where(LabStudy.is_active.is_(True)).order_by(LabStudy.name.asc()))).all()
    )
    default_reason = ""
    if appointment is not None:
        default_reason = appointment.notes or f"Consulta de {appointment.specialty}"

    return templates.TemplateResponse(
        request,
        "consultation_form.html",
        consultation_context(
            doctor.full_name,
            patient=patient,
            appointment=appointment,
            studies_catalog=studies_catalog,
            rooms=ROOMS,
            errors={},
            values=consultation_defaults(reason=default_reason),
            can_request_studies=has_permission(user, "studies:request") and isinstance(doctor, Doctor),
            can_write_prescriptions=has_permission(user, "prescriptions:write"),
            can_schedule=has_permission(user, "appointments:write"),
        ),
    )


PRESCRIPTION_MAX_ITEMS = 8


def consultation_defaults(**overrides) -> dict:
    values = {
        "reason": "",
        "diagnosis": "",
        "notes": "",
        "blood_pressure": "",
        "heart_rate": "",
        "respiratory_rate": "",
        "temperature_c": "",
        "oxygen_saturation": "",
        "weight_kg": "",
        "height_cm": "",
        "physical_exam": "",
        "study_ids": [],
        "requires_prescription": False,
        "recipe_items": [{"medication": "", "dose": "", "frequency": "", "duration": ""}],
        "prescription_notes": "",
        "next_enabled": False,
        "next_when": "",
        "next_specialty": "",
        "next_room": "",
    }
    values.update(overrides)
    return values


def consultation_context(
    doctor_name: str,
    *,
    patient: Patient,
    appointment: Appointment | None,
    studies_catalog: list[LabStudy],
    rooms: tuple[str, ...],
    errors: dict,
    values: dict,
    can_request_studies: bool,
    can_write_prescriptions: bool,
    can_schedule: bool,
) -> dict:
    return {
        "doctor_name": doctor_name,
        "active": "pacientes",
        "patient": patient,
        "appointment": appointment,
        "studies_catalog": studies_catalog,
        "rooms": rooms,
        "errors": errors,
        "values": values,
        "can_request_studies": can_request_studies,
        "can_write_prescriptions": can_write_prescriptions,
        "can_schedule": can_schedule,
    }


@router.post("/pacientes/{patient_id:int}/consulta", response_class=HTMLResponse)
async def consultation_submit(
    patient_id: int,
    request: Request,
    reason: str = Form(""),
    diagnosis: str = Form(""),
    notes: str = Form(""),
    blood_pressure: str = Form(""),
    heart_rate: str = Form(""),
    respiratory_rate: str = Form(""),
    temperature_c: str = Form(""),
    oxygen_saturation: str = Form(""),
    weight_kg: str = Form(""),
    height_cm: str = Form(""),
    physical_exam: str = Form(""),
    cita: int = Form(0),
    study_ids: list[int] = Form([]),
    requires_prescription: str = Form(""),
    medication: list[str] = Form([]),
    dose: list[str] = Form([]),
    frequency: list[str] = Form([]),
    duration: list[str] = Form([]),
    prescription_notes: str = Form(""),
    next_enabled: str = Form(""),
    next_when: str = Form(""),
    next_specialty: str = Form(""),
    next_room: str = Form(""),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    doctor = await portal_staff(db, user)
    if not has_permission(user, "consultations:write"):
        return forbidden(request, doctor.full_name, "Tu rol no puede registrar consultas.")
    if not isinstance(doctor, Doctor):
        return forbidden(
            request,
            doctor.full_name,
            "Tu cuenta no tiene ficha de médico. Asigna el rol Médico a una cuenta con especialidad para registrar consultas.",
        )

    patient = await db.get(Patient, patient_id)
    if patient is None:
        return templates.TemplateResponse(
            request, "not_found.html", {"doctor_name": doctor.full_name}, status_code=status.HTTP_404_NOT_FOUND
        )

    appointment = await db.get(Appointment, cita) if cita else None
    if appointment is not None and appointment.patient_id != patient.id:
        appointment = None

    reason = reason.strip()
    diagnosis = diagnosis.strip()
    notes = notes.strip()
    vital_values = {
        "blood_pressure": blood_pressure,
        "heart_rate": heart_rate,
        "respiratory_rate": respiratory_rate,
        "temperature_c": temperature_c,
        "oxygen_saturation": oxygen_saturation,
        "weight_kg": weight_kg,
        "height_cm": height_cm,
        "physical_exam": physical_exam,
    }
    errors: dict[str, str] = {}
    if not REASON_MIN <= len(reason) <= REASON_MAX:
        errors["reason"] = f"Escribe el motivo de la consulta ({REASON_MIN} a {REASON_MAX} caracteres)."
    if not DIAGNOSIS_MIN <= len(diagnosis) <= DIAGNOSIS_MAX:
        errors["diagnosis"] = f"Escribe el diagnóstico ({DIAGNOSIS_MIN} a {DIAGNOSIS_MAX} caracteres)."
    if len(notes) > NOTES_MAX:
        errors["notes"] = f"Las notas no deben pasar de {NOTES_MAX} caracteres."
    vitals = _parse_vitals(vital_values, errors)

    # Receta: cada fila capturada debe tener medicamento, dosis y frecuencia.
    items: list[dict] = []
    if requires_prescription:
        for med, item_dose, item_freq, item_duration in zip(medication, dose, frequency, duration):
            med, item_dose, item_freq, item_duration = med.strip(), item_dose.strip(), item_freq.strip(), item_duration.strip()
            if not (med or item_dose or item_freq or item_duration):
                continue
            if not (med and item_dose and item_freq):
                errors["prescription"] = "Cada medicamento necesita nombre, dosis y frecuencia."
                break
            items.append(
                {
                    "medication": med[:120],
                    "dose": item_dose[:80],
                    "frequency": item_freq[:80],
                    "duration": item_duration[:80] or None,
                }
            )
        if not items and "prescription" not in errors:
            errors["prescription"] = "Agrega al menos un medicamento a la receta."
        if len(items) > PRESCRIPTION_MAX_ITEMS:
            errors["prescription"] = f"Una receta admite hasta {PRESCRIPTION_MAX_ITEMS} medicamentos."

    # Estudios solicitados: la orden la firma una cuenta con ficha de médico.
    studies: list[LabStudy] = []
    if study_ids:
        if not has_permission(user, "studies:request"):
            errors["studies"] = "Tu rol no puede ordenar estudios."
        elif not isinstance(doctor, Doctor):
            errors["studies"] = "Solo una cuenta con ficha de médico puede ordenar estudios."
        else:
            studies = list(
                (
                    await db.scalars(
                        select(LabStudy).where(LabStudy.id.in_(study_ids), LabStudy.is_active.is_(True))
                    )
                ).all()
            )
            if not studies:
                errors["studies"] = "Los estudios seleccionados no están disponibles."

    # Próxima cita: se valida antes de crear nada para no dejar datos a medias.
    next_payload: dict | None = None
    if next_enabled:
        if not has_permission(user, "appointments:write"):
            errors["next"] = "Tu rol no puede agendar citas."
        else:
            try:
                naive = datetime.fromisoformat(next_when) if next_when else None
            except ValueError:
                naive = None
            if naive is None:
                errors["next"] = "Elige la fecha y hora de la próxima cita."
            else:
                scheduled_at = naive.replace(tzinfo=deps.CLINIC_TIMEZONE).astimezone(timezone.utc)
                clean_room = next_room.strip() if next_room.strip() in ROOMS else None
                doctor_obj = doctor if isinstance(doctor, Doctor) else None
                try:
                    await ensure_available(
                        db, patient=patient, doctor=doctor_obj, room=clean_room, scheduled_at=scheduled_at
                    )
                    next_payload = {
                        "doctor": doctor_obj,
                        "specialty": next_specialty.strip() or "Medicina General",
                        "scheduled_at": scheduled_at,
                        "room": clean_room,
                    }
                except AppointmentError as err:
                    errors["next"] = str(err)

    if errors:
        studies_catalog = list(
            (await db.scalars(select(LabStudy).where(LabStudy.is_active.is_(True)).order_by(LabStudy.name.asc()))).all()
        )
        values = consultation_defaults(
            reason=reason,
            diagnosis=diagnosis,
            notes=notes,
            blood_pressure=vital_values["blood_pressure"],
            heart_rate=vital_values["heart_rate"],
            respiratory_rate=vital_values["respiratory_rate"],
            temperature_c=vital_values["temperature_c"],
            oxygen_saturation=vital_values["oxygen_saturation"],
            weight_kg=vital_values["weight_kg"],
            height_cm=vital_values["height_cm"],
            physical_exam=vital_values["physical_exam"],
            study_ids=list(study_ids),
            requires_prescription=bool(requires_prescription),
            recipe_items=items
            or [
                {"medication": med, "dose": d, "frequency": f, "duration": du}
                for med, d, f, du in zip(medication, dose, frequency, duration)
            ]
            or consultation_defaults()["recipe_items"],
            prescription_notes=prescription_notes.strip(),
            next_enabled=bool(next_enabled),
            next_when=next_when,
            next_specialty=next_specialty,
            next_room=next_room,
        )
        return templates.TemplateResponse(
            request,
            "consultation_form.html",
            consultation_context(
                doctor.full_name,
                patient=patient,
                appointment=appointment,
                studies_catalog=studies_catalog,
                rooms=ROOMS,
                errors=errors,
                values=values,
                can_request_studies=has_permission(user, "studies:request") and isinstance(doctor, Doctor),
                can_write_prescriptions=has_permission(user, "prescriptions:write"),
                can_schedule=has_permission(user, "appointments:write"),
            ),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    consultation = await create_consultation(
        db,
        doctor=doctor,
        patient=patient,
        reason=reason,
        diagnosis=diagnosis,
        notes=notes or None,
        **vitals,
    )
    if appointment is not None:
        appointment.status = AppointmentStatus.ATTENDED
    consultation.appointment_id = appointment.id if appointment is not None else None

    await write_audit_event(
        db,
        user=user,
        action="portal_create_consultation",
        entity_type="consultation",
        entity_id=consultation.id,
        request=request,
        detail=f"patient_id={patient.id}",
    )

    if studies:
        orders = await create_orders(
            db,
            patient=patient,
            doctor=doctor,
            consultation_id=consultation.id,
            studies=studies,
            indications=notes or None,
        )
        await write_audit_event(
            db,
            user=user,
            action="portal_create_study_orders",
            entity_type="consultation",
            entity_id=consultation.id,
            request=request,
            detail=f"ordenes={len(orders)}",
        )

    if items and isinstance(doctor, Doctor):
        prescription = Prescription(
            patient_id=patient.id,
            doctor_id=doctor.id,
            consultation_id=consultation.id,
            notes=prescription_notes.strip()[:300] or None,
        )
        db.add(prescription)
        await db.flush()
        for item in items:
            db.add(PrescriptionItem(prescription_id=prescription.id, **item))
        await db.flush()

        pdf = build_prescription_pdf(
            patient_name=patient.full_name,
            patient_curp=patient.curp,
            doctor_name=doctor.full_name,
            notes=prescription.notes,
            items=items,
            created_at=datetime.now(timezone.utc),
        )
        document = await store_document_bytes(
            db,
            patient=patient,
            uploader=user,
            title=f"Receta médica · {deps.clinic_now().strftime('%d/%m/%Y')}",
            category="receta",
            data=pdf,
            content_type="application/pdf",
            original_name=f"receta-{prescription.id}.pdf",
        )
        prescription.document_id = document.id
        await write_audit_event(
            db,
            user=user,
            action="portal_create_prescription",
            entity_type="prescription",
            entity_id=prescription.id,
            request=request,
            detail=f"document_id={document.id}",
        )

    if next_payload is not None:
        next_appointment = await create_appointment(
            db,
            patient=patient,
            doctor=next_payload["doctor"],
            specialty=next_payload["specialty"],
            scheduled_at=next_payload["scheduled_at"],
            location=next_payload["room"] or "Consulta externa",
            notes="Próxima cita de seguimiento",
            room=next_payload["room"],
        )
        await write_audit_event(
            db,
            user=user,
            action="portal_schedule_next_appointment",
            entity_type="appointment",
            entity_id=next_appointment.id,
            request=request,
            detail=f"para={next_payload['scheduled_at'].isoformat(timespec='minutes')}",
        )

    await db.commit()

    return RedirectResponse(
        f"/portal/pacientes/{patient.id}?creada={consultation.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# ── Corrección de una consulta ya registrada ──────────────────────────────────


async def _consultation_for_patient(
    db: AsyncSession, patient_id: int, consultation_id: int
) -> Consultation | None:
    consultation = await db.get(Consultation, consultation_id)
    if consultation is None or consultation.patient_id != patient_id:
        return None
    return consultation


@router.get("/pacientes/{patient_id:int}/consulta/{consultation_id:int}/pdf")
async def consultation_pdf(
    patient_id: int,
    consultation_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Nota clínica SOAP imprimible; solo roles con acceso al historial."""
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    if not has_permission(user, "consultations:read"):
        return forbidden(request, user.username, "Tu rol no puede descargar notas clínicas.")

    patient = await db.get(Patient, patient_id)
    consultation = await _consultation_for_patient(db, patient_id, consultation_id)
    if patient is None or consultation is None:
        return templates.TemplateResponse(
            request, "not_found.html", {"doctor_name": user.username}, status_code=status.HTTP_404_NOT_FOUND
        )

    author = await db.get(Doctor, consultation.doctor_id)
    pdf = build_consultation_pdf(
        patient_name=patient.full_name,
        patient_curp=patient.curp,
        doctor_name=author.full_name if author else "Médico",
        specialty=author.specialty if author else "",
        created_at=consultation.created_at,
        reason=consultation.reason,
        diagnosis=consultation.diagnosis,
        notes=consultation.notes,
        blood_pressure=consultation.blood_pressure,
        heart_rate=consultation.heart_rate,
        respiratory_rate=consultation.respiratory_rate,
        temperature_c=consultation.temperature_c,
        oxygen_saturation=consultation.oxygen_saturation,
        weight_kg=consultation.weight_kg,
        height_cm=consultation.height_cm,
        physical_exam=consultation.physical_exam,
    )
    await write_audit_event(
        db,
        user=user,
        action="portal_download_consultation",
        entity_type="consultation",
        entity_id=consultation.id,
        request=request,
        detail=f"patient_id={patient.id}",
    )
    await db.commit()
    filename = quote(f"nota-consulta-{consultation.id}.pdf")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{filename}"},
    )


@router.get("/pacientes/{patient_id:int}/consulta/{consultation_id:int}/editar", response_class=HTMLResponse)
async def consultation_edit_page(
    patient_id: int,
    consultation_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    doctor = await portal_staff(db, user)
    if not has_permission(user, "consultations:write"):
        return forbidden(request, doctor.full_name, "Tu rol no puede corregir consultas.")
    if not isinstance(doctor, Doctor):
        return forbidden(
            request,
            doctor.full_name,
            "Tu cuenta no tiene ficha de médico. Solo un médico puede corregir una consulta.",
        )

    patient = await db.get(Patient, patient_id)
    consultation = await _consultation_for_patient(db, patient_id, consultation_id)
    if patient is None or consultation is None:
        return templates.TemplateResponse(
            request, "not_found.html", {"doctor_name": doctor.full_name}, status_code=status.HTTP_404_NOT_FOUND
        )

    author = await db.get(Doctor, consultation.doctor_id)
    return templates.TemplateResponse(
        request,
        "consultation_edit.html",
        {
            "doctor_name": doctor.full_name,
            "active": "pacientes",
            "patient": patient,
            "consultation": consultation,
            "author_name": author.full_name if author else "Médico",
            "errors": {},
            "values": {
                "reason": consultation.reason,
                "diagnosis": consultation.diagnosis,
                "notes": consultation.notes or "",
                "blood_pressure": consultation.blood_pressure or "",
                "heart_rate": "" if consultation.heart_rate is None else str(consultation.heart_rate),
                "respiratory_rate": "" if consultation.respiratory_rate is None else str(consultation.respiratory_rate),
                "temperature_c": "" if consultation.temperature_c is None else str(consultation.temperature_c),
                "oxygen_saturation": (
                    "" if consultation.oxygen_saturation is None else str(consultation.oxygen_saturation)
                ),
                "weight_kg": "" if consultation.weight_kg is None else str(consultation.weight_kg),
                "height_cm": "" if consultation.height_cm is None else str(consultation.height_cm),
                "physical_exam": consultation.physical_exam or "",
            },
        },
    )


@router.post(
    "/pacientes/{patient_id:int}/consulta/{consultation_id:int}/editar",
    response_class=HTMLResponse,
)
async def consultation_edit_submit(
    patient_id: int,
    consultation_id: int,
    request: Request,
    reason: str = Form(""),
    diagnosis: str = Form(""),
    notes: str = Form(""),
    blood_pressure: str = Form(""),
    heart_rate: str = Form(""),
    respiratory_rate: str = Form(""),
    temperature_c: str = Form(""),
    oxygen_saturation: str = Form(""),
    weight_kg: str = Form(""),
    height_cm: str = Form(""),
    physical_exam: str = Form(""),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    doctor = await portal_staff(db, user)
    if not has_permission(user, "consultations:write"):
        return forbidden(request, doctor.full_name, "Tu rol no puede corregir consultas.")
    if not isinstance(doctor, Doctor):
        return forbidden(
            request,
            doctor.full_name,
            "Tu cuenta no tiene ficha de médico. Solo un médico puede corregir una consulta.",
        )

    patient = await db.get(Patient, patient_id)
    consultation = await _consultation_for_patient(db, patient_id, consultation_id)
    if patient is None or consultation is None:
        return templates.TemplateResponse(
            request, "not_found.html", {"doctor_name": doctor.full_name}, status_code=status.HTTP_404_NOT_FOUND
        )

    reason = reason.strip()
    diagnosis = diagnosis.strip()
    notes = notes.strip()
    vital_values = {
        "blood_pressure": blood_pressure,
        "heart_rate": heart_rate,
        "respiratory_rate": respiratory_rate,
        "temperature_c": temperature_c,
        "oxygen_saturation": oxygen_saturation,
        "weight_kg": weight_kg,
        "height_cm": height_cm,
        "physical_exam": physical_exam,
    }
    errors: dict[str, str] = {}
    if not REASON_MIN <= len(reason) <= REASON_MAX:
        errors["reason"] = f"Escribe el motivo de la consulta ({REASON_MIN} a {REASON_MAX} caracteres)."
    if not DIAGNOSIS_MIN <= len(diagnosis) <= DIAGNOSIS_MAX:
        errors["diagnosis"] = f"Escribe el diagnóstico ({DIAGNOSIS_MIN} a {DIAGNOSIS_MAX} caracteres)."
    if len(notes) > NOTES_MAX:
        errors["notes"] = f"Las notas no deben pasar de {NOTES_MAX} caracteres."
    vitals = _parse_vitals(vital_values, errors)

    author = await db.get(Doctor, consultation.doctor_id)
    if errors:
        return templates.TemplateResponse(
            request,
            "consultation_edit.html",
            {
                "doctor_name": doctor.full_name,
                "active": "pacientes",
                "patient": patient,
                "consultation": consultation,
                "author_name": author.full_name if author else "Médico",
                "errors": errors,
                "values": {
                    "reason": reason,
                    "diagnosis": diagnosis,
                    "notes": notes,
                    **vital_values,
                },
            },
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    new_values = {
        "reason": reason,
        "diagnosis": diagnosis,
        "notes": notes or None,
        **vitals,
    }
    changes = [
        field for field, value in new_values.items() if getattr(consultation, field) != value
    ]

    if changes:
        for field, value in new_values.items():
            setattr(consultation, field, value)
        consultation.updated_at = datetime.now(timezone.utc)
        await db.flush()

    await write_audit_event(
        db,
        user=user,
        action="portal_update_consultation",
        entity_type="consultation",
        entity_id=consultation.id,
        request=request,
        detail=f"patient_id={patient.id} campos={','.join(changes) if changes else 'sin_cambios'}",
    )
    await db.commit()

    return RedirectResponse(
        f"/portal/pacientes/{patient.id}?editada={consultation.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/pacientes/{patient_id:int}/estudio-demo")
async def patient_demo_study(
    patient_id: int,
    request: Request,
    study_id: int = Form(0),
    indications: str = Form(""),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Crea una orden real para demostrar el flujo de laboratorio en clase.

    Queda auditada como cualquier otra orden: no genera datos falsos ni salta
    la cola del laboratorio.
    """
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    doctor = await portal_staff(db, user)
    if not has_permission(user, "studies:request"):
        return forbidden(request, doctor.full_name, "Tu rol no puede solicitar estudios.")
    if not isinstance(doctor, Doctor):
        return forbidden(
            request,
            doctor.full_name,
            "Solo una cuenta con ficha de médico puede solicitar estudios.",
        )

    patient = await db.get(Patient, patient_id)
    if patient is None:
        return RedirectResponse("/portal/pacientes", status_code=status.HTTP_303_SEE_OTHER)

    study = await db.get(LabStudy, study_id) if study_id else None
    if study is None or not study.is_active:
        return RedirectResponse(
            f"/portal/pacientes/{patient.id}?estudio_error=Elige+un+estudio+disponible",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    clean = indications.strip()[:200]
    orders = await create_orders(
        db,
        patient=patient,
        doctor=doctor,
        consultation_id=None,
        studies=[study],
        indications=clean or None,
    )
    order = orders[0]
    await write_audit_event(
        db,
        user=user,
        action="portal_create_demo_study_order",
        entity_type="study_order",
        entity_id=order.id,
        request=request,
        detail=f"patient_id={patient.id} study_id={study.id}",
    )
    await db.commit()

    return RedirectResponse(
        f"/portal/pacientes/{patient.id}?estudio={order.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
