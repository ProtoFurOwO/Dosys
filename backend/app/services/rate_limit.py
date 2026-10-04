"""Límite de peticiones para las rutas sensibles de autenticación.

Ventana deslizante en memoria del proceso: suficiente para el despliegue de un
solo contenedor. Con varias instancias se sustituye por Redis sin cambiar las
rutas que lo usan.
"""

from collections import deque
from time import monotonic

from fastapi import Request

from app.core.config import settings

_WINDOW_SECONDS = 60
_buckets: dict[str, deque[float]] = {}


def client_ip(request: Request) -> str:
    """IP real del cliente respetando el proxy inverso (Nginx Proxy Manager)."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "desconocida"


def exceeded(scope: str, request: Request) -> bool:
    """Registra la petición y devuelve True si esa IP superó el límite por minuto."""
    key = f"{scope}:{client_ip(request)}"
    now = monotonic()
    bucket = _buckets.setdefault(key, deque())
    while bucket and now - bucket[0] >= _WINDOW_SECONDS:
        bucket.popleft()
    if len(bucket) >= settings.auth_rate_limit_per_minute:
        return True
    bucket.append(now)
    return False
