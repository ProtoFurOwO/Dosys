"""Límite de peticiones para las rutas sensibles de autenticación.

Ventana deslizante en memoria del proceso: suficiente para el despliegue de un
solo contenedor. Con varias instancias se sustituye por Redis sin cambiar las
rutas que lo usan.
"""

from collections import deque
from time import monotonic

from fastapi import Request

from app.core.config import settings
from app.core.request_ip import resolve_client_ip

_WINDOW_SECONDS = 60
_buckets: dict[str, deque[float]] = {}


def client_ip(request: Request) -> str:
    """IP real del cliente; misma resolución que la auditoría."""
    return resolve_client_ip(request) or "desconocida"


def exceeded(scope: str, request: Request, limit: int | None = None) -> bool:
    """Registra la petición y devuelve True si esa IP superó el límite por minuto.

    ``limit`` permite un umbral propio para el sondeo de estado, que es más
    frecuente que el resto de rutas de autenticación.
    """
    key = f"{scope}:{client_ip(request)}"
    now = monotonic()
    bucket = _buckets.setdefault(key, deque())
    while bucket and now - bucket[0] >= _WINDOW_SECONDS:
        bucket.popleft()
    threshold = limit if limit is not None else settings.auth_rate_limit_per_minute
    if len(bucket) >= threshold:
        return True
    bucket.append(now)
    return False
