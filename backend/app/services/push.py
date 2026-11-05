"""Notificaciones push de seguridad con Firebase Cloud Messaging.

Con ``FCM_CREDENTIALS_FILE`` apuntando a la cuenta de servicio se envían
notificaciones reales; sin credenciales el envío queda **simulado** (log
informativo y ``(False, motivo)``), igual que el correo, para que la demo
funcione solo con el sondeo en primer plano.

El payload nunca incluye datos personales ni secretos: solo ``type`` y
``transfer_id``. El texto visible es genérico.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

_init_lock = threading.Lock()
_initialized = False

_NOTIFICATION_TITLE = "D.O.S.Y.S · Seguridad"
_NOTIFICATION_BODY = "Hay una solicitud de acceso esperando tu aprobación."


def delivery_enabled() -> bool:
    path = settings.fcm_credentials_file.strip()
    return bool(path) and Path(path).is_file()


def _ensure_app() -> None:
    global _initialized
    with _init_lock:
        if _initialized:
            return
        import firebase_admin
        from firebase_admin import credentials

        if not firebase_admin._apps:  # noqa: SLF001 — API pública de inicialización
            firebase_admin.initialize_app(
                credentials.Certificate(settings.fcm_credentials_file.strip())
            )
        _initialized = True


def _send_sync(fcm_token: str, transfer_id: str) -> tuple[bool, str]:
    try:
        _ensure_app()
        from firebase_admin import messaging

        message = messaging.Message(
            token=fcm_token,
            data={"type": "device_transfer", "transfer_id": transfer_id},
            notification=messaging.Notification(
                title=_NOTIFICATION_TITLE,
                body=_NOTIFICATION_BODY,
            ),
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    channel_id="security",
                    visibility="private",
                ),
            ),
        )
        messaging.send(message)
        return True, ""
    except Exception as error:  # firebase-admin lanza tipos propios por token inválido
        name = type(error).__name__
        if name in {"UnregisteredError", "SenderIdMismatchError", "InvalidArgumentError"}:
            logger.info("FCM rechazó el token del dispositivo (%s); se descartará.", name)
            return False, "token inválido"
        logger.warning("No se pudo enviar la notificación FCM: %s", name)
        return False, f"error de envío ({name})"


async def notify_device_transfer(fcm_token: str | None, transfer_id: str) -> tuple[bool, str]:
    """Despierta al dispositivo activo. Devuelve (enviado, motivo)."""
    if not fcm_token:
        return False, "sin token FCM registrado"
    if not delivery_enabled():
        logger.info(
            "Notificación simulada (sin FCM_CREDENTIALS_FILE): transferencia %s",
            transfer_id,
        )
        return False, "sin credenciales configuradas"
    return await asyncio.to_thread(_send_sync, fcm_token, transfer_id)
