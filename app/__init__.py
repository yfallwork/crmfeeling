import os
from flask import Flask
from config import config
from app.extensions import db, login_manager, mail


def create_app(env="default"):
    app = Flask(__name__)
    app.config.from_object(config[env])

    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)

    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.clientes import clientes_bp
    from app.routes.reservas import reservas_bp
    from app.routes.calendario import calendario_bp
    from app.routes.woocommerce import woo_bp
    from app.routes.api import api_bp
    from app.routes.estadisticas import estadisticas_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(clientes_bp, url_prefix="/clientes")
    app.register_blueprint(reservas_bp, url_prefix="/reservas")
    app.register_blueprint(calendario_bp, url_prefix="/calendario")
    app.register_blueprint(woo_bp, url_prefix="/woocommerce")
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(estadisticas_bp)

    with app.app_context():
        # Importar modelos para que SQLAlchemy los registre antes de create_all
        from app.models import comunicacion  # noqa: F401
        db.create_all()
        _migrate_columns()
        _seed_admin()

    # Iniciar scheduler solo en el proceso principal (evita doble arranque con reloader)
    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        from app.scheduler import init_scheduler
        init_scheduler(app)

    return app


def _migrate_columns():
    """Añade columnas nuevas a tablas existentes sin borrar datos."""
    from sqlalchemy import text
    nuevas = [
        ("reservas", "horario",  "VARCHAR(20) DEFAULT ''"),
        ("reservas", "variante", "VARCHAR(150) DEFAULT ''"),
    ]
    with db.engine.connect() as conn:
        for tabla, columna, tipo in nuevas:
            try:
                conn.execute(text(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}"))
                conn.commit()
            except Exception:
                pass  # La columna ya existe


def _seed_admin():
    from app.models.usuario import Usuario
    if not Usuario.query.filter_by(email="admin@crm.local").first():
        admin = Usuario(nombre="Admin", email="admin@crm.local", rol="admin")
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.commit()
