from datetime import datetime, timezone

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.appointment import Appointment
from app.models.consultation import Consultation
from app.models.doctor import Doctor
from app.models.enums import AppointmentStatus, UserRole
from app.models.patient import Patient
from app.models.user import User


async def seed_demo_data() -> None:
    """Inserta datos ficticios idempotentes para la demostración local.

    Credenciales de demo:
    - paciente / Paciente123!
    - medico / Medico123!
    """
    async with SessionLocal() as db:
        patient_user = await db.scalar(select(User).where(User.username == "paciente"))
        if patient_user is None:
            patient_user = User(
                username="paciente",
                password_hash=hash_password("Paciente123!"),
                role=UserRole.PATIENT,
            )
            db.add(patient_user)
            await db.flush()

            patient = Patient(
                user_id=patient_user.id,
                full_name="José Antonio Matuz",
                curp="MAAJ010415HCSRRN09",
                blood_type="O+",
                emergency_contact="María Argueta · 961 123 4567",
            )
            db.add(patient)
        else:
            patient = await db.scalar(select(Patient).where(Patient.user_id == patient_user.id))

        doctor_user = await db.scalar(select(User).where(User.username == "medico"))
        if doctor_user is None:
            doctor_user = User(
                username="medico",
                password_hash=hash_password("Medico123!"),
                role=UserRole.DOCTOR,
            )
            db.add(doctor_user)
            await db.flush()

            doctor = Doctor(
                user_id=doctor_user.id,
                full_name="Dra. López Hernández",
                specialty="Medicina General",
            )
            db.add(doctor)
        else:
            doctor = await db.scalar(select(Doctor).where(Doctor.user_id == doctor_user.id))

        await db.flush()
        if patient is None or doctor is None:
            raise RuntimeError("No se pudieron preparar los datos demo")

        existing_consultation = await db.scalar(
            select(Consultation).where(Consultation.patient_id == patient.id).limit(1)
        )
        if existing_consultation is None:
            db.add(
                Consultation(
                    patient_id=patient.id,
                    doctor_id=doctor.id,
                    reason="Control de presión arterial",
                    diagnosis="Hipertensión arterial en control",
                    notes="Datos ficticios para la demostración académica.",
                )
            )

        existing_appointment = await db.scalar(
            select(Appointment).where(Appointment.patient_id == patient.id).limit(1)
        )
        if existing_appointment is None:
            db.add(
                Appointment(
                    patient_id=patient.id,
                    doctor_id=doctor.id,
                    specialty="Medicina General",
                    scheduled_at=datetime(2026, 9, 24, 16, 30, tzinfo=timezone.utc),
                    location="Consultorio 3",
                    status=AppointmentStatus.CONFIRMED,
                    checkin_code="A7K9M2",
                    notes="Control de hipertensión",
                )
            )
        elif not existing_appointment.checkin_code:
            # Rellena el código de check-in en bases creadas antes de la migración.
            existing_appointment.checkin_code = "A7K9M2"

        await db.commit()
