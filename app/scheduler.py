"""
Tareas programadas con APScheduler.
Se inicializa una sola vez desde create_app().
"""
import atexit
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

log = logging.getLogger(__name__)

_scheduler = None


def get_scheduler():
    """Returns the running APScheduler instance, or None if not started."""
    return _scheduler


def init_scheduler(app):
    global _scheduler
    if _scheduler is not None:
        return  # ya iniciado (evita duplicados con Flask reloader)

    _scheduler = BackgroundScheduler(timezone="Europe/Madrid", daemon=True)

    _scheduler.add_job(
        func=lambda: _job_recordatorios(app),
        trigger=CronTrigger(hour=9, minute=0),
        id="recordatorios_auto",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    _scheduler.add_job(
        func=lambda: _job_seguro_recordatorio(app),
        trigger=CronTrigger(hour=9, minute=10),  # 09:10 — tras el job de recordatorios
        id="seguro_recordatorio",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    _scheduler.add_job(
        func=lambda: _job_temporal_tags(app),
        trigger=CronTrigger(hour=7, minute=0),
        id="temporal_tags_scan",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    _scheduler.add_job(
        func=lambda: _job_vip_criterio(app),
        trigger=CronTrigger(hour=7, minute=15),  # 07:15 — tras el job de temporales
        id="vip_criterio_scan",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    _scheduler.add_job(
        func=lambda: _job_aniversario(app),
        trigger=CronTrigger(hour=7, minute=30),  # 07:30 — tras VIP
        id="aniversario_scan",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    _scheduler.add_job(
        func=lambda: _job_gran_cuenta(app),
        trigger=CronTrigger(hour=7, minute=45),  # 07:45 — tras aniversario
        id="gran_cuenta_scan",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    _scheduler.add_job(
        func=lambda: _job_campanas(app),
        trigger=CronTrigger(minute="*/5"),  # cada 5 minutos
        id="campanas_scheduler",
        replace_existing=True,
        misfire_grace_time=300,
    )

    _scheduler.add_job(
        func=lambda: _job_plazo_inscripciones(app),
        trigger=CronTrigger(hour=8, minute=0),
        id="plazo_inscripciones",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    _scheduler.add_job(
        func=lambda: _job_plazo_eventos(app),
        trigger=CronTrigger(hour=8, minute=5),
        id="plazo_eventos_calendario",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    _scheduler.add_job(
        func=lambda: _job_woo_sync(app),
        trigger=IntervalTrigger(minutes=10),
        id="woo_sync_periodico",
        replace_existing=True,
        misfire_grace_time=300,
    )

    _scheduler.start()
    atexit.register(_scheduler.shutdown)

    # Ejecutar comprobaciones de plazos al arrancar sin esperar las 08:00
    import threading
    threading.Thread(target=lambda: _job_plazo_inscripciones(app), daemon=True).start()
    threading.Thread(target=lambda: _job_plazo_eventos(app), daemon=True).start()

    log.info("Scheduler iniciado — recordatorios 09:00, etiquetas temporales 07:00, plazos inscripciones 08:00, woo_sync cada 10 min")


def _job_recordatorios(app):
    """Envía recordatorio por email a las reservas que ocurren en las próximas 48 h."""
    with app.app_context():
        from app.extensions import db
        from app.models.reserva import Reserva
        from app.models.comunicacion import ComunicacionLog
        from app.services.email_service import enviar_recordatorio

        ahora  = datetime.utcnow()
        inicio = ahora + timedelta(hours=24)
        fin    = ahora + timedelta(hours=72)

        proximas = Reserva.query.filter(
            Reserva.fecha_disfrute >= inicio,
            Reserva.fecha_disfrute <= fin,
            Reserva.estado.in_(["reservado", "pendiente"]),
        ).all()

        enviados = 0
        for reserva in proximas:
            # No reenviar si ya hay un auto_recordatorio exitoso en las últimas 48 h
            ya_enviado = ComunicacionLog.query.filter_by(
                reserva_id=reserva.id,
                tipo="auto_recordatorio",
                ok=True,
            ).filter(
                ComunicacionLog.enviado_en >= ahora - timedelta(hours=48)
            ).first()

            if ya_enviado:
                continue

            try:
                ok = enviar_recordatorio(reserva)
                db.session.add(ComunicacionLog(
                    reserva_id=reserva.id,
                    tipo="auto_recordatorio",
                    canal="email",
                    ok=ok,
                    error="" if ok else "Error al enviar",
                ))
                db.session.commit()
                if ok:
                    enviados += 1
                    log.info(f"Recordatorio auto enviado → reserva #{reserva.id}")
            except Exception as e:
                db.session.rollback()
                log.error(f"Error en recordatorio auto reserva #{reserva.id}: {e}")

        log.info(f"Job recordatorios: {enviados}/{len(proximas)} enviados")


def _job_seguro_recordatorio(app):
    """Envía por email el enlace para rellenar los datos de seguro a las
    reservas que, teniendo ya fecha de disfrute, siguen sin esos datos y
    están a X días vista (configurable en Configuración general)."""
    with app.app_context():
        try:
            from datetime import date
            from app.extensions import db
            from app.models.reserva import Reserva
            from app.models.comunicacion import ComunicacionLog
            from app.models.configuracion import Configuracion
            from app.services.email_service import enviar_datos_seguro

            config = Configuracion.get()
            if not config.seguro_recordatorio_activo:
                return

            objetivo = date.today() + timedelta(days=config.seguro_recordatorio_dias)

            candidatas = Reserva.query.filter(
                Reserva.fecha_disfrute.isnot(None),
                db.func.date(Reserva.fecha_disfrute) == objetivo.isoformat(),
                Reserva.estado.in_(["reservado", "pendiente"]),
                Reserva.cliente_id.isnot(None),
            ).all()

            enviados = 0
            for reserva in candidatas:
                if reserva.tiene_datos_seguro:
                    continue

                ya_enviado = ComunicacionLog.query.filter_by(
                    reserva_id=reserva.id, tipo="seguro_recordatorio", ok=True,
                ).first()
                if ya_enviado:
                    continue

                try:
                    ok = enviar_datos_seguro(reserva)
                    db.session.add(ComunicacionLog(
                        reserva_id=reserva.id,
                        tipo="seguro_recordatorio",
                        canal="email",
                        ok=ok,
                        error="" if ok else "Error al enviar",
                    ))
                    db.session.commit()
                    if ok:
                        enviados += 1
                        log.info(f"Recordatorio de seguro enviado → reserva #{reserva.id}")
                except Exception as e:
                    db.session.rollback()
                    log.error(f"Error en recordatorio de seguro reserva #{reserva.id}: {e}")

            log.info(f"Job seguro_recordatorio: {enviados}/{len(candidatas)} enviados")
        except Exception as e:
            log.error(f"Error en job seguro_recordatorio: {e}")


def _job_vip_criterio(app):
    """Evalúa y sincroniza todos los tags con criterio VIP activos."""
    with app.app_context():
        try:
            from app.services.vip_criterio import evaluar_vip_criterio
            stats = evaluar_vip_criterio()
            log.info(f"Job vip_criterio: +{stats['asignadas']} VIP asignados, "
                     f"-{stats['quitadas']} retirados, {stats['errores']} errores")
        except Exception as e:
            log.error(f"Error en job vip_criterio: {e}")


def _job_gran_cuenta(app):
    """Evalúa y sincroniza etiquetas Gran Cuenta B2B con criterio configurable."""
    with app.app_context():
        try:
            from app.services.gran_cuenta_criterio import evaluar_gran_cuenta
            stats = evaluar_gran_cuenta()
            log.info(f"Job gran_cuenta: +{stats['asignadas']} asignadas, "
                     f"-{stats['quitadas']} retiradas, {stats['errores']} errores")
        except Exception as e:
            log.error(f"Error en job gran_cuenta: {e}")


def _job_aniversario(app):
    """Asigna/retira etiquetas de mes aniversario a clientes y empresas."""
    with app.app_context():
        try:
            from app.services.aniversario_tags import evaluar_aniversarios
            stats = evaluar_aniversarios()
            log.info(f"Job aniversario: +{stats['asignadas']} asignadas, "
                     f"-{stats['quitadas']} retiradas, {stats['errores']} errores")
        except Exception as e:
            log.error(f"Error en job aniversario: {e}")


def _job_woo_sync(app):
    """Red de seguridad para el webhook de WooCommerce: re-sincroniza los
    pedidos recientes cada pocos minutos por si algún webhook puntual no
    llegó (servidor caído, WooCommerce sin reintento, etc.). max_pages bajo
    porque solo necesita cubrir lo reciente, no un histórico completo."""
    with app.app_context():
        try:
            if not app.config.get("WOO_CONSUMER_KEY") or not app.config.get("WOO_CONSUMER_SECRET"):
                return  # integración WooCommerce no configurada en este entorno
            from app.services.woo_sync import sync_orders
            stats = sync_orders(max_pages=3)
            if stats["nuevas"] or stats["actualizadas"] or stats["errores"]:
                log.info(f"Job woo_sync: {stats['nuevas']} nuevas, "
                         f"{stats['actualizadas']} actualizadas, {stats['errores']} errores")
        except Exception as e:
            log.error(f"Error en job woo_sync: {e}")


def _job_campanas(app):
    """Lanza campañas programadas cuya fecha_envio ya ha llegado."""
    with app.app_context():
        try:
            from app.services.campana_service import check_scheduled_campaigns
            n = check_scheduled_campaigns()
            if n:
                log.info(f"Job campañas: {n} campaña(s) ejecutada(s)")
        except Exception as e:
            log.error(f"Error en job campañas: {e}")


def _job_temporal_tags(app):
    """Evalúa y sincroniza todas las etiquetas temporales activas."""
    with app.app_context():
        try:
            from app.services.temporal_tags import evaluar_tags_temporales
            stats = evaluar_tags_temporales()
            log.info(f"Job temporal_tags: +{stats['asignadas']} asignadas, "
                     f"-{stats['quitadas']} retiradas, {stats['errores']} errores")
        except Exception as e:
            log.error(f"Error en job temporal_tags: {e}")


def _job_plazo_eventos(app):
    """Notifica cuando faltan <= 10 días para el plazo de un evento sin inscripción creada."""
    with app.app_context():
        try:
            from datetime import date, timedelta
            from app.extensions import db
            from app.models.competicion_evento import CompeticionEvento
            from app.models.inscripcion import Inscripcion
            from app.models.notificacion import Notificacion

            hoy    = date.today()
            limite = hoy + timedelta(days=10)

            eventos = CompeticionEvento.query.filter(
                CompeticionEvento.fecha_plazo.isnot(None),
                CompeticionEvento.fecha_plazo >= hoy,
                CompeticionEvento.fecha_plazo <= limite,
            ).all()

            creadas = 0
            for ev in eventos:
                ref = f"plazo_evento_{ev.id}"
                if Notificacion.query.filter_by(referencia=ref, leida=False).first():
                    continue
                # Comprobar si ya existe una inscripción para la misma prueba
                # (la prueba puede durar varios días, así que se comprueba que
                # la fecha del evento caiga dentro del rango fecha_prueba..fecha_fin)
                ya_inscrito = Inscripcion.query.filter(
                    Inscripcion.fecha_prueba <= ev.fecha,
                    db.func.coalesce(Inscripcion.fecha_fin, Inscripcion.fecha_prueba) >= ev.fecha,
                ).first()
                if ya_inscrito:
                    continue  # Ya tiene inscripción, no notificar
                dias = (ev.fecha_plazo - hoy).days
                tipo = "danger" if dias <= 3 else "warning"
                db.session.add(Notificacion(
                    tipo=tipo,
                    titulo=f"Falta inscripción: {ev.titulo}",
                    mensaje=(f"Quedan {dias} día{'s' if dias != 1 else ''} para el plazo "
                             f"y todavía no se ha creado la inscripción para esta prueba "
                             f"({ev.fecha.strftime('%d/%m/%Y')})."),
                    url=f"/autoclub/calendario",
                    referencia=ref,
                ))
                creadas += 1

            db.session.commit()
            log.info(f"Job plazo_eventos: {creadas} notificación(es) creada(s)")
        except Exception as e:
            log.error(f"Error en job plazo_eventos: {e}")


def _job_plazo_inscripciones(app):
    """Crea notificaciones internas por cada piloto (principal o adicional)
    cuya inscripción individual siga pendiente con el plazo a <= 10 días.
    Una inscripción puede tener varios pilotos: si a uno ya se le envió pero
    a otro no, solo se avisa del que sigue pendiente."""
    with app.app_context():
        try:
            from datetime import date, timedelta
            from app.extensions import db
            from app.models.inscripcion import Inscripcion
            from app.models.notificacion import Notificacion

            hoy    = date.today()
            limite = hoy + timedelta(days=10)

            en_plazo = Inscripcion.query.filter(
                Inscripcion.fecha_plazo.isnot(None),
                Inscripcion.fecha_plazo >= hoy,
                Inscripcion.fecha_plazo <= limite,
            ).all()

            creadas = 0
            for insc in en_plazo:
                dias = (insc.fecha_plazo - hoy).days
                tipo = "danger" if dias <= 3 else "warning"

                # Piloto principal
                if insc.estado == "pendiente":
                    ref = f"plazo_insc_{insc.id}_principal"
                    if not Notificacion.query.filter_by(referencia=ref, leida=False).first():
                        piloto_nombre = insc.piloto.nombre_completo if insc.piloto else "—"
                        db.session.add(Notificacion(
                            tipo=tipo,
                            titulo=f"Plazo próximo: {insc.nombre_prueba}",
                            mensaje=(f"Quedan {dias} día{'s' if dias != 1 else ''} para presentar la inscripción. "
                                     f"Piloto: {piloto_nombre}."),
                            url=f"/autoclub/inscripciones/{insc.id}",
                            referencia=ref,
                        ))
                        creadas += 1

                # Pilotos adicionales
                for part in insc.participantes:
                    if part.estado != "pendiente":
                        continue
                    ref = f"plazo_insc_{insc.id}_part_{part.id}"
                    if Notificacion.query.filter_by(referencia=ref, leida=False).first():
                        continue
                    piloto_nombre = part.piloto.nombre_completo if part.piloto else "—"
                    db.session.add(Notificacion(
                        tipo=tipo,
                        titulo=f"Plazo próximo: {insc.nombre_prueba}",
                        mensaje=(f"Quedan {dias} día{'s' if dias != 1 else ''} para presentar la inscripción. "
                                 f"Piloto: {piloto_nombre}."),
                        url=f"/autoclub/inscripciones/{insc.id}",
                        referencia=ref,
                    ))
                    creadas += 1

            db.session.commit()
            log.info(f"Job plazo_inscripciones: {creadas} notificación(es) creada(s)")
        except Exception as e:
            log.error(f"Error en job plazo_inscripciones: {e}")
