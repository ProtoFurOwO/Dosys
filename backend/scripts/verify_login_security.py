"""Prueba de aceptación de la seguridad del login.

Cubre: bloqueo por intentos fallidos, desbloqueo desde el portal, activación de
2FA (TOTP), login en dos pasos, código incorrecto, token de acceso rechazado
como desafío y códigos de recuperación de un solo uso.

No usa dependencias extra: el TOTP se calcula aquí con HMAC-SHA1 (RFC 6238).
"""

import base64
import hashlib
import hmac
import json
import os
import re
import time
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen

BASE_URL = os.getenv("DOSYS_API_URL", "http://127.0.0.1:8000").rstrip("/")
USER_AGENT = "D.O.Y.S.S/1.0 (verificacion academica)"
DOCTOR = {"username": "medico", "password": "Medico123!"}
WRONG_PASSWORD = "Incorrecta999"


def api(path: str, *, method: str = "GET", body: dict | None = None, token: str | None = None):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    headers = {"User-Agent": USER_AGENT}
    if data:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=15) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        payload = error.read().decode("utf-8")
        try:
            return error.code, json.loads(payload)
        except json.JSONDecodeError:
            return error.code, {"detail": payload}


def totp_now(secret: str, step: int = 30, digits: int = 6) -> str:
    padding = "=" * ((8 - len(secret) % 8) % 8)
    key = base64.b32decode(secret.upper() + padding)
    counter = int(time.time()) // step
    digest = hmac.new(key, counter.to_bytes(8, "big"), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (int.from_bytes(digest[offset : offset + 4], "big") & 0x7FFFFFFF) % (10**digits)
    return f"{code:0{digits}d}"


def portal_opener():
    return build_opener(HTTPCookieProcessor(CookieJar()))


def portal_request(opener, path: str, fields: dict | None = None):
    data = urlencode(fields).encode() if fields is not None else None
    request = Request(
        f"{BASE_URL}{path}",
        data=data,
        headers={"User-Agent": USER_AGENT},
        method="POST" if fields is not None else "GET",
    )
    try:
        with opener.open(request, timeout=15) as response:
            return response.status, response.read().decode("utf-8")
    except HTTPError as error:
        return error.code, error.read().decode("utf-8")


def main() -> None:
    suffix = time.strftime("%H%M%S")
    username = f"seg_prueba_{suffix}"
    password = "Prueba1234"

    portal = portal_opener()
    portal_request(portal, "/portal/login", DOCTOR)

    # 1. Crear un paciente de prueba desde el portal.
    status, html = portal_request(
        portal,
        "/portal/pacientes/nuevo",
        {
            "full_name": "Paciente Seguridad",
            "curp": f"TEST{suffix}HCSRRN09",
            "birth_date": "1999-05-05",
            "blood_type": "B+",
            "emergency_contact": "Contacto Seguridad",
            "email": f"{username}@correo.com",
            "username": username,
            "password": password,
            "password_confirm": password,
        },
    )
    assert status == 201, f"El paciente de prueba debe crearse (fue {status})"

    # 2. Bloqueo por intentos fallidos.
    for _ in range(5):
        status, _ = api("/api/v1/auth/login", method="POST", body={"username": username, "password": WRONG_PASSWORD})
        assert status == 401, "Cada intento fallido debe responder 401"
    status, body = api("/api/v1/auth/login", method="POST", body={"username": username, "password": password})
    assert status == 423, f"La cuenta bloqueada debe responder 423 (fue {status})"
    assert "bloqueada" in body["detail"].lower()

    # 3. Desbloqueo desde el expediente del paciente (lo hace el médico).
    match = re.search(r'/portal/pacientes/(\d+)"', html)
    assert match, "La credencial debe enlazar al expediente del paciente"
    patient_id = match.group(1)
    status, body_text = portal_request(portal, f"/portal/pacientes/{patient_id}/desbloquear", {})
    assert status == 200, f"desbloqueo respondio {status}: {body_text[:160]}"

    status, login = api("/api/v1/auth/login", method="POST", body={"username": username, "password": password})
    assert status == 200 and "access_token" in login, "Tras desbloquear debe poder entrar"
    token = login["access_token"]

    # 4. Un token de acceso no sirve como desafío de 2FA.
    status, _ = api(
        "/api/v1/auth/2fa/verify",
        method="POST",
        body={"challenge_token": token, "code": "123456"},
    )
    assert status == 401, "El token de acceso no debe aceptarse como desafío 2FA"

    # 5. Activar 2FA y confirmar con un código real.
    status, setup = api("/api/v1/auth/2fa/setup", method="POST", token=token)
    assert status == 200 and "secret" in setup, "El setup debe devolver el secreto y la URI"
    assert setup["otpauth_uri"].startswith("otpauth://totp/")

    code = totp_now(setup["secret"])
    status, enabled = api("/api/v1/auth/2fa/confirm", method="POST", token=token, body={"code": code})
    assert status == 200 and enabled["enabled"] is True, "El código correcto debe activar el 2FA"
    assert len(enabled["recovery_codes"]) == 8, "Deben generarse 8 códigos de recuperación"
    recovery_code = enabled["recovery_codes"][0]

    status, status_body = api("/api/v1/auth/2fa/status", token=token)
    assert status == 200 and status_body["enabled"] and status_body["recovery_codes_remaining"] == 8

    # 6. Login en dos pasos.
    status, challenge = api("/api/v1/auth/login", method="POST", body={"username": username, "password": password})
    assert status == 200 and challenge.get("requires_2fa") is True, "El login debe pedir el segundo factor"
    challenge_token = challenge["challenge_token"]

    status, _ = api(
        "/api/v1/auth/2fa/verify",
        method="POST",
        body={"challenge_token": challenge_token, "code": "000000"},
    )
    assert status == 401, "Un código TOTP incorrecto debe rechazarse"

    status, tokens = api(
        "/api/v1/auth/2fa/verify",
        method="POST",
        body={"challenge_token": challenge_token, "code": totp_now(setup["secret"])},
    )
    assert status == 200 and "access_token" in tokens, "El código correcto completa el login"

    # 7. Código de recuperación: sirve una vez y no se repite.
    status, challenge = api("/api/v1/auth/login", method="POST", body={"username": username, "password": password})
    challenge_token = challenge["challenge_token"]
    status, recovered = api(
        "/api/v1/auth/2fa/verify",
        method="POST",
        body={"challenge_token": challenge_token, "code": recovery_code},
    )
    assert status == 200 and "access_token" in recovered, "El código de recuperación debe servir"

    status, challenge = api("/api/v1/auth/login", method="POST", body={"username": username, "password": password})
    challenge_token = challenge["challenge_token"]
    status, _ = api(
        "/api/v1/auth/2fa/verify",
        method="POST",
        body={"challenge_token": challenge_token, "code": recovery_code},
    )
    assert status == 401, "Un código de recuperación ya usado no debe servir"

    status, status_body = api("/api/v1/auth/2fa/status", token=recovered["access_token"])
    assert status_body["recovery_codes_remaining"] == 7, "Debe quedar un código de recuperación menos"

    print(
        json.dumps(
            {
                "lockout": "5 intentos -> 423",
                "unlock_por_portal": True,
                "access_token_rechazado_como_desafio": True,
                "2fa_activado": True,
                "login_en_dos_pasos": True,
                "codigo_incorrecto": 401,
                "codigo_recuperacion_un_solo_uso": True,
                "recovery_codes_restantes": status_body["recovery_codes_remaining"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
