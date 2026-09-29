"""Genera el código TOTP de 6 dígitos a partir del secreto base32.

Útil para pruebas automatizadas y como respaldo en la demo si el teléfono falla.

Uso:
    py -3.12 scripts/totp_code.py <secreto_base32>
"""

import base64
import hashlib
import hmac
import sys
import time


def totp_now(secret: str, step: int = 30, digits: int = 6) -> str:
    padding = "=" * ((8 - len(secret) % 8) % 8)
    key = base64.b32decode(secret.upper() + padding)
    counter = int(time.time()) // step
    digest = hmac.new(key, counter.to_bytes(8, "big"), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (int.from_bytes(digest[offset : offset + 4], "big") & 0x7FFFFFFF) % (10**digits)
    return f"{code:0{digits}d}"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: py -3.12 scripts/totp_code.py <secreto_base32>")
        raise SystemExit(1)
    print(totp_now(sys.argv[1]))
