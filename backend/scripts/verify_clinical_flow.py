"""Verificación de aceptación del expediente clínico y del laboratorio.

Cubre: datos clínicos del paciente (alergias, antecedentes y crónicos),
edición posterior, consulta con estudio, corrección auditada de una consulta,
orden de estudio de demostración y captura de resultado con PDF.

Requiere el stack local levantado. Datos ficticios.
"""

import json
import os
import re
import time

import requests

BASE_URL = os.getenv("DOSYS_API_URL", "http://127.0.0.1:8000").rstrip("/")
USER_AGENT = "D.O.S.Y.S/1.0 (verificacion clinica)"
MEDICO = {"username": "medico", "password": "Medico123!"}
ADMIN = {"username": "admin", "password": "Admin123!"}
PASSWORD = "Prueba1234"

_passed = 0
_failed = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"  OK   {name}")
    else:
        _failed += 1
        print(f"  FALLA {name} {detail}")


def opener() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def request(op: requests.Session, path: str, fields: dict | None = None):
    if fields is None:
        response = op.get(f"{BASE_URL}{path}", timeout=30)
    else:
        response = op.post(f"{BASE_URL}{path}", data=fields, timeout=30, allow_redirects=True)
    return response.status_code, response.text


def login(op: requests.Session, credentials: dict) -> bool:
    status, _ = request(op, "/portal/login", credentials)
    return status in (200, 303)


def create_patient(op, suffix: str) -> tuple[int, str]:
    status, html = request(
        op,
        "/portal/pacientes/nuevo",
        {
            "full_name": f"Paciente Clínico {suffix}",
            "curp": f"TEST{suffix}HCSRRN88",
            "birth_date": "1997-03-18",
            "blood_type": "A+",
            "emergency_contact": "Contacto 961 222 3344",
            "email": f"clinico{suffix}@correo.com",
            "username": f"clinico{suffix}",
            "password": PASSWORD,
            "password_confirm": PASSWORD,
            "allergies": "Penicilina (urticaria)",
            "medical_history": "Apendicectomía (2018); padre con diabetes tipo 2",
            "chronic_conditions": "Hipertensión arterial en control",
        },
    )
    assert status == 201, f"No se creó el paciente ({status})"
    match = re.search(r'/portal/pacientes/(\d+)"', html)
    assert match, "La credencial debe enlazar al expediente"
    return int(match.group(1)), f"clinico{suffix}"


def create_lab_user(admin, suffix: str) -> str:
    username = f"lab_verify_{suffix}"
    status, html = request(
        admin,
        "/portal/usuarios/nuevo",
        {
            "full_name": f"Laboratorio Verificación {suffix}",
            "role_code": "laboratory",
            "specialty": "Laboratorio clínico",
            "email": f"{username}@correo.com",
            "username": username,
            "password": PASSWORD,
            "password_confirm": PASSWORD,
        },
    )
    assert status == 201 and username in html, f"No se creó el usuario de laboratorio ({status})"
    return username


def main() -> int:
    suffix = time.strftime("%H%M%S")
    admin = opener()
    check("admin entra al portal", login(admin, ADMIN))

    med = opener()
    check("médico entra al portal", login(med, MEDICO))

    patient_id, _ = create_patient(med, suffix)

    status, detail = request(med, f"/portal/pacientes/{patient_id}")
    check(
        "el expediente muestra alergias, antecedentes y crónicos",
        status == 200
        and "Penicilina" in detail
        and "Apendicectomía" in detail
        and "Hipertensión" in detail
        and "Alertas clínicas" in detail,
        f"status={status}",
    )

    status, edited = request(
        med,
        f"/portal/pacientes/{patient_id}/editar",
        {
            "full_name": f"Paciente Clínico Editado {suffix}",
            "birth_date": "1997-03-18",
            "blood_type": "A+",
            "emergency_contact": "Contacto 961 555 6677",
            "email": f"clinico{suffix}@correo.com",
            "allergies": "Penicilina, sulfas",
            "medical_history": "Apendicectomía (2018); padre con diabetes tipo 2",
            "chronic_conditions": "Hipertensión arterial y dislipidemia",
        },
    )
    check("editar paciente y sus alergias", status == 200 and "Datos del paciente actualizados" in edited, f"status={status}")

    status, form = request(med, f"/portal/pacientes/{patient_id}/consulta")
    studies = re.findall(r'name="study_ids" value="(\d+)"', form)
    check("el formulario de consulta abre con estudios", status == 200 and bool(studies), f"status={status}")

    status, saved = request(
        med,
        f"/portal/pacientes/{patient_id}/consulta",
        {
            "reason": "Dolor de cabeza persistente",
            "diagnosis": "Cefalea tensional",
            "notes": "Se solicita biometría hemática.",
            "cita": "0",
            "study_ids": studies[0] if studies else "",
        },
    )
    check("consulta con estudio se guarda sin recargar en silencio", status == 200 and "Consulta registrada" in saved, f"status={status}")
    consultation_match = re.search(r"/consulta/(\d+)/editar", saved)
    check("la consulta ofrece corrección auditada", bool(consultation_match), "sin botón")
    consultation_id = int(consultation_match.group(1)) if consultation_match else 0

    if consultation_id:
        status, fixed = request(
            med,
            f"/portal/pacientes/{patient_id}/consulta/{consultation_id}/editar",
            {
                "reason": "Dolor de cabeza persistente",
                "diagnosis": "Cefalea tensional; descartar migraña",
                "notes": "Control en 7 días y biometría hemática.",
            },
        )
        check("corregir diagnóstico", status == 200 and "Consulta corregida" in fixed, f"status={status}")

    status, patient_html = request(med, f"/portal/pacientes/{patient_id}")
    options = re.findall(r'<option value="(\d+)">([^<]+)</option>', patient_html)
    study_id = options[0][0] if options else "0"
    status, demo = request(
        med,
        f"/portal/pacientes/{patient_id}/estudio-demo",
        {"study_id": study_id, "indications": "Ayuno de 8 horas"},
    )
    check("el botón demo genera una orden real", status == 200 and "Estudio solicitado" in demo, f"status={status}")

    lab_username = create_lab_user(admin, suffix)
    lab = opener()
    check("laboratorio entra al portal", login(lab, {"username": lab_username, "password": PASSWORD}))

    status, lab_html = request(lab, "/portal/laboratorio")
    check(
        "el laboratorio ve la cola y sus filtros",
        status == 200 and "Órdenes pendientes" in lab_html and "lab-stats" in lab_html,
        f"status={status}",
    )
    orders = re.findall(r"/portal/laboratorio/(\d+)/completar", lab_html)
    check("hay órdenes pendientes para capturar", bool(orders), "sin órdenes")

    if orders:
        order_id = orders[0]
        status, started = request(lab, f"/portal/laboratorio/{order_id}/iniciar", {})
        check("iniciar orden", status == 200 and "en proceso" in started, f"status={status}")
        status, completed = request(
            lab,
            f"/portal/laboratorio/{order_id}/completar",
            {"result_text": "Hemoglobina 14.2 g/dL; leucocitos 6.8; plaquetas 245. Sin hallazgos agudos."},
        )
        check(
            "capturar resultado genera PDF con huella",
            status == 200 and "huella SHA-256" in completed and "Resultado PDF" in completed,
            f"status={status}",
        )

    status, activity = request(med, "/portal/actividad?entidad=consultation&texto=campos")
    check(
        "la bitácora registra la corrección con campos cambiados",
        status == 200 and "campos cambiados" in activity and "Consulta corregida" in activity,
        f"status={status}",
    )
    status, csv_body = request(med, "/portal/actividad.csv?entidad=study_order")
    check("la bitácora se exporta a CSV", status == 200 and "Fecha,Usuario" in csv_body, f"status={status}")

    status, admin_detail = request(admin, f"/portal/pacientes/{patient_id}")
    check(
        "una cuenta sin ficha de médico no ve Nueva consulta",
        status == 200 and "Nueva consulta" not in admin_detail,
        f"status={status}",
    )
    status, admin_form = request(admin, f"/portal/pacientes/{patient_id}/consulta")
    check("una cuenta sin ficha de médico no abre el formulario", status == 403, f"status={status}")

    print(f"\nResultado: {_passed} correctas, {_failed} fallidas")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
