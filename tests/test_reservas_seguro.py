"""
Verifica los datos de seguro en Reserva: nombre, apellidos, fecha de
nacimiento y DNI de la persona que realiza físicamente la experiencia
(puede no coincidir con el cliente que reservó), tanto al crear como al
editar una reserva.
"""
from app.extensions import db
from app.models.cliente import Cliente
from app.models.experiencia import TipoExperiencia
from app.models.reserva import Reserva


def test_crear_reserva_con_datos_de_seguro(auth_client, auth_csrf_token, app):
    with app.app_context():
        tipo = TipoExperiencia(nombre="QA Experiencia Seguro")
        cliente = Cliente(nombre="QA", apellido="Cliente Seguro", email="qa.seguro@example.com")
        db.session.add_all([tipo, cliente])
        db.session.commit()
        tipo_id, cliente_id = tipo.id, cliente.id

    resp = auth_client.post(
        "/reservas/nueva",
        data={
            "tipo_reserva": "individual",
            "cliente_id": cliente_id,
            "tipo_experiencia_id": tipo_id,
            "estado": "pendiente",
            "precio": "100",
            "piloto_nombre": "Juan",
            "piloto_primer_apellido": "Pérez",
            "piloto_segundo_apellido": "García",
            "piloto_fecha_nacimiento": "1990-05-15",
            "piloto_dni": "12345678A",
            "csrf_token": auth_csrf_token,
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        reserva = Reserva.query.filter_by(cliente_id=cliente_id).first()
        assert reserva is not None
        assert reserva.piloto_nombre == "Juan"
        assert reserva.piloto_primer_apellido == "Pérez"
        assert reserva.piloto_segundo_apellido == "García"
        assert reserva.piloto_dni == "12345678A"
        assert reserva.piloto_fecha_nacimiento.isoformat() == "1990-05-15"
        assert reserva.piloto_nombre_completo == "Juan Pérez García"
        assert reserva.tiene_datos_seguro is True
        reserva_id = reserva.id

    # Se muestran en la ficha de detalle
    resp = auth_client.get(f"/reservas/{reserva_id}")
    assert resp.status_code == 200
    assert "Pérez".encode("utf-8") in resp.data
    assert "García".encode("utf-8") in resp.data
    assert b"12345678A" in resp.data

    # Editar la reserva actualiza los datos de seguro
    resp = auth_client.post(
        f"/reservas/{reserva_id}/editar",
        data={
            "tipo_reserva": "individual",
            "cliente_id": cliente_id,
            "tipo_experiencia_id": tipo_id,
            "estado": "pendiente",
            "precio": "100",
            "piloto_nombre": "María",
            "piloto_primer_apellido": "López",
            "piloto_segundo_apellido": "Ruiz",
            "piloto_fecha_nacimiento": "1985-01-01",
            "piloto_dni": "87654321B",
            "csrf_token": auth_csrf_token,
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        reserva = Reserva.query.get(reserva_id)
        assert reserva.piloto_nombre == "María"
        assert reserva.piloto_primer_apellido == "López"
        assert reserva.piloto_segundo_apellido == "Ruiz"
        assert reserva.piloto_dni == "87654321B"

    # Limpieza
    with app.app_context():
        Reserva.query.filter_by(id=reserva_id).delete()
        Cliente.query.filter_by(id=cliente_id).delete()
        TipoExperiencia.query.filter_by(id=tipo_id).delete()
        db.session.commit()


def test_tarjeta_de_seguro_siempre_visible_y_editable_desde_el_detalle(auth_client, auth_csrf_token, app):
    with app.app_context():
        tipo = TipoExperiencia(nombre="QA Experiencia Sin Seguro")
        cliente = Cliente(nombre="QA", apellido="Sin Seguro", email="qa.sinseguro@example.com")
        db.session.add_all([tipo, cliente])
        db.session.flush()
        reserva = Reserva(cliente_id=cliente.id, tipo_experiencia_id=tipo.id, estado="pendiente")
        db.session.add(reserva)
        db.session.commit()
        reserva_id = reserva.id
        tipo_id, cliente_id = tipo.id, cliente.id

    # La tarjeta (con el formulario) aparece siempre, aunque no haya datos todavía
    resp = auth_client.get(f"/reservas/{reserva_id}")
    assert resp.status_code == 200
    assert "Datos para el seguro".encode("utf-8") in resp.data
    assert "Faltan datos".encode("utf-8") in resp.data

    # Se puede rellenar directamente desde el propio visor de la reserva
    resp = auth_client.post(
        f"/reservas/{reserva_id}/seguro",
        data={
            "piloto_nombre": "Ana", "piloto_primer_apellido": "Gómez", "piloto_segundo_apellido": "Ruiz",
            "piloto_fecha_nacimiento": "1995-07-20", "piloto_dni": "11223344C",
            "csrf_token": auth_csrf_token,
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Completos".encode("utf-8") in resp.data
    with app.app_context():
        reserva = Reserva.query.get(reserva_id)
        assert reserva.piloto_nombre == "Ana"
        assert reserva.piloto_dni == "11223344C"

    with app.app_context():
        Reserva.query.filter_by(id=reserva_id).delete()
        Cliente.query.filter_by(id=cliente_id).delete()
        TipoExperiencia.query.filter_by(id=tipo_id).delete()
        db.session.commit()
