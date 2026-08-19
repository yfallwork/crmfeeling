"""
Verifica el envío de email con el enlace de datos de seguro (botón manual
desde la reserva, vista previa, y el job automático que lo manda X días
antes de la fecha de disfrute si el cliente todavía no ha rellenado nada),
y el toggle/ajuste de días en Configuración general.
"""
from datetime import datetime, timedelta

from app.extensions import db
from app.models.cliente import Cliente
from app.models.experiencia import TipoExperiencia
from app.models.reserva import Reserva
from app.models.comunicacion import ComunicacionLog
from app.models.configuracion import Configuracion


def _crear_reserva(app, fecha_disfrute=None, con_datos_seguro=False, sufijo="a"):
    with app.app_context():
        tipo = TipoExperiencia(nombre=f"QA Experiencia Email Seguro {sufijo}")
        cliente = Cliente(nombre="QA", apellido="EmailSeguro", email=f"qa.emailseguro.{sufijo}@example.com")
        db.session.add_all([tipo, cliente])
        db.session.flush()
        reserva = Reserva(cliente_id=cliente.id, tipo_experiencia_id=tipo.id, estado="reservado",
                           fecha_disfrute=fecha_disfrute)
        if con_datos_seguro:
            reserva.piloto_nombre = "Ya"
            reserva.piloto_primer_apellido = "Relleno"
            reserva.piloto_dni = "00000000Z"
            reserva.piloto_fecha_nacimiento = datetime(1990, 1, 1).date()
        db.session.add(reserva)
        db.session.commit()
        return reserva.id, cliente.id, tipo.id


def _borrar(app, reserva_id, cliente_id, tipo_id):
    with app.app_context():
        ComunicacionLog.query.filter_by(reserva_id=reserva_id).delete()
        Reserva.query.filter_by(id=reserva_id).delete()
        Cliente.query.filter_by(id=cliente_id).delete()
        TipoExperiencia.query.filter_by(id=tipo_id).delete()
        db.session.commit()


def test_preview_email_seguro_incluye_el_enlace(auth_client, app):
    reserva_id, cliente_id, tipo_id = _crear_reserva(app)
    try:
        resp = auth_client.get(f"/api/reservas/{reserva_id}/preview?tipo=seguro&canal=email")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "seguro" in data["asunto"].lower() or "Faltan" in data["asunto"]
        assert "/seguro/" in data["html"]
        assert data["destinatario"] == "qa.emailseguro.a@example.com"
    finally:
        _borrar(app, reserva_id, cliente_id, tipo_id)


def test_boton_manual_envia_email_y_registra_log(auth_client, auth_csrf_token, app):
    reserva_id, cliente_id, tipo_id = _crear_reserva(app)
    try:
        resp = auth_client.post(
            f"/api/reservas/{reserva_id}/notificar",
            json={"tipo": "seguro", "canal": "email"},
            headers={"X-CSRFToken": auth_csrf_token},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        with app.app_context():
            logs = ComunicacionLog.query.filter_by(reserva_id=reserva_id, tipo="seguro").all()
            assert len(logs) == 1
            assert logs[0].ok is True
            # El token ya debe existir tras generar/enviar el email
            assert Reserva.query.get(reserva_id).token_seguro is not None
    finally:
        _borrar(app, reserva_id, cliente_id, tipo_id)


def test_configuracion_actualiza_activo_y_dias(auth_client, auth_csrf_token, app):
    resp = auth_client.post(
        "/configuracion/seguro-recordatorio",
        data={"activo": "on", "dias": "10", "csrf_token": auth_csrf_token},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        config = Configuracion.get()
        assert config.seguro_recordatorio_activo is True
        assert config.seguro_recordatorio_dias == 10

    # Desactivar
    resp = auth_client.post(
        "/configuracion/seguro-recordatorio",
        data={"dias": "10", "csrf_token": auth_csrf_token},  # sin "activo" => desmarcado
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        config = Configuracion.get()
        assert config.seguro_recordatorio_activo is False

        # Restaurar valores por defecto para no afectar a otros tests
        config.seguro_recordatorio_activo = True
        config.seguro_recordatorio_dias = 7
        db.session.commit()


def test_job_seguro_recordatorio_envia_solo_a_quien_le_faltan_datos(app):
    from app.scheduler import _job_seguro_recordatorio

    with app.app_context():
        config = Configuracion.get()
        config.seguro_recordatorio_activo = True
        config.seguro_recordatorio_dias = 7
        db.session.commit()

    objetivo = datetime.utcnow() + timedelta(days=7)
    id_falta, cliente_falta, tipo_falta = _crear_reserva(app, fecha_disfrute=objetivo, con_datos_seguro=False, sufijo="falta")
    id_completa, cliente_completa, tipo_completa = _crear_reserva(app, fecha_disfrute=objetivo, con_datos_seguro=True, sufijo="completa")

    try:
        _job_seguro_recordatorio(app)

        with app.app_context():
            # A quien le faltan datos, se le envía y se registra el log
            log_falta = ComunicacionLog.query.filter_by(reserva_id=id_falta, tipo="seguro_recordatorio").first()
            assert log_falta is not None
            assert log_falta.ok is True

            # A quien ya los tenía completos, no se le envía nada
            log_completa = ComunicacionLog.query.filter_by(reserva_id=id_completa, tipo="seguro_recordatorio").first()
            assert log_completa is None

        # Volver a ejecutar el job no debe duplicar el envío (ya hay un log ok=True)
        _job_seguro_recordatorio(app)
        with app.app_context():
            assert ComunicacionLog.query.filter_by(reserva_id=id_falta, tipo="seguro_recordatorio").count() == 1
    finally:
        _borrar(app, id_falta, cliente_falta, tipo_falta)
        _borrar(app, id_completa, cliente_completa, tipo_completa)


def test_job_no_envia_si_recordatorio_desactivado(app):
    from app.scheduler import _job_seguro_recordatorio

    with app.app_context():
        config = Configuracion.get()
        config.seguro_recordatorio_activo = False
        db.session.commit()

    objetivo = datetime.utcnow() + timedelta(days=7)
    reserva_id, cliente_id, tipo_id = _crear_reserva(app, fecha_disfrute=objetivo, con_datos_seguro=False)
    try:
        _job_seguro_recordatorio(app)
        with app.app_context():
            assert ComunicacionLog.query.filter_by(reserva_id=reserva_id, tipo="seguro_recordatorio").count() == 0
    finally:
        with app.app_context():
            config = Configuracion.get()
            config.seguro_recordatorio_activo = True
            db.session.commit()
        _borrar(app, reserva_id, cliente_id, tipo_id)
