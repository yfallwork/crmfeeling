"""
Pruebas de `calendario/eventos`, `calendario/pendientes` y `calendario/mover`
emulando distintos estados de reservas TeamBuilding (TB, sin cliente_id,
con empresa_id) frente a reservas individuales (con cliente_id).

Cubre:
  - P1: /eventos no debe hacer N+1 (1 sola query de reservas, con independencia
        de cuántas reservas relacionadas con cliente/empresa/tipo existan).
  - U2: /pendientes no debe romper con reservas TB sin fecha_disfrute.
  - U3: /mover no debe romper con reservas TB (antes fallaba en
        reserva.cliente.nombre_completo cuando cliente era None).
"""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import event

from app.extensions import db
from app.models.cliente import Cliente
from app.models.empresa import Empresa
from app.models.experiencia import TipoExperiencia
from app.models.reserva import Reserva


@pytest.fixture()
def escenario(app):
    """Crea un tipo de experiencia, un cliente individual y una empresa TB
    de prueba. Limpia todo (incluidas las reservas que cuelguen de ellos)
    al terminar el test."""
    with app.app_context():
        tipo = TipoExperiencia(nombre="QA Carcross", activo=True)
        cliente = Cliente(nombre="QA", apellido="Individual",
                           email="qa.calendario.individual@example.com", telefono="+34600111222")
        empresa = Empresa(nombre="QA Empresa TeamBuilding", email="qa.empresa.tb@example.com",
                           telefono="+34900333444", activo=True)
        db.session.add_all([tipo, cliente, empresa])
        db.session.commit()
        ids = {"tipo_id": tipo.id, "cliente_id": cliente.id, "empresa_id": empresa.id}

    yield ids

    with app.app_context():
        Reserva.query.filter(
            (Reserva.cliente_id == ids["cliente_id"]) | (Reserva.empresa_id == ids["empresa_id"])
        ).delete(synchronize_session=False)
        Cliente.query.filter_by(id=ids["cliente_id"]).delete()
        Empresa.query.filter_by(id=ids["empresa_id"]).delete()
        TipoExperiencia.query.filter_by(id=ids["tipo_id"]).delete()
        db.session.commit()


def _crear_reserva(app, escenario, **kwargs):
    with app.app_context():
        defaults = dict(tipo_experiencia_id=escenario["tipo_id"], estado="pendiente")
        defaults.update(kwargs)
        r = Reserva(**defaults)
        db.session.add(r)
        db.session.commit()
        return r.id


# ── /calendario/eventos ───────────────────────────────────────────────────

def test_eventos_incluye_individual_y_tb_sin_romper(auth_client, app, escenario):
    id_individual = _crear_reserva(
        app, escenario, cliente_id=escenario["cliente_id"], estado="reservado",
        fecha_disfrute=datetime.utcnow() + timedelta(days=5),
    )
    id_tb = _crear_reserva(
        app, escenario, empresa_id=escenario["empresa_id"], estado="reservado",
        nombre_grupo="QA Grupo TB", fecha_disfrute=datetime.utcnow() + timedelta(days=6),
    )

    resp = auth_client.get("/calendario/eventos")
    assert resp.status_code == 200
    eventos = {int(ev["id"]): ev for ev in resp.get_json()}

    assert id_individual in eventos
    assert id_tb in eventos

    ev_tb = eventos[id_tb]
    assert ev_tb["extendedProps"]["es_teambuilding"] is True
    # El teléfono debe venir de la empresa, no petar por cliente=None
    assert ev_tb["extendedProps"]["telefono"] == "+34900333444"

    ev_ind = eventos[id_individual]
    assert ev_ind["extendedProps"]["es_teambuilding"] is False
    assert ev_ind["extendedProps"]["telefono"] == "+34600111222"


def test_eventos_no_dispara_n_mas_1_queries(auth_client, app, escenario):
    """Regresión de P1: independientemente del número de reservas devueltas,
    la consulta de reservas debe seguir siendo una sola (gracias a joinedload),
    no una por cada relación (cliente/empresa/tipo_experiencia)."""
    for i in range(5):
        _crear_reserva(
            app, escenario, cliente_id=escenario["cliente_id"], estado="reservado",
            fecha_disfrute=datetime.utcnow() + timedelta(days=i + 1),
        )

    queries = []
    with app.app_context():
        listener = lambda *a: queries.append(a[2])
        event.listen(db.engine, "before_cursor_execute", listener)
        try:
            resp = auth_client.get("/calendario/eventos")
        finally:
            event.remove(db.engine, "before_cursor_execute", listener)

    assert resp.status_code == 200
    reservas_queries = [q for q in queries if "FROM reservas" in q]
    assert len(reservas_queries) == 1, (
        f"Se esperaba 1 sola query de reservas, se ejecutaron {len(reservas_queries)}: {reservas_queries}"
    )


# ── /calendario/pendientes ────────────────────────────────────────────────

def test_pendientes_incluye_tb_sin_fecha_sin_romper(auth_client, app, escenario):
    """U2: antes de la corrección, una reserva TB (cliente=None) sin
    fecha_disfrute hacía que la ruta lanzara AttributeError."""
    id_tb = _crear_reserva(
        app, escenario, empresa_id=escenario["empresa_id"], estado="pendiente",
        nombre_grupo="QA Grupo Pendiente",
    )

    resp = auth_client.get("/calendario/pendientes")
    assert resp.status_code == 200
    data = {item["id"]: item for item in resp.get_json()}

    assert id_tb in data
    item = data[id_tb]
    assert item["es_teambuilding"] is True
    assert item["cliente"] == "QA Empresa TeamBuilding"
    assert item["email"] == "qa.empresa.tb@example.com"
    assert item["telefono"] == "+34900333444"


def test_pendientes_incluye_individual_sin_fecha(auth_client, app, escenario):
    id_individual = _crear_reserva(
        app, escenario, cliente_id=escenario["cliente_id"], estado="pendiente",
    )

    resp = auth_client.get("/calendario/pendientes")
    assert resp.status_code == 200
    data = {item["id"]: item for item in resp.get_json()}

    assert id_individual in data
    item = data[id_individual]
    assert item["es_teambuilding"] is False
    assert item["cliente"] == "QA Individual"
    assert item["telefono"] == "+34600111222"


def test_pendientes_no_incluye_reservas_ya_con_fecha(auth_client, app, escenario):
    id_con_fecha = _crear_reserva(
        app, escenario, cliente_id=escenario["cliente_id"], estado="reservado",
        fecha_disfrute=datetime.utcnow() + timedelta(days=1),
    )
    resp = auth_client.get("/calendario/pendientes")
    assert resp.status_code == 200
    ids = {item["id"] for item in resp.get_json()}
    assert id_con_fecha not in ids


# ── /calendario/mover ──────────────────────────────────────────────────────

def test_mover_reserva_tb_sin_fecha_no_rompe(auth_client, auth_csrf_token, app, escenario):
    """U3: antes de la corrección, mover una reserva TB lanzaba AttributeError
    en `reserva.cliente.nombre_completo` al construir el log."""
    id_tb = _crear_reserva(
        app, escenario, empresa_id=escenario["empresa_id"], estado="pendiente",
        nombre_grupo="QA Grupo Mover",
    )
    nueva_fecha = (datetime.utcnow() + timedelta(days=10)).isoformat()

    resp = auth_client.post(
        f"/calendario/mover/{id_tb}",
        json={"fecha": nueva_fecha},
        headers={"X-CSRFToken": auth_csrf_token},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["estado"] == "reservado"  # pendiente -> reservado al asignar fecha

    with app.app_context():
        reserva = Reserva.query.get(id_tb)
        assert reserva.fecha_disfrute is not None
        assert reserva.estado == "reservado"


def test_mover_reserva_individual_no_rompe(auth_client, auth_csrf_token, app, escenario):
    id_individual = _crear_reserva(
        app, escenario, cliente_id=escenario["cliente_id"], estado="pendiente",
    )
    nueva_fecha = (datetime.utcnow() + timedelta(days=3)).isoformat()

    resp = auth_client.post(
        f"/calendario/mover/{id_individual}",
        json={"fecha": nueva_fecha},
        headers={"X-CSRFToken": auth_csrf_token},
    )
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


def test_mover_sin_fecha_devuelve_400_sin_tocar_bd(auth_client, auth_csrf_token, app, escenario):
    id_tb = _crear_reserva(app, escenario, empresa_id=escenario["empresa_id"], estado="pendiente")

    resp = auth_client.post(
        f"/calendario/mover/{id_tb}", json={}, headers={"X-CSRFToken": auth_csrf_token},
    )
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False

    with app.app_context():
        reserva = Reserva.query.get(id_tb)
        assert reserva.fecha_disfrute is None
        assert reserva.estado == "pendiente"


def test_mover_fecha_invalida_devuelve_400(auth_client, auth_csrf_token, app, escenario):
    id_tb = _crear_reserva(app, escenario, empresa_id=escenario["empresa_id"], estado="pendiente")

    resp = auth_client.post(
        f"/calendario/mover/{id_tb}",
        json={"fecha": "esto-no-es-una-fecha"},
        headers={"X-CSRFToken": auth_csrf_token},
    )
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False


def test_mover_reserva_inexistente_devuelve_404(auth_client, auth_csrf_token):
    resp = auth_client.post(
        "/calendario/mover/9999999",
        json={"fecha": datetime.utcnow().isoformat()},
        headers={"X-CSRFToken": auth_csrf_token},
    )
    assert resp.status_code == 404
