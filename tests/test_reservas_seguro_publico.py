"""
Verifica la ficha pública por reserva: el enlace único (token, sin login)
que se le envía al cliente para que rellene sus propios datos de seguro,
la generación/lectura del token desde el panel admin, la regeneración de
enlaces, y que el formulario público exige los campos obligatorios.
"""
from app.extensions import db
from app.models.cliente import Cliente
from app.models.experiencia import TipoExperiencia
from app.models.reserva import Reserva


def _crear_reserva(app):
    with app.app_context():
        tipo = TipoExperiencia(nombre="QA Experiencia Enlace")
        cliente = Cliente(nombre="QA", apellido="Enlace", email="qa.enlace@example.com")
        db.session.add_all([tipo, cliente])
        db.session.flush()
        reserva = Reserva(cliente_id=cliente.id, tipo_experiencia_id=tipo.id, estado="pendiente")
        db.session.add(reserva)
        db.session.commit()
        return reserva.id, cliente.id, tipo.id


def _borrar_reserva(app, reserva_id, cliente_id, tipo_id):
    with app.app_context():
        Reserva.query.filter_by(id=reserva_id).delete()
        Cliente.query.filter_by(id=cliente_id).delete()
        TipoExperiencia.query.filter_by(id=tipo_id).delete()
        db.session.commit()


def test_detalle_genera_token_y_muestra_el_enlace(auth_client, app):
    reserva_id, cliente_id, tipo_id = _crear_reserva(app)
    try:
        with app.app_context():
            assert Reserva.query.get(reserva_id).token_seguro is None

        resp = auth_client.get(f"/reservas/{reserva_id}")
        assert resp.status_code == 200
        assert b"/seguro/" in resp.data

        with app.app_context():
            reserva = Reserva.query.get(reserva_id)
            assert reserva.token_seguro is not None
            token = reserva.token_seguro
        assert token.encode("utf-8") in resp.data
    finally:
        _borrar_reserva(app, reserva_id, cliente_id, tipo_id)


def test_formulario_publico_sin_login_permite_rellenar_datos(app):
    reserva_id, cliente_id, tipo_id = _crear_reserva(app)
    try:
        with app.app_context():
            reserva = Reserva.query.get(reserva_id)
            reserva.asegurar_token_seguro()
            db.session.commit()
            token = reserva.token_seguro

        client = app.test_client()  # sin login

        resp = client.get(f"/seguro/{token}")
        assert resp.status_code == 200
        assert "QA Experiencia Enlace".encode("utf-8") in resp.data

        import re
        m = re.search(r'csrf_token" value="([^"]+)"', resp.get_data(as_text=True))
        csrf_token = m.group(1)

        # Sin campos obligatorios -> error, no guarda
        resp = client.post(f"/seguro/{token}", data={"csrf_token": csrf_token}, follow_redirects=True)
        assert resp.status_code == 200
        assert "obligatorios".encode("utf-8") in resp.data
        with app.app_context():
            assert Reserva.query.get(reserva_id).tiene_datos_seguro is False

        # Con todos los datos -> se guarda y confirma
        resp = client.post(
            f"/seguro/{token}",
            data={
                "piloto_nombre": "Cliente", "piloto_primer_apellido": "Final",
                "piloto_segundo_apellido": "Test", "piloto_fecha_nacimiento": "2000-01-01",
                "piloto_dni": "99999999R", "csrf_token": csrf_token,
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "guardados correctamente".encode("utf-8") in resp.data
        with app.app_context():
            reserva = Reserva.query.get(reserva_id)
            assert reserva.piloto_nombre == "Cliente"
            assert reserva.piloto_dni == "99999999R"

        # Una vez rellenado: el GET ya no muestra el formulario, solo los datos (bloqueado)
        resp = client.get(f"/seguro/{token}")
        assert resp.status_code == 200
        assert "no se pueden modificar".encode("utf-8") in resp.data
        assert b'name="piloto_nombre"' not in resp.data

        # Intentar reenviar el formulario (bypass de la UI) no debe modificar nada
        resp = client.post(
            f"/seguro/{token}",
            data={
                "piloto_nombre": "Otro", "piloto_primer_apellido": "Intento",
                "piloto_dni": "11111111Z", "piloto_fecha_nacimiento": "1999-09-09",
                "csrf_token": csrf_token,
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        with app.app_context():
            reserva = Reserva.query.get(reserva_id)
            assert reserva.piloto_nombre == "Cliente"  # no cambió
            assert reserva.piloto_dni == "99999999R"
    finally:
        _borrar_reserva(app, reserva_id, cliente_id, tipo_id)


def test_token_invalido_da_404(app):
    client = app.test_client()
    resp = client.get("/seguro/token-que-no-existe-123")
    assert resp.status_code == 404


def test_regenerar_enlace_invalida_el_token_anterior(auth_client, auth_csrf_token, app):
    reserva_id, cliente_id, tipo_id = _crear_reserva(app)
    try:
        auth_client.get(f"/reservas/{reserva_id}")  # genera el primer token
        with app.app_context():
            token_viejo = Reserva.query.get(reserva_id).token_seguro

        resp = auth_client.post(f"/reservas/{reserva_id}/regenerar-enlace-seguro",
                                 data={"csrf_token": auth_csrf_token}, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            token_nuevo = Reserva.query.get(reserva_id).token_seguro
        assert token_nuevo != token_viejo

        client = app.test_client()
        resp = client.get(f"/seguro/{token_viejo}")
        assert resp.status_code == 404
        resp = client.get(f"/seguro/{token_nuevo}")
        assert resp.status_code == 200
    finally:
        _borrar_reserva(app, reserva_id, cliente_id, tipo_id)
