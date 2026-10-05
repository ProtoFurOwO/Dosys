"""Demostración guiada de la seguridad de la API (para la presentación).

Ejecuta paso a paso, con explicación, los requisitos técnicos y de seguridad
del caso práctico: petición sin token (401), JWT y sus claims, petición
autenticada con Authorization: Bearer, autorización por rol (403), firma
alterada (401) y refresh token con rotación (401).

Uso:
    py -3.12 scripts\\demo_api_seguridad.py
    py -3.12 scripts\\demo_api_seguridad.py --limite   (además demuestra el 429)

Variables opcionales:
    DOSYS_API_URL        por defecto https://medicos.stolasimp.dev
    DOSYS_DEMO_USUARIO   por defecto medico
    DOSYS_DEMO_PASSWORD  por defecto Medico123!
"""

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE_URL = os.getenv("DOSYS_API_URL", "https://medicos.stolasimp.dev").rstrip("/")
USER_AGENT = "D.O.S.Y.S/1.0 (demostracion academica)"
USERNAME = os.getenv("DOSYS_DEMO_USUARIO", "medico")
PASSWORD = os.getenv("DOSYS_DEMO_PASSWORD", "Medico123!")
ANCHO = 66

if hasattr(sys.stdout, "reconfigure"):
    # Consolas de Windows: evita errores si algún carácter no está en la página de códigos.
    sys.stdout.reconfigure(errors="replace")

_aciertos = 0


def titulo(numero: str, texto: str) -> None:
    print()
    print("=" * ANCHO)
    print(f" {numero}. {texto}")
    print("=" * ANCHO)


def veredicto(condicion: bool, texto: str) -> None:
    global _aciertos
    marca = "OK  " if condicion else "REVISA"
    if condicion:
        _aciertos += 1
    print(f"  [{marca}] {texto}")


def api(path: str, *, method: str = "GET", body: dict | None = None, token: str | None = None):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    headers = {"User-Agent": USER_AGENT}
    if data:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = response.read().decode("utf-8")
            return response.status, json.loads(payload) if payload else {}
    except urllib.error.HTTPError as error:
        payload = error.read().decode("utf-8")
        try:
            return error.code, json.loads(payload)
        except json.JSONDecodeError:
            return error.code, {"detail": payload}


def mostrar_jwt(token: str) -> None:
    def decode(part: str):
        padding = "=" * ((4 - len(part) % 4) % 4)
        return json.loads(base64.urlsafe_b64decode(part + padding))

    encabezado, contenido, _ = token.split(".")
    print(f"  Token (recortado): {token[:48]}…")
    print(f"  Encabezado: {json.dumps(decode(encabezado))}")
    claims = decode(contenido)
    resumen = {
        "sub": claims.get("sub"),
        "role": claims.get("role"),
        "permissions": f"{len(claims.get('permissions', []))} permisos",
        "purpose": claims.get("purpose"),
        "exp": time.strftime("%H:%M:%S", time.localtime(claims.get("exp", 0))),
    }
    print(f"  Contenido: {json.dumps(resumen, ensure_ascii=False)}")
    minutos = max(0, round((claims.get("exp", 0) - time.time()) / 60))
    print(f"  Firmado con HS256 (secreto fuera del código) y expira en ~{minutos} minutos.")


def main() -> int:
    print()
    print("#" * ANCHO)
    print("#  D.O.S.Y.S · Demostración de seguridad de la API REST")
    print(f"#  Servidor: {BASE_URL}")
    print(f"#  Cuenta:   {USERNAME}")
    print("#" * ANCHO)

    titulo("1", "Petición sin token: el servidor exige autenticación")
    status, body = api("/api/v1/patients/me")
    print(f"  GET /api/v1/patients/me  ->  {status}  {body.get('detail', '')}")
    veredicto(status == 401, "Sin JWT no se entrega ningún dato (401).")

    titulo("2", "Inicio de sesión: aquí nace el JWT")
    status, login = api("/api/v1/auth/login", method="POST", body={"username": USERNAME, "password": PASSWORD})
    if status == 200 and login.get("requires_2fa"):
        print("  Esta cuenta tiene segundo factor activo.")
        print("  Desde el portal: Pacientes/Usuarios -> 'Reiniciar 2FA', o usa otra cuenta con DOSYS_DEMO_USUARIO.")
        return 1
    veredicto(status == 200 and bool(login.get("access_token")), f"Login correcto ({status}).")
    token = login.get("access_token", "")
    refresh = login.get("refresh_token", "")
    mostrar_jwt(token)
    veredicto(bool(refresh), "También entrega refresh token (renovación de 7 días con rotación).")

    titulo("3", "Petición autenticada con el encabezado Authorization")
    print(f"  Encabezado enviado: Authorization: Bearer {token[:32]}…")
    status, pacientes = api("/api/v1/doctor/patients", token=token)
    total = len(pacientes) if isinstance(pacientes, list) else 0
    veredicto(status == 200, f"El endpoint clínico responde {status} y entrega {total} pacientes.")

    titulo("4", "Autorización por rol: el servidor decide, no la interfaz")
    status, body = api("/api/v1/admin/users", token=token)
    print(f"  GET /api/v1/admin/users con el token del médico  ->  {status}  {body.get('detail', '')}")
    veredicto(status == 403, "El rol 'doctor' no administra usuarios: 403 aunque el endpoint exista.")

    titulo("5", "Firma del token: cualquier alteración se detecta")
    alterado = token[:-2] + ("AA" if not token.endswith("AA") else "BB")
    status, body = api("/api/v1/doctor/patients", token=alterado)
    print(f"  Token con la firma alterada  ->  {status}  {body.get('detail', '')}")
    veredicto(status == 401, "La firma HS256 no coincide: 401.")

    titulo("6", "Renovación de sesión: refresh de un solo uso (rotación)")
    status, renovado = api("/api/v1/auth/refresh", method="POST", body={"refresh_token": refresh})
    veredicto(status == 200 and bool(renovado.get("access_token")), f"El refresh entrega un acceso nuevo ({status}).")
    status, body = api("/api/v1/auth/refresh", method="POST", body={"refresh_token": refresh})
    print(f"  Reutilizar el refresh anterior  ->  {status}  {body.get('detail', '')}")
    veredicto(status == 401, "El refresh usado queda revocado: no se puede reutilizar.")

    if "--limite" in sys.argv:
        titulo("7", "Límite de peticiones (nota: limita el login ~1 minuto)")
        limite = None
        for intento in range(1, 26):
            status, _ = api("/api/v1/auth/login", method="POST", body={"username": "no_existe_demo", "password": "Incorrecta999"})
            if status == 429:
                limite = intento
                break
        veredicto(limite is not None, f"El servidor responde 429 al intento {limite} (rate limiting activo).")

    print()
    print("#" * ANCHO)
    print(f"#  Demostración completa: {_aciertos} verificaciones correctas")
    print("#" * ANCHO)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
