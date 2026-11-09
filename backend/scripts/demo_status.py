"""Resumen del día de demostración de ``demo.paciente``.

Uso (dentro del contenedor de la API):

    sudo docker exec -it dosys-api python scripts/demo_status.py

No modifica nada. Sirve para verificar antes de presentar que la cita de hoy,
la solicitud pendiente, el laboratorio y los dispositivos están en el estado
esperado.
"""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.enums import StudyOrderStatus
from app.models.patient import Patient
from app.models.study_order import StudyOrder
from app.models.user import User
from app.models.user_device import UserDevice
from app.services import checkin

CLINIC_TZ = ZoneInfo("America/Mexico_City")


def local(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(CLINIC_TZ).strftime("%Y-%m-%d %H:%M")


async def main() -> None:
    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.username == "demo.paciente"))
        if user is None:
            raise SystemExit("No existe demo.paciente. Corre el seed primero.")
        patient = await db.scalar(select(Patient).where(Patient.user_id == user.id))
        if patient is None:
            raise SystemExit("demo.paciente no tiene perfil clínico.")

        now = datetime.now(timezone.utc)
        appointments = (
            await db.scalars(
                select(Appointment)
                .where(
                    Appointment.patient_id == patient.id,
                    Appointment.scheduled_at >= now - timedelta(days=1),
                )
                .order_by(Appointment.scheduled_at.asc())
            )
        ).all()
        devices = (
            await db.scalars(
                select(UserDevice)
                .where(UserDevice.user_id == user.id, UserDevice.is_active.is_(True))
                .order_by(UserDevice.id.asc())
            )
        ).all()
        pending_orders = (
            await db.scalars(
                select(StudyOrder).where(
                    StudyOrder.patient_id == patient.id,
                    StudyOrder.status.in_(
                        (StudyOrderStatus.REQUESTED, StudyOrderStatus.IN_PROGRESS)
                    ),
                )
            )
        ).all()

        print(f"Paciente: {patient.full_name} (@{user.username})")
        print(f"Dispositivos activos: {len(devices)}/3")
        for device in devices:
            print(f"  - {device.name} (id {device.id})")

        print("\nCitas próximas:")
        if not appointments:
            print("  (sin citas)")
        for appointment in appointments:
            doctor = (
                await db.get(Doctor, appointment.doctor_id)
                if appointment.doctor_id
                else None
            )
            window = checkin.window_for(appointment, now=now)
            print(
                f"  - id {appointment.id} · {local(appointment.scheduled_at)} · "
                f"{appointment.status.value} · {appointment.specialty}"
                + (f" · {doctor.full_name}" if doctor else "")
            )
            print(
                f"    consultorio={appointment.room or 'sin asignar'} · "
                f"check-in={'ABIERTO' if window.available else window.label()} · "
                f"código={appointment.checkin_code or 'sin código'}"
            )
            print(f"    portal=/portal/citas/{appointment.id}")

        print("\nLaboratorio pendiente:")
        if not pending_orders:
            print("  (sin órdenes pendientes)")
        for order in pending_orders:
            print(f"  - orden {order.id} · {order.status.value}")

        print("\nSiguiente paso: abre /portal/citas/<id> y el teléfono con demo.paciente.")


if __name__ == "__main__":
    asyncio.run(main())
