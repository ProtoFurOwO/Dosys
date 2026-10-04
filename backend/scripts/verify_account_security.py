"""Prueba de aceptación de la seguridad de cuentas.

Cubre: cambio de contraseña propio (API y portal), recuperación con token de un
solo uso, sesión renovable (refresh con rotación), límite de peticiones por IP y
la API de administración con los verbos PUT y DELETE.

Uso: python scripts/verify_account_security.py
"""

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
ADMIN = {"username": "admin", "password": "Admin123!"}
PATIENT = {"username": "paciente", "password": "Paciente123!"}

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


def portal_request(opener, path: str, fields: dict | list[tuple] | None = None):
    data = urlencode(fields, doseq=True).encode() if fields is not None else None
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


def main() -> int:
    suffix = time.strftime("%H%M%S")
    username = f"cuenta_prueba_{suffix}"
    original = "Cuenta1234"
    changed = "Cambiada1234"
    portal_password = "Portal12345"
    recovered = "Final12345"

    print("== Cambio de contraseña (API) ==")
    _, login = api("/api/v1/auth/login", method="POST", body={"username": PATIENT["username"], "password": PATIENT["password"]})
    check("login de paciente con token de renovación", bool(login.get("refresh_token")))

    # Cuenta desechable creada desde el portal para no tocar las cuentas demo.
    admin_portal = portal_opener()
    portal_request(admin_portal, "/portal/login", {"username": ADMIN["username"], "password": ADMIN["password"]})
    status, _ = portal_request(
        admin_portal,
        "/portal/usuarios/nuevo",
        {
            "full_name": f"Cuenta de prueba {suffix}",
            "specialty": "Verificación",
            "username": username,
            "password": original,
            "password_confirm": original,
        },
    )
    check("cuenta desechable creada desde el portal", status < 400, f"status={status}")

    status, login = api("/api/v1/auth/login", method="POST", body={"username": username, "password": original})
    check("login inicial de la cuenta desechable", status == 200, f"status={status}")
    token = login.get("access_token")

    status, body = api(
        "/api/v1/auth/password/change",
        method="POST",
        token=token,
        body={"current_password": "NoEsLaActual1", "new_password": changed, "new_password_confirm": changed},
    )
    check("cambio con contraseña actual incorrecta se rechaza", status == 400, f"status={status}")

    status, body = api(
        "/api/v1/auth/password/change",
        method="POST",
        token=token,
        body={"current_password": original, "new_password": "solamenteletras", "new_password_confirm": "solamenteletras"},
    )
    check("política de contraseña se valida", status == 400, f"status={status}")

    status, body = api(
        "/api/v1/auth/password/change",
        method="POST",
        token=token,
        body={"current_password": original, "new_password": changed, "new_password_confirm": changed},
    )
    check("cambio correcto responde 200", status == 200, f"status={status}")

    status, _ = api("/api/v1/auth/login", method="POST", body={"username": username, "password": original})
    check("la contraseña anterior ya no sirve", status == 401, f"status={status}")
    status, login = api("/api/v1/auth/login", method="POST", body={"username": username, "password": changed})
    check("la contraseña nueva sí sirve", status == 200, f"status={status}")
    token = login.get("access_token")

    print("== Cambio de contraseña (portal) ==")
    doctor_portal = portal_opener()
    portal_request(doctor_portal, "/portal/login", {"username": username, "password": changed})
    status, html = portal_request(
        doctor_portal,
        "/portal/seguridad/contrasena",
        {"current_password": changed, "new_password": portal_password, "new_password_confirm": portal_password},
    )
    check("el portal confirma el cambio de contraseña", "Contraseña actualizada" in html, f"status={status}")

    print("== Recuperación de contraseña ==")
    anonymous = portal_opener()
    status, html = portal_request(anonymous, "/portal/login")
    check("el acceso muestra el enlace de recuperación", "/portal/recuperar" in html)

    status, html = portal_request(anonymous, "/portal/recuperar", {"identifier": username})
    match = re.search(r"/portal/restablecer\?token=([A-Za-z0-9_\-]+)", html)
    check("se genera el enlace de restablecimiento", match is not None, f"status={status}")
    check("la vista previa simulada se muestra sin proveedor de correo", "Vista previa simulada" in html)

    if match:
        token_url = f"/portal/restablecer?token={match.group(1)}"
        status, html = portal_request(anonymous, token_url)
        check("la página de restablecimiento abre con el token", status == 200 and "Nueva contraseña" in html, f"status={status}")

        status, _ = portal_request(
            anonymous,
            "/portal/restablecer",
            {"token": match.group(1), "password": recovered, "password_confirm": recovered},
        )
        check("el restablecimiento se guarda", status < 400, f"status={status}")

        status, _ = api("/api/v1/auth/login", method="POST", body={"username": username, "password": recovered})
        check("se puede entrar con la contraseña restablecida", status == 200, f"status={status}")

        status, _ = portal_request(
            anonymous,
            "/portal/restablecer",
            {"token": match.group(1), "password": "OtraClave123", "password_confirm": "OtraClave123"},
        )
        check("el token de un solo uso ya no sirve", status == 400, f"status={status}")

    print("== Sesión renovable (refresh con rotación) ==")
    status, login = api("/api/v1/auth/login", method="POST", body={"username": PATIENT["username"], "password": PATIENT["password"]})
    first_refresh = login.get("refresh_token", "")
    check("el login entrega refresh token", bool(first_refresh))

    status, renewed = api("/api/v1/auth/refresh", method="POST", body={"refresh_token": first_refresh})
    check("el refresh entrega un acceso nuevo", status == 200 and bool(renewed.get("access_token")), f"status={status}")
    check("el refresh rota el token", renewed.get("refresh_token") and renewed["refresh_token"] != first_refresh)

    status, _ = api("/api/v1/auth/refresh", method="POST", body={"refresh_token": first_refresh})
    check("el refresh anterior queda revocado", status == 401, f"status={status}")

    status, _ = api("/api/v1/auth/2fa/status", token=renewed.get("access_token"))
    check("el acceso renovado sirve en la API", status == 200, f"status={status}")

    print("== API de administración (GET/PUT/DELETE) ==")
    status, admin_login = api("/api/v1/auth/login", method="POST", body=ADMIN)
    admin_token = admin_login.get("access_token")
    check("login de administrador", status == 200 and bool(admin_token), f"status={status}")

    status, users = api("/api/v1/admin/users", token=admin_token)
    if not isinstance(users, list):
        users = []
    check("GET /admin/users lista cuentas", status == 200 and any(u["username"] == username for u in users), f"status={status}")
    scratch = next((u for u in users if u["username"] == username), None)

    if scratch:
        status, updated = api(
            f"/api/v1/admin/users/{scratch['id']}/role",
            method="PUT",
            token=admin_token,
            body={"role_code": "patient"},
        )
        check("PUT cambia el rol de la cuenta", status == 200 and updated.get("role_code") == "patient", f"status={status}")

        status, _ = api(
            f"/api/v1/admin/users/{scratch['id']}/role",
            method="PUT",
            token=admin_token,
            body={"role_code": "rol_inexistente"},
        )
        check("PUT con rol inexistente responde 404", status == 404, f"status={status}")

    # Rol desechable para probar PUT/DELETE de roles.
    role_code = f"rol_prueba_{suffix}"
    status, _ = portal_request(
        admin_portal,
        "/portal/roles/nuevo",
        {"code": role_code, "name": "Rol de prueba", "description": "Verificación", "permissions": ["portal:access"]},
    )
    check("rol desechable creado desde el portal", status < 400, f"status={status}")

    status, roles = api("/api/v1/admin/roles", token=admin_token)
    check("GET /admin/roles lista roles", status == 200 and any(r["code"] == role_code for r in roles), f"status={status}")
    scratch_role = next((r for r in roles if r["code"] == role_code), None)
    admin_role = next((r for r in roles if r["code"] == "admin"), None)

    if scratch_role:
        status, updated = api(
            f"/api/v1/admin/roles/{scratch_role['id']}",
            method="PUT",
            token=admin_token,
            body={"name": "Rol de prueba editado", "description": "Verificación", "permissions": ["portal:access", "patients:read"]},
        )
        check(
            "PUT actualiza nombre y permisos del rol",
            status == 200 and updated.get("name") == "Rol de prueba editado" and "patients:read" in updated.get("permissions", []),
            f"status={status}",
        )

        status, _ = api(
            f"/api/v1/admin/roles/{scratch_role['id']}",
            method="PUT",
            token=admin_token,
            body={"name": "Rol de prueba", "permissions": ["permiso_inexistente"]},
        )
        check("PUT con permiso desconocido responde 422", status == 422, f"status={status}")

        status, _ = api(f"/api/v1/admin/roles/{scratch_role['id']}", method="DELETE", token=admin_token)
        check("DELETE elimina el rol desechable", status == 204, f"status={status}")

        status, _ = api(f"/api/v1/admin/roles/{scratch_role['id']}", method="DELETE", token=admin_token)
        check("DELETE repetido responde 404", status == 404, f"status={status}")

    if admin_role:
        status, _ = api(f"/api/v1/admin/roles/{admin_role['id']}", method="DELETE", token=admin_token)
        check("un rol base no se elimina (409)", status == 409, f"status={status}")

    print("== Límite de peticiones ==")
    limited = False
    for _ in range(25):
        status, _ = api("/api/v1/auth/login", method="POST", body={"username": "no_existe_limite", "password": "Incorrecta999"})
        if status == 429:
            limited = True
            break
    check("el exceso de intentos responde 429", limited)

    print()
    print(f"Resultado: {_passed} pruebas correctas, {_failed} fallidas")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
