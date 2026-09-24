"""Instancia compartida de Jinja2 con los filtros en español."""

from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.portal import deps
from app.portal.labels import action_label

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.filters["fecha_hora"] = deps.format_datetime
templates.env.filters["fecha"] = deps.format_date
templates.env.filters["ultima_visita"] = deps.format_last_visit
templates.env.filters["hora"] = deps.format_time
templates.env.filters["accion"] = action_label


def credential_context(
    *,
    doctor_name: str,
    person_name: str,
    role_label: str,
    username: str,
    password: str,
    email: str | None,
    user_id: int,
    back_url: str,
    back_label: str,
) -> dict:
    """Datos de la credencial que se muestra una sola vez."""
    return {
        "doctor_name": doctor_name,
        "active": "usuarios",
        "person_name": person_name,
        "role_label": role_label,
        "username": username,
        "password": password,
        "email": email,
        "user_id": user_id,
        "back_url": back_url,
        "back_label": back_label,
        "errors": {},
    }
