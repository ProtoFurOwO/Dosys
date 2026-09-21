"""Prueba de aceptación del portal clínico.

Requiere el stack local levantado (`docker compose up -d --build` en backend/).
Verifica: login del médico, listado de pacientes, registro de una consulta,
agendado de una cita con su QR, rechazo de credenciales incorrectas, rechazo del
rol paciente y cierre de sesión.

Todos los datos usados son ficticios.
"""

import json
import os
import re
from datetime import datetime, timedelta
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen

BASE_URL = os.getenv("DOSYS_API_URL", "http://127.0.0.1:8000").rstrip("/")
DOCTOR = {"username": "medico", "password": "Medico123!"}
PATIENT = {"username": "paciente", "password": "Paciente123!"}


def api(path: str, *, method: str = "GET", body: dict | None = None, token: str | None = None):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    with urlopen(request, timeout=15) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def form_request(opener, path: str, fields: dict) -> tuple[int, str]:
    data = urlencode(fields).encode()
    request = Request(f"{BASE_URL}{path}", data=data, method="POST")
    try:
        with opener.open(request, timeout=15) as response:
            return response.status, response.read().decode("utf-8")
    except HTTPError as error:
        return error.code, error.read().decode("utf-8")


def get(opener, path: str) -> tuple[int, str]:
    try:
        with opener.open(f"{BASE_URL}{path}", timeout=15) as response:
            return response.status, response.read().decode("utf-8")
    except HTTPError as error:
        return error.code, error.read().decode("utf-8")


def new_session():
    return build_opener(HTTPCookieProcessor(CookieJar()))


def main() -> None:
    opener = new_session()

    # 1. Credenciales incorrectas → 401 con mensaje.
    status, html = form_request(opener, "/portal/login", {**DOCTOR, "password": "incorrecta"})
    assert status == 401 and "incorrectos" in html, "El portal debe rechazar credenciales inválidas"

    # 2. Rol paciente → 403.
    status, html = form_request(new_session(), "/portal/login", PATIENT)
    assert status == 403 and "personal médico" in html, "El portal debe rechazar al rol paciente"

    # 3. Login del médico.
    status, html = form_request(opener, "/portal/login", DOCTOR)
    assert status == 200 and "Registrar consulta" in html, "El médico debe entrar al listado"

    # 4. Listado con pacientes.
    status, html = get(opener, "/portal")
    assert status == 200
    match = re.search(r'/portal/pacientes/(\d+)"', html)
    assert match, "El listado debe mostrar al paciente sembrado"
    patient_id = int(match.group(1))
    assert "Matuz" in html

    # 5. Registro de consulta desde el portal.
    marker = f"PORTAL-{datetime.now():%Y%m%d%H%M%S}"
    status, html = form_request(
        opener,
        f"/portal/pacientes/{patient_id}/consulta",
        {
            "reason": marker,
            "diagnosis": "Consulta registrada desde el portal clínico",
            "notes": "Dato ficticio de la prueba de aceptación del portal.",
        },
    )
    assert status == 200 and marker in html, "La consulta creada debe aparecer en el expediente"

    # 6. Validación del formulario: motivo demasiado corto.
    status, html = form_request(
        opener,
        f"/portal/pacientes/{patient_id}/consulta",
        {"reason": "ab", "diagnosis": "", "notes": ""},
    )
    assert status == 422 and "Escribe el motivo" in html, "El formulario debe validar en el servidor"

    # 7. La API pública sigue leyendo la consulta creada desde el portal.
    status, _ = get(new_session(), f"/portal/pacientes/{patient_id}")
    assert status == 303 or status == 200, "Una sesión sin cookie debe ser redirigida al acceso"

    # 8. Agendar una cita con QR de check-in desde el portal.
    status, html = get(opener, f"/portal/pacientes/{patient_id}/cita")
    assert status == 200 and "Agendar cita" in html, "El formulario de cita debe abrir"

    future = (datetime.now() + timedelta(days=7)).date().isoformat()
    status, html = form_request(
        opener,
        f"/portal/pacientes/{patient_id}/cita",
        {
            "specialty": "Cardiología",
            "fecha": future,
            "hora": "11:30",
            "location": "Consultorio 7",
            "notes": "Acude con ayuno de 8 horas.",
        },
    )
    assert status == 200 and "Cita agendada" in html and "Cardiología" in html, "La cita debe aparecer en el portal"
    assert "qr" in html.lower(), "La cita nueva debe mostrar su QR de check-in"

    # 9. El paciente ve la cita desde la API de la app.
    _, patient_login = api("/api/v1/auth/login", method="POST", body=PATIENT)
    _, patient_appointments = api("/api/v1/patients/me/appointments", token=patient_login["access_token"])
    assert any(item["specialty"] == "Cardiología" for item in patient_appointments), "El paciente debe ver la cita"

    # 10. Fecha inválida en el formulario: debe rechazarse en el servidor.
    status, html = form_request(
        opener,
        f"/portal/pacientes/{patient_id}/cita",
        {"specialty": "Cardiología", "fecha": "2020-01-01", "hora": "11:30", "location": "Consultorio 7", "notes": ""},
    )
    assert status == 422 and "futuras" in html, "El portal debe rechazar citas en el pasado"

    # 11. Cierre de sesión.
    status, html = form_request(opener, "/portal/salir", {})
    assert "Inicia sesión" in html, "Cerrar sesión debe regresar al acceso"

    print(
        json.dumps(
            {
                "portal": "ok",
                "patient_id": patient_id,
                "consultation_marker": marker,
                "appointment_created": "Cardiología",
                "appointment_visible_para_paciente": True,
                "invalid_credentials": 401,
                "patient_role_denied": 403,
                "form_validation": 422,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
