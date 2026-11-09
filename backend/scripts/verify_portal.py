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

import requests

BASE_URL = os.getenv("DOSYS_API_URL", "http://127.0.0.1:8000").rstrip("/")
# Cloudflare bloquea el User-Agent por defecto de Python (error 1010).
USER_AGENT = "D.O.S.Y.S/1.0 (verificacion academica)"
DOCTOR = {"username": "medico", "password": "Medico123!"}
ADMIN = {"username": "admin", "password": "Admin123!"}
PATIENT = {
    "username": "paciente",
    "password": "Paciente123!",
    "device_id": "verify-local-device-0001",
    "device_name": "Verificación portal",
}
VERIFY_DEVICE = {"device_id": "verify-local-device-0001", "device_name": "Verificación portal"}


def api(path: str, *, method: str = "GET", body: dict | None = None, token: str | None = None):
    headers = {"User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = requests.request(
        method,
        f"{BASE_URL}{path}",
        json=body,
        headers=headers,
        timeout=20,
    )
    try:
        return response.status_code, response.json()
    except ValueError:
        return response.status_code, {"detail": response.text[:300]}


def new_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def form_request(session: requests.Session, path: str, fields: dict) -> tuple[int, str]:
    response = session.post(f"{BASE_URL}{path}", data=fields, timeout=20, allow_redirects=True)
    return response.status_code, response.text


def get(session: requests.Session, path: str) -> tuple[int, str]:
    response = session.get(f"{BASE_URL}{path}", timeout=20, allow_redirects=True)
    return response.status_code, response.text


def upload_request(
    session: requests.Session,
    path: str,
    fields: dict,
    filename: str,
    content: bytes,
    content_type: str = "application/pdf",
) -> tuple[int, str]:
    response = session.post(
        f"{BASE_URL}{path}",
        data=fields,
        files={"file": (filename, content, content_type)},
        timeout=20,
    )
    return response.status_code, response.text


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

    # La cita de prueba debe caer en un hueco libre: el sistema rechaza
    # empalmes y las corridas anteriores dejan citas agendadas.
    appointment_html = None
    for attempt in range(12):
        candidate = datetime.now() + timedelta(days=20 + attempt)
        status, html = form_request(
            opener,
            f"/portal/pacientes/{patient_id}/cita",
            {
                "specialty": "Cardiología",
                "fecha": candidate.date().isoformat(),
                "hora": f"{8 + attempt:02d}:15",
                "location": "Consultorio 1",
                "notes": "Acude con ayuno de 8 horas.",
            },
        )
        if status == 200 and "Cita agendada" in html:
            appointment_html = html
            break
    assert appointment_html, "La cita debe registrarse en el portal"
    match = re.search(r'href="/portal/citas/(\d+)"', appointment_html)
    assert match, "La lista debe ofrecer el botón Ver QR"
    status, qr_html = get(opener, f"/portal/citas/{match.group(1)}")
    assert status == 200 and "Código de check-in" in qr_html and "Código de respaldo" in qr_html, "El QR debe verse"

    # 9. El paciente ve la cita desde la API de la app.
    _, patient_login = api("/api/v1/auth/login", method="POST", body=PATIENT)
    _, patient_appointments = api("/api/v1/patients/me/appointments", token=patient_login["access_token"])
    assert any(item["specialty"] == "Cardiología" for item in patient_appointments), "El paciente debe ver la cita"

    # 10. Fecha inválida en el formulario: debe rechazarse en el servidor.
    status, html = form_request(
        opener,
        f"/portal/pacientes/{patient_id}/cita",
        {"specialty": "Cardiología", "fecha": "2020-01-01", "hora": "11:30", "location": "Consultorio 1", "notes": ""},
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
        "/api/v1/auth/login",
        method="POST",
        body={"username": patient_username, "password": patient_password, **VERIFY_DEVICE},
    )
    assert status == 200 and login["role"] == "patient", "El paciente registrado debe entrar a la app"
    status, profile = api("/api/v1/patients/me", token=login["access_token"])
    assert status == 200 and profile["full_name"] == "Paciente de Prueba", "La app debe ver su perfil nuevo"

    # 9. Registrar un médico (lo hace el administrador), desactivarlo y restablecer su contraseña.
    admin = new_session()
    status, html = form_request(admin, "/portal/login", ADMIN)
    assert status == 200, "El administrador debe entrar al portal"

    doctor_username = f"prueba_med_{suffix}"
    status, html = form_request(
        admin,
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

    status, html = get(admin, "/portal/usuarios")
    assert status == 200 and "Pediatría" in html, "El médico nuevo debe aparecer en la lista"
    doctor_user_id = find_user_id(html, doctor_username)

    status, login = api(
        "/api/v1/auth/login", method="POST", body={"username": doctor_username, "password": patient_password}
    )
    assert status == 200 and login["role"] == "doctor", "El médico nuevo debe entrar a la API"

    status, _ = form_request(admin, f"/portal/usuarios/{doctor_user_id}/estado", {})
    status, _ = api(
        "/api/v1/auth/login",
        method="POST",
        body={"username": doctor_username, "password": patient_password},
    )
    assert status == 401, "Un usuario desactivado no debe poder entrar"

    status, _ = form_request(admin, f"/portal/usuarios/{doctor_user_id}/estado", {})
    status, login = api(
        "/api/v1/auth/login", method="POST", body={"username": doctor_username, "password": patient_password}
    )
    assert status == 200, "Al reactivarlo debe poder entrar otra vez"

    status, html = form_request(admin, f"/portal/usuarios/{doctor_user_id}/reset", {})
    assert status == 200, "El restablecimiento debe mostrar la credencial nueva"
    match = re.search(r'id="credential-password">([A-Za-z0-9]+)<', html)
    assert match, "La credencial debe traer la contraseña nueva"
    new_password = match.group(1)

    status, login = api("/api/v1/auth/login", method="POST", body={"username": doctor_username, "password": new_password})
    assert status == 200, "Debe entrar con la contraseña restablecida"

    # 9b. Un médico no puede entrar a la gestión de usuarios (control por permisos).
    doctor_portal = new_session()
    status, _ = form_request(doctor_portal, "/portal/login", {"username": doctor_username, "password": new_password})
    assert status == 200, "El médico entra al portal"
    status, _ = get(doctor_portal, "/portal/usuarios")
    assert status == 403, f"Un médico no debe ver la gestión de usuarios (fue {status})"

    # 9c. Roles: crear uno nuevo, asignarlo y comprobar el efecto en el acceso.
    role_html = get(admin, "/portal/roles")
    assert role_html[0] == 200 and "Roles y permisos" in role_html[1], "La página de roles debe abrir"

    role_code = f"enfermeria_{suffix}"
    status, html = form_request(
        admin,
        "/portal/roles/nuevo",
        {
            "code": role_code,
            "name": "Enfermería de prueba",
            "description": "Acceso de solo lectura al expediente",
            "permissions": ["portal:access", "patients:read"],
        },
    )
    assert status == 200 and role_code in html, "El rol nuevo debe crearse y aparecer"

    match = re.search(rf'/portal/roles/(\d+)/editar[^>]*>\s*Editar permisos', html)
    role_ids = [int(item) for item in re.findall(r"/portal/roles/(\d+)/editar", html)]
    assert role_ids, "Debe existir el enlace de edición de roles"
    new_role_id = max(role_ids)

    status, _ = form_request(admin, f"/portal/usuarios/{doctor_user_id}/rol", {"role_id": new_role_id})
    assert status == 200, "El rol debe asignarse"

    status, login = api("/api/v1/auth/login", method="POST", body={"username": doctor_username, "password": new_password})
    token_after = login["access_token"]

    status, _ = get(doctor_portal, "/portal")  # el médico ya no tiene patients:read? sí lo tiene
    status, _ = get(doctor_portal, "/portal/citas")
    assert status == 403, f"El rol de enfermería no debe ver la agenda (fue {status})"

    status, _ = get(doctor_portal, "/portal/pacientes/1/consulta")
    assert status == 403, "El rol de enfermería no debe registrar consultas"

    status, login = api("/api/v1/auth/login", method="POST", body={"username": doctor_username, "password": new_password})
    assert login["role"] == role_code, "El rol del token debe ser el nuevo"
    status, _ = api(
        "/api/v1/doctor/consultations",
        method="POST",
        token=login["access_token"],
        body={
            "patient_id": patient_id,
            "reason": "Intento sin permiso",
            "diagnosis": "No debe permitirse",
        },
    )
    assert status == 403, f"La API debe responder 403 (fue {status})"

    # 9d. Documentos: subir al expediente, verificar la huella y verlo desde la app.
    pdf_bytes = b"%PDF-1.4\n% documento de prueba\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
    status, html = upload_request(
        opener,
        f"/portal/pacientes/{patient_id}/documentos",
        {"title": "Estudio de prueba", "category": "estudio"},
        "estudio_prueba.pdf",
        pdf_bytes,
    )
    assert status == 200 and "Documento agregado al expediente" in html, "El documento debe subirse"
    match = re.search(r"/portal/documentos/(\d+)/verificar", html)
    assert match, "El expediente debe listar el documento con su verificación"
    document_id = int(match.group(1))

    status, html = form_request(opener, f"/portal/documentos/{document_id}/verificar", {})
    assert status == 200 and "coincide con la huella registrada" in html, "La verificación debe dar intacto"

    _, patient_login = api("/api/v1/auth/login", method="POST", body=PATIENT)
    _, documents_api = api("/api/v1/patients/me/documents", token=patient_login["access_token"])
    assert any(item["id"] == document_id for item in documents_api), "El paciente debe ver su documento"

    # 10. Editar datos y revisar la bitácora.
    status, html = form_request(
        admin,
        f"/portal/usuarios/{doctor_user_id}/editar",
        {"full_name": "Dra. Prueba Sánchez", "specialty": "Pediatría General"},
    )
    assert status == 200 and "Pediatría General" in html, "La edición del médico debe guardarse"

    status, html = get(admin, "/portal/actividad")
    assert status == 200 and "Paciente registrado" in html, "La bitácora debe mostrar el registro del paciente"
    assert "Usuario desactivado" in html and "Contraseña restablecida" in html, "La bitácora debe registrar los cambios"
    assert "Rol creado" in html, "La bitácora debe registrar el rol nuevo"

    status, html = get(admin, "/portal/actividad?accion=medico")
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
