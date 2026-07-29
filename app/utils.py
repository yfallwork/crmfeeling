from functools import wraps
from urllib.parse import urlparse

from flask import abort
from flask_login import current_user, login_required


def admin_required(view_func):
    """Exige sesión iniciada y rol admin. Devuelve 403 si no lo es."""
    @wraps(view_func)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.es_admin:
            abort(403)
        return view_func(*args, **kwargs)
    return wrapped


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
