"""Tipo SQLAlchemy que cifra y descifra texto de forma transparente.

La base de datos guarda ``enc:v1:<base64>``; la aplicación y la API reciben el
texto claro. El cifrado ocurre en el límite del ORM, así que ningún endpoint
necesita conocer los detalles de AES-GCM.
"""

from __future__ import annotations

from sqlalchemy.types import Text, TypeDecorator

from app.core.crypto import decrypt_text, encrypt_text


class EncryptedText(TypeDecorator):
    """Columna ``TEXT`` con cifrado AES-256-GCM en reposo."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect) -> str | None:
        return encrypt_text(value)

    def process_result_value(self, value: str | None, dialect) -> str | None:
        return decrypt_text(value)
