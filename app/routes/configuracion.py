from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required
from app.extensions import db
from app.models.configuracion import Configuracion
from app.services.log_service import registrar_log

configuracion_bp = Blueprint("configuracion", __name__)


@configuracion_bp.route("/")
@login_required
def index():
    config = Configuracion.get()
    return render_template("configuracion/index.html", config=config)


@configuracion_bp.route("/toggle-marketing", methods=["POST"])
@login_required
def toggle_marketing():
    config = Configuracion.get()
    config.marketing_activo = not config.marketing_activo
    db.session.commit()
    estado = "activados" if config.marketing_activo else "desactivados"
    flash(f"Procesos de marketing {estado}.", "success")
    registrar_log(
        "cambiar_estado", "configuracion", config.id,
        f"Procesos de marketing {estado} desde Configuración general",
    )
    return redirect(url_for("configuracion.index"))


@configuracion_bp.route("/toggle-campanas", methods=["POST"])
@login_required
def toggle_campanas():
    config = Configuracion.get()
    config.campanas_activo = not config.campanas_activo
    db.session.commit()
    estado = "activados" if config.campanas_activo else "desactivados"
    flash(f"Procesos de campañas {estado}.", "success")
    registrar_log(
        "cambiar_estado", "configuracion", config.id,
        f"Procesos de campañas {estado} desde Configuración general",
    )
    return redirect(url_for("configuracion.index"))
