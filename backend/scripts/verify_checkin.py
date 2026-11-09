"""Prueba de aceptación del check-in con QR.

Requiere el stack local levantado. Crea una cita cercana desde el portal,
verifica que el QR tenga código, que un código incorrecto se rechace, que la
ventana se respete, que el código correcto confirme la llegada y que la
operación sea idempotente y visible para recepción.

Todos los datos usados son ficticios.
"""

import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen

BASE_URL = os.getenv("DOSYS_API_URL", "http://127.0.0.1:8000").rstrip("/")
USER_AGENT = "D.O.S.Y.S/1.0 (verificacion academica)"
# México dejó el horario de verano en 2022: UTC-6 todo el año.
CLINIC = timezone(timedelta(hours=-6))
PATIENT = {
    "username": "paciente",
    "password": "Paciente123!",
    "device_id": "verify-local-device-0001",
    "device_name": "Verificación check-in",
}
STAFF = {"username": "medico", "password": "Medico123!"}
ADMIN = {"username": "admin", "password": "Admin123!"}
PASSWORD = "Prueba1234"


def request(path: str, *, method: str = "GET", body: dict | None = None, token: str | None = None):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    headers = {"User-Agent": USER_AGENT}
    if data:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    http_request = Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urlopen(http_request, timeout=15) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        body = error.read().decode("utf-8")
        try:
            return error.code, json.loads(body)
        except json.JSONDecodeError:
            return error.code, {"detail": body[:300]}


def portal_session(credentials: dict | None = None):
    """Sesión del portal (recepción/médico/admin) para crear la cita y ver el QR."""
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    data = urlencode(credentials or STAFF).encode()
    opener.open(Request(f"{BASE_URL}/portal/login", data=data, headers={"User-Agent": USER_AGENT}), timeout=15).read()
    return opener


def portal_get(opener, path: str) -> tuple[int, str]:
    http_request = Request(f"{BASE_URL}{path}", headers={"User-Agent": USER_AGENT})
    try:
        with opener.open(http_request, timeout=15) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except HTTPError as error:
        return error.code, error.read().decode("utf-8", "replace")


def portal_post(opener, path: str, body: dict) -> tuple[int, str, str]:
    data = urlencode(body).encode()
    http_request = Request(
        f"{BASE_URL}{path}",
        data=data,
        headers={"User-Agent": USER_AGENT, "Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with opener.open(http_request, timeout=15) as response:
            return response.status, response.read().decode("utf-8", "replace"), response.url
    except HTTPError as error:
        return error.code, error.read().decode("utf-8", "replace"), error.url



def create_doctor(admin, suffix: str) -> str:
    """Crea un médico nuevo para que su agenda no choque con citas de pruebas."""
    username = f"checkin_med_{suffix}"
    status, html, _ = portal_post(
        admin,
        "/portal/usuarios/nuevo",
        {
            "full_name": f"Dra. Check-in {suffix}",
            "role_code": "doctor",
            "specialty": "Medicina General",
            "email": f"{username}@correo.com",
            "username": username,
            "password": PASSWORD,
            "password_confirm": PASSWORD,
        },
    )
    assert status == 201 and username in html, f"No se creó el médico de check-in ({status})"
    return username


def create_patient(opener, suffix: str) -> tuple[int, str]:
    username = f"checkin_{suffix}"
    status, html, _ = portal_post(
        opener,
        "/portal/pacientes/nuevo",
        {
            "full_name": f"Paciente Check-in {suffix}",
            "curp": f"TEST{suffix}HCSRRN77",
            "birth_date": "1998-07-21",
            "blood_type": "O+",
            "emergency_contact": "Contacto 961 000 1122",
            "email": f"{username}@correo.com",
            "username": username,
            "password": PASSWORD,
            "password_confirm": PASSWORD,
            "allergies": "Sin alergias conocidas",
            "medical_history": "Sin antecedentes de importancia",
            "chronic_conditions": "Ninguno",
        },
    )
    assert status == 201, f"No se creó el paciente de check-in ({status})"
    match = re.search(r'/portal/pacientes/(\d+)"', html)
    assert match, "La credencial debe enlazar al expediente"
    return int(match.group(1)), username


def schedule_checkin_cita(
    opener,
    patient_id: int,
    *,
    offsets: tuple[int, ...],
    room: str = "Consultorio 1",
) -> int:
    last_status = 0
    last_html = ""
    for minutes_ahead in offsets:
        moment = datetime.now(CLINIC) + timedelta(minutes=minutes_ahead)
        status, html, final_url = portal_post(
            opener,
            f"/portal/pacientes/{patient_id}/cita",
            {
                "specialty": "Medicina General",
                "fecha": moment.date().isoformat(),
                "hora": moment.strftime("%H:%M"),
                "location": room,
                "notes": "Cita de verificación de check-in",
            },
        )
        last_status, last_html = status, html
        if status == 200:
            match = re.search(r"creada=(\d+)", final_url) or re.search(r"creada=(\d+)", html)
            assert match, f"La cita creada debe aparecer en la URL ({final_url})"
            return int(match.group(1))
        if status != 422 or "ya tiene otra cita" not in html:
            break
    raise AssertionError(f"No se creó la cita de verificación ({last_status})")


def qr_code_for(opener, appointment_id: int) -> str:
    status, html = portal_get(opener, f"/portal/citas/{appointment_id}")
    assert status == 200, f"No se abrió el QR ({status})"
    match = re.search(r"Código de respaldo:\s*<strong>([A-Z0-9]+)</strong>", html)
    assert match, "El QR debe mostrar el código de respaldo"
    return match.group(1)


def main() -> None:
    suffix = time.strftime("%H%M%S")
    admin = portal_session(ADMIN)
    doctor_username = create_doctor(admin, suffix)
    portal = portal_session({"username": doctor_username, "password": PASSWORD})
    patient_id, username = create_patient(portal, suffix)

    status, login = request(
        "/api/v1/auth/login",
        method="POST",
        body={
            "username": username,
            "password": PASSWORD,
            "device_id": f"verify-checkin-{suffix}",
            "device_name": "Check-in de verificación",
        },
    )
    assert status == 200, "El paciente de check-in debe entrar a la app"
    token = login["access_token"]

    near_id = schedule_checkin_cita(portal, patient_id, offsets=(10, 40, 70, 100))
    near_code = qr_code_for(portal, near_id)
    far_id = schedule_checkin_cita(portal, patient_id, offsets=(1440, 1500, 1560), room="Consultorio 2")
    far_code = qr_code_for(portal, far_id)

    status, appointments = request("/api/v1/patients/me/appointments", token=token)
    assert status == 200, "La app debe listar las citas"
    near = next(item for item in appointments if item["id"] == near_id)
    assert near["checkin_available"] is True and near["is_upcoming"] is True, (
        "La cita cercana debe tener el check-in abierto"
    )

    status, blocked = request(
        f"/api/v1/patients/me/appointments/{far_id}/check-in",
        method="POST",
        token=token,
        body={"code": far_code},
    )
    assert status == 409 and "2 horas" in blocked["detail"], "La ventana debe rechazar el check-in temprano"

    status, _ = request(
        f"/api/v1/patients/me/appointments/{near_id}/check-in",
        method="POST",
        token=token,
        body={"code": "0000"},
    )
    assert status == 400, "Un código incorrecto debe rechazarse"

    status, confirmed = request(
        "/api/v1/patients/me/check-in",
        method="POST",
        token=token,
        body={"code": near_code},
    )
    assert status == 200 and confirmed["checked_in_at"], "El código correcto debe confirmar la llegada"
    assert confirmed["status"] == "confirmed", "La cita debe pasar a confirmada"

    # La pantalla del portal (la que ve recepción) debe reflejar la llegada.
    http_request = Request(f"{BASE_URL}/portal/citas/{near_id}/estado", headers={"User-Agent": USER_AGENT})
    with portal.open(http_request, timeout=15) as response:
        state = json.loads(response.read().decode("utf-8"))
    assert state["checked_in"] is True and state["checked_in_label"], (
        "El portal debe ver la cita con llegada confirmada"
    )

    status, again = request(
        "/api/v1/patients/me/check-in",
        method="POST",
        token=token,
        body={"code": near_code},
    )
    assert status == 200 and again["checked_in_at"] == confirmed["checked_in_at"], "El check-in debe ser idempotente"

    print(
        json.dumps(
            {
                "checkin": "ok",
                "appointment_id": near_id,
                "wrong_code": 400,
                "early_window": 409,
                "confirmed_at": confirmed["checked_in_at"],
                "idempotent": True,
                "portal_aviso_en_vivo": True,
                "portal_hora": state["checked_in_label"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
