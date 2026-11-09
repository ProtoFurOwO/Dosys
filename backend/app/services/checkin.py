"""Ventana de check-in de una cita.

El QR de recepción no debe servir días después ni antes de que el paciente
llegue. La ventana se calcula en el servidor y se comparte entre la API y el
portal para que ambos muestren el mismo estado.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.models.appointment import Appointment
from app.models.enums import AppointmentStatus


@dataclass(frozen=True)
class CheckInWindow:
    opens_at: datetime
    closes_at: datetime
    available: bool
    reason: str | None

    def label(self) -> str:
        if self.available:
            return "Check-in abierto"
        if self.reason == "too_early":
            return "Aún no abre el check-in"
        if self.reason == "closed":
            return "El check-in ya cerró"
        if self.reason == "requested":
            return "Solicitud pendiente de confirmación"
        if self.reason == "already_checked_in":
            return "Llegada ya confirmada"
        if self.reason == "attended":
            return "Cita ya atendida"
        if self.reason == "cancelled":
            return "Cita cancelada"
        return "Check-in no disponible"


def _aware(value: datetime) -> datetime:
    """Normaliza a UTC las fechas que algunos motores entregan sin zona."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def window_for(appointment: Appointment, now: datetime | None = None) -> CheckInWindow:
    moment = _aware(now or datetime.now(timezone.utc))
    scheduled = _aware(appointment.scheduled_at)
    opens_at = scheduled - timedelta(minutes=settings.checkin_window_before_minutes)
    closes_at = scheduled + timedelta(minutes=settings.checkin_window_after_minutes)

    reason: str | None = None
    if appointment.status == AppointmentStatus.CANCELLED:
        reason = "cancelled"
    elif appointment.status == AppointmentStatus.ATTENDED:
        reason = "attended"
    elif appointment.status == AppointmentStatus.REQUESTED:
        reason = "requested"
    elif appointment.checked_in_at is not None:
        reason = "already_checked_in"
    elif moment < opens_at:
        reason = "too_early"
    elif moment > closes_at:
        reason = "closed"

    return CheckInWindow(
        opens_at=opens_at,
        closes_at=closes_at,
        available=reason is None,
        reason=reason,
    )


def check_in_error(appointment: Appointment, now: datetime | None = None) -> str | None:
    """Mensaje listo para mostrar o ``None`` si la ventana está abierta."""
    window = window_for(appointment, now=now)
    if window.reason == "cancelled":
        return "Esta cita fue cancelada."
    if window.reason == "attended":
        return "Esta cita ya fue atendida."
    if window.reason == "requested":
        return "Tu cita aún no ha sido confirmada por recepción."
    if window.reason == "already_checked_in":
        return "Tu llegada ya estaba confirmada."
    if window.reason == "too_early":
        minutes = settings.checkin_window_before_minutes
        if minutes >= 60 and minutes % 60 == 0:
            return f"El check-in abre {minutes // 60} horas antes de la cita."
        return f"El check-in abre {minutes} minutos antes de la cita."
    if window.reason == "closed":
        return "El check-in de esta cita ya cerró. Pide apoyo en recepción."
    return None


def window_payload(appointment: Appointment, now: datetime | None = None) -> dict:
    window = window_for(appointment, now=now)
    return {
        "checkin_available": window.available,
        "checkin_opens_at": window.opens_at,
        "checkin_closes_at": window.closes_at,
        "checkin_reason": window.reason,
    }
