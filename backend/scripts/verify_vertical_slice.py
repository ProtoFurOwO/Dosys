"""Prueba de aceptación: médico → PostgreSQL → paciente.

Requiere que `docker compose up -d --build` esté ejecutándose en backend/.
No imprime JWT ni credenciales. Todos los datos usados son ficticios.
"""

import json
import os
from datetime import datetime
from urllib.error import HTTPError
from urllib.request import Request, urlopen


BASE_URL = os.getenv("DOSYS_API_URL", "http://127.0.0.1:8000").rstrip("/")


def request(path: str, *, method: str = "GET", body: dict | None = None, token: str | None = None) -> tuple[int, object]:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    http_request = Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    with urlopen(http_request, timeout=15) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def status_only(path: str, *, token: str | None = None) -> int:
    try:
        return request(path, token=token)[0]
    except HTTPError as error:
        return error.code


def login(username: str, password: str) -> dict:
    _, result = request(
        "/api/v1/auth/login",
        method="POST",
        body={"username": username, "password": password},
    )
    return result  # type: ignore[return-value]


def main() -> None:
    health_status, health = request("/health")
    assert health_status == 200 and health == {"status": "ok", "database": "ok"}

    doctor = login("medico", "Medico123!")
    _, patients = request("/api/v1/doctor/patients", token=doctor["access_token"])
    assert patients, "La semilla debe incluir un paciente ficticio"
    # El paciente sembrado puede no ser el primero de la lista si hay más registros.
    target = next((item for item in patients if item["full_name"] == "José Antonio Matuz"), patients[0])

    marker = f"VALIDACION-E2E-{datetime.now():%Y%m%d%H%M%S}"
    created_status, created = request(
        "/api/v1/doctor/consultations",
        method="POST",
        token=doctor["access_token"],
        body={
            "patient_id": target["id"],
            "reason": marker,
            "diagnosis": "Consulta registrada por la prueba de aceptación",
            "notes": "Dato ficticio de validación local.",
        },
    )
    assert created_status == 201

    patient = login("paciente", "Paciente123!")
    _, consultations = request("/api/v1/patients/me/consultations", token=patient["access_token"])
    patient_can_read = any(item["id"] == created["id"] and item["reason"] == marker for item in consultations)
    assert patient_can_read, "El paciente no recibió la consulta recién creada"

    patient_to_doctor_status = status_only("/api/v1/doctor/patients", token=patient["access_token"])
    anonymous_profile_status = status_only("/api/v1/patients/me")
    assert patient_to_doctor_status == 403
    assert anonymous_profile_status == 401

    print(
        json.dumps(
            {
                "health": "ok",
                "doctor_created_consultation_id": created["id"],
                "patient_can_read_created_consultation": patient_can_read,
                "patient_to_doctor_endpoint": patient_to_doctor_status,
                "anonymous_patient_profile": anonymous_profile_status,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
