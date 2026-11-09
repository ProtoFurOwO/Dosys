"""Reinicia el expediente de demostración de ``demo.paciente``.

Uso (dentro del contenedor de la API):

    sudo docker exec -it dosys-api python scripts/demo_reset.py --reset
    sudo docker exec -it dosys-api python scripts/demo_reset.py --reset --live

Borra solo las citas, consultas, recetas, estudios, documentos y dispositivos
del paciente demo; conserva la cuenta y el resto de la base. Después crea un
recorrido listo para exponer: cita agendada, solicitud pendiente, consulta SOAP,
orden de laboratorio y nota firmada. Con ``--live`` la cita principal es de hoy,
nace confirmada y queda lista para el check-in con QR.
"""

import argparse
import asyncio
import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

# Permite ejecutar `python scripts/demo_reset.py` desde /app en el contenedor.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.appointment import Appointment
from app.models.consultation import Consultation
from app.models.device_transfer import DeviceTransfer
from app.models.doctor import Doctor
from app.models.document import Document
from app.models.enums import AppointmentStatus
from app.models.lab_study import LabStudy
from app.models.patient import Patient
from app.models.prescription import Prescription
from app.models.session_token import RefreshToken
from app.models.study_order import StudyOrder
from app.models.user import User
from app.models.user_device import UserDevice
from app.services.appointments import create_appointment
from app.services.consultations import create_consultation
from app.services.documents import document_path, store_document_bytes
from app.services.lab import create_orders
from app.services.reports import build_consultation_pdf

CLINIC_TZ = ZoneInfo("America/Mexico_City")


async def main(reset: bool, live: bool) -> None:
    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.username == "demo.paciente"))
        doctor_user = await db.scalar(select(User).where(User.username == "demo.medico"))
        if user is None or doctor_user is None:
            raise SystemExit("Faltan demo.paciente o demo.medico. Ejecuta el seed de la app primero.")
        patient = await db.scalar(select(Patient).where(Patient.user_id == user.id))
        doctor = await db.scalar(select(Doctor).where(Doctor.user_id == doctor_user.id))
        if patient is None or doctor is None:
            raise SystemExit("El paciente o el médico demo no tienen perfil clínico.")

        if not reset:
            print("Usa --reset para limpiar y recrear el recorrido de demo.")
            return

        for document in (
            await db.scalars(select(Document).where(Document.patient_id == patient.id))
        ).all():
            document_path(document).unlink(missing_ok=True)
            await db.delete(document)
        for prescription in (
            await db.scalars(select(Prescription).where(Prescription.patient_id == patient.id))
        ).all():
            await db.delete(prescription)
        for order in (
            await db.scalars(select(StudyOrder).where(StudyOrder.patient_id == patient.id))
        ).all():
            await db.delete(order)
        for consultation in (
            await db.scalars(select(Consultation).where(Consultation.patient_id == patient.id))
        ).all():
            await db.delete(consultation)
        for appointment in (
            await db.scalars(select(Appointment).where(Appointment.patient_id == patient.id))
        ).all():
            await db.delete(appointment)
        for model in (DeviceTransfer, RefreshToken, UserDevice):
            for row in (await db.scalars(select(model).where(model.user_id == user.id))).all():
                await db.delete(row)
        await db.flush()

        clinic_now = datetime.now(CLINIC_TZ)
        clinic_today = clinic_now.date()
        if live:
            # Cita de hoy, confirmada y con la ventana de check-in abierta.
            scheduled = (clinic_now + timedelta(minutes=20)).replace(
                second=0, microsecond=0
            )
            scheduled += timedelta(minutes=(-scheduled.minute) % 5)
            appointment_status = AppointmentStatus.CONFIRMED
            appointment_note = "Cita de demostración en vivo"
        else:
            target = clinic_today + timedelta(days=1)
            while target.weekday() == 6:
                target += timedelta(days=1)
            scheduled = datetime.combine(target, time(10, 0), tzinfo=CLINIC_TZ)
            appointment_status = AppointmentStatus.SCHEDULED
            appointment_note = "Cita de demostración"

        appointment = await create_appointment(
            db,
            patient=patient,
            doctor=doctor,
            specialty="Medicina General",
            scheduled_at=scheduled.astimezone(timezone.utc),
            location="Consultorio 3",
            room="Consultorio 3",
            notes=appointment_note,
            status=appointment_status,
        )
        consultation = await create_consultation(
            db,
            doctor=doctor,
            patient=patient,
            reason="Dolor de cabeza intenso desde hace 3 días",
            diagnosis="Cefalea tensional. Sin datos de alarma.",
            notes="Hidratación, descanso y control en 7 días.",
            blood_pressure="120/80",
            heart_rate=72,
            respiratory_rate=16,
            temperature_c=36.5,
            oxygen_saturation=98,
            weight_kg=70,
            height_cm=170,
            physical_exam="Paciente consciente, orientado, cardiopulmonar sin agregados, abdomen blando.",
        )
        study = await db.scalar(select(LabStudy).where(LabStudy.code == "biometria"))
        if study is not None:
            await create_orders(
                db,
                patient=patient,
                doctor=doctor,
                consultation_id=consultation.id,
                studies=[study],
                indications="Control de demostración",
            )

        pdf = build_consultation_pdf(
            patient_name=patient.full_name,
            patient_curp=patient.curp,
            doctor_name=doctor.full_name,
            specialty=doctor.specialty,
            created_at=datetime.now(timezone.utc),
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
        await store_document_bytes(
            db,
            patient=patient,
            uploader=doctor_user,
            title="Nota de consulta demo",
            category="informe",
            data=pdf,
            content_type="application/pdf",
            original_name="nota-consulta-demo.pdf",
        )

        request_target = clinic_today + timedelta(days=1)
        while request_target.weekday() == 6:
            request_target += timedelta(days=1)
        requested_at = datetime.combine(request_target, time(12, 30), tzinfo=CLINIC_TZ)
        await create_appointment(
            db,
            patient=patient,
            doctor=doctor,
            specialty="Medicina General",
            scheduled_at=requested_at.astimezone(timezone.utc),
            location="Por asignar",
            notes="Solicitud pendiente de confirmar",
            status=AppointmentStatus.REQUESTED,
        )
        await db.commit()

        print("Demo recreada:")
        print(f"  Modo: {'día en vivo' if live else 'histórico'}")
        print(f"  Paciente: {patient.full_name} (id {patient.id})")
        print(
            f"  Cita de hoy: {scheduled.isoformat(timespec='minutes')} "
            f"({appointment_status.value}) · /portal/citas/{appointment.id}"
        )
        print(f"  Solicitud pendiente: {requested_at.isoformat(timespec='minutes')}")
        print(f"  Consulta SOAP: id {consultation.id}")
        print("  Documento firmado: Nota de consulta demo")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="limpia y recrea el recorrido demo")
    parser.add_argument(
        "--live",
        action="store_true",
        help="crea la cita principal para hoy, confirmada y lista para check-in",
    )
    args = parser.parse_args()
    asyncio.run(main(args.reset, args.live))
