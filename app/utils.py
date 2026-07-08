from urllib.parse import urlparse


def safe_next_url(next_url):
    """Devuelve next_url solo si es una ruta relativa interna, para evitar
    Open Redirect (ej. /login?next=https://evil.com). En cualquier otro caso
    (URL absoluta, con esquema o con netloc) devuelve None."""
    if not next_url:
        return None
    parsed = urlparse(next_url)
    if parsed.scheme or parsed.netloc:
        return None
    if not next_url.startswith("/"):
        return None
    return next_url
