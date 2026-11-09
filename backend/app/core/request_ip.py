"""Resolución de la IP real del cliente detrás de NPM y Cloudflare.

La API nunca se publica directo: Nginx Proxy Manager la alcanza por la red
interna de Docker. Por eso solo se aceptan cabeceras de proxy cuando el par
inmediato pertenece a un rango privado (Docker/host). Así la auditoría y el
límite de peticiones usan la IP del paciente y no la del contenedor de NPM.
"""

from ipaddress import ip_address, ip_network

from fastapi import Request

# Rangos internos: loopback y redes privadas de Docker.
_TRUSTED_PROXY_NETWORKS = (
    ip_network("127.0.0.0/8"),
    ip_network("10.0.0.0/8"),
    ip_network("172.16.0.0/12"),
    ip_network("192.168.0.0/16"),
    ip_network("::1/128"),
    ip_network("fc00::/7"),
)


def _parse_ip(value: str | None) -> str | None:
    """Valida y normaliza una IP; ignora puertos, comas y valores basura."""
    if not value:
        return None
    candidate = value.split(",", 1)[0].strip()
    try:
        return str(ip_address(candidate))
    except ValueError:
        return None


def _is_trusted_proxy(host: str | None) -> bool:
    if not host:
        return False
    try:
        address = ip_address(host)
    except ValueError:
        return False
    return any(address in network for network in _TRUSTED_PROXY_NETWORKS)


def resolve_client_ip(request: Request) -> str | None:
    """IP real: Cloudflare > primer X-Forwarded-For > X-Real-IP > par directo."""
    peer = request.client.host if request.client else None
    if not _is_trusted_proxy(peer):
        # Sin proxy de confianza de por medio, no se cree ninguna cabecera.
        return peer

    cloudflare_ip = _parse_ip(request.headers.get("cf-connecting-ip"))
    if cloudflare_ip is not None:
        return cloudflare_ip

    forwarded_ip = _parse_ip(request.headers.get("x-forwarded-for"))
    if forwarded_ip is not None:
        return forwarded_ip

    real_ip = _parse_ip(request.headers.get("x-real-ip"))
    if real_ip is not None:
        return real_ip

    return peer
