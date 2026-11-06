"""Clientes del resumen del expediente.

- LocalLlmClient: resumen determinista generado en el servidor, sin red.
- AnthropicLlmClient: httpx contra la API de mensajes del proveedor.

Ninguno registra cuerpos de petición ni de respuesta, y todas las fallas se
traducen a `AiUnavailable` sin datos clínicos en el mensaje.
"""

from __future__ import annotations

import json
from typing import Protocol

import httpx

from app.core.config import settings
from app.services.local_summary import build_local_summary

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
MAX_TOKENS = 1500


class AiUnavailable(RuntimeError):
    """La función no está disponible o el proveedor falló (mensaje sin datos)."""


class LlmClient(Protocol):
    async def complete(self, system: str, user_json: str) -> str: ...


class LocalLlmClient:
    """Agrupa, ordena y marca inconsistencias con reglas, sin salir a la red."""

    async def complete(self, system: str, user_json: str) -> str:
        return json.dumps(build_local_summary(json.loads(user_json)), ensure_ascii=False)


# Compatibilidad con la configuración anterior (AI_PROVIDER=fake).
FakeLlmClient = LocalLlmClient


class AnthropicLlmClient:
    """Cliente HTTP de la API de mensajes de Anthropic (sin SDK)."""

    def __init__(self) -> None:
        self.api_key = settings.ai_api_key
        self.model = settings.ai_model
        self.timeout = settings.ai_timeout_seconds

    async def complete(self, system: str, user_json: str) -> str:
        if not self.api_key or not self.model:
            raise AiUnavailable("El proveedor del modelo no está configurado.")

        body = {
            "model": self.model,
            "max_tokens": MAX_TOKENS,
            "system": system,
            "messages": [{"role": "user", "content": user_json}],
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

        # Un solo reintento y solo ante error 5xx; nunca se registra el cuerpo.
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(ANTHROPIC_URL, headers=headers, json=body)
            except httpx.HTTPError as exc:
                raise AiUnavailable("No se pudo contactar al proveedor del modelo.") from exc

            if response.status_code >= 500 and attempt == 0:
                continue
            if response.status_code >= 400:
                raise AiUnavailable("El proveedor del modelo rechazó la solicitud.")
            try:
                payload = response.json()
                return payload["content"][0]["text"]
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                raise AiUnavailable("El proveedor devolvió una respuesta no válida.") from exc

        raise AiUnavailable("El proveedor del modelo no está disponible.")


def build_llm_client() -> LlmClient:
    if settings.ai_provider in ("local", "fake"):
        return LocalLlmClient()
    if settings.ai_provider == "anthropic":
        return AnthropicLlmClient()
    raise AiUnavailable("Proveedor de modelo no soportado.")
