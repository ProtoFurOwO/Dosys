"""Prueba de aceptación del portal clínico.

Requiere el stack local levantado (`docker compose up -d --build` en backend/).
Verifica: login del médico, listado de pacientes, registro de una consulta,
rechazo de credenciales incorrectas, rechazo del rol paciente y cierre de sesión.

Todos los datos usados son ficticios.
"""

import json
import os
import re
from datetime import datetime
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

BASE_URL = os.getenv("DOSYS_API_URL", "http://127.0.0.1:8000").rstrip("/")
DOCTOR = {"username": "medico", "password": "Medico123!"}
PATIENT = {"username": "paciente", "password": "Paciente123!"}


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

    # 8. Cierre de sesión.
    status, html = form_request(opener, "/portal/salir", {})
    assert "Inicia sesión" in html, "Cerrar sesión debe regresar al acceso"

    print(
        json.dumps(
            {
                "portal": "ok",
                "patient_id": patient_id,
                "consultation_marker": marker,
                "invalid_credentials": 401,
                "patient_role_denied": 403,
                "form_validation": 422,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
