"""Prueba de aceptación de la transferencia de sesión entre dispositivos.

Cubre el flujo completo P2P: dispositivo nuevo (B) recibe un desafío, propone
el código que muestra el dispositivo activo (A), A lo compara y aprueba con su
token criptográfico, B recibe los tokens una sola vez y A queda sin acceso de
inmediato. También valida límites, rechazos y las alternativas para no dejar al
paciente fuera (2FA, liberar desde el portal, cierre de sesión).

Uso: python scripts/verify_device_transfer.py
Respeta DOSYS_API_URL, igual que el resto de scripts verify_*.
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
USER_AGENT = "D.O.S.Y.S/1.0 (verificacion academica)"
DOCTOR = {"username": "medico", "password": "Medico123!"}
PASSWORD = "Prueba1234"

_passed = 0
_failed = 0
_patient_counter = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"  OK   {name}")
    else:
        _failed += 1
        print(f"  FALLA {name} {detail}")


def api(path: str, *, method: str = "GET", body: dict | None = None, token: str | None = None):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    headers = {"User-Agent": USER_AGENT}
    if data:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=20) as response:
            payload = response.read().decode("utf-8")
            return response.status, json.loads(payload) if payload else {}
    except HTTPError as error:
        payload = error.read().decode("utf-8")
        try:
            return error.code, json.loads(payload)
        except json.JSONDecodeError:
            return error.code, {"detail": payload}


def portal_opener():
    return build_opener(HTTPCookieProcessor(CookieJar()))


def portal_request(opener, path: str, fields: dict | None = None):
    data = urlencode(fields, doseq=True).encode() if fields is not None else None
    request = Request(
        f"{BASE_URL}{path}",
        data=data,
        headers={"User-Agent": USER_AGENT},
        method="POST" if fields is not None else "GET",
    )
    try:
        with opener.open(request, timeout=20) as response:
            return response.status, response.read().decode("utf-8")
    except HTTPError as error:
        return error.code, error.read().decode("utf-8")


def totp_now(secret: str, step: int = 30, digits: int = 6) -> str:
    padding = "=" * ((8 - len(secret) % 8) % 8)
    key = base64.b32decode(secret.upper() + padding)
    counter = int(time.time()) // step
    digest = hmac.new(key, counter.to_bytes(8, "big"), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (int.from_bytes(digest[offset : offset + 4], "big") & 0x7FFFFFFF) % (10**digits)
    return f"{code:0{digits}d}"


def create_patient(portal, prefix: str) -> tuple[str, str]:
    global _patient_counter
    _patient_counter += 1
    suffix = time.strftime("%H%M%S")
    username = f"{prefix}_{suffix}"
    status, html = portal_request(
        portal,
        "/portal/pacientes/nuevo",
        {
            "full_name": f"Paciente {prefix} {suffix}",
            "curp": f"TEST{suffix}HCSRRN{_patient_counter:02d}",
            "birth_date": "1999-05-05",
            "blood_type": "B+",
            "emergency_contact": "Contacto de prueba",
            "email": f"{username}@correo.com",
            "username": username,
            "password": PASSWORD,
            "password_confirm": PASSWORD,
        },
    )
    assert status == 201, f"No se creó el paciente de prueba ({status})"
    match = re.search(r'/portal/pacientes/(\d+)"', html)
    assert match, "La credencial debe enlazar al expediente del paciente"
    return username, match.group(1)


def login(username: str, device_id: str | None = None, device_name: str | None = None):
    body = {"username": username, "password": PASSWORD}
    if device_id is not None:
        body["device_id"] = device_id
    if device_name is not None:
        body["device_name"] = device_name
    return api("/api/v1/auth/login", method="POST", body=body)


def transfer_status(transfer_id: str, challenge_token: str):
    return api(
        f"/api/v1/auth/device-transfer/{transfer_id}/status",
        method="POST",
        body={"challenge_token": challenge_token},
    )


def submit_code(transfer_id: str, challenge_token: str, code: str):
    return api(
        f"/api/v1/auth/device-transfer/{transfer_id}/code",
        method="POST",
        body={"challenge_token": challenge_token, "code": code},
    )


def pending_for(token: str):
    return api("/api/v1/devices/transfers/pending", token=token)


def main() -> int:
    portal = portal_opener()
    portal_request(portal, "/portal/login", DOCTOR)
    stamp = time.strftime("%H%M%S")

    # ── Flujo feliz, cierre inmediato de A y límites ──────────────────────────
    print("== Flujo feliz (A aprueba, B recibe tokens una sola vez) ==")
    username, patient_id = create_patient(portal, "transf")
    device_a = f"device-a-{stamp}"
    device_b = f"device-b-{stamp}"

    status, first = login(username, device_a, "Equipo A")
    check("el primer login registra el dispositivo", status == 200 and "access_token" in first, f"status={status}")
    token_a = first.get("access_token")
    refresh_a = first.get("refresh_token")

    status, again = login(username, device_a, "Equipo A")
    check("volver a entrar desde el mismo dispositivo es normal", status == 200 and "access_token" in again, f"status={status}")

    status, challenge = login(username, device_b, "Equipo B")
    check(
        "un dispositivo distinto recibe el desafío",
        status == 200 and challenge.get("requires_device_transfer") is True,
        f"status={status}",
    )
    check("el dispositivo nuevo no recibe tokens", "access_token" not in challenge)
    transfer_id = challenge["transfer_id"]
    challenge_token = challenge["challenge_token"]

    status, pending = pending_for(token_a)
    check(
        "A ve la solicitud con su token de aprobación",
        status == 200 and pending.get("approval_token") and pending.get("submitted_code") is None,
        f"status={status}",
    )

    status, submitted = submit_code(transfer_id, challenge_token, "482913")
    check("B propone el código (202)", status == 202 and submitted.get("submissions_left") == 2, f"status={status}")

    status, _ = submit_code(transfer_id, challenge_token, "111111")
    check("no se aceptan dos propuestas simultáneas (409)", status == 409, f"status={status}")

    status, pending = pending_for(token_a)
    check("A recibe la propuesta para compararla localmente", status == 200 and pending.get("submitted_code") == "482913")

    status, _ = api(
        f"/api/v1/devices/transfers/{transfer_id}/approve",
        method="POST",
        token=token_a,
        body={"approval_token": "x" * 32},
    )
    check("un token de aprobación incorrecto se rechaza (403)", status == 403, f"status={status}")

    status, _ = api(
        f"/api/v1/devices/transfers/{transfer_id}/approve",
        method="POST",
        token=token_a,
        body={"approval_token": pending["approval_token"]},
    )
    check("A aprueba con su token criptográfico", status == 200, f"status={status}")

    status, resolved = transfer_status(transfer_id, challenge_token)
    check("B consulta y recibe los tokens", status == 200 and resolved.get("status") == "approved" and resolved.get("tokens"), f"status={status}")
    token_b = (resolved.get("tokens") or {}).get("access_token")

    status, repeated = transfer_status(transfer_id, challenge_token)
    check("B no recibe los tokens una segunda vez", status == 200 and repeated.get("tokens") is None, f"status={status}")

    status, _ = api("/api/v1/patients/me", token=token_a)
    check("el access token de A responde 401 de inmediato", status == 401, f"status={status}")

    status, _ = api("/api/v1/auth/refresh", method="POST", body={"refresh_token": refresh_a})
    check("el refresh token de A quedó revocado", status == 401, f"status={status}")

    status, _ = api("/api/v1/patients/me", token=token_b)
    check("el access token de B funciona", status == 200, f"status={status}")

    status, no_device = login(username)
    check(
        "omitir device_id con un dispositivo activo también exige transferencia",
        status == 200 and no_device.get("requires_device_transfer") is True,
        f"status={status}",
    )
    status, _ = api(
        f"/api/v1/auth/device-transfer/{no_device['transfer_id']}/cancel",
        method="POST",
        body={"challenge_token": no_device["challenge_token"]},
    )
    check("B puede cancelar su solicitud", status == 200, f"status={status}")

    status, challenge_c = login(username, f"device-c-{stamp}", "Equipo C")
    status, _ = api(
        f"/api/v1/devices/transfers/{challenge_c['transfer_id']}/approve",
        method="POST",
        token=token_a,
        body={"approval_token": "y" * 32},
    )
    check("un dispositivo que ya no es el activo no puede aprobar (401)", status == 401, f"status={status}")
    api(
        f"/api/v1/auth/device-transfer/{challenge_c['transfer_id']}/cancel",
        method="POST",
        body={"challenge_token": challenge_c["challenge_token"]},
    )

    limited = False
    for index in range(6):
        status, body = login(username, f"device-x{index}-{stamp}", f"Equipo X{index}")
        if status == 429:
            limited = True
            break
    check("el límite de solicitudes por hora responde 429", limited)

    # ── Códigos incorrectos, not_me y expiración ──────────────────────────────
    print("== Rechazos y intentos agotados ==")
    username2, _ = create_patient(portal, "rechaz")
    status, first2 = login(username2, f"device-a-{stamp}", "Equipo A")
    token_a2 = first2.get("access_token")
    check("segundo paciente con dispositivo registrado", status == 200 and bool(token_a2), f"status={status}")

    status, challenge2 = login(username2, f"device-b-{stamp}", "Equipo B")
    transfer2 = challenge2["transfer_id"]
    token_challenge2 = challenge2["challenge_token"]

    for attempt in range(3):
        status, _ = submit_code(transfer2, token_challenge2, f"11111{attempt}")
        status, pending2 = pending_for(token_a2)
        status, _ = api(
            f"/api/v1/devices/transfers/{transfer2}/reject",
            method="POST",
            token=token_a2,
            body={"reason": "mismatch"},
        )
        check(f"propuesta incorrecta {attempt + 1} rechazada", status == 200, f"status={status}")

    status, failed = transfer_status(transfer2, token_challenge2)
    check("tras 3 propuestas la transferencia pasa a failed", failed.get("status") == "failed", f"status={failed.get('status')}")
    status, pending2 = pending_for(token_a2)
    check("A ya no ve propuestas pendientes (204)", status == 204, f"status={status}")
    status, _ = submit_code(transfer2, token_challenge2, "222222")
    check("la cuarta propuesta se rechaza (409)", status == 409, f"status={status}")

    status, challenge3 = login(username2, f"device-c-{stamp}", "Equipo C")
    status, pending3 = pending_for(token_a2)
    status, _ = api(
        f"/api/v1/devices/transfers/{challenge3['transfer_id']}/reject",
        method="POST",
        token=token_a2,
        body={"reason": "not_me"},
    )
    check("el botón 'No fui yo' termina la transferencia", status == 200 and pending3.get("approval_token"), f"status={status}")
    status, rejected = transfer_status(challenge3["transfer_id"], challenge3["challenge_token"])
    check("B ve el rechazo", rejected.get("status") == "rejected", f"status={rejected.get('status')}")
    status, _ = api("/api/v1/patients/me", token=token_a2)
    check("A conserva el acceso tras rechazar", status == 200, f"status={status}")

    status, challenge4 = login(username2, f"device-d-{stamp}", "Equipo D")
    status, pending4 = pending_for(token_a2)
    api(
        f"/api/v1/devices/transfers/{challenge4['transfer_id']}/reject",
        method="POST",
        token=token_a2,
        body={"reason": "expired"},
    )
    status, _ = api(
        f"/api/v1/devices/transfers/{challenge4['transfer_id']}/approve",
        method="POST",
        token=token_a2,
        body={"approval_token": pending4.get("approval_token", "z" * 32)},
    )
    check("una transferencia expirada no se puede aprobar (409)", status == 409, f"status={status}")

    status, challenge5 = login(username2, f"device-e-{stamp}", "Equipo E")
    status, fallback = api(
        f"/api/v1/auth/device-transfer/{challenge5['transfer_id']}/fallback",
        method="POST",
        body={"challenge_token": challenge5["challenge_token"]},
    )
    check(
        "sin 2FA, la alternativa invita a recuperar la contraseña (409)",
        status == 409 and "contraseña" in fallback.get("detail", "").lower(),
        f"status={status}",
    )

    # ── 2FA como alternativa y liberación desde el portal ─────────────────────
    print("== Alternativas: 2FA y liberación desde el portal ==")
    username3, patient3_id = create_patient(portal, "dospas")
    status, first3 = login(username3, f"device-a-{stamp}", "Equipo A")
    token_a3 = first3.get("access_token")
    status, setup = api("/api/v1/auth/2fa/setup", method="POST", token=token_a3)
    status, enabled = api(
        "/api/v1/auth/2fa/confirm",
        method="POST",
        token=token_a3,
        body={"code": totp_now(setup["secret"])},
    )
    check("2FA activado en la cuenta de prueba", status == 200 and enabled.get("enabled"), f"status={status}")

    status, challenge6 = login(username3, f"device-b-{stamp}", "Equipo B")
    check("con 2FA, un dispositivo nuevo sigue exigiendo transferencia", challenge6.get("requires_device_transfer") is True)

    status, fallback = api(
        f"/api/v1/auth/device-transfer/{challenge6['transfer_id']}/fallback",
        method="POST",
        body={"challenge_token": challenge6["challenge_token"]},
    )
    check(
        "con 2FA, la alternativa devuelve el desafío del segundo factor",
        status == 200 and fallback.get("requires_2fa") is True,
        f"status={status}",
    )
    status, verified = api(
        "/api/v1/auth/2fa/verify",
        method="POST",
        body={"challenge_token": fallback["challenge_token"], "code": totp_now(setup["secret"])},
    )
    check("el código TOTP completa la recuperación de acceso", status == 200 and bool(verified.get("access_token")), f"status={status}")
    token_b3 = verified.get("access_token")
    status, _ = api("/api/v1/patients/me", token=token_a3)
    check("el dispositivo anterior queda fuera tras usar la alternativa", status == 401, f"status={status}")
    status, _ = api("/api/v1/patients/me", token=token_b3)
    check("el dispositivo nuevo entra con su token", status == 200, f"status={status}")

    status, html = portal_request(portal, f"/portal/usuarios/{patient3_id}/liberar-dispositivo", {})
    check("el portal libera el dispositivo de confianza", status == 200 and "liberado" in html.lower(), f"status={status}")

    status, fresh = login(username3, f"device-f-{stamp}", "Equipo F")
    check("tras liberarlo, entrar desde cualquier teléfono es normal", status == 200 and "access_token" in fresh, f"status={fresh.get('detail', status)}")

    status, _ = api(
        "/api/v1/auth/logout",
        method="POST",
        body={"refresh_token": fresh.get("refresh_token", "")},
    )
    check("cerrar sesión revoca la sesión renovable", status == 200, f"status={status}")
    status, after_logout = login(username3, f"device-g-{stamp}", "Equipo G")
    check(
        "cerrar sesión libera el dispositivo de confianza",
        status == 200 and "access_token" in after_logout,
        f"status={status}",
    )

    # ── Otros roles no cambian ────────────────────────────────────────────────
    print("== Sin cambios para otros roles ==")
    status, doctor = api("/api/v1/auth/login", method="POST", body=DOCTOR)
    check(
        "el personal del portal entra sin transferencia",
        status == 200 and doctor.get("role") == "doctor" and "access_token" in doctor,
        f"status={status}",
    )

    print()
    print(f"Resultado: {_passed} pruebas correctas, {_failed} fallidas")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
