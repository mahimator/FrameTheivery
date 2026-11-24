import ipaddress
import socket
from urllib.parse import urlparse
import httpx

class UnsafeURL(ValueError):
    pass

def validate_public_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise UnsafeURL("Only absolute HTTP(S) URLs are supported.")
    if parsed.username or parsed.password:
        raise UnsafeURL("URLs containing embedded credentials are not allowed.")
    host = parsed.hostname.rstrip(".").lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise UnsafeURL("Local network destinations are not allowed.")
    try:
        addresses = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise UnsafeURL("The hostname could not be resolved.")
    for item in addresses:
        ip = ipaddress.ip_address(item[4][0])
        if not ip.is_global:
            raise UnsafeURL("Private, loopback and reserved network destinations are not allowed.")
    return url

async def validate_redirect(request: httpx.Request) -> None:
    validate_public_url(str(request.url))
