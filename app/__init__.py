import os
from flask import Flask, render_template
from config import config
from app.extensions import db, login_manager, mail, csrf


def create_app(env="default"):
    app = Flask(__name__)
    app.config.from_object(config[env])

    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)

    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.clientes import clientes_bp
    from app.routes.reservas import reservas_bp
    from app.routes.calendario import calendario_bp
    from app.routes.woocommerce import woo_bp
    from app.routes.api import api_bp
    from app.routes.estadisticas import estadisticas_bp
    from app.routes.logs import logs_bp
    from app.routes.agenda import agenda_bp
    from app.routes.autoclub import autoclub_bp
    from app.routes.teambuilding import teambuilding_bp
    from app.routes.marketing import marketing_bp
    from app.routes.vista import vista_bp
    from app.routes.configuracion import configuracion_bp
    from app.routes.seguro_publico import seguro_bp
    from app.routes.seleccion_femenina import seleccion_femenina_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(clientes_bp, url_prefix="/clientes")
    app.register_blueprint(reservas_bp, url_prefix="/reservas")
    app.register_blueprint(calendario_bp, url_prefix="/calendario")
    app.register_blueprint(woo_bp, url_prefix="/woocommerce")
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(estadisticas_bp)
    app.register_blueprint(logs_bp)
    app.register_blueprint(agenda_bp, url_prefix="/agenda")
    app.register_blueprint(autoclub_bp, url_prefix="/autoclub")
    app.register_blueprint(teambuilding_bp, url_prefix="/teambuilding")
    app.register_blueprint(marketing_bp, url_prefix="/marketing")
    app.register_blueprint(vista_bp, url_prefix="/vista")
    app.register_blueprint(configuracion_bp, url_prefix="/configuracion")
    app.register_blueprint(seguro_bp, url_prefix="/seguro")
    app.register_blueprint(seleccion_femenina_bp, url_prefix="/seleccion-femenina")

    with app.app_context():
        from app.models import comunicacion, log  # noqa: F401
        from app.models import agenda  # noqa: F401
        from app.models import socio  # noqa: F401  # usado por autoclub
        from app.models import patrocinador  # noqa: F401  # usado por autoclub
        from app.models import empresa  # noqa: F401  # usado por teambuilding
        from app.models import empresa_nota  # noqa: F401
        from app.models import autoclub_nota  # noqa: F401
        from app.models import tag  # noqa: F401  # usado por marketing
        from app.models import rule  # noqa: F401  # usado por marketing (plantillas + normas)
        from app.models import marketing_log  # noqa: F401  # log de automatización marketing
        from app.models import campana  # noqa: F401  # campañas y plantillas WA
        from app.models import piloto             # noqa: F401
        from app.models import vehiculo           # noqa: F401
        from app.models import inscripcion        # noqa: F401
        from app.models import inscripcion_piloto # noqa: F401
        from app.models import gasto_inscripcion  # noqa: F401
        from app.models import staff_miembro          # noqa: F401
        from app.models import resultado_inscripcion  # noqa: F401
        from app.models import competicion_evento    # noqa: F401
        from app.models import autoclub_info        # noqa: F401
        from app.models import medio_contacto       # noqa: F401
        from app.models import notificacion         # noqa: F401
        from app.models import fecha_apertura       # noqa: F401
        from app.models import configuracion        # noqa: F401
        from app.models import preinscripcion_carcross  # noqa: F401
        from app.models import evento                   # noqa: F401
        db.create_all()
        _migrate_columns()
        _migrate_indices()
        _migrate_reservas_for_teambuilding()
        _migrate_gastos_evento()
        _seed_usuarios()
        _seed_autoclub()
        _seed_teambuilding()
        _seed_tags()
        _seed_plantillas()
        _seed_normas()
        _seed_notificaciones()
        _migrate_trigger_eventos()
        _migrate_vip_tag()
        _migrate_aniversario_tags()
        _migrate_presupuesto_dinamica()
        _migrate_descargo_dossier()
        _migrate_gran_cuenta_tag()
        _seed_plantillas_wa()
        _seed_campanas()
        _seed_marketing_logs_ejemplo()
        _seed_empresa_notas()

    import json as _json
    app.jinja_env.filters['from_json'] = lambda s: _json.loads(s) if s else []

    from flask import request as _req, redirect as _redir
    from flask_login import current_user

    # Rutas que el rol "vista" puede llamar (API + su propio blueprint)
    _VISTA_ALLOWED = (
        "/vista",
        "/static/",
        "/login",
        "/logout",
        "/calendario/eventos",
        "/calendario/aperturas",
        "/agenda/api/",
        "/agenda/entradas/nueva",
        "/autoclub/calendario/eventos",
        "/autoclub/calendario/evento/nuevo",
        "/api/reservas/",
    )

    @app.before_request
    def _restrict_vista_role():
        if not current_user.is_authenticated:
            return
        if current_user.rol != "vista":
            return
        path = _req.path
        for allowed in _VISTA_ALLOWED:
            if path.startswith(allowed):
                return
        return _redir("/vista/")

    # Blueprints siempre accesibles para cualquier usuario autenticado,
    # independientemente de sus permisos por módulo.
    _SIN_RESTRICCION = ("auth", "dashboard", "static", "api", "vista")

    @app.before_request
    def _restrict_modulos():
        if not current_user.is_authenticated:
            return
        if current_user.rol in ("admin", "vista"):
            return
        bp = _req.blueprint
        if not bp or bp in _SIN_RESTRICCION:
            return
        from app.models.usuario import MODULOS_KEYS, AUTOCLUB_SECCIONES_KEYS
        from flask import abort as _abort
        if bp in MODULOS_KEYS and not current_user.puede_acceder(bp):
            _abort(403)
        if bp == "autoclub":
            for seccion in AUTOCLUB_SECCIONES_KEYS:
                if _req.path.startswith(f"/autoclub/{seccion}") and not current_user.puede_acceder_autoclub(seccion):
                    _abort(403)

    # Cache en memoria del badge de notificaciones: evita una query de BD en
    # cada request autenticado. TTL corto porque es solo un contador visual.
    _NOTIF_CACHE = {}
    _NOTIF_TTL_SEGUNDOS = 20

    @app.context_processor
    def _inject_notificaciones():
        import time
        try:
            if current_user.is_authenticated:
                ahora = time.time()
                cache_entry = _NOTIF_CACHE.get(current_user.id)
                if cache_entry and ahora - cache_entry[0] < _NOTIF_TTL_SEGUNDOS:
                    _, count, notifs = cache_entry
                    return {"notif_count": count, "notificaciones_recientes": notifs}

                from app.models.notificacion import Notificacion
                notifs = (Notificacion.query
                          .filter_by(leida=False)
                          .order_by(Notificacion.creado_en.desc())
                          .limit(15).all())
                _NOTIF_CACHE[current_user.id] = (ahora, len(notifs), notifs)
                return {"notif_count": len(notifs), "notificaciones_recientes": notifs}
        except Exception:
            pass
        return {"notif_count": 0, "notificaciones_recientes": []}

    # ── Páginas de error personalizadas ─────────────────────────────────────
    def _wants_json():
        return (
            _req.path.startswith("/api/")
            or _req.accept_mimetypes["application/json"] >= _req.accept_mimetypes["text/html"]
        )

    @app.errorhandler(403)
    def _handle_403(err):
        if _wants_json():
            from flask import jsonify
            return jsonify({"ok": False, "error": "No tienes permiso para acceder a este recurso"}), 403
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def _handle_404(err):
        if _wants_json():
            from flask import jsonify
            return jsonify({"ok": False, "error": "Recurso no encontrado"}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def _handle_500(err):
        db.session.rollback()
        app.logger.exception("Error interno no controlado")
        if _wants_json():
            from flask import jsonify
            return jsonify({"ok": False, "error": "Error interno del servidor"}), 500
        return render_template("errors/500.html"), 500

    # Iniciar scheduler solo en el proceso principal (evita doble arranque con reloader)
    # y nunca durante los tests (evita hilos en segundo plano contra la BD de test).
    if not app.config.get("TESTING") and (not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true"):
        from app.scheduler import init_scheduler
        init_scheduler(app)

    return app


def _migrate_columns():
    """Adds new columns to existing tables without losing data."""
    from sqlalchemy import text
    nuevas = [
        ("reservas",      "horario",                "VARCHAR(20) DEFAULT ''"),
        ("reservas",      "variante",               "VARCHAR(150) DEFAULT ''"),
        ("usuarios",      "username",               "VARCHAR(50)"),
        ("patrocinadores", "logo_positivo_filename", "VARCHAR(255) DEFAULT ''"),
        ("patrocinadores", "logo_negativo_filename", "VARCHAR(255) DEFAULT ''"),
        ("patrocinadores", "logo_banner_filename",   "VARCHAR(255) DEFAULT ''"),
        ("tags",           "tiempo_sin_reserva_dias",  "INTEGER"),
        ("tags",           "criterio_min_gasto",       "REAL"),
        ("tags",           "criterio_min_reservas",    "INTEGER"),
        ("tags",           "criterio_min_empleados",   "INTEGER"),
        ("empresas_tb",       "num_empleados",    "INTEGER"),
        ("marketing_logs",    "campana_id",       "INTEGER"),
        ("marketing_logs",    "campana_nombre",        "VARCHAR(200) DEFAULT ''"),
        ("gastos_inscripcion", "documento_filename",   "VARCHAR(255)"),
        ("gastos_inscripcion", "factura_filename",     "VARCHAR(255)"),
        ("inscripciones",      "fecha_fin",             "DATE"),
        ("inscripcion_pilotos", "estado",                "VARCHAR(20) DEFAULT 'pendiente'"),
        ("autoclub_info",      "firma_html",            "TEXT DEFAULT ''"),
        ("inscripciones",      "fecha_plazo",           "DATE"),
        ("competicion_eventos", "fecha_plazo",           "DATE"),
        ("fechas_apertura",    "capacidad_ideal",       "INTEGER"),
        ("usuarios",           "permisos_json",         "TEXT"),
        ("reservas",           "piloto_nombre",           "VARCHAR(100) DEFAULT ''"),
        ("reservas",           "piloto_primer_apellido",  "VARCHAR(100) DEFAULT ''"),
        ("reservas",           "piloto_segundo_apellido", "VARCHAR(100) DEFAULT ''"),
        ("reservas",           "piloto_fecha_nacimiento", "DATE"),
        ("reservas",           "piloto_dni",              "VARCHAR(20) DEFAULT ''"),
        ("reservas",           "token_seguro",            "VARCHAR(64)"),
        ("configuracion",      "seguro_recordatorio_activo", "BOOLEAN DEFAULT 1"),
        ("configuracion",      "seguro_recordatorio_dias",   "INTEGER DEFAULT 7"),
        ("eventos",            "woo_producto_ids",          "TEXT DEFAULT ''"),
        ("entradas_evento",    "fecha_pedido",              "DATETIME"),
        ("entradas_evento",    "cargo_institucional",       "VARCHAR(100) DEFAULT ''"),
        ("entradas_evento",    "institucion",               "VARCHAR(150) DEFAULT ''"),
        ("entradas_evento",    "cif_institucion",           "VARCHAR(20) DEFAULT ''"),
        ("entradas_evento",    "num_acompanantes",          "INTEGER DEFAULT 0"),
    ]
    with db.engine.connect() as conn:
        for tabla, columna, tipo in nuevas:
            try:
                conn.execute(text(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}"))
                conn.commit()
            except Exception:
                pass  # column already exists


def _migrate_indices():
    """Crea índices en columnas muy filtradas para bases de datos ya existentes
    (los modelos ya declaran index=True, pero eso solo aplica a tablas nuevas)."""
    from sqlalchemy import text
    indices = [
        ("ix_clientes_creado_en",       "clientes",  "creado_en"),
        ("ix_reservas_estado",          "reservas",  "estado"),
        ("ix_reservas_fecha_disfrute",  "reservas",  "fecha_disfrute"),
        ("ix_reservas_cliente_id",      "reservas",  "cliente_id"),
        ("ix_reservas_empresa_id",      "reservas",  "empresa_id"),
        ("ix_tags_tipo",                "tags",      "tipo"),
        ("ix_tags_segmento",            "tags",      "segmento"),
        ("ix_tags_activo",              "tags",      "activo"),
        ("ix_reservas_token_seguro",    "reservas",  "token_seguro"),
    ]
    with db.engine.connect() as conn:
        for nombre, tabla, columna in indices:
            try:
                conn.execute(text(f"CREATE INDEX IF NOT EXISTS {nombre} ON {tabla} ({columna})"))
                conn.commit()
            except Exception:
                pass  # índice ya existe o tabla no soporta la sintaxis


def _migrate_gran_cuenta_tag():
    """Convierte gran_cuenta_b2b de dinámica a sistemática con criterios."""
    from app.models.tag import Tag
    tag = Tag.query.filter_by(slug="gran_cuenta_b2b").first()
    if tag and tag.tipo != "sistematica":
        tag.tipo = "sistematica"
        tag.trigger_evento = ""
        db.session.commit()


def _migrate_descargo_dossier():
    """
    Convierte descargo_dossier a dinámica sin trigger: no hay dossier ni lo habrá.
    Queda visible en la UI y se puede borrar manualmente desde Etiquetas.
    """
    from app.models.tag import Tag
    tag = Tag.query.filter_by(slug="descargo_dossier").first()
    if tag and tag.tipo == "sistematica":
        tag.tipo = "dinamica"
        tag.trigger_evento = ""
        db.session.commit()


def _migrate_presupuesto_dinamica():
    """
    Convierte presupuesto_solicitado de sistemática a dinámica (asignación manual).
    También corrige el trigger de experiencia_reservada a crm.reserva.creada.
    """
    from app.models.tag import Tag
    changed = False

    tag = Tag.query.filter_by(slug="presupuesto_solicitado").first()
    if tag and tag.tipo == "sistematica":
        tag.tipo = "dinamica"
        tag.trigger_evento = ""
        changed = True

    tag_res = Tag.query.filter_by(slug="experiencia_reservada").first()
    if tag_res and tag_res.trigger_evento != "crm.reserva.creada":
        tag_res.trigger_evento = "crm.reserva.creada"
        changed = True

    if changed:
        db.session.commit()


def _migrate_aniversario_tags():
    """Crea las etiquetas de mes aniversario si no existen todavía."""
    from app.models.tag import Tag

    nuevos = [
        dict(
            slug="mes_aniversario_cliente",
            nombre="Mes aniversario cliente",
            descripcion="El mes actual coincide con el mes en que se dio de alta el cliente (su aniversario con nosotros).",
            tipo="sistematica", entidad="cliente", segmento="b2c",
            color="#EC4899", icono="bi-calendar-heart-fill",
            trigger_evento="",
        ),
        dict(
            slug="mes_aniversario_empresa",
            nombre="Mes aniversario empresa",
            descripcion="El mes actual coincide con el mes en que se dio de alta la empresa (su aniversario con nosotros).",
            tipo="sistematica", entidad="empresa", segmento="b2b",
            color="#8B5CF6", icono="bi-calendar-heart-fill",
            trigger_evento="",
        ),
    ]
    changed = False
    for datos in nuevos:
        if not Tag.query.filter_by(slug=datos["slug"]).first():
            db.session.add(Tag(**datos))
            changed = True
    if changed:
        db.session.commit()


def _migrate_vip_tag():
    """Convierte el tag cliente_vip_particular de dinámica a sistemática con criterios."""
    from app.models.tag import Tag
    tag = Tag.query.filter_by(slug="cliente_vip_particular").first()
    if tag and tag.tipo != "sistematica":
        tag.tipo = "sistematica"
        db.session.commit()


def _migrate_trigger_eventos():
    """
    Actualiza los triggers de tags sistemáticas para usar eventos CRM genéricos.
    Esto permite que tanto clientes manuales como de WooCommerce disparen el mismo flujo.
    """
    from app.models.tag import Tag
    cambios = {
        "lead_particular_nuevo": "crm.cliente.creado",
        "lead_empresa_nuevo":    "crm.empresa.creada",
    }
    changed = False
    for slug, nuevo_trigger in cambios.items():
        tag = Tag.query.filter_by(slug=slug).first()
        if tag and tag.trigger_evento != nuevo_trigger:
            tag.trigger_evento = nuevo_trigger
            changed = True
    if changed:
        db.session.commit()


def _migrate_reservas_for_teambuilding():
    """Recreates reservas table to support empresa_id + TB columns.

    SQLite does not support ALTER COLUMN so if the table exists without empresa_id
    we create reservas_v2, copy data, drop old table, rename.
    """
    from sqlalchemy import text, inspect
    inspector = inspect(db.engine)
    if "reservas" not in inspector.get_table_names():
        return  # db.create_all() will create it with the new schema
    existing_cols = {c["name"] for c in inspector.get_columns("reservas")}
    if "empresa_id" in existing_cols:
        return  # already migrated

    copy_cols = [c for c in [
        "id", "cliente_id", "tipo_experiencia_id",
        "fecha_compra", "fecha_disfrute", "estado", "precio",
        "horario", "variante", "notas",
        "woo_order_id", "woo_order_status", "creado_en", "actualizado_en",
    ] if c in existing_cols]

    insert_cols = copy_cols + ["empresa_id", "num_participantes", "nombre_grupo"]
    select_exprs = copy_cols + ["NULL", "1", "''"]

    with db.engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE reservas_v2 (
                id INTEGER PRIMARY KEY,
                cliente_id INTEGER REFERENCES clientes(id),
                empresa_id INTEGER REFERENCES empresas_tb(id),
                tipo_experiencia_id INTEGER NOT NULL REFERENCES tipos_experiencia(id),
                fecha_compra DATETIME,
                fecha_disfrute DATETIME,
                estado VARCHAR(20) DEFAULT 'pendiente',
                precio FLOAT DEFAULT 0.0,
                horario VARCHAR(20) DEFAULT '',
                variante VARCHAR(150) DEFAULT '',
                notas TEXT DEFAULT '',
                num_participantes INTEGER DEFAULT 1,
                nombre_grupo VARCHAR(150) DEFAULT '',
                woo_order_id INTEGER UNIQUE,
                woo_order_status VARCHAR(30) DEFAULT '',
                creado_en DATETIME,
                actualizado_en DATETIME
            )
        """))
        conn.execute(text(
            f"INSERT INTO reservas_v2 ({', '.join(insert_cols)}) "
            f"SELECT {', '.join(str(e) for e in select_exprs)} FROM reservas"
        ))
        conn.execute(text("DROP TABLE reservas"))
        conn.execute(text("ALTER TABLE reservas_v2 RENAME TO reservas"))
        conn.commit()


def _migrate_gastos_evento():
    """Permite que un gasto se vincule a un evento de competición además de
    a una inscripción. SQLite no soporta ALTER COLUMN para quitar el
    NOT NULL de inscripcion_id, así que se recrea la tabla igual que en
    _migrate_reservas_for_teambuilding()."""
    from sqlalchemy import text, inspect
    inspector = inspect(db.engine)
    if "gastos_inscripcion" not in inspector.get_table_names():
        return  # db.create_all() ya la crea con el esquema nuevo
    existing_cols = {c["name"] for c in inspector.get_columns("gastos_inscripcion")}
    if "evento_id" in existing_cols:
        return  # ya migrada

    copy_cols = [c for c in [
        "id", "inscripcion_id", "concepto", "importe", "categoria",
        "fecha", "documento_filename", "factura_filename", "creado_en",
    ] if c in existing_cols]

    with db.engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE gastos_inscripcion_v2 (
                id INTEGER PRIMARY KEY,
                inscripcion_id INTEGER REFERENCES inscripciones(id),
                evento_id INTEGER REFERENCES competicion_eventos(id),
                concepto VARCHAR(200) NOT NULL,
                importe FLOAT DEFAULT 0.0,
                categoria VARCHAR(50) DEFAULT 'Otros',
                fecha DATE,
                documento_filename VARCHAR(255),
                factura_filename VARCHAR(255),
                creado_en DATETIME
            )
        """))
        conn.execute(text(
            f"INSERT INTO gastos_inscripcion_v2 ({', '.join(copy_cols)}, evento_id) "
            f"SELECT {', '.join(copy_cols)}, NULL FROM gastos_inscripcion"
        ))
        conn.execute(text("DROP TABLE gastos_inscripcion"))
        conn.execute(text("ALTER TABLE gastos_inscripcion_v2 RENAME TO gastos_inscripcion"))
        conn.commit()


def _seed_usuarios():
    """
    Crea las cuentas iniciales si no existen. Las contraseñas nunca están
    hardcodeadas: se toman de variables de entorno (SEED_<USER>_PASSWORD) o,
    si no se definen, se genera una aleatoria fuerte que se muestra una única
    vez en el log de arranque para que el administrador la guarde.
    """
    import secrets
    from app.models.usuario import Usuario

    generadas = []

    def _password_para(env_var):
        valor = os.environ.get(env_var)
        if valor:
            return valor, False
        return secrets.token_urlsafe(9), True

    if not Usuario.query.filter_by(email="admin@crm.local").first():
        pwd, fue_generada = _password_para("SEED_ADMIN_PASSWORD")
        admin = Usuario(nombre="Admin", email="admin@crm.local", rol="admin")
        admin.set_password(pwd)
        db.session.add(admin)
        if fue_generada:
            generadas.append(("admin@crm.local", pwd))

    if not Usuario.query.filter(
        (Usuario.username == "maria") | (Usuario.email == "maria@fe.local")
    ).first():
        pwd, fue_generada = _password_para("SEED_MARIA_PASSWORD")
        maria = Usuario(nombre="Maria", username="maria", email="maria@fe.local", rol="admin")
        maria.set_password(pwd)
        db.session.add(maria)
        if fue_generada:
            generadas.append(("maria", pwd))

    if not Usuario.query.filter(
        (Usuario.username == "andres") | (Usuario.email == "andres@fe.local")
    ).first():
        pwd, fue_generada = _password_para("SEED_ANDRES_PASSWORD")
        andres = Usuario(nombre="Andres", username="andres", email="andres@fe.local", rol="admin")
        andres.set_password(pwd)
        db.session.add(andres)
        if fue_generada:
            generadas.append(("andres", pwd))

    if not Usuario.query.filter_by(username="admincalendario").first():
        pwd, fue_generada = _password_para("SEED_ADMINCALENDARIO_PASSWORD")
        cal = Usuario(
            nombre="Admin Calendarios",
            username="admincalendario",
            email="admincalendario@calendarios.local",
            rol="vista",
            activo=True,
        )
        cal.set_password(pwd)
        db.session.add(cal)
        if fue_generada:
            generadas.append(("admincalendario", pwd))

    db.session.commit()

    if generadas:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("=" * 60)
        logger.warning("Cuentas creadas con contraseña generada automáticamente:")
        for usuario, pwd in generadas:
            logger.warning(f"  {usuario}: {pwd}")
        logger.warning(
            "Guarda estas contraseñas ahora: no se van a volver a mostrar. "
            "Para fijarlas tú mismo, define SEED_<USUARIO>_PASSWORD en el .env."
        )
        logger.warning("=" * 60)


def _seed_autoclub():
    """Inserts example socios and patrocinadores if tables are empty."""
    from datetime import date, datetime
    from app.models.socio import Socio
    from app.models.patrocinador import Patrocinador

    if Socio.query.count() == 0:
        socios = [
            Socio(nombre="Carlos",   apellido="Garcia Lopez",      email="carlos.garcia@example.com",
                  telefono="+34 612 345 678", dni="12345678A", tipo="premium",
                  fecha_alta=date(2022, 3, 15), activo=True,
                  notas="Piloto aficionado. Participa en los autocross trimestrales."),
            Socio(nombre="Maria",    apellido="Fernandez Ruiz",     email="maria.fernandez@example.com",
                  telefono="+34 623 456 789", dni="23456789B", tipo="vip",
                  fecha_alta=date(2021, 6, 1),  activo=True,
                  notas="Socia fundadora. Descuento especial en eventos VIP."),
            Socio(nombre="Antonio",  apellido="Martinez Sanchez",   email="antonio.martinez@example.com",
                  telefono="+34 634 567 890", dni="34567890C", tipo="familiar",
                  fecha_alta=date(2023, 1, 10), activo=True,
                  notas="Socio familiar - 2 adultos + 1 menor. Coche: BMW M3 E46."),
            Socio(nombre="Laura",    apellido="Gonzalez Perez",     email="laura.gonzalez@example.com",
                  telefono="+34 645 678 901", dni="45678901D", tipo="regular",
                  fecha_alta=date(2023, 8, 20), activo=True),
            Socio(nombre="Javier",   apellido="Lopez Torres",       email="javier.lopez@example.com",
                  telefono="+34 656 789 012", dni="56789012E", tipo="premium",
                  fecha_alta=date(2022, 11, 5), activo=False,
                  fecha_baja=datetime(2024, 3, 1),
                  notas="Baja temporal por traslado laboral."),
            Socio(nombre="Ana",      apellido="Jimenez Morales",    email="ana.jimenez@example.com",
                  telefono="+34 667 890 123", dni="67890123F", tipo="vip",
                  fecha_alta=date(2020, 4, 12), activo=True,
                  notas="Coleccionista. Porsche 911 (993) y Alfa Romeo 156 GTA."),
            Socio(nombre="Pedro",    apellido="Hernandez Castro",   email="pedro.hernandez@example.com",
                  telefono="+34 678 901 234", dni="78901234G", tipo="familiar",
                  fecha_alta=date(2023, 5, 30), activo=True),
            Socio(nombre="Carmen",   apellido="Diaz Romero",        email="carmen.diaz@example.com",
                  telefono="+34 689 012 345", dni="89012345H", tipo="regular",
                  fecha_alta=date(2024, 2, 14), activo=True,
                  notas="Nueva socia. Interesada en talleres de conduccion segura."),
        ]
        db.session.add_all(socios)

    if Patrocinador.query.count() == 0:
        patrocinadores = [
            Patrocinador(
                nombre="Talleres Hispano Motor",
                sector="Automacion y motor",
                persona_contacto="Roberto Serrano",
                email="info@hispanomotor.es",
                telefono="+34 91 234 56 78",
                web="https://hispanomotor.es",
                instagram="https://instagram.com/hispanomotor",
                facebook="https://facebook.com/hispanomotor",
                notas="Patrocinador principal desde 2021. Descuento del 15% a socios en mano de obra.",
                activo=True,
            ),
            Patrocinador(
                nombre="Seguros Amparo",
                sector="Seguros",
                persona_contacto="Elena Vargas",
                email="evargas@segurosamparo.com",
                telefono="+34 93 345 67 89",
                web="https://segurosamparo.com",
                linkedin="https://linkedin.com/company/segurosamparo",
                notas="Seguro de vehiculo colectivo para socios. Renovacion anual en diciembre.",
                activo=True,
            ),
            Patrocinador(
                nombre="Combustibles Noroeste",
                sector="Energia y utilities",
                persona_contacto="Manuel Prieto",
                email="mprieto@comb-noroeste.es",
                telefono="+34 986 45 67 89",
                web="https://comb-noroeste.es",
                notas="Descuento de 3 centimos/litro en gasolineras asociadas con tarjeta de socio.",
                activo=True,
            ),
            Patrocinador(
                nombre="Evento Motor Media",
                sector="Eventos y produccion",
                persona_contacto="Silvia Montoya",
                email="silvia@eventomotor.media",
                telefono="+34 696 56 78 90",
                web="https://eventomotor.media",
                instagram="https://instagram.com/eventomotormedia",
                youtube="https://youtube.com/@eventomotormedia",
                tiktok="https://tiktok.com/@eventomotormedia",
                notas="Cobertura audiovisual oficial de eventos del club.",
                activo=True,
            ),
            Patrocinador(
                nombre="Recambios Veloz SL",
                sector="Comercio al por menor",
                persona_contacto="Tomas Iglesias",
                email="tomas@recambiosveloz.es",
                telefono="+34 95 567 89 01",
                web="https://recambiosveloz.es",
                instagram="https://instagram.com/recambiosveloz",
                facebook="https://facebook.com/recambiosveloz",
                notas="10% de descuento en recambios y accesorios con codigo AUTOCLUB24.",
                activo=False,
            ),
        ]
        db.session.add_all(patrocinadores)

    db.session.commit()


def _seed_teambuilding():
    """Inserts example TB empresas and reservations if tables are empty."""
    from datetime import datetime, timedelta
    from app.models.empresa import Empresa
    from app.models.experiencia import TipoExperiencia
    from app.models.reserva import Reserva

    if Empresa.query.count() > 0:
        db.session.commit()
        return

    empresas = [
        Empresa(
            nombre="Innovatech Solutions",
            sector="Tecnologia de la informacion",
            persona_contacto="Elena Castillo",
            email="ecastillo@innovatech.es",
            telefono="+34 91 234 56 78",
            web="https://innovatech.es",
            linkedin="https://linkedin.com/company/innovatech",
            notas="Empresa tecnologica de 80 empleados. Interesada en actividades de cohesion anuales.",
            activo=True,
        ),
        Empresa(
            nombre="Construcciones Marvell S.A.",
            sector="Construccion e inmobiliaria",
            persona_contacto="Ricardo Fuentes",
            email="rfuentes@marvell.es",
            telefono="+34 93 456 78 90",
            web="https://marvellconstrucciones.es",
            facebook="https://facebook.com/marvellconstrucciones",
            instagram="https://instagram.com/marvellconstrucciones",
            notas="Constructora mediana. Busca actividades outdoor para su equipo.",
            activo=True,
        ),
        Empresa(
            nombre="Distribuidora Mediterranea SL",
            sector="Comercio al por mayor",
            persona_contacto="Susana Herrero",
            email="sherrero@distrib-med.com",
            telefono="+34 96 567 89 01",
            web="https://distribmed.com",
            notas="Empresa logistica con 40 trabajadores. Evento anual de motivacion.",
            activo=True,
        ),
        Empresa(
            nombre="Grupo Educativo Pilar",
            sector="Educacion y formacion",
            persona_contacto="Fernando Navas",
            email="fnavas@grupoeducativopila.es",
            telefono="+34 91 678 90 12",
            linkedin="https://linkedin.com/company/grupoeducativopilar",
            youtube="https://youtube.com/@grupoeducativopilar",
            notas="Red de centros educativos. Buscan experiencias para el equipo docente.",
            activo=False,
        ),
    ]
    db.session.add_all(empresas)
    db.session.flush()

    tipo = TipoExperiencia.query.filter_by(activo=True).first()
    if tipo:
        hoy = datetime.utcnow()
        reservas_tb = [
            Reserva(
                empresa_id=empresas[0].id,
                tipo_experiencia_id=tipo.id,
                fecha_compra=hoy - timedelta(days=15),
                fecha_disfrute=hoy + timedelta(days=20),
                estado="reservado",
                precio=1200.0,
                num_participantes=20,
                nombre_grupo="Equipo Tech Innovatech",
                notas="Reserva grupal confirmada. 20 personas. Preferencia manana.",
            ),
            Reserva(
                empresa_id=empresas[1].id,
                tipo_experiencia_id=tipo.id,
                fecha_compra=hoy - timedelta(days=5),
                fecha_disfrute=hoy + timedelta(days=45),
                estado="pendiente",
                precio=800.0,
                num_participantes=12,
                nombre_grupo="Equipo de Obra Marvell",
                notas="Pendiente de confirmar fecha exacta.",
            ),
            Reserva(
                empresa_id=empresas[2].id,
                tipo_experiencia_id=tipo.id,
                fecha_compra=hoy - timedelta(days=30),
                fecha_disfrute=hoy - timedelta(days=2),
                estado="disfrutado",
                precio=600.0,
                num_participantes=10,
                nombre_grupo="Comercial Mediterranea",
                notas="Experiencia disfrutada. Muy satisfechos.",
            ),
        ]
        db.session.add_all(reservas_tb)

    db.session.commit()


def _seed_tags():
    """Inserts predefined marketing tags if the tags table is empty."""
    from app.models.tag import Tag

    if Tag.query.count() > 0:
        return

    tags = [
        # ── B2C Sistemáticas ──────────────────────────────────────
        Tag(slug="lead_particular_nuevo",   nombre="Lead particular nuevo",
            descripcion="Primer pedido creado en WooCommerce por un cliente particular.",
            tipo="sistematica", entidad="cliente", segmento="b2c",
            color="#3B82F6", icono="bi-person-plus-fill",
            trigger_evento="woo.order.created"),
        Tag(slug="carrito_abandonado",      nombre="Carrito abandonado",
            descripcion="El cliente inició el checkout pero no completó el pago.",
            tipo="sistematica", entidad="cliente", segmento="b2c",
            color="#F59E0B", icono="bi-cart-x-fill",
            trigger_evento="woo.cart.abandoned"),
        Tag(slug="experiencia_reservada",   nombre="Experiencia reservada",
            descripcion="El cliente tiene al menos una reserva en estado reservado.",
            tipo="sistematica", entidad="cliente", segmento="b2c",
            color="#10B981", icono="bi-calendar-check-fill",
            trigger_evento="woo.order.completed"),
        Tag(slug="experiencia_realizada",   nombre="Experiencia realizada",
            descripcion="El cliente ha disfrutado al menos una experiencia.",
            tipo="sistematica", entidad="cliente", segmento="b2c",
            color="#8B5CF6", icono="bi-trophy-fill",
            trigger_evento="crm.reserva.disfrutada"),
        Tag(slug="compro_para_regalo",      nombre="Compro para regalo",
            descripcion="El pedido WooCommerce fue marcado como regalo.",
            tipo="sistematica", entidad="cliente", segmento="b2c",
            color="#EC4899", icono="bi-gift-fill",
            trigger_evento="woo.order.gift"),
        # ── B2C Dinamicas ─────────────────────────────────────────
        Tag(slug="cliente_dormido_particular", nombre="Cliente dormido",
            descripcion="Sin reservas en los ultimos 180 dias habiendo tenido al menos una reserva historica.",
            tipo="dinamica", entidad="cliente", segmento="b2c",
            color="#6B7280", icono="bi-moon-fill",
            filtro_descripcion="Clientes con fecha_disfrute mas reciente > 180 dias y al menos 1 reserva completada"),
        Tag(slug="cliente_vip_particular",  nombre="Cliente VIP",
            descripcion="Ha realizado 3 o mas experiencias o ha gastado mas de 500 euros.",
            tipo="dinamica", entidad="cliente", segmento="b2c",
            color="#F59E0B", icono="bi-star-fill",
            filtro_descripcion="Clientes con reservas completadas >= 3 OR suma de precios >= 500"),
        Tag(slug="local_madrid",            nombre="Local Madrid",
            descripcion="Cliente con codigo postal de la Comunidad de Madrid.",
            tipo="dinamica", entidad="cliente", segmento="b2c",
            color="#EF4444", icono="bi-geo-alt-fill",
            filtro_descripcion="Clientes con codigo_postal LIKE 28xxx, 45xxx, 19xxx"),
        Tag(slug="cumpleanos_mes",          nombre="Cumpleanos este mes",
            descripcion="El cumpleanos del cliente cae en el mes en curso.",
            tipo="dinamica", entidad="cliente", segmento="b2c",
            color="#EC4899", icono="bi-balloon-fill",
            filtro_descripcion="strftime('%m', fecha_nacimiento) = strftime('%m', 'now')"),
        # ── B2B Sistematicas ──────────────────────────────────────
        Tag(slug="lead_empresa_nuevo",      nombre="Lead empresa nuevo",
            descripcion="Primera vez que una empresa contacta o descarga el dossier.",
            tipo="sistematica", entidad="empresa", segmento="b2b",
            color="#8B5CF6", icono="bi-buildings-fill",
            trigger_evento="crm.empresa.creada"),
        Tag(slug="descargo_dossier",        nombre="Descargo dossier",
            descripcion="La empresa descargo el dossier corporativo de TB.",
            tipo="sistematica", entidad="empresa", segmento="b2b",
            color="#6366F1", icono="bi-file-earmark-arrow-down-fill",
            trigger_evento="crm.empresa.dossier_descargado"),
        Tag(slug="identificado_como_empresa", nombre="Identificado como empresa",
            descripcion="Contacto cualificado como empresa B2B.",
            tipo="sistematica", entidad="empresa", segmento="b2b",
            color="#0EA5E9", icono="bi-briefcase-fill",
            trigger_evento="crm.empresa.cualificada"),
        Tag(slug="presupuesto_solicitado",  nombre="Presupuesto solicitado",
            descripcion="La empresa ha solicitado un presupuesto de evento.",
            tipo="sistematica", entidad="empresa", segmento="b2b",
            color="#F59E0B", icono="bi-receipt",
            trigger_evento="crm.empresa.presupuesto_solicitado"),
        Tag(slug="evento_empresa_realizado", nombre="Evento empresa realizado",
            descripcion="La empresa ha completado al menos un evento TB.",
            tipo="sistematica", entidad="empresa", segmento="b2b",
            color="#10B981", icono="bi-check-circle-fill",
            trigger_evento="crm.reserva.disfrutada"),
        # ── B2B Dinamicas ─────────────────────────────────────────
        Tag(slug="gran_cuenta_b2b",         nombre="Gran cuenta B2B",
            descripcion="Empresa con 50 o mas participantes historicos o 3+ eventos realizados.",
            tipo="dinamica", entidad="empresa", segmento="b2b",
            color="#8B5CF6", icono="bi-gem",
            filtro_descripcion="Empresas con suma(num_participantes) >= 50 OR reservas completadas >= 3"),
        Tag(slug="b2b_sin_contacto_3meses", nombre="B2B sin contacto 3 meses",
            descripcion="Empresa sin actividad en los ultimos 90 dias.",
            tipo="dinamica", entidad="empresa", segmento="b2b",
            color="#6B7280", icono="bi-clock-history",
            filtro_descripcion="Empresas con ultima reserva o actividad hace mas de 90 dias"),
        Tag(slug="recurrente_anual_b2b",    nombre="Recurrente anual B2B",
            descripcion="Empresa que ha realizado eventos en 2 o mas anos consecutivos.",
            tipo="dinamica", entidad="empresa", segmento="b2b",
            color="#10B981", icono="bi-arrow-repeat",
            filtro_descripcion="Empresas con reservas completadas en distintos anos >= 2"),
        Tag(slug="interesado_navidad_b2b",  nombre="Interesado navidad B2B",
            descripcion="Empresa que historicamente ha reservado en el Q4 (Oct-Dic).",
            tipo="dinamica", entidad="empresa", segmento="b2b",
            color="#EF4444", icono="bi-snow",
            filtro_descripcion="Empresas con al menos 1 reserva con fecha_disfrute en mes 10, 11 o 12"),
    ]
    db.session.add_all(tags)
    db.session.commit()


def _seed_plantillas():
    """Inserts example email templates if the table is empty."""
    from app.models.rule import PlantillaEmail

    if PlantillaEmail.query.count() > 0:
        return

    plantillas = [
        # ── B2C ───────────────────────────────────────────────────────────────
        PlantillaEmail(
            nombre="Bienvenida — Lead particular",
            asunto="Bienvenido/a a Feeling Experience, {{nombre}}",
            segmento="b2c",
            descripcion="Se envía cuando un cliente particular compra por primera vez en WooCommerce.",
            cuerpo_html="""<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;color:#111">
  <div style="background:#111;padding:24px 32px;border-radius:12px 12px 0 0;text-align:center">
    <h1 style="color:#fff;font-size:22px;margin:0">Feeling Experience</h1>
  </div>
  <div style="background:#f9f9f9;padding:32px">
    <h2 style="font-size:20px;margin-bottom:8px">Hola, {{nombre}} 👋</h2>
    <p>Gracias por tu primera compra. Ya tienes tu experiencia reservada y estamos deseando que la disfrutes.</p>
    <p>Si tienes cualquier duda o quieres cambiar la fecha, escríbenos a <a href="mailto:info@feelingexperience.es">info@feelingexperience.es</a> y te respondemos enseguida.</p>
    <div style="text-align:center;margin:32px 0">
      <a href="{{crm_url}}" style="background:#111;color:#fff;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:bold">
        Ver mis reservas
      </a>
    </div>
    <p style="font-size:13px;color:#666">¡Nos vemos pronto!</p>
    <p style="font-size:13px;color:#666">— El equipo de Feeling Experience</p>
  </div>
  <div style="background:#eee;padding:12px 32px;border-radius:0 0 12px 12px;text-align:center">
    <p style="font-size:11px;color:#999;margin:0">
      <a href="{{unsubscribe_url}}" style="color:#999">Darse de baja</a>
    </p>
  </div>
</div>""",
        ),
        PlantillaEmail(
            nombre="Carrito abandonado — Recuperación",
            asunto="{{nombre}}, te has dejado algo en el carrito 🛒",
            segmento="b2c",
            descripcion="Se envía 24h después de que el cliente abandone el checkout sin pagar.",
            cuerpo_html="""<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;color:#111">
  <div style="background:#111;padding:24px 32px;border-radius:12px 12px 0 0;text-align:center">
    <h1 style="color:#fff;font-size:22px;margin:0">Feeling Experience</h1>
  </div>
  <div style="background:#f9f9f9;padding:32px">
    <h2 style="font-size:20px;margin-bottom:8px">Hola {{nombre}},</h2>
    <p>Vimos que empezaste a reservar tu experiencia pero no llegaste a completar el pago. ¡Pasa pocas veces y lo entendemos!</p>
    <p>Tu experiencia todavía está disponible. Completa tu reserva ahora y disfruta de un <strong>5% de descuento</strong> usando el código:</p>
    <div style="text-align:center;margin:24px 0">
      <span style="background:#111;color:#fff;padding:10px 28px;border-radius:8px;font-size:20px;font-weight:bold;letter-spacing:4px">VUELVE5</span>
    </div>
    <div style="text-align:center;margin:24px 0">
      <a href="{{crm_url}}" style="background:#F59E0B;color:#fff;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:bold">
        Completar reserva
      </a>
    </div>
    <p style="font-size:12px;color:#999">El descuento caduca en 48h.</p>
  </div>
  <div style="background:#eee;padding:12px 32px;border-radius:0 0 12px 12px;text-align:center">
    <p style="font-size:11px;color:#999;margin:0"><a href="{{unsubscribe_url}}" style="color:#999">Darse de baja</a></p>
  </div>
</div>""",
        ),
        PlantillaEmail(
            nombre="Post-experiencia — Solicitar valoración",
            asunto="¿Qué te pareció? Cuéntanos tu experiencia, {{nombre}} ⭐",
            segmento="b2c",
            descripcion="Se envía 48h después de que la reserva pase a estado 'disfrutado'.",
            cuerpo_html="""<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;color:#111">
  <div style="background:#111;padding:24px 32px;border-radius:12px 12px 0 0;text-align:center">
    <h1 style="color:#fff;font-size:22px;margin:0">Feeling Experience</h1>
  </div>
  <div style="background:#f9f9f9;padding:32px">
    <h2 style="font-size:20px;margin-bottom:8px">¡Esperamos que lo hayas disfrutado, {{nombre}}! 🎉</h2>
    <p>Hace unos días viviste <strong>{{experiencia}}</strong> y nos encantaría saber qué te pareció.</p>
    <p>Tu opinión nos ayuda a mejorar y también ayuda a otros a decidirse. ¿Nos dejas una valoración?</p>
    <div style="text-align:center;margin:32px 0">
      <a href="{{crm_url}}" style="background:#8B5CF6;color:#fff;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:bold">
        Dejar valoración
      </a>
    </div>
    <p>Y si quieres repetir o regalar una experiencia, te tenemos cubierto/a 😊</p>
  </div>
  <div style="background:#eee;padding:12px 32px;border-radius:0 0 12px 12px;text-align:center">
    <p style="font-size:11px;color:#999;margin:0"><a href="{{unsubscribe_url}}" style="color:#999">Darse de baja</a></p>
  </div>
</div>""",
        ),
        PlantillaEmail(
            nombre="Reactivar cliente dormido",
            asunto="{{nombre}}, ¡te echamos de menos! 😊",
            segmento="b2c",
            descripcion="Se envía a clientes sin actividad en más de 180 días.",
            cuerpo_html="""<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;color:#111">
  <div style="background:#111;padding:24px 32px;border-radius:12px 12px 0 0;text-align:center">
    <h1 style="color:#fff;font-size:22px;margin:0">Feeling Experience</h1>
  </div>
  <div style="background:#f9f9f9;padding:32px">
    <h2 style="font-size:20px;margin-bottom:8px">Hola de nuevo, {{nombre}} 👋</h2>
    <p>Hace tiempo que no sabemos de ti y queremos que sepas que tenemos novedades que te pueden interesar.</p>
    <p>Hemos incorporado nuevas experiencias y hay fechas disponibles durante las próximas semanas.</p>
    <div style="text-align:center;margin:32px 0">
      <a href="{{crm_url}}" style="background:#6B7280;color:#fff;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:bold">
        Ver novedades
      </a>
    </div>
    <p style="font-size:13px;color:#666">Nos alegra tenerte de vuelta cuando quieras.</p>
  </div>
  <div style="background:#eee;padding:12px 32px;border-radius:0 0 12px 12px;text-align:center">
    <p style="font-size:11px;color:#999;margin:0"><a href="{{unsubscribe_url}}" style="color:#999">Darse de baja</a></p>
  </div>
</div>""",
        ),
        PlantillaEmail(
            nombre="Felicitación de cumpleaños",
            asunto="¡Feliz cumpleaños, {{nombre}}! 🎂 Un regalo para ti",
            segmento="b2c",
            descripcion="Se envía el día del cumpleaños del cliente con un código de descuento.",
            cuerpo_html="""<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;color:#111">
  <div style="background:#EC4899;padding:24px 32px;border-radius:12px 12px 0 0;text-align:center">
    <h1 style="color:#fff;font-size:26px;margin:0">🎂 ¡Feliz cumpleaños!</h1>
  </div>
  <div style="background:#f9f9f9;padding:32px;text-align:center">
    <h2 style="font-size:20px;margin-bottom:16px">{{nombre}}, hoy es tu día 🎉</h2>
    <p>En Feeling Experience queremos celebrarlo contigo. Aquí tienes tu regalo:</p>
    <div style="margin:24px 0">
      <span style="background:#EC4899;color:#fff;padding:10px 28px;border-radius:8px;font-size:22px;font-weight:bold;letter-spacing:4px">CUMPLE10</span>
    </div>
    <p style="font-size:13px;color:#666">10% de descuento en tu próxima reserva. Válido durante 30 días.</p>
    <div style="margin:24px 0">
      <a href="{{crm_url}}" style="background:#111;color:#fff;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:bold">
        Usar mi descuento
      </a>
    </div>
  </div>
  <div style="background:#eee;padding:12px 32px;border-radius:0 0 12px 12px;text-align:center">
    <p style="font-size:11px;color:#999;margin:0"><a href="{{unsubscribe_url}}" style="color:#999">Darse de baja</a></p>
  </div>
</div>""",
        ),
        # ── B2B ───────────────────────────────────────────────────────────────
        PlantillaEmail(
            nombre="Bienvenida empresa — Team Building",
            asunto="Bienvenidos a Feeling Experience, {{nombre}} 🏢",
            segmento="b2b",
            descripcion="Se envía cuando se da de alta una nueva empresa en el módulo Team Building.",
            cuerpo_html="""<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;color:#111">
  <div style="background:#111;padding:24px 32px;border-radius:12px 12px 0 0;text-align:center">
    <h1 style="color:#fff;font-size:22px;margin:0">Feeling Experience — Team Building</h1>
  </div>
  <div style="background:#f9f9f9;padding:32px">
    <h2 style="font-size:20px;margin-bottom:8px">Hola, {{nombre}},</h2>
    <p>Muchas gracias por vuestro interés en nuestros eventos de Team Building. Es un placer teneros como contacto.</p>
    <p>Os adjuntamos nuestro dossier corporativo con todas las actividades disponibles, capacidades y precios orientativos.</p>
    <p>Nuestro equipo comercial se pondrá en contacto con vosotros en breve para conocer vuestras necesidades y preparar una propuesta personalizada.</p>
    <div style="background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:20px;margin:24px 0">
      <p style="margin:0;font-size:13px;color:#666">
        <strong>Contacto directo:</strong><br>
        📧 teambuilding@feelingexperience.es<br>
        📞 +34 600 000 000
      </p>
    </div>
    <p style="font-size:13px;color:#666">Estamos a vuestra disposición para cualquier consulta.</p>
  </div>
  <div style="background:#eee;padding:12px 32px;border-radius:0 0 12px 12px;text-align:center">
    <p style="font-size:11px;color:#999;margin:0"><a href="{{unsubscribe_url}}" style="color:#999">Darse de baja</a></p>
  </div>
</div>""",
        ),
        PlantillaEmail(
            nombre="Follow-up presupuesto B2B",
            asunto="{{nombre}}, ¿pudisteis revisar la propuesta?",
            segmento="b2b",
            descripcion="Se envía 72h después de enviar un presupuesto si no hay respuesta.",
            cuerpo_html="""<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;color:#111">
  <div style="background:#111;padding:24px 32px;border-radius:12px 12px 0 0;text-align:center">
    <h1 style="color:#fff;font-size:22px;margin:0">Feeling Experience — Team Building</h1>
  </div>
  <div style="background:#f9f9f9;padding:32px">
    <h2 style="font-size:20px;margin-bottom:8px">Hola, {{nombre}},</h2>
    <p>Hace unos días os enviamos una propuesta para vuestro evento de Team Building y queríamos saber si habéis tenido oportunidad de revisarla.</p>
    <p>Estamos disponibles para resolver cualquier duda, ajustar fechas o modificar el programa según vuestras necesidades.</p>
    <div style="text-align:center;margin:32px 0">
      <a href="mailto:teambuilding@feelingexperience.es" style="background:#F59E0B;color:#fff;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:bold">
        Responder por email
      </a>
    </div>
    <p style="font-size:13px;color:#666">Si no es el momento adecuado, no os preocupéis. Quedamos a vuestra disposición.</p>
  </div>
  <div style="background:#eee;padding:12px 32px;border-radius:0 0 12px 12px;text-align:center">
    <p style="font-size:11px;color:#999;margin:0"><a href="{{unsubscribe_url}}" style="color:#999">Darse de baja</a></p>
  </div>
</div>""",
        ),
        PlantillaEmail(
            nombre="Campaña navidad B2B — Propuesta Q4",
            asunto="{{nombre}}, ¿ya tenéis plan para el evento de fin de año? 🎄",
            segmento="b2b",
            descripcion="Campaña de septiembre para empresas que históricamente reservan en Q4.",
            cuerpo_html="""<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;color:#111">
  <div style="background:#EF4444;padding:24px 32px;border-radius:12px 12px 0 0;text-align:center">
    <h1 style="color:#fff;font-size:22px;margin:0">🎄 Eventos de fin de año — Feeling Experience</h1>
  </div>
  <div style="background:#f9f9f9;padding:32px">
    <h2 style="font-size:20px;margin-bottom:8px">Hola, {{nombre}},</h2>
    <p>Se acerca el cuarto trimestre y sabemos que muchas empresas empiezan a planificar sus eventos de fin de año. ¡Queríamos ser los primeros en contactaros!</p>
    <p>Este año tenemos propuestas especiales para grupos de empresa en octubre, noviembre y diciembre, con disponibilidad limitada.</p>
    <ul style="padding-left:20px;color:#444;line-height:2">
      <li>Actividades outdoor e indoor adaptadas a cualquier grupo</li>
      <li>Precios especiales para reservas antes del 30 de septiembre</li>
      <li>Flexibilidad total en fechas y número de participantes</li>
    </ul>
    <div style="text-align:center;margin:32px 0">
      <a href="mailto:teambuilding@feelingexperience.es" style="background:#EF4444;color:#fff;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:bold">
        Solicitar propuesta Q4
      </a>
    </div>
  </div>
  <div style="background:#eee;padding:12px 32px;border-radius:0 0 12px 12px;text-align:center">
    <p style="font-size:11px;color:#999;margin:0"><a href="{{unsubscribe_url}}" style="color:#999">Darse de baja</a></p>
  </div>
</div>""",
        ),
    ]
    db.session.add_all(plantillas)
    db.session.commit()


def _seed_normas():
    """Inserts example automation rules with multi-action support."""
    from app.models.tag import Tag
    from app.models.rule import PlantillaEmail, Rule, RuleTag, RuleAccion

    # Skip only when fully seeded (rules + acciones both present)
    if Rule.query.count() > 0 and RuleAccion.query.count() > 0:
        return
    # Always wipe rule_tags + rules before re-seeding to handle:
    #   - old single-action structure (rules exist, no acciones)
    #   - orphaned rule_tags from a crashed partial run
    # synchronize_session=False skips session-map sync for bulk deletes
    RuleTag.query.delete(synchronize_session=False)
    Rule.query.delete(synchronize_session=False)
    db.session.commit()

    def tag(slug):
        return Tag.query.filter_by(slug=slug).first()

    def pid(nombre):
        p = PlantillaEmail.query.filter_by(nombre=nombre).first()
        return p.id if p else None

    normas = [
        # ── B2C ───────────────────────────────────────────────────────────────
        {
            "rule": Rule(
                nombre="Bienvenida lead particular",
                descripcion="Email de bienvenida + WhatsApp de confirmación al recibir el primer pedido.",
                segmento="b2c", entidad="cliente", delay_horas=0,
            ),
            "req": ["lead_particular_nuevo"], "exc": [],
            "acciones": [
                {"tipo": "email",     "plantilla": "Bienvenida — Lead particular"},
                {"tipo": "whatsapp",  "msg_wa":    "Hola {{nombre}}, bienvenido/a a Feeling Experience! Ya tienes tu experiencia reservada. Cualquier duda estamos aqui 🎉"},
            ],
        },
        {
            "rule": Rule(
                nombre="Recuperar carrito abandonado",
                descripcion="Email + llamada de seguimiento 24h después de un carrito sin pagar.",
                segmento="b2c", entidad="cliente", delay_horas=24,
            ),
            "req": ["carrito_abandonado"], "exc": ["experiencia_reservada"],
            "acciones": [
                {"tipo": "email",         "plantilla":    "Carrito abandonado — Recuperación"},
                {"tipo": "notificacion",  "msg_notif":    "Llamar al cliente para recordar la reserva pendiente en el carrito."},
            ],
        },
        {
            "rule": Rule(
                nombre="Solicitar valoración post-experiencia",
                descripcion="Email de valoración + WhatsApp 48h después de disfrutar la experiencia.",
                segmento="b2c", entidad="cliente", delay_horas=48,
            ),
            "req": ["experiencia_realizada"], "exc": [],
            "acciones": [
                {"tipo": "email",    "plantilla": "Post-experiencia — Solicitar valoración"},
                {"tipo": "whatsapp", "msg_wa":    "Hola {{nombre}}! Esperamos que hayas disfrutado tu experiencia. Nos dejarias una valoracion? Significa mucho para nosotros 🌟"},
            ],
        },
        {
            "rule": Rule(
                nombre="Reactivar cliente dormido",
                descripcion="Email de reactivación + notificación interna para clientes sin actividad en 6 meses.",
                segmento="b2c", entidad="cliente", delay_horas=0,
            ),
            "req": ["cliente_dormido_particular"], "exc": ["experiencia_reservada"],
            "acciones": [
                {"tipo": "email",        "plantilla":   "Reactivar cliente dormido"},
                {"tipo": "notificacion", "msg_notif":   "Cliente sin actividad 6+ meses. Llamar para ofrecer novedad o descuento especial."},
            ],
        },
        {
            "rule": Rule(
                nombre="Felicitación de cumpleaños",
                descripcion="Email con descuento + WhatsApp de felicitación el día del cumpleaños.",
                segmento="b2c", entidad="cliente", delay_horas=0,
            ),
            "req": ["cumpleanos_mes"], "exc": [],
            "acciones": [
                {"tipo": "email",    "plantilla": "Felicitación de cumpleaños"},
                {"tipo": "whatsapp", "msg_wa":    "Feliz cumpleanos, {{nombre}}! 🎂 En Feeling Experience te tenemos un regalo especial. Mira tu email!"},
            ],
        },
        {
            "rule": Rule(
                nombre="Cliente VIP — activar protocolo",
                descripcion="Notificación interna + email exclusivo cuando un cliente alcanza nivel VIP.",
                segmento="b2c", entidad="cliente", delay_horas=0,
            ),
            "req": ["cliente_vip_particular"], "exc": [],
            "acciones": [
                {"tipo": "notificacion", "msg_notif":  "Cliente ha alcanzado nivel VIP. Llamar para ofrecer acceso exclusivo y experiencias premium."},
                {"tipo": "whatsapp",     "msg_wa":     "Hola {{nombre}}, nos complace informarte de que ya eres cliente VIP de Feeling Experience! Pronto te contactamos con ventajas exclusivas 🏆"},
            ],
        },
        # ── B2B ───────────────────────────────────────────────────────────────
        {
            "rule": Rule(
                nombre="Bienvenida empresa Team Building",
                descripcion="Email con dossier corporativo + llamada comercial al crear una empresa.",
                segmento="b2b", entidad="empresa", delay_horas=1,
            ),
            "req": ["lead_empresa_nuevo"], "exc": [],
            "acciones": [
                {"tipo": "email",        "plantilla":  "Bienvenida empresa — Team Building"},
                {"tipo": "notificacion", "msg_notif":  "Nueva empresa dada de alta. Llamar en las próximas 24h para presentar la oferta TB y resolver dudas."},
            ],
        },
        {
            "rule": Rule(
                nombre="Follow-up presupuesto B2B",
                descripcion="Email de seguimiento + llamada + WhatsApp 72h después de enviar presupuesto.",
                segmento="b2b", entidad="empresa", delay_horas=72,
            ),
            "req": ["presupuesto_solicitado"], "exc": ["evento_empresa_realizado"],
            "acciones": [
                {"tipo": "email",        "plantilla":  "Follow-up presupuesto B2B"},
                {"tipo": "notificacion", "msg_notif":  "Empresa con presupuesto enviado sin respuesta en 72h. Llamar para hacer seguimiento comercial."},
                {"tipo": "whatsapp",     "msg_wa":     "Hola {{nombre}}, os enviamos la propuesta hace unos dias. Estamos disponibles para resolver cualquier duda o ajustar el programa. Un saludo!"},
            ],
        },
        {
            "rule": Rule(
                nombre="Reactivar empresa B2B inactiva",
                descripcion="Notificación + WhatsApp para empresas sin contacto en 3 meses.",
                segmento="b2b", entidad="empresa", delay_horas=0,
            ),
            "req": ["b2b_sin_contacto_3meses"], "exc": ["presupuesto_solicitado"],
            "acciones": [
                {"tipo": "notificacion", "msg_notif":  "Empresa sin contacto en 3+ meses. Llamar para reactivar relación y presentar novedades."},
                {"tipo": "whatsapp",     "msg_wa":     "Hola {{nombre}}, hace tiempo que no sabemos de vosotros. Tenemos novedades en nuestros eventos TB que pueden interesaros. Os llamamos esta semana?"},
            ],
        },
        {
            "rule": Rule(
                nombre="Campaña navidad B2B",
                descripcion="Email Q4 + WhatsApp + llamada a empresas que reservaron en Q4 años anteriores.",
                segmento="b2b", entidad="empresa", delay_horas=0,
            ),
            "req": ["interesado_navidad_b2b"], "exc": [],
            "acciones": [
                {"tipo": "email",        "plantilla":  "Campaña navidad B2B — Propuesta Q4"},
                {"tipo": "whatsapp",     "msg_wa":     "Hola {{nombre}}! Se acerca fin de ano y ya tenemos nuestras propuestas para eventos de empresa. Reservad pronto, las fechas se agotan rapido 🎄"},
                {"tipo": "notificacion", "msg_notif":  "Empresa con histórico de reservas Q4. Llamar para confirmar interés en la campaña navidad y reservar fecha."},
            ],
        },
    ]

    # Pre-resolve all plantilla IDs before entering the loop to avoid
    # autoflush collisions (SQLAlchemy flushes pending RuleTags when a
    # query runs inside the same session).
    for item in normas:
        for acc in item["acciones"]:
            if acc.get("plantilla"):
                acc["_pid"] = pid(acc["plantilla"])

    with db.session.no_autoflush:
        for item in normas:
            rule = item["rule"]
            db.session.add(rule)
            db.session.flush()
            for slug in item["req"]:
                t = tag(slug)
                if t:
                    db.session.add(RuleTag(rule_id=rule.id, tag_id=t.id, tipo="requerida"))
            for slug in item["exc"]:
                t = tag(slug)
                if t:
                    db.session.add(RuleTag(rule_id=rule.id, tag_id=t.id, tipo="excluida"))
            for orden, acc in enumerate(item["acciones"]):
                db.session.add(RuleAccion(
                    rule_id=rule.id,
                    tipo=acc["tipo"],
                    plantilla_id=acc.get("_pid"),
                    mensaje_whatsapp=acc.get("msg_wa"),
                    mensaje_notificacion=acc.get("msg_notif"),
                    orden=orden,
                ))

    db.session.commit()


def _seed_notificaciones():
    """Inserts example internal notifications if the table is empty."""
    from datetime import datetime, timedelta
    from app.models.rule import Notificacion, Rule

    if Notificacion.query.count() > 0:
        return

    hoy = datetime.utcnow()

    def rule_id(nombre):
        r = Rule.query.filter_by(nombre=nombre).first()
        return r.id if r else None

    notifs = [
        Notificacion(
            titulo="Llamar a Innovatech Solutions — presupuesto pendiente",
            mensaje="Enviamos propuesta TB hace 4 días sin respuesta. Llamar al contacto Elena Castillo para hacer seguimiento.",
            tipo="llamada", prioridad="alta",
            entidad="empresa", entidad_nombre="Innovatech Solutions",
            rule_id=rule_id("Follow-up presupuesto B2B"),
            resuelta=False,
            creado_en=hoy - timedelta(hours=2),
        ),
        Notificacion(
            titulo="Cliente VIP detectado — Carlos García",
            mensaje="Carlos García ha alcanzado nivel VIP (3+ experiencias, gasto > 500€). Llamar para ofrecer acceso exclusivo y experiencias premium.",
            tipo="llamada", prioridad="alta",
            entidad="cliente", entidad_nombre="Carlos García López",
            rule_id=rule_id("Cliente VIP — activar protocolo"),
            resuelta=False,
            creado_en=hoy - timedelta(hours=5),
        ),
        Notificacion(
            titulo="Nueva empresa — Distribuidora Mediterránea",
            mensaje="Empresa dada de alta hace 1h. Llamar en las próximas 24h para presentar la oferta TB y resolver dudas.",
            tipo="recordatorio", prioridad="media",
            entidad="empresa", entidad_nombre="Distribuidora Mediterránea SL",
            rule_id=rule_id("Bienvenida empresa Team Building"),
            resuelta=False,
            creado_en=hoy - timedelta(hours=1),
        ),
        Notificacion(
            titulo="Cliente dormido — María Fernández",
            mensaje="Sin actividad desde hace 7 meses. Se envió email de reactivación automáticamente. Llamar si no hay respuesta en 48h.",
            tipo="recordatorio", prioridad="baja",
            entidad="cliente", entidad_nombre="María Fernández Ruiz",
            rule_id=rule_id("Reactivar cliente dormido"),
            resuelta=False,
            creado_en=hoy - timedelta(days=1),
        ),
        Notificacion(
            titulo="Carrito abandonado — Ana Jiménez",
            mensaje="Ana inició el checkout para una experiencia hace 26h sin completar el pago. Llamar para ofrecer ayuda o código de descuento.",
            tipo="llamada", prioridad="media",
            entidad="cliente", entidad_nombre="Ana Jiménez Morales",
            rule_id=rule_id("Recuperar carrito abandonado"),
            resuelta=False,
            creado_en=hoy - timedelta(hours=26),
        ),
        Notificacion(
            titulo="Grupo Educativo Pilar — inactiva 3 meses",
            mensaje="Empresa B2B sin contacto desde hace 95 días. Llamar para reactivar relación y presentar novedades de temporada.",
            tipo="llamada", prioridad="media",
            entidad="empresa", entidad_nombre="Grupo Educativo Pilar",
            rule_id=rule_id("Reactivar empresa B2B inactiva"),
            resuelta=True,
            creado_en=hoy - timedelta(days=3),
            resuelta_en=hoy - timedelta(hours=4),
        ),
    ]
    db.session.add_all(notifs)
    db.session.commit()


def _seed_plantillas_wa():
    """Inserts example WhatsApp templates if the table is empty."""
    from app.models.campana import PlantillaWA

    if PlantillaWA.query.count() > 0:
        return

    plantillas = [
        PlantillaWA(
            nombre="Bienvenida cliente B2C",
            descripcion="Mensaje de bienvenida automático tras la primera reserva.",
            cuerpo=(
                "Hola {{nombre}} 👋\n\n"
                "¡Bienvenido/a a *Feeling Experience*! 🎉\n\n"
                "Ya tienes tu experiencia confirmada. Estamos deseando que la disfrutes.\n\n"
                "Si necesitas cambiar algo o tienes cualquier duda, escríbenos aquí mismo o llámanos. "
                "Estamos a tu disposición.\n\n"
                "_¡Hasta pronto!_ 🚀"
            ),
            activo=True,
        ),
        PlantillaWA(
            nombre="Recordatorio de experiencia — 48h antes",
            descripcion="Recordatorio enviado 2 días antes de la fecha de disfrute.",
            cuerpo=(
                "Hola {{nombre}} 😊\n\n"
                "Te recordamos que *pasado mañana* disfrutas de tu experiencia con nosotros.\n\n"
                "📅 Fecha: {{fecha_disfrute}}\n"
                "📍 Lugar: Feeling Experience, Madrid\n\n"
                "Si tienes alguna duda de última hora, aquí estamos. "
                "¡Nos vemos pronto! 🏁"
            ),
            activo=True,
        ),
        PlantillaWA(
            nombre="Follow-up post-experiencia",
            descripcion="Mensaje de agradecimiento y solicitud de valoración tras disfrutar la experiencia.",
            cuerpo=(
                "Hola {{nombre}} 🌟\n\n"
                "Esperamos que hayas disfrutado muchísimo tu experiencia con *Feeling Experience*.\n\n"
                "Nos encantaría saber qué te pareció. "
                "¿Nos dejas una valoración rápida? Significa mucho para nosotros y ayuda a otros a decidirse 🙏\n\n"
                "Y si quieres repetir o regalar una experiencia, ya sabes dónde encontrarnos 😉\n\n"
                "_¡Gracias por confiar en nosotros!_"
            ),
            activo=True,
        ),
        PlantillaWA(
            nombre="Bienvenida empresa B2B",
            descripcion="Primer contacto con una empresa nueva interesada en Team Building.",
            cuerpo=(
                "Hola {{nombre}} 🏢\n\n"
                "Gracias por vuestro interés en nuestros eventos de *Team Building*.\n\n"
                "Os acabo de enviar un email con nuestro dossier corporativo y toda la información. "
                "En breve nos ponemos en contacto para conocer vuestras necesidades y prepararos una propuesta personalizada.\n\n"
                "Cualquier cosa, estamos aquí. ¡Un saludo!"
            ),
            activo=True,
        ),
        PlantillaWA(
            nombre="Oferta especial campaña",
            descripcion="Plantilla genérica para campañas con oferta o descuento.",
            cuerpo=(
                "Hola {{nombre}} 🎁\n\n"
                "Tenemos algo especial para ti en *Feeling Experience*.\n\n"
                "{{mensaje_campana}}\n\n"
                "¿Te interesa? Escríbenos y te damos todos los detalles. "
                "Las plazas son limitadas 🏎️\n\n"
                "_¡Hasta pronto!_"
            ),
            activo=True,
        ),
    ]
    db.session.add_all(plantillas)
    db.session.commit()


def _seed_campanas():
    """Inserts example campaigns if the table is empty."""
    from datetime import datetime, timedelta
    from app.models.campana import Campana, CampanaTag
    from app.models.tag import Tag
    from app.models.rule import PlantillaEmail

    if Campana.query.count() > 0:
        return

    hoy = datetime.utcnow()

    def tag_id(slug):
        t = Tag.query.filter_by(slug=slug).first()
        return t.id if t else None

    def plantilla_id(nombre):
        p = PlantillaEmail.query.filter_by(nombre=nombre).first()
        return p.id if p else None

    campanas = [
        {
            "campana": Campana(
                nombre="Campaña navidad B2B 2024",
                descripcion="Email + WhatsApp a empresas que reservaron en Q4 años anteriores para ofrecerles propuesta de fin de año.",
                canal="ambos",
                segmento="empresa",
                plantilla_email_id=plantilla_id("Campaña navidad B2B — Propuesta Q4"),
                fecha_envio=hoy + timedelta(days=3),
                estado="programada",
            ),
            "incluir": ["interesado_navidad_b2b", "recurrente_anual_b2b"],
            "excluir": [],
        },
        {
            "campana": Campana(
                nombre="Reactivación clientes dormidos — Junio",
                descripcion="Campaña de email para recuperar clientes B2C que no han hecho reservas en más de 6 meses.",
                canal="email",
                segmento="cliente",
                plantilla_email_id=plantilla_id("Reactivar cliente dormido"),
                fecha_envio=None,
                estado="borrador",
            ),
            "incluir": ["cliente_dormido_particular"],
            "excluir": ["experiencia_reservada"],
        },
        {
            "campana": Campana(
                nombre="Bienvenida masiva leads nuevos",
                descripcion="Email de bienvenida para todos los leads particulares que todavía no han disfrutado ninguna experiencia.",
                canal="email",
                segmento="cliente",
                plantilla_email_id=plantilla_id("Bienvenida — Lead particular"),
                fecha_envio=hoy - timedelta(days=10),
                estado="enviada",
                enviado_en=hoy - timedelta(days=10),
                total_enviados=48,
                total_errores=2,
            ),
            "incluir": ["lead_particular_nuevo"],
            "excluir": ["experiencia_realizada"],
        },
    ]

    with db.session.no_autoflush:
        for item in campanas:
            c = item["campana"]
            db.session.add(c)
            db.session.flush()
            for slug in item["incluir"]:
                tid = tag_id(slug)
                if tid:
                    db.session.add(CampanaTag(campana_id=c.id, tag_id=tid, modo="incluir"))
            for slug in item["excluir"]:
                tid = tag_id(slug)
                if tid:
                    db.session.add(CampanaTag(campana_id=c.id, tag_id=tid, modo="excluir"))

    db.session.commit()


def _seed_marketing_logs_ejemplo():
    """Inserts example marketing log entries linked to existing clients/companies."""
    from datetime import datetime, timedelta
    from app.models.marketing_log import MarketingLog
    from app.models.cliente import Cliente
    from app.models.empresa import Empresa
    from app.models.campana import Campana

    if MarketingLog.query.count() > 0:
        return

    hoy = datetime.utcnow()

    # Tomamos los primeros clientes y empresas que existan
    clientes = Cliente.query.order_by(Cliente.id).limit(4).all()
    empresas = Empresa.query.order_by(Empresa.id).limit(3).all()
    campana_enviada = Campana.query.filter_by(estado="enviada").first()
    campana_prog    = Campana.query.filter_by(estado="programada").first()

    logs = []

    # ── Logs de clientes ──────────────────────────────────────────────
    if clientes:
        c0 = clientes[0]
        logs += [
            MarketingLog(
                evento="tag_asignada", resultado="ok",
                entidad="cliente", entidad_id=c0.id, entidad_nombre=c0.nombre_completo,
                tag_nombre="Lead particular nuevo", origen="automatico",
                detalle="Etiqueta asignada automáticamente al crear el cliente.",
                fecha=hoy - timedelta(days=30),
            ),
            MarketingLog(
                evento="accion_email", resultado="ok",
                entidad="cliente", entidad_id=c0.id, entidad_nombre=c0.nombre_completo,
                accion_tipo="email", rule_nombre="Bienvenida lead particular",
                detalle="Email de bienvenida enviado correctamente.",
                fecha=hoy - timedelta(days=30, hours=1),
            ),
            MarketingLog(
                evento="accion_whatsapp", resultado="ok",
                entidad="cliente", entidad_id=c0.id, entidad_nombre=c0.nombre_completo,
                accion_tipo="whatsapp", rule_nombre="Bienvenida lead particular",
                detalle="WhatsApp de bienvenida enviado.",
                fecha=hoy - timedelta(days=30, hours=1),
            ),
        ]

    if len(clientes) > 1:
        c1 = clientes[1]
        logs += [
            MarketingLog(
                evento="tag_asignada", resultado="ok",
                entidad="cliente", entidad_id=c1.id, entidad_nombre=c1.nombre_completo,
                tag_nombre="Experiencia realizada", origen="automatico",
                detalle="Etiqueta asignada tras marcar reserva como disfrutada.",
                fecha=hoy - timedelta(days=15),
            ),
            MarketingLog(
                evento="accion_email", resultado="ok",
                entidad="cliente", entidad_id=c1.id, entidad_nombre=c1.nombre_completo,
                accion_tipo="email", rule_nombre="Solicitar valoración post-experiencia",
                detalle="Email de valoración enviado 48h después de disfrutar la experiencia.",
                fecha=hoy - timedelta(days=13),
            ),
            MarketingLog(
                evento="accion_whatsapp", resultado="ok",
                entidad="cliente", entidad_id=c1.id, entidad_nombre=c1.nombre_completo,
                accion_tipo="whatsapp", rule_nombre="Solicitar valoración post-experiencia",
                detalle="WhatsApp de solicitud de valoración enviado.",
                fecha=hoy - timedelta(days=13),
            ),
        ]

    if len(clientes) > 2:
        c2 = clientes[2]
        logs += [
            MarketingLog(
                evento="tag_asignada", resultado="ok",
                entidad="cliente", entidad_id=c2.id, entidad_nombre=c2.nombre_completo,
                tag_nombre="Carrito abandonado", origen="automatico",
                detalle="Etiqueta asignada automáticamente al detectar checkout sin pago.",
                fecha=hoy - timedelta(days=5),
            ),
            MarketingLog(
                evento="accion_email", resultado="ok",
                entidad="cliente", entidad_id=c2.id, entidad_nombre=c2.nombre_completo,
                accion_tipo="email", rule_nombre="Recuperar carrito abandonado",
                detalle="Email de recuperación de carrito enviado con código VUELVE5.",
                fecha=hoy - timedelta(days=4),
            ),
            MarketingLog(
                evento="notificacion_creada", resultado="ok",
                entidad="cliente", entidad_id=c2.id, entidad_nombre=c2.nombre_completo,
                rule_nombre="Recuperar carrito abandonado",
                detalle="Notificación interna: llamar al cliente para recordar la reserva pendiente.",
                fecha=hoy - timedelta(days=4),
            ),
        ]

    if len(clientes) > 3 and campana_enviada:
        c3 = clientes[3]
        logs += [
            MarketingLog(
                evento="campana_email_ok", resultado="ok",
                entidad="cliente", entidad_id=c3.id, entidad_nombre=c3.nombre_completo,
                accion_tipo="email",
                campana_id=campana_enviada.id, campana_nombre=campana_enviada.nombre,
                detalle=f"Email enviado en campaña '{campana_enviada.nombre}'.",
                fecha=hoy - timedelta(days=10),
            ),
        ]

    # ── Logs de empresas ──────────────────────────────────────────────
    if empresas:
        e0 = empresas[0]
        logs += [
            MarketingLog(
                evento="tag_asignada", resultado="ok",
                entidad="empresa", entidad_id=e0.id, entidad_nombre=e0.nombre,
                tag_nombre="Lead empresa nuevo", origen="automatico",
                detalle="Etiqueta asignada automáticamente al crear la empresa.",
                fecha=hoy - timedelta(days=20),
            ),
            MarketingLog(
                evento="accion_email", resultado="ok",
                entidad="empresa", entidad_id=e0.id, entidad_nombre=e0.nombre,
                accion_tipo="email", rule_nombre="Bienvenida empresa Team Building",
                detalle="Email de bienvenida con dossier corporativo enviado.",
                fecha=hoy - timedelta(days=20, hours=1),
            ),
            MarketingLog(
                evento="notificacion_creada", resultado="ok",
                entidad="empresa", entidad_id=e0.id, entidad_nombre=e0.nombre,
                rule_nombre="Bienvenida empresa Team Building",
                detalle="Notificación: llamar en las próximas 24h para presentar oferta TB.",
                fecha=hoy - timedelta(days=20, hours=1),
            ),
            MarketingLog(
                evento="accion_email", resultado="ok",
                entidad="empresa", entidad_id=e0.id, entidad_nombre=e0.nombre,
                accion_tipo="email", rule_nombre="Follow-up presupuesto B2B",
                detalle="Email de seguimiento enviado 72h después del presupuesto sin respuesta.",
                fecha=hoy - timedelta(days=5),
            ),
        ]

    if len(empresas) > 1 and campana_prog:
        e1 = empresas[1]
        logs += [
            MarketingLog(
                evento="campana_programada", resultado="ok",
                entidad="empresa", entidad_id=e1.id, entidad_nombre=e1.nombre,
                campana_id=campana_prog.id, campana_nombre=campana_prog.nombre,
                detalle=f"Empresa incluida en campaña programada '{campana_prog.nombre}'.",
                fecha=hoy - timedelta(hours=2),
            ),
        ]

    if len(empresas) > 2:
        e2 = empresas[2]
        logs += [
            MarketingLog(
                evento="tag_asignada", resultado="ok",
                entidad="empresa", entidad_id=e2.id, entidad_nombre=e2.nombre,
                tag_nombre="Evento empresa realizado", origen="automatico",
                detalle="Etiqueta asignada al marcar reserva grupal como disfrutada.",
                fecha=hoy - timedelta(days=3),
            ),
            MarketingLog(
                evento="accion_whatsapp", resultado="ok",
                entidad="empresa", entidad_id=e2.id, entidad_nombre=e2.nombre,
                accion_tipo="whatsapp", rule_nombre="Solicitar valoración post-experiencia",
                detalle="WhatsApp de agradecimiento y valoración enviado a la empresa.",
                fecha=hoy - timedelta(days=3, hours=2),
            ),
        ]

    if logs:
        db.session.add_all(logs)
        db.session.commit()


def _seed_empresa_notas():
    from datetime import datetime, timedelta
    from app.models.empresa import Empresa
    from app.models.empresa_nota import EmpresaNota

    # Solo skip si ya hay notas de seed (contenido específico)
    if EmpresaNota.query.filter(EmpresaNota.contenido.ilike("%Elena Castillo%")).first():
        return

    empresas = Empresa.query.order_by(Empresa.id).limit(4).all()
    if not empresas:
        return

    hoy = datetime.utcnow()
    notas = []

    if len(empresas) > 0:
        e = empresas[0]
        notas += [
            EmpresaNota(empresa_id=e.id, usuario_nombre="Admin",
                        creado_en=hoy - timedelta(days=18),
                        contenido="Primera llamada con Elena Castillo. Muy receptiva. Buscan algo al aire libre para 20 personas en primavera. Piden presupuesto para experiencia de día completo."),
            EmpresaNota(empresa_id=e.id, usuario_nombre="Admin",
                        creado_en=hoy - timedelta(days=12),
                        contenido="Enviado dossier con 3 opciones: senderismo+picnic, escape room outdoor y taller de cocina. Elena prefiere la opción outdoor. Pendiente de confirmar fecha exacta."),
            EmpresaNota(empresa_id=e.id, usuario_nombre="Admin",
                        creado_en=hoy - timedelta(days=3),
                        contenido="Llamada de seguimiento. Confirman 22 personas (2 más de lo previsto). En la próxima llamada darles precio cerrado para 22 pax y opciones de transporte desde Madrid."),
        ]

    if len(empresas) > 1:
        e = empresas[1]
        notas += [
            EmpresaNota(empresa_id=e.id, usuario_nombre="Admin",
                        creado_en=hoy - timedelta(days=30),
                        contenido="Contacto inicial por formulario web. Ricardo Fuentes (RRHH) quiere algo para el equipo de obra — actividad física, nada de salas. Anotado para propuesta outdoor."),
            EmpresaNota(empresa_id=e.id, usuario_nombre="Admin",
                        creado_en=hoy - timedelta(days=10),
                        contenido="Reunión presencial. Presupuesto aprobado internamente pero necesitan factura antes del día 30 del mes. Verificar con administración si podemos adelantar la facturación."),
        ]

    if len(empresas) > 2:
        e = empresas[2]
        notas += [
            EmpresaNota(empresa_id=e.id, usuario_nombre="Admin",
                        creado_en=hoy - timedelta(days=45),
                        contenido="Primera toma de contacto con Susana Herrero. Evento anual de motivación para 40 personas. Tienen presupuesto de ~800€ por persona. Prefieren fin de semana."),
            EmpresaNota(empresa_id=e.id, usuario_nombre="Admin",
                        creado_en=hoy - timedelta(days=7),
                        contenido="Recordatorio: llamar a Susana esta semana para cerrar fechas de octubre. Tienen 2 opciones encima de la mesa. Importante no dejar pasar más de una semana o lo pierde la competencia."),
        ]

    if len(empresas) > 3:
        e = empresas[3]
        notas += [
            EmpresaNota(empresa_id=e.id, usuario_nombre="Admin",
                        creado_en=hoy - timedelta(days=60),
                        contenido="Grupo educativo con 6 centros. Fernando Navas (director de operaciones) interesado en experiencias para el claustro de profesores. Evento de team building antes de fin de curso."),
            EmpresaNota(empresa_id=e.id, usuario_nombre="Admin",
                        creado_en=hoy - timedelta(days=55),
                        contenido="Empresa marcada como inactiva porque no responde. Volver a intentar en septiembre cuando empiece el nuevo curso escolar."),
        ]

    if notas:
        db.session.add_all(notas)
        db.session.commit()
