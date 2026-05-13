"""
Tareas programadas con APScheduler.
Se inicializa una sola vez desde create_app().
"""
import atexit
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

log = logging.getLogger(__name__)

_scheduler = None


def init_scheduler(app):
    global _scheduler
    if _scheduler is not None:
        return  # ya iniciado (evita duplicados con Flask reloader)

    _scheduler = BackgroundScheduler(timezone="Europe/Madrid", daemon=True)

    _scheduler.add_job(
        func=lambda: _job_recordatorios(app),
        trigger=CronTrigger(hour=9, minute=0),   # todos los días a las 09:00
        id="recordatorios_auto",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    _scheduler.start()
    atexit.register(_scheduler.shutdown)
    log.info("Scheduler iniciado — recordatorios automáticos a las 09:00")


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
