import os
from dotenv import load_dotenv

load_dotenv(override=True)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

_WEAK_SECRET_VALUES = {
    "", "dev-secret-key-insegura", "cambia-esto-por-una-clave-segura",
}


def _require_secret_key():
    value = os.environ.get("SECRET_KEY", "")
    if value in _WEAK_SECRET_VALUES:
        raise RuntimeError(
            "SECRET_KEY no está definida (o usa un valor de ejemplo débil) en el entorno. "
            "Define una clave fuerte en .env. Puedes generar una con:\n"
            "  python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    return value


class Config:
    SECRET_KEY = _require_secret_key()
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'crm.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # URL pública base del propio CRM (para construir enlaces absolutos —
    # ej. el formulario público de seguro — desde tareas en segundo plano
    # sin contexto de petición, donde url_for(_external=True) no funciona).
    APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://127.0.0.1:5000")

    # WooCommerce
    WOO_BASE_URL = os.environ.get("WOO_BASE_URL", "https://www.regaloexperiencias.com")
    WOO_CONSUMER_KEY = os.environ.get("WOO_CONSUMER_KEY", "")
    WOO_CONSUMER_SECRET = os.environ.get("WOO_CONSUMER_SECRET", "")

    # Email
    MAIL_SERVER  = os.environ.get("MAIL_SERVER", "smtp.dondominio.com")
    MAIL_PORT    = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USE_SSL = os.environ.get("MAIL_USE_SSL", "false").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "")

    # Email prensa / AutoClub (cuenta separada en Dondominio)
    MAIL_PRENSA_SERVER   = os.environ.get("MAIL_PRENSA_SERVER", "smtp.arsys.es")
    MAIL_PRENSA_PORT     = int(os.environ.get("MAIL_PRENSA_PORT", 587))
    MAIL_PRENSA_USERNAME = os.environ.get("MAIL_PRENSA_USERNAME", "")
    MAIL_PRENSA_PASSWORD = os.environ.get("MAIL_PRENSA_PASSWORD", "")
    MAIL_PRENSA_SENDER   = os.environ.get("MAIL_PRENSA_SENDER", "")

    # Twilio
    TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
    TWILIO_WHATSAPP_FROM = os.environ.get("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

    # WooCommerce Webhook
    WOO_WEBHOOK_SECRET = os.environ.get("WOO_WEBHOOK_SECRET", "")

    # Paginación
    ITEMS_PER_PAGE = 25

    # Límite de tamaño de subida (16 MB)
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 16 * 1024 * 1024))


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    DEBUG = False
    WTF_CSRF_ENABLED = True  # explícito: los tests de CSRF dependen de que siga activo


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
