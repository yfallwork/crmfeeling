"""
Calendario de publicaciones en redes y campañas (dentro de Marketing):
vista mensual, ficha de cada publicación con subida de vídeos/fotos y su
descripción, y avisos por email del contenido pendiente de subir.
Las rutas se registran sobre marketing_bp (mismos permisos que Marketing).
"""
import calendar
import mimetypes
import os
import re
import uuid
from datetime import date, timedelta

from flask import (render_template, request, redirect, url_for, flash, abort,
                   send_from_directory, current_app)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models.configuracion import Configuracion
from app.models.publicacion_rrss import (
    PublicacionRRSS, CampanaRRSS, ArchivoPublicacion, DestinatarioAvisoRRSS,
    CATEGORIAS_RRSS, TIPOS_RRSS, PRODUCCION_RRSS, ESTADOS_RRSS,
)
from app.routes.marketing import marketing_bp
from app.services.log_service import registrar_log

EXTENSIONES_PERMITIDAS = {"jpg", "jpeg", "png", "webp", "gif", "heic", "mp4", "mov", "m4v", "webm"}
# Límite propio de esta subida (los vídeos de reels superan el límite general).
MAX_SUBIDA_MB = 500
MESES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
         "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _carpeta_archivos():
    carpeta = os.path.join(current_app.instance_path, "uploads", "publicaciones")
    os.makedirs(carpeta, exist_ok=True)
    return carpeta


def _parse_fecha(raw):
    try:
        return date.fromisoformat((raw or "").strip())
    except ValueError:
        return None


# ── Calendario ────────────────────────────────────────────────────────────

@marketing_bp.route("/publicaciones")
@login_required
def publicaciones_calendario():
    hoy = date.today()
    try:
        anio, mes = (int(x) for x in request.args.get("mes", "").split("-"))
        primero = date(anio, mes, 1)
    except ValueError:
        primero = hoy.replace(day=1)
    semanas = calendar.Calendar(firstweekday=0).monthdatescalendar(primero.year, primero.month)
    inicio, fin = semanas[0][0], semanas[-1][-1]

    pubs = (PublicacionRRSS.query
            .filter(PublicacionRRSS.fecha >= inicio, PublicacionRRSS.fecha <= fin)
            .order_by(PublicacionRRSS.fecha, PublicacionRRSS.id).all())
    por_dia = {}
    for p in pubs:
        por_dia.setdefault(p.fecha, []).append(p)
    campanas = (CampanaRRSS.query
                .filter(CampanaRRSS.fecha_inicio <= fin, CampanaRRSS.fecha_fin >= inicio)
                .order_by(CampanaRRSS.fecha_inicio).all())

    anterior = (primero - timedelta(days=1)).replace(day=1)
    siguiente = (primero + timedelta(days=32)).replace(day=1)
    pendientes_proximas = (PublicacionRRSS.query
                           .filter(PublicacionRRSS.estado == "pendiente",
                                   PublicacionRRSS.en_directo.is_(False),
                                   PublicacionRRSS.fecha <= hoy + timedelta(days=7))
                           .order_by(PublicacionRRSS.fecha).limit(12).all())
    return render_template(
        "marketing/publicaciones/calendario.html",
        semanas=semanas, primero=primero, por_dia=por_dia, campanas=campanas, hoy=hoy,
        titulo_mes=f"{MESES[primero.month]} {primero.year}",
        mes_anterior=anterior.strftime("%Y-%m"), mes_siguiente=siguiente.strftime("%Y-%m"),
        mes_actual=hoy.strftime("%Y-%m"),
        pubs_mes=[p for p in pubs if p.fecha.month == primero.month],
        pendientes_proximas=pendientes_proximas,
        categorias=CATEGORIAS_RRSS, tipos=TIPOS_RRSS, estados=ESTADOS_RRSS,
    )


# ── CRUD publicaciones ────────────────────────────────────────────────────

def _leer_form(form, errores):
    fecha = _parse_fecha(form.get("fecha"))
    if not fecha:
        errores["fecha"] = "Indica la fecha."
    titulo = form.get("titulo", "").strip()
    if not titulo:
        errores["titulo"] = "Indica el título."
    categoria = form.get("categoria", "")
    tipo = form.get("tipo", "")
    estado = form.get("estado", "pendiente")
    produccion = form.get("produccion", "")
    campana_id = form.get("campana_id", type=int)
    if campana_id and not db.session.get(CampanaRRSS, campana_id):
        campana_id = None
    return {
        "fecha": fecha, "titulo": titulo,
        "categoria": categoria if categoria in CATEGORIAS_RRSS else "ventas",
        "tipo": tipo if tipo in TIPOS_RRSS else "post",
        "estado": estado if estado in ESTADOS_RRSS else "pendiente",
        "produccion": produccion if produccion in PRODUCCION_RRSS else "",
        "formato": form.get("formato", "").strip(),
        "indicaciones": form.get("indicaciones", "").strip(),
        "descripcion": form.get("descripcion", "").strip(),
        "campana_id": campana_id,
        "en_directo": bool(form.get("en_directo")),
    }


def _render_form(publicacion, datos, errores):
    return render_template(
        "marketing/publicaciones/form.html", publicacion=publicacion, datos=datos, errores=errores,
        categorias=CATEGORIAS_RRSS, tipos=TIPOS_RRSS, producciones=PRODUCCION_RRSS, estados=ESTADOS_RRSS,
        campanas=CampanaRRSS.query.order_by(CampanaRRSS.fecha_inicio.desc()).all(),
    ), (400 if errores else 200)


@marketing_bp.route("/publicaciones/nueva", methods=["GET", "POST"])
@login_required
def publicaciones_nueva():
    errores = {}
    if request.method == "POST":
        datos = _leer_form(request.form, errores)
        if not errores:
            p = PublicacionRRSS(**datos)
            db.session.add(p)
            db.session.commit()
            registrar_log("crear", "publicacion_rrss", p.id, f"Publicación creada: {p.titulo} ({p.fecha:%d/%m/%Y})")
            flash("Publicación creada. Ya puedes subir el vídeo o la foto.", "success")
            return redirect(url_for("marketing.publicaciones_detalle", id=p.id))
        flash("Revisa los campos marcados.", "danger")
        return _render_form(None, request.form, errores)
    fecha = _parse_fecha(request.args.get("fecha")) or date.today()
    return _render_form(None, {"fecha": fecha.isoformat(), "estado": "pendiente"}, errores)


@marketing_bp.route("/publicaciones/<int:id>")
@login_required
def publicaciones_detalle(id):
    p = PublicacionRRSS.query.get_or_404(id)
    return render_template(
        "marketing/publicaciones/detalle.html", p=p, estados=ESTADOS_RRSS,
        n_destinatarios=DestinatarioAvisoRRSS.query.filter_by(activo=True).count(),
        extensiones=", ".join(sorted(EXTENSIONES_PERMITIDAS)), max_mb=MAX_SUBIDA_MB,
    )


@marketing_bp.route("/publicaciones/<int:id>/editar", methods=["GET", "POST"])
@login_required
def publicaciones_editar(id):
    p = PublicacionRRSS.query.get_or_404(id)
    errores = {}
    if request.method == "POST":
        datos = _leer_form(request.form, errores)
        if not errores:
            for k, v in datos.items():
                setattr(p, k, v)
            db.session.commit()
            registrar_log("editar", "publicacion_rrss", p.id, f"Publicación editada: {p.titulo}")
            flash("Publicación actualizada.", "success")
            return redirect(url_for("marketing.publicaciones_detalle", id=p.id))
        flash("Revisa los campos marcados.", "danger")
        return _render_form(p, request.form, errores)
    datos = {c: getattr(p, c) or "" for c in ("titulo", "categoria", "tipo", "estado", "produccion",
                                                  "formato", "indicaciones", "descripcion")}
    datos["fecha"] = p.fecha.isoformat()
    datos["campana_id"] = p.campana_id or ""
    datos["en_directo"] = p.en_directo
    return _render_form(p, datos, errores)


@marketing_bp.route("/publicaciones/<int:id>/descripcion", methods=["POST"])
@login_required
def publicaciones_descripcion(id):
    p = PublicacionRRSS.query.get_or_404(id)
    p.descripcion = request.form.get("descripcion", "").strip()
    db.session.commit()
    flash("Descripción guardada.", "success")
    return redirect(url_for("marketing.publicaciones_detalle", id=p.id) + "#descripcion")


@marketing_bp.route("/publicaciones/<int:id>/estado", methods=["POST"])
@login_required
def publicaciones_estado(id):
    p = PublicacionRRSS.query.get_or_404(id)
    estado = request.form.get("estado", "")
    if estado in ESTADOS_RRSS:
        p.estado = estado
        db.session.commit()
        registrar_log("cambiar_estado", "publicacion_rrss", p.id, f"{p.titulo} → {ESTADOS_RRSS[estado][0]}")
        flash(f"Marcada como «{ESTADOS_RRSS[estado][0]}».", "success")
    return redirect(request.form.get("volver") or url_for("marketing.publicaciones_detalle", id=p.id))


@marketing_bp.route("/publicaciones/<int:id>/en-directo", methods=["POST"])
@login_required
def publicaciones_en_directo(id):
    p = PublicacionRRSS.query.get_or_404(id)
    p.en_directo = not p.en_directo
    db.session.commit()
    registrar_log("editar", "publicacion_rrss", p.id,
                  f"{p.titulo}: {'se publica en el momento' if p.en_directo else 'requiere subir el contenido antes'}")
    flash("Marcada para grabar y publicar en el momento: no se avisará de subirla antes." if p.en_directo
          else "Ahora requiere subir el contenido antes: se avisará como pendiente.", "success")
    return redirect(url_for("marketing.publicaciones_detalle", id=p.id))


@marketing_bp.route("/publicaciones/<int:id>/eliminar", methods=["POST"])
@login_required
def publicaciones_eliminar(id):
    p = PublicacionRRSS.query.get_or_404(id)
    carpeta = _carpeta_archivos()
    for a in p.archivos:
        try:
            os.remove(os.path.join(carpeta, a.nombre_archivo))
        except OSError:
            pass
    mes = p.fecha.strftime("%Y-%m")
    titulo = p.titulo
    db.session.delete(p)
    db.session.commit()
    registrar_log("eliminar", "publicacion_rrss", id, f"Publicación eliminada: {titulo}")
    flash("Publicación eliminada.", "success")
    return redirect(url_for("marketing.publicaciones_calendario", mes=mes))


# ── Archivos (vídeo / foto) ───────────────────────────────────────────────

@marketing_bp.route("/publicaciones/<int:id>/archivos", methods=["POST"])
@login_required
def publicaciones_subir(id):
    p = PublicacionRRSS.query.get_or_404(id)
    ficheros = [f for f in request.files.getlist("archivos") if f and f.filename]
    if not ficheros:
        flash("Selecciona al menos un vídeo o foto.", "danger")
        return redirect(url_for("marketing.publicaciones_detalle", id=p.id) + "#archivos")

    carpeta = _carpeta_archivos()
    subidos, rechazados = 0, []
    for f in ficheros:
        original = f.filename
        ext = original.rsplit(".", 1)[-1].lower() if "." in original else ""
        if ext not in EXTENSIONES_PERMITIDAS:
            rechazados.append(original)
            continue
        nombre = f"{p.id}_{uuid.uuid4().hex}.{ext}"
        ruta = os.path.join(carpeta, nombre)
        f.save(ruta)
        mime = f.mimetype if f.mimetype and f.mimetype != "application/octet-stream" else (mimetypes.guess_type(original)[0] or "")
        db.session.add(ArchivoPublicacion(
            publicacion_id=p.id, nombre_archivo=nombre,
            nombre_original=secure_filename(original) or nombre,
            mimetype=mime, tamano=os.path.getsize(ruta), subido_por_id=current_user.id,
        ))
        subidos += 1

    if subidos and p.estado == "pendiente":
        p.estado = "listo"
    db.session.commit()
    if subidos:
        registrar_log("editar", "publicacion_rrss", p.id, f"{subidos} archivo(s) subido(s) a «{p.titulo}»")
        flash(f"{subidos} archivo{'s' if subidos != 1 else ''} subido{'s' if subidos != 1 else ''}.", "success")
    if rechazados:
        flash(f"No se admiten estos archivos: {', '.join(rechazados)}. Formatos: {', '.join(sorted(EXTENSIONES_PERMITIDAS))}.", "danger")
    return redirect(url_for("marketing.publicaciones_detalle", id=p.id) + "#archivos")


@marketing_bp.route("/publicaciones/archivos/<int:aid>")
@login_required
def publicaciones_archivo(aid):
    a = ArchivoPublicacion.query.get_or_404(aid)
    return send_from_directory(_carpeta_archivos(), a.nombre_archivo, mimetype=a.mimetype or None,
                               as_attachment=request.args.get("descargar") == "1",
                               download_name=a.nombre_original, conditional=True)


@marketing_bp.route("/publicaciones/archivos/<int:aid>/eliminar", methods=["POST"])
@login_required
def publicaciones_archivo_eliminar(aid):
    a = ArchivoPublicacion.query.get_or_404(aid)
    p = a.publicacion
    try:
        os.remove(os.path.join(_carpeta_archivos(), a.nombre_archivo))
    except OSError:
        pass
    db.session.delete(a)
    db.session.flush()
    if p.estado == "listo" and not p.archivos:
        p.estado = "pendiente"
    db.session.commit()
    flash("Archivo eliminado.", "success")
    return redirect(url_for("marketing.publicaciones_detalle", id=p.id) + "#archivos")


# ── Campañas ──────────────────────────────────────────────────────────────

@marketing_bp.route("/publicaciones/campanas", methods=["GET", "POST"])
@login_required
def publicaciones_campanas():
    if request.method == "POST":
        cid = request.form.get("id", type=int)
        c = db.session.get(CampanaRRSS, cid) if cid else CampanaRRSS()
        if cid and not c:
            abort(404)
        nombre = request.form.get("nombre", "").strip()
        ini = _parse_fecha(request.form.get("fecha_inicio"))
        fin = _parse_fecha(request.form.get("fecha_fin"))
        if not nombre or not ini or not fin or fin < ini:
            flash("Indica nombre y un rango de fechas válido.", "danger")
        else:
            c.nombre, c.fecha_inicio, c.fecha_fin = nombre, ini, fin
            c.color = request.form.get("color") or "#854D0E"
            c.descripcion = request.form.get("descripcion", "").strip()
            if not cid:
                db.session.add(c)
            db.session.commit()
            flash("Campaña guardada.", "success")
        return redirect(url_for("marketing.publicaciones_campanas"))
    campanas = CampanaRRSS.query.order_by(CampanaRRSS.fecha_inicio.desc()).all()
    return render_template("marketing/publicaciones/campanas.html", campanas=campanas)


@marketing_bp.route("/publicaciones/campanas/<int:cid>/eliminar", methods=["POST"])
@login_required
def publicaciones_campana_eliminar(cid):
    c = CampanaRRSS.query.get_or_404(cid)
    db.session.delete(c)
    db.session.commit()
    flash("Campaña eliminada (sus publicaciones se mantienen).", "success")
    return redirect(url_for("marketing.publicaciones_campanas"))


# ── Avisos por email ──────────────────────────────────────────────────────

@marketing_bp.route("/publicaciones/avisos", methods=["GET", "POST"])
@login_required
def publicaciones_avisos():
    config = Configuracion.get()
    if request.method == "POST":
        accion = request.form.get("accion")
        if accion == "anadir":
            email = request.form.get("email", "").strip().lower()
            if not _EMAIL_RE.match(email):
                flash("Email no válido.", "danger")
            elif DestinatarioAvisoRRSS.query.filter_by(email=email).first():
                flash("Ese correo ya está añadido.", "warning")
            else:
                db.session.add(DestinatarioAvisoRRSS(email=email, nombre=request.form.get("nombre", "").strip()))
                db.session.commit()
                flash(f"{email} recibirá los avisos.", "success")
        elif accion in ("quitar", "alternar"):
            d = DestinatarioAvisoRRSS.query.get_or_404(request.form.get("id", type=int))
            if accion == "quitar":
                db.session.delete(d)
            else:
                d.activo = not d.activo
            db.session.commit()
        elif accion == "config":
            config.rrss_aviso_activo = bool(request.form.get("activo"))
            dias = request.form.get("dias", type=int)
            if dias is not None and 0 <= dias <= 14:
                config.rrss_aviso_dias = dias
            db.session.commit()
            flash("Configuración de avisos guardada.", "success")
        elif accion == "enviar_ahora":
            from app.services.publicaciones_aviso import enviar_resumen
            n, nd, error = enviar_resumen(forzar=True)
            if error:
                flash(f"No se pudo enviar: {error}", "danger")
            elif n:
                flash(f"Resumen enviado a {nd} correo{'s' if nd != 1 else ''} con {n} contenido{'s' if n != 1 else ''} pendiente{'s' if n != 1 else ''}.", "success")
            else:
                flash("No hay contenido pendiente en el periodo: no se ha enviado nada.", "info")
        return redirect(url_for("marketing.publicaciones_avisos"))

    from app.services.publicaciones_aviso import pendientes_para_aviso, en_directo_de_hoy
    return render_template(
        "marketing/publicaciones/avisos.html", config=config,
        destinatarios=DestinatarioAvisoRRSS.query.order_by(DestinatarioAvisoRRSS.email).all(),
        pendientes=pendientes_para_aviso(config.rrss_aviso_dias), directo_hoy=en_directo_de_hoy(), hoy=date.today(),
    )


@marketing_bp.route("/publicaciones/<int:id>/avisar", methods=["POST"])
@login_required
def publicaciones_avisar(id):
    from app.services.publicaciones_aviso import enviar_aviso_publicacion
    p = PublicacionRRSS.query.get_or_404(id)
    nd, error = enviar_aviso_publicacion(p)
    if error:
        flash(f"No se pudo enviar el aviso: {error}", "danger")
    else:
        flash(f"Aviso enviado a {nd} correo{'s' if nd != 1 else ''}.", "success")
    return redirect(url_for("marketing.publicaciones_detalle", id=p.id))
