import csv
import io
import os
import uuid
from datetime import date
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, Response, current_app, jsonify)
from flask_login import login_required
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models.socio import Socio
from app.models.patrocinador import Patrocinador
from app.services.log_service import registrar_log

autoclub_bp = Blueprint("autoclub", __name__)

TIPOS_SOCIO = ["regular", "premium", "familiar", "vip"]
LOGO_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "svg"}

SECTORES_ESPAÑA = sorted([
    "Administración pública",
    "Aeronáutica y aviación",
    "Agricultura y ganadería",
    "Alimentación y bebidas",
    "Arquitectura y urbanismo",
    "Arte y cultura",
    "Asesoría y gestoría",
    "Automoción y motor",
    "Banca y finanzas",
    "Biotecnología",
    "Comercio al por menor",
    "Comercio al por mayor",
    "Comunicación y marketing",
    "Construcción e inmobiliaria",
    "Consultoría y estrategia",
    "Defensa y seguridad pública",
    "Deporte y ocio activo",
    "Diseño gráfico y UX",
    "Distribución y logística",
    "Educación y formación",
    "Electrónica y semiconductores",
    "Energía y utilities",
    "Entretenimiento y espectáculos",
    "Envases y embalajes",
    "Eventos y producción",
    "Farmacia y salud",
    "Fotografía y audiovisual",
    "Gastronomía y restauración",
    "Hostelería y turismo",
    "Industria química",
    "Industria manufacturera",
    "Ingeniería e I+D",
    "Joyería y moda de lujo",
    "Legal y compliance",
    "Maquinaria e industria pesada",
    "Medioambiente y sostenibilidad",
    "Medios de comunicación",
    "Minería y extracción",
    "Moda y textil",
    "Naval y marítimo",
    "Nuevas tecnologías e IA",
    "Óptica y oftalmología",
    "Papel e impresión",
    "Publicidad y RRPP",
    "Recursos humanos",
    "Salud y bienestar",
    "Seguros",
    "Seguridad privada",
    "Servicios sociales",
    "Software y SaaS",
    "Telecomunicaciones",
    "Transporte y movilidad",
    "Veterinaria y mascotas",
    "Viajes y agencias de viaje",
    "Videojuegos y esports",
])


# ── CONTEXT PROCESSOR — inyecta sectores en todas las plantillas del blueprint ─

@autoclub_bp.context_processor
def inject_autoclub():
    return {"sectores_espana": SECTORES_ESPAÑA}


# ── HELPERS UPLOAD ─────────────────────────────────────────────────────────────

def _logo_dir():
    path = os.path.join(current_app.root_path, "static", "uploads", "autoclub", "patrocinadores")
    os.makedirs(path, exist_ok=True)
    return path


def _save_logo(file, old_filename=None):
    if not file or not file.filename:
        return None
    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in LOGO_EXTENSIONS:
        return None
    filename = f"{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(_logo_dir(), filename))
    if old_filename:
        _delete_logo(old_filename)
    return filename


def _delete_logo(filename):
    if not filename:
        return
    try:
        os.remove(os.path.join(_logo_dir(), filename))
    except OSError:
        pass


# ── DASHBOARD ──────────────────────────────────────────────────────────────────

@autoclub_bp.route("/")
@login_required
def dashboard():
    total      = Socio.query.count()
    activos    = Socio.query.filter_by(activo=True).count()
    inactivos  = Socio.query.filter_by(activo=False).count()
    por_tipo   = {t: Socio.query.filter_by(tipo=t, activo=True).count() for t in TIPOS_SOCIO}
    recientes  = Socio.query.filter_by(activo=True).order_by(Socio.creado_en.desc()).limit(6).all()

    total_patrocinadores   = Patrocinador.query.count()
    activos_patrocinadores = Patrocinador.query.filter_by(activo=True).count()
    recientes_patrocinadores = Patrocinador.query.filter_by(activo=True).order_by(Patrocinador.creado_en.desc()).limit(4).all()

    return render_template(
        "autoclub/dashboard.html",
        total=total, activos=activos, inactivos=inactivos,
        por_tipo=por_tipo, recientes=recientes, tipos=TIPOS_SOCIO,
        total_patrocinadores=total_patrocinadores,
        activos_patrocinadores=activos_patrocinadores,
        recientes_patrocinadores=recientes_patrocinadores,
    )


# ── BÚSQUEDA (AJAX) ────────────────────────────────────────────────────────────

@autoclub_bp.route("/buscar")
@login_required
def buscar():
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify({"socios": [], "patrocinadores": []})

    like = f"%{q}%"

    socios = Socio.query.filter(db.or_(
        Socio.nombre.ilike(like),
        Socio.apellido.ilike(like),
        Socio.email.ilike(like),
        Socio.dni.ilike(like),
    )).limit(6).all()

    patrocinadores = Patrocinador.query.filter(db.or_(
        Patrocinador.nombre.ilike(like),
        Patrocinador.sector.ilike(like),
        Patrocinador.persona_contacto.ilike(like),
        Patrocinador.email.ilike(like),
    )).limit(6).all()

    return jsonify({
        "socios": [
            {
                "id": s.id,
                "nombre": s.nombre_completo,
                "tipo": s.tipo,
                "email": s.email,
                "activo": s.activo,
                "url": url_for("autoclub.detalle", id=s.id),
            }
            for s in socios
        ],
        "patrocinadores": [
            {
                "id": p.id,
                "nombre": p.nombre,
                "sector": p.sector,
                "tiene_logo": p.tiene_logo,
                "logo": p.logo_principal,
                "url": url_for("autoclub.patrocinadores_detalle", id=p.id),
            }
            for p in patrocinadores
        ],
    })


# ══════════════════════════════════════════════════════════════════════════════
#  SOCIOS
# ══════════════════════════════════════════════════════════════════════════════

@autoclub_bp.route("/socios/")
@login_required
def lista():
    q      = request.args.get("q", "").strip()
    estado = request.args.get("estado", "activos")
    tipo   = request.args.get("tipo", "")
    page   = request.args.get("page", 1, type=int)

    query = Socio.query
    if estado == "activos":
        query = query.filter_by(activo=True)
    elif estado == "inactivos":
        query = query.filter_by(activo=False)
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(
            Socio.nombre.ilike(like), Socio.apellido.ilike(like),
            Socio.email.ilike(like), Socio.telefono.ilike(like),
            Socio.dni.ilike(like),
        ))
    if tipo:
        query = query.filter_by(tipo=tipo)

    socios = query.order_by(Socio.nombre.asc()).paginate(page=page, per_page=25, error_out=False)
    return render_template("autoclub/socios/lista.html",
                           socios=socios, q=q, estado=estado, tipo=tipo, tipos=TIPOS_SOCIO)


@autoclub_bp.route("/socios/nuevo", methods=["GET", "POST"])
@login_required
def nuevo():
    if request.method == "POST":
        fecha_alta = None
        raw = request.form.get("fecha_alta", "").strip()
        if raw:
            try:
                fecha_alta = date.fromisoformat(raw)
            except ValueError:
                pass

        socio = Socio(
            nombre=request.form.get("nombre", "").strip(),
            apellido=request.form.get("apellido", "").strip(),
            email=request.form.get("email", "").strip().lower(),
            telefono=request.form.get("telefono", "").strip(),
            dni=request.form.get("dni", "").strip(),
            tipo=request.form.get("tipo", "regular"),
            fecha_alta=fecha_alta,
            notas=request.form.get("notas", "").strip(),
        )
        db.session.add(socio)
        db.session.commit()
        registrar_log("crear", "socio", socio.id, f"Socio creado: {socio.nombre_completo}")
        flash(f"Socio {socio.nombre_completo} creado correctamente.", "success")
        return redirect(url_for("autoclub.detalle", id=socio.id))

    return render_template("autoclub/socios/form.html", socio=None, datos={}, tipos=TIPOS_SOCIO)


@autoclub_bp.route("/socios/<int:id>")
@login_required
def detalle(id):
    socio = Socio.query.get_or_404(id)
    return render_template("autoclub/socios/detalle.html", socio=socio)


@autoclub_bp.route("/socios/<int:id>/editar", methods=["GET", "POST"])
@login_required
def editar(id):
    socio = Socio.query.get_or_404(id)
    if request.method == "POST":
        fecha_alta = socio.fecha_alta
        raw = request.form.get("fecha_alta", "").strip()
        if raw:
            try:
                fecha_alta = date.fromisoformat(raw)
            except ValueError:
                pass
        socio.nombre     = request.form.get("nombre", "").strip()
        socio.apellido   = request.form.get("apellido", "").strip()
        socio.email      = request.form.get("email", "").strip().lower()
        socio.telefono   = request.form.get("telefono", "").strip()
        socio.dni        = request.form.get("dni", "").strip()
        socio.tipo       = request.form.get("tipo", "regular")
        socio.fecha_alta = fecha_alta
        socio.notas      = request.form.get("notas", "").strip()
        db.session.commit()
        registrar_log("editar", "socio", socio.id, f"Socio editado: {socio.nombre_completo}")
        flash("Socio actualizado correctamente.", "success")
        return redirect(url_for("autoclub.detalle", id=socio.id))
    return render_template("autoclub/socios/form.html", socio=socio, datos={}, tipos=TIPOS_SOCIO)


@autoclub_bp.route("/socios/<int:id>/estado", methods=["POST"])
@login_required
def cambiar_estado(id):
    socio = Socio.query.get_or_404(id)
    if socio.activo:
        socio.desactivar()
        registrar_log("cambiar_estado", "socio", socio.id, f"Socio desactivado: {socio.nombre_completo}")
        flash(f"{socio.nombre_completo} marcado como inactivo.", "warning")
    else:
        socio.activar()
        registrar_log("cambiar_estado", "socio", socio.id, f"Socio reactivado: {socio.nombre_completo}")
        flash(f"{socio.nombre_completo} reactivado correctamente.", "success")
    db.session.commit()
    return redirect(url_for("autoclub.detalle", id=socio.id))


@autoclub_bp.route("/socios/<int:id>/eliminar", methods=["POST"])
@login_required
def eliminar(id):
    socio = Socio.query.get_or_404(id)
    nombre = socio.nombre_completo
    db.session.delete(socio)
    db.session.commit()
    registrar_log("eliminar", "socio", id, f"Socio eliminado: {nombre}")
    flash(f"Socio {nombre} eliminado permanentemente.", "info")
    return redirect(url_for("autoclub.lista"))


@autoclub_bp.route("/socios/exportar")
@login_required
def exportar():
    q = request.args.get("q", "").strip()
    estado = request.args.get("estado", "")
    tipo   = request.args.get("tipo", "")
    query  = Socio.query
    if estado == "activos":
        query = query.filter_by(activo=True)
    elif estado == "inactivos":
        query = query.filter_by(activo=False)
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(
            Socio.nombre.ilike(like), Socio.apellido.ilike(like),
            Socio.email.ilike(like), Socio.telefono.ilike(like),
            Socio.dni.ilike(like),
        ))
    if tipo:
        query = query.filter_by(tipo=tipo)
    socios = query.order_by(Socio.nombre.asc()).all()
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["ID", "Nombre", "Apellido", "Email", "Teléfono",
                     "DNI", "Tipo", "Fecha_alta", "Activo", "Registrado"])
    for s in socios:
        writer.writerow([
            s.id, s.nombre, s.apellido, s.email, s.telefono, s.dni, s.tipo,
            s.fecha_alta.strftime("%d/%m/%Y") if s.fecha_alta else "",
            "Sí" if s.activo else "No",
            s.creado_en.strftime("%d/%m/%Y") if s.creado_en else "",
        ])
    return Response(
        "﻿" + output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=socios_autoclub.csv"},
    )


# ══════════════════════════════════════════════════════════════════════════════
#  PATROCINADORES
# ══════════════════════════════════════════════════════════════════════════════

def _update_logo_field(p, field_attr, file_field):
    """Guarda el logo subido para un campo específico. Retorna el nuevo filename o None."""
    file = request.files.get(file_field)
    new_fn = _save_logo(file, old_filename=getattr(p, field_attr) if p else None)
    if new_fn:
        return new_fn
    # Opción de borrar sin reemplazar
    if p and request.form.get(f"eliminar_{file_field}") == "1":
        _delete_logo(getattr(p, field_attr))
        return ""
    return None  # sin cambio


def _extract_logos_from_form(p=None):
    """Procesa los 3 logos del formulario. Devuelve dict con los campos que cambian."""
    changes = {}
    for attr, field in [
        ("logo_positivo_filename", "logo_positivo"),
        ("logo_negativo_filename", "logo_negativo"),
        ("logo_banner_filename",   "logo_banner"),
    ]:
        result = _update_logo_field(p, attr, field)
        if result is not None:
            changes[attr] = result
    return changes


@autoclub_bp.route("/patrocinadores/")
@login_required
def patrocinadores_lista():
    q      = request.args.get("q", "").strip()
    estado = request.args.get("estado", "activos")
    page   = request.args.get("page", 1, type=int)

    query = Patrocinador.query
    if estado == "activos":
        query = query.filter_by(activo=True)
    elif estado == "inactivos":
        query = query.filter_by(activo=False)
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(
            Patrocinador.nombre.ilike(like),
            Patrocinador.sector.ilike(like),
            Patrocinador.persona_contacto.ilike(like),
            Patrocinador.email.ilike(like),
        ))

    patrocinadores = query.order_by(Patrocinador.nombre.asc()).paginate(
        page=page, per_page=25, error_out=False
    )
    return render_template("autoclub/patrocinadores/lista.html",
                           patrocinadores=patrocinadores, q=q, estado=estado)


@autoclub_bp.route("/patrocinadores/nuevo", methods=["GET", "POST"])
@login_required
def patrocinadores_nuevo():
    if request.method == "POST":
        logos = _extract_logos_from_form()
        p = Patrocinador(
            nombre           = request.form.get("nombre", "").strip(),
            sector           = request.form.get("sector", "").strip(),
            persona_contacto = request.form.get("persona_contacto", "").strip(),
            email            = request.form.get("email", "").strip().lower(),
            telefono         = request.form.get("telefono", "").strip(),
            web              = request.form.get("web", "").strip(),
            instagram        = request.form.get("instagram", "").strip(),
            facebook         = request.form.get("facebook", "").strip(),
            twitter          = request.form.get("twitter", "").strip(),
            linkedin         = request.form.get("linkedin", "").strip(),
            tiktok           = request.form.get("tiktok", "").strip(),
            youtube          = request.form.get("youtube", "").strip(),
            logo_positivo_filename = logos.get("logo_positivo_filename", ""),
            logo_negativo_filename = logos.get("logo_negativo_filename", ""),
            logo_banner_filename   = logos.get("logo_banner_filename", ""),
            notas = request.form.get("notas", "").strip(),
        )
        db.session.add(p)
        db.session.commit()
        registrar_log("crear", "patrocinador", p.id, f"Patrocinador creado: {p.nombre}")
        flash(f"Patrocinador {p.nombre} creado correctamente.", "success")
        return redirect(url_for("autoclub.patrocinadores_detalle", id=p.id))

    return render_template("autoclub/patrocinadores/form.html", p=None, datos={})


@autoclub_bp.route("/patrocinadores/<int:id>")
@login_required
def patrocinadores_detalle(id):
    p = Patrocinador.query.get_or_404(id)
    return render_template("autoclub/patrocinadores/detalle.html", p=p)


@autoclub_bp.route("/patrocinadores/<int:id>/editar", methods=["GET", "POST"])
@login_required
def patrocinadores_editar(id):
    p = Patrocinador.query.get_or_404(id)
    if request.method == "POST":
        logos = _extract_logos_from_form(p)
        for attr, val in logos.items():
            setattr(p, attr, val)

        p.nombre           = request.form.get("nombre", "").strip()
        p.sector           = request.form.get("sector", "").strip()
        p.persona_contacto = request.form.get("persona_contacto", "").strip()
        p.email            = request.form.get("email", "").strip().lower()
        p.telefono         = request.form.get("telefono", "").strip()
        p.web              = request.form.get("web", "").strip()
        p.instagram        = request.form.get("instagram", "").strip()
        p.facebook         = request.form.get("facebook", "").strip()
        p.twitter          = request.form.get("twitter", "").strip()
        p.linkedin         = request.form.get("linkedin", "").strip()
        p.tiktok           = request.form.get("tiktok", "").strip()
        p.youtube          = request.form.get("youtube", "").strip()
        p.notas            = request.form.get("notas", "").strip()
        db.session.commit()
        registrar_log("editar", "patrocinador", p.id, f"Patrocinador editado: {p.nombre}")
        flash("Patrocinador actualizado correctamente.", "success")
        return redirect(url_for("autoclub.patrocinadores_detalle", id=p.id))

    return render_template("autoclub/patrocinadores/form.html", p=p, datos={})


@autoclub_bp.route("/patrocinadores/<int:id>/estado", methods=["POST"])
@login_required
def patrocinadores_estado(id):
    p = Patrocinador.query.get_or_404(id)
    if p.activo:
        p.activo = False
        registrar_log("cambiar_estado", "patrocinador", p.id, f"Patrocinador desactivado: {p.nombre}")
        flash(f"{p.nombre} marcado como inactivo.", "warning")
    else:
        p.activo = True
        registrar_log("cambiar_estado", "patrocinador", p.id, f"Patrocinador reactivado: {p.nombre}")
        flash(f"{p.nombre} reactivado correctamente.", "success")
    db.session.commit()
    return redirect(url_for("autoclub.patrocinadores_detalle", id=p.id))


@autoclub_bp.route("/patrocinadores/<int:id>/eliminar", methods=["POST"])
@login_required
def patrocinadores_eliminar(id):
    p = Patrocinador.query.get_or_404(id)
    nombre = p.nombre
    for fn in [p.logo_positivo_filename, p.logo_negativo_filename, p.logo_banner_filename]:
        _delete_logo(fn)
    db.session.delete(p)
    db.session.commit()
    registrar_log("eliminar", "patrocinador", id, f"Patrocinador eliminado: {nombre}")
    flash(f"Patrocinador {nombre} eliminado.", "info")
    return redirect(url_for("autoclub.patrocinadores_lista"))


# ══════════════════════════════════════════════════════════════════════════════
#  SEGUIMIENTO / LOGS
# ══════════════════════════════════════════════════════════════════════════════

@autoclub_bp.route("/seguimiento")
@login_required
def seguimiento():
    from app.models.log import Log
    from app.models.usuario import Usuario
    from datetime import datetime

    page      = request.args.get("page", 1, type=int)
    usuario   = request.args.get("usuario", "").strip()
    accion    = request.args.get("accion", "").strip()
    fecha_ini = request.args.get("fecha_ini", "").strip()
    fecha_fin = request.args.get("fecha_fin", "").strip()

    # Mostrar solo logs relevantes para AutoClub: sesiones + acciones sobre socios/patrocinadores
    query = Log.query.filter(
        db.or_(
            Log.accion.in_(["login", "logout", "login_fallido"]),
            Log.entidad.in_(["socio", "patrocinador"]),
        )
    )

    if usuario:
        query = query.filter(Log.usuario_nombre.ilike(f"%{usuario}%"))
    if accion:
        query = query.filter(Log.accion == accion)
    if fecha_ini:
        try:
            query = query.filter(Log.fecha >= datetime.strptime(fecha_ini, "%Y-%m-%d"))
        except ValueError:
            pass
    if fecha_fin:
        from datetime import timedelta
        try:
            query = query.filter(
                Log.fecha < datetime.strptime(fecha_fin, "%Y-%m-%d") + timedelta(days=1)
            )
        except ValueError:
            pass

    logs = query.order_by(Log.fecha.desc()).paginate(page=page, per_page=40, error_out=False)

    acciones_disponibles = ["login", "logout", "login_fallido",
                            "crear", "editar", "eliminar", "cambiar_estado"]
    usuarios_distintos = sorted({
        r[0] for r in db.session.query(Log.usuario_nombre).filter(
            db.or_(
                Log.accion.in_(["login", "logout", "login_fallido"]),
                Log.entidad.in_(["socio", "patrocinador"]),
            )
        ).distinct().all()
    })

    return render_template(
        "autoclub/seguimiento.html",
        logs=logs,
        acciones=acciones_disponibles,
        usuarios=usuarios_distintos,
        filtro_usuario=usuario,
        filtro_accion=accion,
        filtro_fecha_ini=fecha_ini,
        filtro_fecha_fin=fecha_fin,
    )
