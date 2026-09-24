"""Portal clínico del personal médico (HTML servido por el mismo backend).

Seguridad: cookie de sesión HttpOnly con el mismo JWT de la API, rol médico
validado en el servidor en cada petición, y bitácora de todos los accesos.
"""

from datetime import datetime, timezone
import re

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.db.session import get_db
from app.models.appointment import Appointment
from app.models.consultation import Consultation
from app.models.doctor import Doctor
from app.models.enums import AppointmentStatus, UserRole
from app.models.patient import Patient
from app.models.user import User
from app.portal import deps
from app.portal.labels import ROLE_LABELS
from app.portal.qr import qr_svg
from app.portal.templating import credential_context, templates
from app.services.appointments import create_appointment
from app.services.audit import write_audit_event
from app.services.consultations import create_consultation
from app.services.users import (
    CURP_PATTERN,
    EMAIL_PATTERN,
    USERNAME_PATTERN,
    AccountError,
    create_patient_account,
    password_policy_error,
)

router = APIRouter(prefix="/portal", tags=["Portal clínico"], include_in_schema=False)

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


def render_login(request: Request, *, error: str | None, username: str = "", code: int = 200) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "login.html",
        {"error": error, "username": username},
        status_code=code,
    )


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

    if user is None or not user.is_active or not verify_password(password, user.password_hash):
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

    if user.role is not UserRole.DOCTOR:
        await write_audit_event(
            db,
            user=user,
            action="portal_login_denied",
            entity_type="authentication",
            entity_id=user.id,
            request=request,
            detail=f"role={user.role.value}",
        )
        await db.commit()
        return render_login(
            request,
            error="Este portal es exclusivo del personal médico.",
            username=username.strip(),
            code=status.HTTP_403_FORBIDDEN,
        )

    token, expires_in = create_access_token(user.id, user.role)
    await write_audit_event(
        db,
        user=user,
        action="portal_login_success",
        entity_type="authentication",
        entity_id=user.id,
        request=request,
    )
    await db.commit()

    response = RedirectResponse("/portal", status_code=status.HTTP_303_SEE_OTHER)
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
    doctor = await doctor_profile(db, user)
    if doctor is None:
        return login_redirect()

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
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    user = await deps.current_doctor(request, db)
    if user is None:
        return login_redirect()
    doctor = await doctor_profile(db, user)
    if doctor is None:
        return login_redirect()

    patient = await db.get(Patient, patient_id)
    if patient is None:
        return templates.TemplateResponse(
            request, "not_found.html", {"doctor_name": doctor.full_name}, status_code=status.HTTP_404_NOT_FOUND
        )

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
        },
    )


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
    doctor = await doctor_profile(db, user)
    if doctor is None:
        return login_redirect()

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
    doctor = await doctor_profile(db, user)
    if doctor is None:
        return login_redirect()

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
    doctor = await doctor_profile(db, user)
    if doctor is None:
        return login_redirect()

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
            role_label=ROLE_LABELS[UserRole.PATIENT],
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
    doctor = await doctor_profile(db, user)
    if doctor is None:
        return login_redirect()

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
    doctor = await doctor_profile(db, user)
    if doctor is None:
        return login_redirect()

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
    doctor = await doctor_profile(db, user)
    if doctor is None:
        return login_redirect()

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
    doctor = await doctor_profile(db, user)
    if doctor is None:
        return login_redirect()

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
    doctor = await doctor_profile(db, user)
    if doctor is None:
        return login_redirect()

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
    doctor = await doctor_profile(db, user)
    if doctor is None:
        return login_redirect()

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
