"""
Landing pública + preinscripción para el proyecto "Selección Femenina de
Pilotos de Carcross" (JCCM / Autoclub La Dehesa / Motorsport Ibérica /
Feeling Experience). Blueprint deliberadamente SIN login: cualquier persona
debe poder entrar a informarse y preinscribirse. Por eso vive fuera de
`autoclub_bp` (que exige sesión en todas sus rutas) aunque el contenido
pertenezca al ámbito de AutoClub.
"""
import re
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash

from app.extensions import db
from app.models.preinscripcion_carcross import PreinscripcionCarcross, EXPERIENCIA_PREVIA_OPCIONES
from app.services.log_service import registrar_log

seleccion_femenina_bp = Blueprint("seleccion_femenina", __name__)

EDAD_MINIMA = 14
EDAD_MAXIMA = 18
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
FECHA_PONENCIA = datetime(2026, 9, 3).date()


@seleccion_femenina_bp.route("/")
def landing():
    dias_ponencia = (FECHA_PONENCIA - datetime.utcnow().date()).days
    return render_template(
        "seleccion_femenina/landing.html",
        experiencia_opciones=EXPERIENCIA_PREVIA_OPCIONES,
        datos=None, errores=None,
        dias_ponencia=dias_ponencia if dias_ponencia >= 0 else None,
    )


@seleccion_femenina_bp.route("/preinscripcion", methods=["POST"])
def preinscripcion():
    form = request.form
    nombre = form.get("nombre_completo", "").strip()
    fnac_str = form.get("fecha_nacimiento", "").strip()
    localidad = form.get("localidad", "").strip()
    email = form.get("email", "").strip()
    telefono = form.get("telefono", "").strip()
    experiencia = form.get("experiencia_previa", "ninguna")
    motivacion = form.get("motivacion", "").strip()
    acepta = bool(form.get("acepta_privacidad"))

    errores = {}
    fecha_nacimiento = None

    if not nombre:
        errores["nombre_completo"] = "Indica tu nombre y apellidos."
    if not fnac_str:
        errores["fecha_nacimiento"] = "Indica tu fecha de nacimiento."
    else:
        try:
            fecha_nacimiento = datetime.strptime(fnac_str, "%Y-%m-%d").date()
            hoy = datetime.utcnow().date()
            edad = hoy.year - fecha_nacimiento.year - ((hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day))
            if edad < EDAD_MINIMA or edad > EDAD_MAXIMA:
                errores["fecha_nacimiento"] = f"Este proyecto es para chicas de {EDAD_MINIMA} a {EDAD_MAXIMA} años."
        except ValueError:
            errores["fecha_nacimiento"] = "Fecha no válida."
    if not email or not _EMAIL_RE.match(email):
        errores["email"] = "Indica un email válido."
    if not telefono:
        errores["telefono"] = "Indica un teléfono de contacto."
    if not acepta:
        errores["acepta_privacidad"] = "Debes aceptar la política de privacidad para continuar."
    if experiencia not in dict(EXPERIENCIA_PREVIA_OPCIONES):
        experiencia = "ninguna"

    if errores:
        flash("Revisa los datos marcados: hay algún campo obligatorio sin rellenar.", "danger")
        dias_ponencia = (FECHA_PONENCIA - datetime.utcnow().date()).days
        return render_template(
            "seleccion_femenina/landing.html",
            experiencia_opciones=EXPERIENCIA_PREVIA_OPCIONES,
            datos=form, errores=errores,
            dias_ponencia=dias_ponencia if dias_ponencia >= 0 else None,
        ), 400

    preinscripcion = PreinscripcionCarcross(
        nombre_completo=nombre,
        fecha_nacimiento=fecha_nacimiento,
        localidad=localidad,
        email=email,
        telefono=telefono,
        experiencia_previa=experiencia,
        motivacion=motivacion,
        acepta_privacidad=True,
        ip=request.remote_addr or "",
    )
    db.session.add(preinscripcion)
    db.session.commit()

    registrar_log(
        "crear", "preinscripcion_carcross", preinscripcion.id,
        f"Preinscripción recibida: {nombre}",
        origen="publico",
    )

    return redirect(url_for("seleccion_femenina.gracias"))


@seleccion_femenina_bp.route("/gracias")
def gracias():
    return render_template("seleccion_femenina/gracias.html")


@seleccion_femenina_bp.route("/privacidad")
def privacidad():
    return render_template("seleccion_femenina/privacidad.html")
