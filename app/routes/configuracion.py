import json

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.configuracion import Configuracion
from app.models.usuario import Usuario, MODULOS, AUTOCLUB_SECCIONES
from app.services.log_service import registrar_log
from app.utils import admin_required

configuracion_bp = Blueprint("configuracion", __name__)


def _permisos_json_desde_form(form):
    return json.dumps({
        "modulos": form.getlist("modulos"),
        "autoclub_secciones": form.getlist("autoclub_secciones"),
    })


def _form_kwargs(usuario=None, datos=None):
    return dict(usuario=usuario, modulos_disponibles=MODULOS,
                autoclub_secciones_disponibles=AUTOCLUB_SECCIONES, datos=datos)


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


@configuracion_bp.route("/seguro-recordatorio", methods=["POST"])
@login_required
def actualizar_seguro_recordatorio():
    config = Configuracion.get()
    config.seguro_recordatorio_activo = bool(request.form.get("activo"))
    dias = request.form.get("dias", type=int)
    if dias and 1 <= dias <= 60:
        config.seguro_recordatorio_dias = dias
    db.session.commit()
    estado = "activado" if config.seguro_recordatorio_activo else "desactivado"
    flash(f"Recordatorio de datos de seguro {estado} ({config.seguro_recordatorio_dias} días antes).", "success")
    registrar_log(
        "cambiar_estado", "configuracion", config.id,
        f"Recordatorio de seguro {estado}, {config.seguro_recordatorio_dias} días antes",
    )
    return redirect(url_for("configuracion.index"))


@configuracion_bp.route("/usuarios")
@admin_required
def usuarios_lista():
    usuarios = Usuario.query.order_by(Usuario.nombre).all()
    return render_template("configuracion/usuarios/lista.html", usuarios=usuarios,
                            modulos_disponibles=MODULOS, autoclub_secciones_disponibles=AUTOCLUB_SECCIONES)


@configuracion_bp.route("/usuarios/nuevo", methods=["GET", "POST"])
@admin_required
def usuarios_nuevo():
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        username = request.form.get("username", "").strip() or None
        email = request.form.get("email", "").strip() or None
        password = request.form.get("password", "")
        rol = request.form.get("rol", "gestor")

        if not nombre or not password:
            flash("Nombre y contraseña son obligatorios.", "danger")
            return render_template("configuracion/usuarios/form.html",
                                    **_form_kwargs(datos=request.form))

        usuario = Usuario(
            nombre=nombre,
            username=username,
            email=email,
            rol=rol,
            activo=bool(request.form.get("activo")),
            permisos_json=_permisos_json_desde_form(request.form),
        )
        usuario.set_password(password)
        db.session.add(usuario)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Ya existe un usuario con ese nombre de usuario o email.", "danger")
            return render_template("configuracion/usuarios/form.html",
                                    **_form_kwargs(datos=request.form))

        registrar_log("crear", "usuario", usuario.id, f"Usuario creado: {usuario.nombre} ({usuario.rol})")
        flash(f"Usuario «{usuario.nombre}» creado correctamente.", "success")
        return redirect(url_for("configuracion.usuarios_lista"))

    return render_template("configuracion/usuarios/form.html", **_form_kwargs())


@configuracion_bp.route("/usuarios/<int:id>/editar", methods=["GET", "POST"])
@admin_required
def usuarios_editar(id):
    usuario = Usuario.query.get_or_404(id)

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        username = request.form.get("username", "").strip() or None
        email = request.form.get("email", "").strip() or None
        password = request.form.get("password", "")
        rol = request.form.get("rol", usuario.rol)
        activo = bool(request.form.get("activo"))

        if not nombre:
            flash("El nombre es obligatorio.", "danger")
            return render_template("configuracion/usuarios/form.html",
                                    **_form_kwargs(usuario, request.form))

        # No permitir quitarse a uno mismo el rol de admin ni desactivarse,
        # ni dejar la app sin ningún admin activo.
        if usuario.id == current_user.id and (rol != "admin" or not activo):
            flash("No puedes quitarte a ti mismo el rol de administrador ni desactivar tu propia cuenta.", "danger")
            return render_template("configuracion/usuarios/form.html",
                                    **_form_kwargs(usuario, request.form))
        if usuario.rol == "admin" and (rol != "admin" or not activo):
            otros_admins_activos = Usuario.query.filter(
                Usuario.rol == "admin", Usuario.activo.is_(True), Usuario.id != usuario.id
            ).count()
            if otros_admins_activos == 0:
                flash("Debe quedar al menos un administrador activo.", "danger")
                return render_template("configuracion/usuarios/form.html",
                                        **_form_kwargs(usuario, request.form))

        usuario.nombre = nombre
        usuario.username = username
        usuario.email = email
        usuario.rol = rol
        usuario.activo = activo
        usuario.permisos_json = _permisos_json_desde_form(request.form)
        if password:
            usuario.set_password(password)

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Ya existe un usuario con ese nombre de usuario o email.", "danger")
            return render_template("configuracion/usuarios/form.html",
                                    **_form_kwargs(usuario, request.form))

        registrar_log("editar", "usuario", usuario.id, f"Usuario modificado: {usuario.nombre}")
        flash(f"Usuario «{usuario.nombre}» actualizado correctamente.", "success")
        return redirect(url_for("configuracion.usuarios_lista"))

    return render_template("configuracion/usuarios/form.html", **_form_kwargs(usuario))


@configuracion_bp.route("/usuarios/<int:id>/eliminar", methods=["POST"])
@admin_required
def usuarios_eliminar(id):
    usuario = Usuario.query.get_or_404(id)

    if usuario.id == current_user.id:
        flash("No puedes eliminar tu propia cuenta.", "danger")
        return redirect(url_for("configuracion.usuarios_lista"))

    if usuario.rol == "admin":
        otros_admins = Usuario.query.filter(Usuario.rol == "admin", Usuario.id != usuario.id).count()
        if otros_admins == 0:
            flash("Debe quedar al menos un administrador en el sistema.", "danger")
            return redirect(url_for("configuracion.usuarios_lista"))

    nombre = usuario.nombre
    db.session.delete(usuario)
    db.session.commit()
    registrar_log("eliminar", "usuario", id, f"Usuario eliminado: {nombre}")
    flash(f"Usuario «{nombre}» eliminado.", "success")
    return redirect(url_for("configuracion.usuarios_lista"))
