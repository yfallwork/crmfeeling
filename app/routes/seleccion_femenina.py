"""
Landing pública + preinscripción para el proyecto "Selección Femenina de
Pilotos de Carcross" (JCCM / Autoclub La Dehesa / Motorsport Ibérica /
Feeling Experience). Blueprint deliberadamente SIN login: cualquier persona
debe poder entrar a informarse y preinscribirse. Por eso vive fuera de
`autoclub_bp` (que exige sesión en todas sus rutas) aunque el contenido
pertenezca al ámbito de AutoClub.
"""
import os
import re
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models.preinscripcion_carcross import PreinscripcionCarcross, EXPERIENCIA_PREVIA_OPCIONES
from app.services.log_service import registrar_log

seleccion_femenina_bp = Blueprint("seleccion_femenina", __name__)

EDAD_MINIMA = 14
EDAD_MAXIMA = 18
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_DNI_NIE_RE = re.compile(r"^(\d{8}[A-Za-z]|[XYZxyz]\d{7}[A-Za-z])$")
_TELEFONO_RE = re.compile(r"^[0-9+\s-]{9,20}$")
DOC_CUSTODIA_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "doc", "docx"}
# Fecha límite de preinscripción = inicio de entrevistas. Es la que se
# muestra en la cuenta atrás de la portada: la presentación del proyecto
# (2 de septiembre) no requiere asistencia de las candidatas, así que no
# tiene sentido contar los días para esa fecha — generaba confusión sobre
# si tenían que acudir ese día.
FECHA_LIMITE_PREINSCRIPCION = datetime(2026, 9, 13).date()


@seleccion_femenina_bp.route("/")
def landing():
    dias_preinscripcion = (FECHA_LIMITE_PREINSCRIPCION - datetime.utcnow().date()).days
    return render_template(
        "seleccion_femenina/landing.html",
        experiencia_opciones=EXPERIENCIA_PREVIA_OPCIONES,
        datos=None, errores=None,
        dias_preinscripcion=dias_preinscripcion if dias_preinscripcion >= 0 else None,
        hoy=datetime.utcnow().date().isoformat(),
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
        dias_preinscripcion = (FECHA_LIMITE_PREINSCRIPCION - datetime.utcnow().date()).days
        return render_template(
            "seleccion_femenina/landing.html",
            experiencia_opciones=EXPERIENCIA_PREVIA_OPCIONES,
            datos=form, errores=errores,
            dias_preinscripcion=dias_preinscripcion if dias_preinscripcion >= 0 else None,
            hoy=datetime.utcnow().date().isoformat(),
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


@seleccion_femenina_bp.route("/bases-legales")
def bases_legales():
    return render_template("seleccion_femenina/bases_legales.html")


# ══════════════════════════════════════════════════════════════════════════
# INSCRIPCIÓN Y AUTORIZACIÓN GENERAL — formulario público de un solo uso,
# accesible solo mediante el token enviado por email cuando una candidata
# pasa a "apta_inscripcion". Sustituye al documento en papel firmado por
# ambos progenitores/tutores legales antes de la entrevista.
# ══════════════════════════════════════════════════════════════════════════

_CAMPOS_TEXTO_INSCRIPCION = [
    "nombre_completo", "fecha_nacimiento", "localidad", "email", "telefono", "dni_nie_participante",
    "emergencia_nombre", "emergencia_telefono", "emergencia_relacion",
    "experiencia_conduccion", "experiencia_competicion", "licencia_federativa", "licencia_federativa_detalle",
    "autorizacion_imagen",
    "tutor1_nombre", "tutor1_dni", "tutor1_relacion", "tutor1_email", "tutor1_telefono", "tutor1_firma_dibujo",
    "tutor2_nombre", "tutor2_dni", "tutor2_relacion", "tutor2_email", "tutor2_telefono", "tutor2_firma_dibujo",
]
_CAMPOS_CHECK_INSCRIPCION = [
    "solo_un_tutor", "consiente_participacion", "consiente_datos_personales",
    "acepta_bases_legales", "acepta_compromisos", "tutor1_firma", "tutor2_firma",
]


def _datos_iniciales_inscripcion(preinscripcion, inscripcion):
    def _si_no(valor):
        if valor is True:
            return "si"
        if valor is False:
            return "no"
        return ""

    datos = {c: "" for c in _CAMPOS_TEXTO_INSCRIPCION}
    datos.update({c: False for c in _CAMPOS_CHECK_INSCRIPCION})
    datos.update({
        "nombre_completo": preinscripcion.nombre_completo,
        "fecha_nacimiento": preinscripcion.fecha_nacimiento.isoformat() if preinscripcion.fecha_nacimiento else "",
        "localidad": preinscripcion.localidad or "",
        "email": preinscripcion.email,
        "telefono": preinscripcion.telefono,
        "dni_nie_participante": inscripcion.dni_nie_participante or "",
        "emergencia_nombre": inscripcion.emergencia_nombre or "",
        "emergencia_telefono": inscripcion.emergencia_telefono or "",
        "emergencia_relacion": inscripcion.emergencia_relacion or "",
        "experiencia_conduccion": inscripcion.experiencia_conduccion or "",
        "experiencia_competicion": inscripcion.experiencia_competicion or "",
        "licencia_federativa": _si_no(inscripcion.licencia_federativa),
        "licencia_federativa_detalle": inscripcion.licencia_federativa_detalle or "",
        "autorizacion_imagen": inscripcion.autorizacion_imagen or "",
        "solo_un_tutor": inscripcion.solo_un_tutor,
        "consiente_participacion": inscripcion.consiente_participacion,
        "consiente_datos_personales": inscripcion.consiente_datos_personales,
        "acepta_bases_legales": inscripcion.acepta_bases_legales,
        "acepta_compromisos": inscripcion.acepta_compromisos,
    })
    return datos


def _datos_repoblar_inscripcion(form):
    datos = {c: form.get(c, "").strip() for c in _CAMPOS_TEXTO_INSCRIPCION}
    datos.update({c: bool(form.get(c)) for c in _CAMPOS_CHECK_INSCRIPCION})
    return datos


def _validar_tutor(form, prefix, errores):
    nombre = form.get(f"{prefix}_nombre", "").strip()
    dni = form.get(f"{prefix}_dni", "").strip()
    relacion = form.get(f"{prefix}_relacion", "").strip()
    email = form.get(f"{prefix}_email", "").strip()
    telefono = form.get(f"{prefix}_telefono", "").strip()
    firma = bool(form.get(f"{prefix}_firma"))
    firma_dibujo = form.get(f"{prefix}_firma_dibujo", "").strip()

    if not nombre:
        errores[f"{prefix}_nombre"] = "Indica el nombre completo."
    if not dni or not _DNI_NIE_RE.match(dni):
        errores[f"{prefix}_dni"] = "DNI/NIE no válido."
    if not relacion:
        errores[f"{prefix}_relacion"] = "Indica la relación con la menor."
    if not email or not _EMAIL_RE.match(email):
        errores[f"{prefix}_email"] = "Email no válido."
    if not telefono or not _TELEFONO_RE.match(telefono):
        errores[f"{prefix}_telefono"] = "Teléfono no válido."
    if not firma:
        errores[f"{prefix}_firma"] = "Debes marcar la declaración de firma."
    if not firma_dibujo.startswith("data:image"):
        errores[f"{prefix}_firma_dibujo"] = "Falta dibujar la firma."

    return {
        "nombre_completo": nombre, "dni_nie": dni, "relacion_menor": relacion,
        "email": email, "telefono": telefono, "firma_dibujo": firma_dibujo,
    }


def _guardar_doc_custodia(token, archivo):
    ext = archivo.filename.rsplit(".", 1)[-1].lower()
    filename = secure_filename(f"custodia_{token[:16]}.{ext}")
    carpeta = os.path.join(current_app.root_path, "static", "uploads", "seleccion_femenina", "custodia")
    os.makedirs(carpeta, exist_ok=True)
    archivo.save(os.path.join(carpeta, filename))
    return f"uploads/seleccion_femenina/custodia/{filename}"


def _guardar_tutor(inscripcion, numero, datos, ip, user_agent, ahora):
    from app.models.inscripcion_autorizacion import TutorLegal
    tutor = TutorLegal.query.filter_by(inscripcion_id=inscripcion.id, numero=numero).first()
    if not tutor:
        tutor = TutorLegal(inscripcion_id=inscripcion.id, numero=numero)
        db.session.add(tutor)
    tutor.nombre_completo = datos["nombre_completo"]
    tutor.dni_nie = datos["dni_nie"]
    tutor.relacion_menor = datos["relacion_menor"]
    tutor.email = datos["email"]
    tutor.telefono = datos["telefono"]
    tutor.firma_dibujo = datos["firma_dibujo"]
    # Firma electrónica simple: se fija UNA vez y no se vuelve a tocar —
    # es la prueba de que este tutor concreto confirmó en este momento.
    tutor.firmado = True
    tutor.firma_ip = ip
    tutor.firma_user_agent = user_agent
    tutor.firma_en = ahora


@seleccion_femenina_bp.route("/inscripcion/<token>", methods=["GET", "POST"])
def inscripcion_formulario(token):
    from app.models.inscripcion_autorizacion import InscripcionAutorizacion

    inscripcion = InscripcionAutorizacion.query.filter_by(token=token).first()
    if not inscripcion:
        abort(404)
    preinscripcion = inscripcion.preinscripcion

    if inscripcion.completo:
        return render_template("seleccion_femenina/inscripcion_completada.html", preinscripcion=preinscripcion)
    if inscripcion.token_expirado:
        return render_template("seleccion_femenina/inscripcion_caducada.html", preinscripcion=preinscripcion), 410

    errores = {}
    datos = _datos_iniciales_inscripcion(preinscripcion, inscripcion)

    if request.method == "POST":
        datos = _datos_repoblar_inscripcion(request.form)

        fecha_nacimiento = preinscripcion.fecha_nacimiento
        if datos["fecha_nacimiento"]:
            try:
                fecha_nacimiento = datetime.strptime(datos["fecha_nacimiento"], "%Y-%m-%d").date()
            except ValueError:
                errores["fecha_nacimiento"] = "Fecha no válida."

        if not datos["nombre_completo"]:
            errores["nombre_completo"] = "Indica el nombre completo."
        if not datos["dni_nie_participante"] or not _DNI_NIE_RE.match(datos["dni_nie_participante"]):
            errores["dni_nie_participante"] = "Indica un DNI/NIE válido."
        if not datos["email"] or not _EMAIL_RE.match(datos["email"]):
            errores["email"] = "Email no válido."
        if not datos["telefono"] or not _TELEFONO_RE.match(datos["telefono"]):
            errores["telefono"] = "Teléfono no válido."

        if not datos["emergencia_nombre"]:
            errores["emergencia_nombre"] = "Indica el nombre del contacto de emergencia."
        if not datos["emergencia_telefono"] or not _TELEFONO_RE.match(datos["emergencia_telefono"]):
            errores["emergencia_telefono"] = "Teléfono de emergencia no válido."

        if datos["licencia_federativa"] not in ("si", "no"):
            errores["licencia_federativa"] = "Indica si dispone de licencia federativa en vigor."
        elif datos["licencia_federativa"] == "si" and not datos["licencia_federativa_detalle"]:
            errores["licencia_federativa_detalle"] = "Indica la disciplina y federación."

        if not datos["consiente_participacion"]:
            errores["consiente_participacion"] = "Debes autorizar la participación en el proceso."
        if not datos["consiente_datos_personales"]:
            errores["consiente_datos_personales"] = "Debes aceptar el tratamiento de datos personales."
        if datos["autorizacion_imagen"] not in ("autoriza", "no_autoriza"):
            errores["autorizacion_imagen"] = "Debes elegir una opción sobre la autorización de imagen."
        if not datos["acepta_bases_legales"]:
            errores["acepta_bases_legales"] = "Debes aceptar las Bases Legales."
        if not datos["acepta_compromisos"]:
            errores["acepta_compromisos"] = "Debes aceptar los compromisos y deberes."

        solo_un_tutor = datos["solo_un_tutor"]
        datos_tutor1 = _validar_tutor(request.form, "tutor1", errores)
        datos_tutor2 = None if solo_un_tutor else _validar_tutor(request.form, "tutor2", errores)

        # El documento de custodia es opcional al enviar (no bloquea el
        # formulario): si falta, el equipo lo revisa y lo pide después por
        # su cuenta — ver InscripcionAutorizacion.necesita_revision_custodia.
        archivo_custodia = request.files.get("doc_custodia")
        if solo_un_tutor and archivo_custodia and archivo_custodia.filename:
            ext = archivo_custodia.filename.rsplit(".", 1)[-1].lower() if "." in archivo_custodia.filename else ""
            if ext not in DOC_CUSTODIA_EXTENSIONS:
                errores["doc_custodia"] = "Formato no admitido (usa PDF, imagen o Word)."

        if not errores:
            preinscripcion.nombre_completo = datos["nombre_completo"]
            preinscripcion.fecha_nacimiento = fecha_nacimiento
            preinscripcion.localidad = datos["localidad"]
            preinscripcion.email = datos["email"]
            preinscripcion.telefono = datos["telefono"]

            inscripcion.dni_nie_participante = datos["dni_nie_participante"]
            inscripcion.emergencia_nombre = datos["emergencia_nombre"]
            inscripcion.emergencia_telefono = datos["emergencia_telefono"]
            inscripcion.emergencia_relacion = datos["emergencia_relacion"]
            inscripcion.experiencia_conduccion = datos["experiencia_conduccion"]
            inscripcion.experiencia_competicion = datos["experiencia_competicion"]
            inscripcion.licencia_federativa = (datos["licencia_federativa"] == "si")
            inscripcion.licencia_federativa_detalle = datos["licencia_federativa_detalle"] if datos["licencia_federativa"] == "si" else ""
            inscripcion.consiente_participacion = datos["consiente_participacion"]
            inscripcion.consiente_datos_personales = datos["consiente_datos_personales"]
            inscripcion.autorizacion_imagen = datos["autorizacion_imagen"]
            inscripcion.acepta_bases_legales = datos["acepta_bases_legales"]
            inscripcion.acepta_compromisos = datos["acepta_compromisos"]
            inscripcion.solo_un_tutor = solo_un_tutor

            if solo_un_tutor and archivo_custodia and archivo_custodia.filename:
                inscripcion.doc_custodia_path = _guardar_doc_custodia(token, archivo_custodia)

            ip = request.remote_addr or ""
            user_agent = request.headers.get("User-Agent", "")[:300]
            ahora = datetime.utcnow()
            _guardar_tutor(inscripcion, 1, datos_tutor1, ip, user_agent, ahora)
            if datos_tutor2:
                _guardar_tutor(inscripcion, 2, datos_tutor2, ip, user_agent, ahora)

            inscripcion.estado = "completado"
            inscripcion.completado_en = ahora
            inscripcion.token_usado_en = ahora
            preinscripcion.estado = "inscripcion_completada"
            db.session.commit()

            registrar_log(
                "editar", "preinscripcion_carcross", preinscripcion.id,
                f"Inscripción y autorización completada: {preinscripcion.nombre_completo}",
                origen="publico",
            )

            from app.services.inscripcion_autorizacion_service import enviar_confirmacion_inscripcion, notificar_equipo_interno
            enviar_confirmacion_inscripcion(preinscripcion, inscripcion)
            notificar_equipo_interno(preinscripcion, inscripcion)

            return redirect(url_for("seleccion_femenina.inscripcion_formulario", token=token))

        flash("Revisa los campos marcados en rojo.", "danger")

    return render_template(
        "seleccion_femenina/inscripcion_form.html",
        preinscripcion=preinscripcion, inscripcion=inscripcion, token=token,
        errores=errores, datos=datos,
    ), (400 if errores else 200)
