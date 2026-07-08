"""
Fixtures compartidas para la suite de pytest.

Usa una base de datos SQLite temporal por sesión de test (nunca la crm.db real).
Las contraseñas de las cuentas seed se fijan por variable de entorno ANTES de
importar la app, para poder loguearnos en los tests sin depender de valores
aleatorios generados en cada arranque.
"""
import os
import tempfile
import re

os.environ.setdefault("SEED_ADMIN_PASSWORD", "admin123-test")
os.environ.setdefault("SEED_MARIA_PASSWORD", "maria2024-test")
os.environ.setdefault("SEED_ANDRES_PASSWORD", "andres2024-test")
os.environ.setdefault("SEED_ADMINCALENDARIO_PASSWORD", "AdminCalendario123-test")

import pytest

import config as config_module
from app import create_app

ADMIN_EMAIL = "admin@crm.local"
ADMIN_PASSWORD = os.environ["SEED_ADMIN_PASSWORD"]


def _extraer_csrf_token(html):
    # El campo oculto de formulario (auth/login) o el <meta> del <head>
    # (presente en cualquier página autenticada, tenga o no formularios).
    m = re.search(r'csrf_token" value="([^"]+)"', html) or \
        re.search(r'name="csrf-token" content="([^"]+)"', html)
    assert m, "No se encontró csrf_token en la página — ¿CSRFProtect sigue activo?"
    return m.group(1)


@pytest.fixture(scope="session")
def app():
    """Crea la app Flask completa (con toda la inicialización real) contra una
    base de datos SQLite temporal, aislada de la BD de desarrollo."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    # Se sobreescribe el atributo de clase directamente: config.py ya ejecutó
    # load_dotenv() al importarse, así que tocar os.environ aquí llegaría tarde.
    config_module.TestingConfig.SQLALCHEMY_DATABASE_URI = f"sqlite:///{db_path}"

    flask_app = create_app("testing")
    flask_app.config["WTF_CSRF_ENABLED"] = True

    yield flask_app

    os.close(db_fd)
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def csrf_token(client):
    """Token CSRF válido para la sesión (todavía anónima) del cliente de test."""
    resp = client.get("/login")
    return _extraer_csrf_token(resp.get_data(as_text=True))


@pytest.fixture()
def auth_client(client, csrf_token):
    """Cliente de test ya autenticado como admin."""
    resp = client.post(
        "/login",
        data={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD, "csrf_token": csrf_token},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    return client


@pytest.fixture()
def auth_csrf_token(auth_client):
    """Token CSRF fresco tomado de una página ya autenticada (se lee del
    <meta name="csrf-token">, presente en todas las páginas del CRM)."""
    resp = auth_client.get("/clientes/")
    return _extraer_csrf_token(resp.get_data(as_text=True))
