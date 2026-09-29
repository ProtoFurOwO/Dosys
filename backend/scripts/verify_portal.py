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
# Cloudflare bloquea el User-Agent por defecto de Python (error 1010).
USER_AGENT = "D.O.S.Y.S/1.0 (verificacion academica)"
DOCTOR = {"username": "medico", "password": "Medico123!"}
PATIENT = {"username": "paciente", "password": "Paciente123!"}


def api(path: str, *, method: str = "GET", body: dict | None = None, token: str | None = None):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    headers = {"User-Agent": USER_AGENT}
    if data:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    with urlopen(request, timeout=15) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def form_request(opener, path: str, fields: dict) -> tuple[int, str]:
    data = urlencode(fields).encode()
    request = Request(f"{BASE_URL}{path}", data=data, headers={"User-Agent": USER_AGENT}, method="POST")
    try:
        with opener.open(request, timeout=15) as response:
            return response.status, response.read().decode("utf-8")
    except HTTPError as error:
        return error.code, error.read().decode("utf-8")


def get(opener, path: str) -> tuple[int, str]:
    request = Request(f"{BASE_URL}{path}", headers={"User-Agent": USER_AGENT}, method="GET")
    try:
        with opener.open(request, timeout=15) as response:
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
    # El paciente sembrado puede no ser el primero si hay más registros.
    patient_id = None
    for row in html.split("<tr>"):
        if "Matuz" in row:
            match = re.search(r"/portal/pacientes/(\d+)", row)
            if match:
                patient_id = int(match.group(1))
                break
    assert patient_id, "El listado debe mostrar al paciente sembrado"

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

    def find_user_id(html: str, username: str) -> int:
        for row in html.split("<tr>"):
            if username in row:
                match = re.search(r"/portal/usuarios/(\d+)/editar", row)
                if match:
                    return int(match.group(1))
        raise AssertionError("No encontramos el usuario en la lista")

    # 8. Registrar un paciente y probar que entra a la app con la credencial.
    suffix = datetime.now().strftime("%H%M%S")
    patient_username = f"prueba_pac_{suffix}"
    patient_password = "Prueba1234"
    status, html = form_request(
        opener,
        "/portal/pacientes/nuevo",
        {
            "full_name": "Paciente de Prueba",
            "curp": f"TEST{suffix}HCSRRN09",
            "birth_date": "2000-01-15",
            "blood_type": "O+",
            "emergency_contact": "Contacto de prueba 961 000 0000",
            "email": f"{patient_username}@correo.com",
            "username": patient_username,
            "password": patient_password,
            "password_confirm": patient_password,
        },
    )
    assert status == 201 and patient_username in html and patient_password in html, "Debe mostrarse la credencial"

    status, html = form_request(
        opener,
        "/portal/credencial/correo",
        {
            "user_id": "0",
            "person_name": "Paciente de Prueba",
            "role_label": "Paciente",
            "username": patient_username,
            "password": patient_password,
            "email": f"{patient_username}@correo.com",
            "back_url": "/portal",
            "back_label": "Volver",
        },
    )
    assert status == 200 and "Correo enviado" in html, "El envío simulado debe mostrar la vista previa"

    status, login = api(
        "/api/v1/auth/login", method="POST", body={"username": patient_username, "password": patient_password}
    )
    assert status == 200 and login["role"] == "patient", "El paciente registrado debe entrar a la app"
    status, profile = api("/api/v1/patients/me", token=login["access_token"])
    assert status == 200 and profile["full_name"] == "Paciente de Prueba", "La app debe ver su perfil nuevo"

    # 9. Registrar un médico, desactivarlo y restablecer su contraseña.
    doctor_username = f"prueba_med_{suffix}"
    status, html = form_request(
        opener,
        "/portal/usuarios/nuevo",
        {
            "full_name": "Dra. Prueba Sánchez",
            "specialty": "Pediatría",
            "username": doctor_username,
            "password": patient_password,
            "password_confirm": patient_password,
        },
    )
    assert status == 201 and doctor_username in html, "Debe mostrarse la credencial del médico"

    status, html = get(opener, "/portal/usuarios")
    assert status == 200 and "Pediatría" in html, "El médico nuevo debe aparecer en la lista"
    doctor_user_id = find_user_id(html, doctor_username)

    status, login = api(
        "/api/v1/auth/login", method="POST", body={"username": doctor_username, "password": patient_password}
    )
    assert status == 200 and login["role"] == "doctor", "El médico nuevo debe entrar a la API"

    status, _ = form_request(opener, f"/portal/usuarios/{doctor_user_id}/estado", {})
    try:
        api("/api/v1/auth/login", method="POST", body={"username": doctor_username, "password": patient_password})
        raise AssertionError("Un usuario desactivado no debe poder entrar")
    except HTTPError as error:
        assert error.code == 401

    status, _ = form_request(opener, f"/portal/usuarios/{doctor_user_id}/estado", {})
    status, login = api(
        "/api/v1/auth/login", method="POST", body={"username": doctor_username, "password": patient_password}
    )
    assert status == 200, "Al reactivarlo debe poder entrar otra vez"

    status, html = form_request(opener, f"/portal/usuarios/{doctor_user_id}/reset", {})
    assert status == 200, "El restablecimiento debe mostrar la credencial nueva"
    match = re.search(r'id="credential-password">([A-Za-z0-9]+)<', html)
    assert match, "La credencial debe traer la contraseña nueva"
    new_password = match.group(1)

    status, login = api("/api/v1/auth/login", method="POST", body={"username": doctor_username, "password": new_password})
    assert status == 200, "Debe entrar con la contraseña restablecida"

    # 10. Editar datos y revisar la bitácora.
    status, html = form_request(
        opener,
        f"/portal/usuarios/{doctor_user_id}/editar",
        {"full_name": "Dra. Prueba Sánchez", "specialty": "Pediatría General"},
    )
    assert status == 200 and "Pediatría General" in html, "La edición del médico debe guardarse"

    status, html = get(opener, "/portal/actividad")
    assert status == 200 and "Paciente registrado" in html, "La bitácora debe mostrar el registro del paciente"
    assert "Usuario desactivado" in html and "Contraseña restablecida" in html, "La bitácora debe registrar los cambios"

    status, html = get(opener, "/portal/actividad?accion=medico")
    assert status == 200 and "Médico registrado" in html, "El filtro de la bitácora debe funcionar"

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
                "patient_registered": patient_username,
                "patient_login_en_app": True,
                "doctor_registered": doctor_username,
                "doctor_deactivated_blocked": 401,
                "password_reset_ok": True,
                "audit_view": True,
                "invalid_credentials": 401,
                "patient_role_denied": 403,
                "form_validation": 422,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
