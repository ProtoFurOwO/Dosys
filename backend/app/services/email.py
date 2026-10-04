"""Envío de correo transaccional.

Con ``RESEND_API_KEY`` configurada se envía el correo real a través de Resend;
sin ella el mensaje se registra en la bitácora del contenedor y el portal
muestra la vista previa simulada para que la demostración académica funcione
sin depender de un proveedor externo.
"""

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_RESEND_ENDPOINT = "https://api.resend.com/emails"


def delivery_enabled() -> bool:
    return bool(settings.resend_api_key.strip())


async def send_email(*, to: str, subject: str, text: str) -> bool:
    """Envía el correo y devuelve True solo si el proveedor lo aceptó."""
    if not to:
        return False
    if not delivery_enabled():
        logger.info("Correo simulado (sin RESEND_API_KEY): %s -> %s", to, subject)
        return False

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                _RESEND_ENDPOINT,
                headers={"Authorization": f"Bearer {settings.resend_api_key.strip()}"},
                json={
                    "from": settings.email_from,
                    "to": [to],
                    "subject": subject,
                    "text": text,
                },
            )
    except httpx.HTTPError:
        logger.warning("No se pudo contactar al proveedor de correo para enviar a %s", to)
        return False

    if response.status_code >= 400:
        logger.warning("El proveedor de correo respondió %s al enviar a %s", response.status_code, to)
        return False
    return True
