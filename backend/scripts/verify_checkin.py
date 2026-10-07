"""Prueba de aceptación del check-in con QR.

Requiere el stack local levantado. Verifica el camino completo del módulo de
cámara: la cita sembrada tiene código, un código incorrecto se rechaza, el
código correcto confirma la llegada, la operación es idempotente y la pantalla
del portal (la que ve recepción) refleja la llegada en su endpoint de estado.

Todos los datos usados son ficticios.
"""

import json
import os
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen

BASE_URL = os.getenv("DOSYS_API_URL", "http://127.0.0.1:8000").rstrip("/")
USER_AGENT = "D.O.S.Y.S/1.0 (verificacion academica)"
PATIENT = {"username": "paciente", "password": "Paciente123!"}
STAFF = {"username": "medico", "password": "Medico123!"}
EXPECTED_CODE = "A7K9M2"


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
        return error.code, json.loads(error.read().decode("utf-8"))


def portal_session():
    """Sesión del portal (recepción) para consultar el estado del check-in."""
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    data = urlencode(STAFF).encode()
    opener.open(Request(f"{BASE_URL}/portal/login", data=data, headers={"User-Agent": USER_AGENT}), timeout=15).read()
    return opener


def portal_state(opener, appointment_id: int):
    http_request = Request(
        f"{BASE_URL}/portal/citas/{appointment_id}/estado", headers={"User-Agent": USER_AGENT}
    )
    try:
        with opener.open(http_request, timeout=15) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


def main() -> None:
    _, login = request("/api/v1/auth/login", method="POST", body=PATIENT)
    token = login["access_token"]

    status, appointments = request("/api/v1/patients/me/appointments", token=token)
    assert status == 200 and appointments, "El paciente debe tener al menos una cita sembrada"
    appointment = appointments[0]
    appointment_id = appointment["id"]

    status, _ = request(
        f"/api/v1/patients/me/appointments/{appointment_id}/check-in",
        method="POST",
        token=token,
        body={"code": "0000"},
    )
    assert status == 400, "Un código incorrecto debe rechazarse"

    status, confirmed = request(
        f"/api/v1/patients/me/appointments/{appointment_id}/check-in",
        method="POST",
        token=token,
        body={"code": EXPECTED_CODE},
    )
    assert status == 200 and confirmed["checked_in_at"], "El código correcto debe confirmar la llegada"

    # La pantalla del portal (la que ve recepción) debe reflejar la llegada.
    portal = portal_session()
    status, state = portal_state(portal, appointment_id)
    assert status == 200 and state["checked_in"] is True and state["checked_in_label"], (
        "El portal debe ver la cita con llegada confirmada"
    )
    assert portal_state(portal, 999999)[0] == 404, "Una cita inexistente debe responder 404"

    status, again = request(
        f"/api/v1/patients/me/appointments/{appointment_id}/check-in",
        method="POST",
        token=token,
        body={"code": EXPECTED_CODE},
    )
    assert status == 200 and again["checked_in_at"] == confirmed["checked_in_at"], "El check-in debe ser idempotente"

    print(
        json.dumps(
            {
                "checkin": "ok",
                "appointment_id": appointment_id,
                "wrong_code": 400,
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
