"""
Verifica la landing pública (sin login) y el formulario de preinscripción
del proyecto "Selección Femenina de Pilotos de Carcross": validaciones
(rango de edad, campos obligatorios, checkbox de privacidad), guardado
correcto, aislamiento de la ruta pública (no requiere sesión), el panel
admin dentro de AutoClub para gestionar lo recibido (CRUD completo) y el
mailing masivo a las inscritas.
"""
import re
from unittest.mock import patch

from app.extensions import db
from app.models.preinscripcion_carcross import PreinscripcionCarcross, MailingSeleccionFemenina


def _extraer_csrf(html):
    m = re.search(r'csrf_token" value="([^"]+)"', html)
    assert m, "No se encontró csrf_token en la landing pública"
    return m.group(1)


def _borrar(app, id_):
    with app.app_context():
        MailingSeleccionFemenina.query.filter_by(preinscripcion_id=id_).delete()
        PreinscripcionCarcross.query.filter_by(id=id_).delete()
        db.session.commit()


def test_landing_publica_accesible_sin_login(app):
    client = app.test_client()
    resp = client.get("/seleccion-femenina/")
    assert resp.status_code == 200
    assert "Selección Femenina".encode("utf-8") in resp.data
    assert b'action="/seleccion-femenina/preinscripcion"' in resp.data


def test_preinscripcion_exitosa_sin_login(app):
    client = app.test_client()
    token = _extraer_csrf(client.get("/seleccion-femenina/").get_data(as_text=True))

    resp = client.post(
        "/seleccion-femenina/preinscripcion",
        data={
            "nombre_completo": "Lucía QA Pérez",
            "fecha_nacimiento": "2010-01-15",  # ~16 años
            "localidad": "Guadalajara",
            "email": "lucia.qa@example.com",
            "telefono": "600111222",
            "experiencia_previa": "conduccion_embrague",
            "motivacion": "Quiero ser piloto",
            "acepta_privacidad": "1",
            "csrf_token": token,
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Preinscripción recibida".encode("utf-8") in resp.data

    with app.app_context():
        p = PreinscripcionCarcross.query.filter_by(email="lucia.qa@example.com").first()
        assert p is not None
        assert p.nombre_completo == "Lucía QA Pérez"
        assert p.acepta_privacidad is True
        assert 14 <= p.edad <= 18
        pid = p.id
    _borrar(app, pid)


def test_preinscripcion_rechaza_fuera_de_rango_de_edad(app):
    client = app.test_client()
    token = _extraer_csrf(client.get("/seleccion-femenina/").get_data(as_text=True))

    resp = client.post(
        "/seleccion-femenina/preinscripcion",
        data={
            "nombre_completo": "QA Mayor De Edad",
            "fecha_nacimiento": "1990-01-01",  # demasiado mayor
            "email": "qa.mayor@example.com",
            "telefono": "600111222",
            "acepta_privacidad": "1",
            "csrf_token": token,
        },
    )
    assert resp.status_code == 400
    assert "14 a 18".encode("utf-8") in resp.data
    with app.app_context():
        assert PreinscripcionCarcross.query.filter_by(email="qa.mayor@example.com").first() is None


def test_preinscripcion_exige_privacidad_y_campos_obligatorios(app):
    client = app.test_client()
    token = _extraer_csrf(client.get("/seleccion-femenina/").get_data(as_text=True))

    resp = client.post(
        "/seleccion-femenina/preinscripcion",
        data={"nombre_completo": "QA Incompleta", "csrf_token": token},
    )
    assert resp.status_code == 400
    with app.app_context():
        assert PreinscripcionCarcross.query.filter_by(nombre_completo="QA Incompleta").first() is None


def test_panel_admin_requiere_login_y_permite_gestionar(auth_client, auth_csrf_token, app):
    # Sin login: la lista admin no es accesible
    anon = app.test_client()
    resp = anon.get("/autoclub/seleccion-femenina")
    assert resp.status_code in (302, 401, 403)

    # Crear una preinscripción real vía la ruta pública
    token = _extraer_csrf(anon.get("/seleccion-femenina/").get_data(as_text=True))
    anon.post(
        "/seleccion-femenina/preinscripcion",
        data={
            "nombre_completo": "QA Panel Admin",
            "fecha_nacimiento": "2009-06-01",
            "email": "qa.paneladmin@example.com",
            "telefono": "600333444",
            "acepta_privacidad": "1",
            "csrf_token": token,
        },
    )
    with app.app_context():
        p = PreinscripcionCarcross.query.filter_by(email="qa.paneladmin@example.com").first()
        assert p is not None
        pid = p.id

    try:
        # El admin (ya logueado en el CRM) sí la ve
        resp = auth_client.get("/autoclub/seleccion-femenina")
        assert resp.status_code == 200
        assert b"QA Panel Admin" in resp.data

        # Puede cambiar su estado
        resp = auth_client.post(
            f"/autoclub/seleccion-femenina/{pid}/estado",
            data={"estado": "contactada", "csrf_token": auth_csrf_token},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        with app.app_context():
            assert PreinscripcionCarcross.query.get(pid).estado == "contactada"

        # Exportar CSV incluye la fila
        resp = auth_client.get("/autoclub/seleccion-femenina/exportar")
        assert resp.status_code == 200
        assert b"QA Panel Admin" in resp.data
    finally:
        _borrar(app, pid)


# ── CRUD desde el panel admin ──────────────────────────────────────────

def test_crear_preinscripcion_manual_desde_el_crm(auth_client, auth_csrf_token, app):
    resp = auth_client.post(
        "/autoclub/seleccion-femenina/nueva",
        data={
            "csrf_token": auth_csrf_token,
            "nombre_completo": "QA Alta Manual",
            "fecha_nacimiento": "2010-03-01",
            "localidad": "Guadalajara",
            "email": "qa.altamanual@example.com",
            "telefono": "600555666",
            "experiencia_previa": "ninguna",
            "motivacion": "",
            "notas_internas": "Se apuntó por teléfono",
            "estado": "pendiente",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    try:
        with app.app_context():
            p = PreinscripcionCarcross.query.filter_by(email="qa.altamanual@example.com").first()
            assert p is not None
            assert p.nombre_completo == "QA Alta Manual"
            assert p.notas_internas == "Se apuntó por teléfono"
            assert p.acepta_privacidad is True
            pid = p.id
    finally:
        _borrar(app, pid)


def test_crear_preinscripcion_manual_sin_nombre_no_guarda_nada(auth_client, auth_csrf_token, app):
    resp = auth_client.post(
        "/autoclub/seleccion-femenina/nueva",
        data={
            "csrf_token": auth_csrf_token,
            "nombre_completo": "",
            "fecha_nacimiento": "2010-03-01",
            "email": "qa.sinnombre@example.com",
            "telefono": "600555666",
        },
    )
    assert resp.status_code == 400
    with app.app_context():
        assert PreinscripcionCarcross.query.filter_by(email="qa.sinnombre@example.com").first() is None


def test_editar_preinscripcion_actualiza_todos_los_campos(auth_client, auth_csrf_token, app):
    with app.app_context():
        p = PreinscripcionCarcross(
            nombre_completo="QA Editar Original", fecha_nacimiento=__import__("datetime").date(2009, 5, 1),
            localidad="Madrid", email="qa.editar@example.com", telefono="600000000",
            experiencia_previa="ninguna", estado="pendiente", acepta_privacidad=True,
        )
        db.session.add(p)
        db.session.commit()
        pid = p.id

    try:
        resp = auth_client.post(
            f"/autoclub/seleccion-femenina/{pid}/editar",
            data={
                "csrf_token": auth_csrf_token,
                "nombre_completo": "QA Editar Actualizada",
                "fecha_nacimiento": "2009-05-01",
                "localidad": "Toledo",
                "email": "qa.editar@example.com",
                "telefono": "600999888",
                "experiencia_previa": "amateur_sin_resultados",
                "motivacion": "Ahora sí",
                "notas_internas": "Nota actualizada",
                "estado": "contactada",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        with app.app_context():
            p = PreinscripcionCarcross.query.get(pid)
            assert p.nombre_completo == "QA Editar Actualizada"
            assert p.localidad == "Toledo"
            assert p.telefono == "600999888"
            assert p.estado == "contactada"
            assert p.notas_internas == "Nota actualizada"
    finally:
        _borrar(app, pid)


def test_editar_con_datos_invalidos_repuebla_el_formulario(auth_client, auth_csrf_token, app):
    with app.app_context():
        p = PreinscripcionCarcross(
            nombre_completo="QA Editar Invalida", fecha_nacimiento=__import__("datetime").date(2009, 5, 1),
            email="qa.editarinvalida@example.com", telefono="600000000",
            estado="pendiente", acepta_privacidad=True,
        )
        db.session.add(p)
        db.session.commit()
        pid = p.id

    try:
        resp = auth_client.post(
            f"/autoclub/seleccion-femenina/{pid}/editar",
            data={"csrf_token": auth_csrf_token, "nombre_completo": "", "email": "qa.editarinvalida@example.com"},
        )
        assert resp.status_code == 400
        assert "QA Editar Invalida".encode("utf-8") not in resp.data  # el form vuelve a mostrar lo enviado, no lo guardado
        with app.app_context():
            # No se ha tocado el registro original
            assert PreinscripcionCarcross.query.get(pid).nombre_completo == "QA Editar Invalida"
    finally:
        _borrar(app, pid)


def test_eliminar_preinscripcion(auth_client, auth_csrf_token, app):
    with app.app_context():
        p = PreinscripcionCarcross(
            nombre_completo="QA Eliminar", fecha_nacimiento=__import__("datetime").date(2009, 5, 1),
            email="qa.eliminar@example.com", telefono="600000000",
            estado="pendiente", acepta_privacidad=True,
        )
        db.session.add(p)
        db.session.commit()
        pid = p.id

    resp = auth_client.post(
        f"/autoclub/seleccion-femenina/{pid}/eliminar",
        data={"csrf_token": auth_csrf_token},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        assert PreinscripcionCarcross.query.get(pid) is None


# ── Mailing masivo ───────────────────────────────────────────────────────

def test_mailing_previsualizar_muestra_destinatarias_y_no_envia_nada(auth_client, auth_csrf_token, app):
    with app.app_context():
        p = PreinscripcionCarcross(
            nombre_completo="QA Mailing Preview", fecha_nacimiento=__import__("datetime").date(2009, 5, 1),
            email="qa.mailingpreview@example.com", telefono="600000000",
            estado="pendiente", acepta_privacidad=True,
        )
        db.session.add(p)
        db.session.commit()
        pid = p.id

    try:
        with patch("app.services.seleccion_femenina_mail.enviar_smtp_prensa") as mock_smtp:
            resp = auth_client.post(
                "/autoclub/seleccion-femenina/mailing",
                data={
                    "csrf_token": auth_csrf_token, "accion": "previsualizar",
                    "asunto": "Novedades del proceso", "cuerpo": "Os contamos las novedades.",
                },
                follow_redirects=True,
            )
        assert resp.status_code == 200
        assert not mock_smtp.called
        assert b"QA Mailing Preview" in resp.data
        assert "Confirmar y enviar".encode("utf-8") in resp.data
    finally:
        _borrar(app, pid)


def test_mailing_enviar_manda_a_cada_inscrita_y_reporta_fallos_parciales(auth_client, auth_csrf_token, app):
    with app.app_context():
        p1 = PreinscripcionCarcross(
            nombre_completo="QA Mailing Uno", fecha_nacimiento=__import__("datetime").date(2009, 5, 1),
            email="qa.mailing1@example.com", telefono="600000000",
            estado="pendiente", acepta_privacidad=True,
        )
        p2 = PreinscripcionCarcross(
            nombre_completo="QA Mailing Dos", fecha_nacimiento=__import__("datetime").date(2009, 5, 1),
            email="qa.mailing2@example.com", telefono="600000000",
            estado="pendiente", acepta_privacidad=True,
        )
        db.session.add_all([p1, p2])
        db.session.commit()
        pid1, pid2 = p1.id, p2.id

    def _side_effect(mime_msg, destinatario):
        if destinatario == "qa.mailing2@example.com":
            raise RuntimeError("fallo smtp simulado")

    try:
        with patch("app.services.seleccion_femenina_mail.enviar_smtp_prensa", side_effect=_side_effect) as mock_smtp:
            resp = auth_client.post(
                "/autoclub/seleccion-femenina/mailing/enviar",
                data={
                    "csrf_token": auth_csrf_token,
                    "asunto": "Novedades del proceso", "cuerpo": "Os contamos las novedades.",
                },
                follow_redirects=True,
            )
        assert resp.status_code == 200
        assert mock_smtp.call_count == 2
        assert b"1 enviados" in resp.data or "1 emails enviados".encode("utf-8") in resp.data
        assert b"QA Mailing Dos" in resp.data  # aparece en la tabla de fallidos
    finally:
        _borrar(app, pid1)
        _borrar(app, pid2)


def test_mailing_enviado_se_ve_en_la_ficha_de_edicion_de_la_candidata(auth_client, auth_csrf_token, app):
    with app.app_context():
        p_ok = PreinscripcionCarcross(
            nombre_completo="QA Historial OK", fecha_nacimiento=__import__("datetime").date(2009, 5, 1),
            email="qa.historialok@example.com", telefono="600000000",
            estado="pendiente", acepta_privacidad=True,
        )
        p_fallo = PreinscripcionCarcross(
            nombre_completo="QA Historial Fallo", fecha_nacimiento=__import__("datetime").date(2009, 5, 1),
            email="qa.historialfallo@example.com", telefono="600000000",
            estado="pendiente", acepta_privacidad=True,
        )
        db.session.add_all([p_ok, p_fallo])
        db.session.commit()
        pid_ok, pid_fallo = p_ok.id, p_fallo.id

    def _side_effect(mime_msg, destinatario):
        if destinatario == "qa.historialfallo@example.com":
            raise RuntimeError("fallo smtp simulado")

    try:
        with patch("app.services.seleccion_femenina_mail.enviar_smtp_prensa", side_effect=_side_effect):
            auth_client.post(
                "/autoclub/seleccion-femenina/mailing/enviar",
                data={
                    "csrf_token": auth_csrf_token,
                    "asunto": "Asunto de prueba historial", "cuerpo": "Cuerpo de prueba.",
                },
                follow_redirects=True,
            )

        with app.app_context():
            m_ok = MailingSeleccionFemenina.query.filter_by(preinscripcion_id=pid_ok).first()
            assert m_ok is not None and m_ok.enviado_ok is True
            m_fallo = MailingSeleccionFemenina.query.filter_by(preinscripcion_id=pid_fallo).first()
            assert m_fallo is not None and m_fallo.enviado_ok is False
            assert "fallo smtp simulado" in m_fallo.error

        resp_ok = auth_client.get(f"/autoclub/seleccion-femenina/{pid_ok}/editar")
        assert resp_ok.status_code == 200
        html_ok = resp_ok.get_data(as_text=True)
        assert "Asunto de prueba historial" in html_ok
        assert "Enviado</span>" in html_ok

        resp_fallo = auth_client.get(f"/autoclub/seleccion-femenina/{pid_fallo}/editar")
        assert resp_fallo.status_code == 200
        html_fallo = resp_fallo.get_data(as_text=True)
        assert "Asunto de prueba historial" in html_fallo
        assert "Fallido</span>" in html_fallo
    finally:
        _borrar(app, pid_ok)
        _borrar(app, pid_fallo)
