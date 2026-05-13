import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-insegura")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'crm.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

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

    # Twilio
    TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
    TWILIO_WHATSAPP_FROM = os.environ.get("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

    # WooCommerce Webhook
    WOO_WEBHOOK_SECRET = os.environ.get("WOO_WEBHOOK_SECRET", "")

    # Paginación
    ITEMS_PER_PAGE = 25


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
