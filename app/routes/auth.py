from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.models.usuario import Usuario
from app.services.log_service import registrar_log
from app.utils import safe_next_url

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        credencial = request.form.get("email", "").strip().lower()
        password   = request.form.get("password", "")

        usuario = (
            Usuario.query.filter_by(username=credencial, activo=True).first()
            or Usuario.query.filter_by(email=credencial, activo=True).first()
        )

        if usuario and usuario.check_password(password):
            login_user(usuario, remember=request.form.get("remember") == "on")
            registrar_log("login", entidad="sistema",
                          detalle=f"Inicio de sesión: {usuario.nombre}")
            if usuario.rol == "vista":
                return redirect(url_for("vista.index"))
            next_page = safe_next_url(request.args.get("next"))
            return redirect(next_page or url_for("dashboard.index"))

        registrar_log("login_fallido", entidad="sistema",
                      detalle=f"Intento fallido con: {credencial}")
        flash("Usuario o contraseña incorrectos.", "danger")

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    registrar_log("logout", entidad="sistema",
                  detalle=f"Cierre de sesión: {current_user.nombre}")
    logout_user()
    flash("Sesión cerrada correctamente.", "info")
    return redirect(url_for("auth.login"))
