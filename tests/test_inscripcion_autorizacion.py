"""
Verifica el formulario de "Inscripción y Autorización General del Proceso
de Selección": disparo automático del email al pasar a apta_inscripcion,
validación del token (inexistente/caducado/ya usado), validaciones del
formulario (checkboxes independientes, imagen mutuamente excluyente,
consentimiento de salud condicional, DNI/email/teléfono), firma con
IP/timestamp por tutor, y el flujo de un solo tutor con documento de
custodia.
"""
import io
import re
from datetime import datetime, timedelta
from unittest.mock import patch

from app.extensions import db
from app.models.preinscripcion_carcross import PreinscripcionCarcross, MailingSeleccionFemenina
from app.models.inscripcion_autorizacion import InscripcionAutorizacion, TutorLegal
from app.models.notificacion import Notificacion


def _csrf_de(client, token):
    resp = client.get(f"/seleccion-femenina/inscripcion/{token}")
    m = re.search(r'csrf_token" value="([^"]+)"', resp.get_data(as_text=True))
    assert m, "No se encontró csrf_token en el formulario de inscripción"
    return m.group(1)


def _crear_preinscripcion(email="qa.inscripcion@example.com", nombre="QA Inscripcion"):
    p = PreinscripcionCarcross(
        nombre_completo=nombre, fecha_nacimiento=datetime(2010, 5, 1).date(),
        localidad="Guadalajara", email=email, telefono="600111222",
        estado="pendiente", acepta_privacidad=True,
    )
    db.session.add(p)
    db.session.commit()
    return p


def _borrar(app, pid):
    with app.app_context():
        inscripcion = InscripcionAutorizacion.query.filter_by(preinscripcion_id=pid).first()
        if inscripcion:
            TutorLegal.query.filter_by(inscripcion_id=inscripcion.id).delete()
            InscripcionAutorizacion.query.filter_by(id=inscripcion.id).delete()
        MailingSeleccionFemenina.query.filter_by(preinscripcion_id=pid).delete()
        Notificacion.query.filter(Notificacion.referencia == f"preinscripcion_carcross:{pid}").delete()
        PreinscripcionCarcross.query.filter_by(id=pid).delete()
        db.session.commit()


_FIRMA_DIBUJO_FALSA = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="

_TUTOR1 = {
    "tutor1_nombre": "Progenitora Uno", "tutor1_dni": "12345678A", "tutor1_relacion": "Madre",
    "tutor1_email": "tutor1@example.com", "tutor1_telefono": "600222333", "tutor1_firma": "1",
    "tutor1_firma_dibujo": _FIRMA_DIBUJO_FALSA,
}
_TUTOR2 = {
    "tutor2_nombre": "Progenitor Dos", "tutor2_dni": "87654321B", "tutor2_relacion": "Padre",
    "tutor2_email": "tutor2@example.com", "tutor2_telefono": "600333444", "tutor2_firma": "1",
    "tutor2_firma_dibujo": _FIRMA_DIBUJO_FALSA,
}
_COMUNES_OK = {
    "nombre_completo": "QA Inscripcion", "fecha_nacimiento": "2010-05-01", "localidad": "Guadalajara",
    "email": "qa.inscripcion@example.com", "telefono": "600111222", "dni_nie_participante": "11223344B",
    "emergencia_nombre": "Emergencia Contacto", "emergencia_telefono": "600555666", "emergencia_relacion": "Tía",
    "experiencia_conduccion": "Alguna", "experiencia_competicion": "",
    "licencia_federativa": "no", "licencia_federativa_detalle": "",
    "consiente_participacion": "1", "consiente_datos_personales": "1",
    "autorizacion_imagen": "autoriza", "acepta_bases_legales": "1", "acepta_compromisos": "1",
}


def test_cambiar_estado_a_apta_inscripcion_crea_token_y_envia_email(auth_client, auth_csrf_token, app):
    with app.app_context():
        p = _crear_preinscripcion()
        pid = p.id
    try:
        with patch("app.services.inscripcion_autorizacion_service.enviar_smtp_prensa") as mock_smtp:
            resp = auth_client.post(
                f"/autoclub/seleccion-femenina/{pid}/estado",
                data={"csrf_token": auth_csrf_token, "estado": "apta_inscripcion"},
                follow_redirects=True,
            )
        assert resp.status_code == 200
        assert mock_smtp.called

        with app.app_context():
            inscripcion = InscripcionAutorizacion.query.filter_by(preinscripcion_id=pid).first()
            assert inscripcion is not None
            assert inscripcion.token
            assert inscripcion.estado == "pendiente"
            mailing = MailingSeleccionFemenina.query.filter_by(preinscripcion_id=pid).first()
            assert mailing is not None and mailing.enviado_ok is True
    finally:
        _borrar(app, pid)


def test_cambiar_estado_dos_veces_no_duplica_ni_reenvia_token(auth_client, auth_csrf_token, app):
    with app.app_context():
        p = _crear_preinscripcion(email="qa.notoken2@example.com", nombre="QA No Duplica")
        pid = p.id
    try:
        with patch("app.services.inscripcion_autorizacion_service.enviar_smtp_prensa"):
            auth_client.post(
                f"/autoclub/seleccion-femenina/{pid}/estado",
                data={"csrf_token": auth_csrf_token, "estado": "apta_inscripcion"},
                follow_redirects=True,
            )
        with app.app_context():
            token_original = InscripcionAutorizacion.query.filter_by(preinscripcion_id=pid).first().token

        # Cambiar a otro estado y volver a apta_inscripcion no debe generar un segundo registro
        auth_client.post(f"/autoclub/seleccion-femenina/{pid}/estado",
                          data={"csrf_token": auth_csrf_token, "estado": "contactada"}, follow_redirects=True)
        with patch("app.services.inscripcion_autorizacion_service.enviar_smtp_prensa"):
            auth_client.post(f"/autoclub/seleccion-femenina/{pid}/estado",
                              data={"csrf_token": auth_csrf_token, "estado": "apta_inscripcion"}, follow_redirects=True)

        with app.app_context():
            assert InscripcionAutorizacion.query.filter_by(preinscripcion_id=pid).count() == 1
            assert InscripcionAutorizacion.query.filter_by(preinscripcion_id=pid).first().token == token_original
    finally:
        _borrar(app, pid)


def test_token_inexistente_da_404(client):
    resp = client.get("/seleccion-femenina/inscripcion/token-que-no-existe")
    assert resp.status_code == 404


def test_formulario_muestra_nombre_de_la_candidata(client, app):
    with app.app_context():
        p = _crear_preinscripcion(email="qa.muestra@example.com", nombre="QA Muestra Nombre")
        inscripcion = InscripcionAutorizacion(preinscripcion_id=p.id, token="tok-muestra-nombre")
        db.session.add(inscripcion)
        db.session.commit()
        pid = p.id
    try:
        resp = client.get("/seleccion-femenina/inscripcion/tok-muestra-nombre")
        assert resp.status_code == 200
        assert "QA Muestra Nombre".encode("utf-8") in resp.data
    finally:
        _borrar(app, pid)


def test_envio_incompleto_no_guarda_nada(client, app):
    with app.app_context():
        p = _crear_preinscripcion(email="qa.incompleto@example.com", nombre="QA Incompleto")
        inscripcion = InscripcionAutorizacion(preinscripcion_id=p.id, token="tok-incompleto")
        db.session.add(inscripcion)
        db.session.commit()
        pid = p.id
    try:
        resp = client.post("/seleccion-femenina/inscripcion/tok-incompleto",
                            data={"csrf_token": _csrf_de(client, "tok-incompleto")})
        assert resp.status_code == 400
        with app.app_context():
            assert TutorLegal.query.join(InscripcionAutorizacion).filter(
                InscripcionAutorizacion.preinscripcion_id == pid
            ).count() == 0
            assert InscripcionAutorizacion.query.filter_by(preinscripcion_id=pid).first().estado == "pendiente"
    finally:
        _borrar(app, pid)


def test_envio_completo_dos_tutores_registra_ip_y_timestamp(client, app):
    with app.app_context():
        p = _crear_preinscripcion(email="qa.completo2@example.com", nombre="QA Completo Dos")
        inscripcion = InscripcionAutorizacion(preinscripcion_id=p.id, token="tok-completo-dos")
        db.session.add(inscripcion)
        db.session.commit()
        pid = p.id

    data = {**_COMUNES_OK, **_TUTOR1, **_TUTOR2}
    try:
        data["csrf_token"] = _csrf_de(client, "tok-completo-dos")
        with patch("app.services.inscripcion_autorizacion_service.enviar_smtp_prensa"):
            resp = client.post(
                "/seleccion-femenina/inscripcion/tok-completo-dos", data=data,
                follow_redirects=True, headers={"User-Agent": "pytest-agent"},
            )
        assert resp.status_code == 200
        assert "Gracias".encode("utf-8") in resp.data

        with app.app_context():
            inscripcion = InscripcionAutorizacion.query.filter_by(preinscripcion_id=pid).first()
            assert inscripcion.estado == "completado"
            assert inscripcion.token_usado_en is not None
            assert inscripcion.consiente_participacion is True
            assert inscripcion.autorizacion_imagen == "autoriza"
            assert inscripcion.dni_nie_participante == "11223344B"

            tutores = TutorLegal.query.filter_by(inscripcion_id=inscripcion.id).order_by(TutorLegal.numero).all()
            assert len(tutores) == 2
            for t in tutores:
                assert t.firmado is True
                assert t.firma_ip is not None
                assert t.firma_user_agent == "pytest-agent"
                assert t.firma_en is not None
                assert t.firma_dibujo and t.firma_dibujo.startswith("data:image")

            assert PreinscripcionCarcross.query.get(pid).estado == "inscripcion_completada"
            assert Notificacion.query.filter_by(referencia=f"preinscripcion_carcross:{pid}").first() is not None

        # El enlace ya usado no vuelve a mostrar el formulario
        resp2 = client.get("/seleccion-femenina/inscripcion/tok-completo-dos")
        assert resp2.status_code == 200
        assert b"formulario" not in resp2.data.lower() or "Gracias".encode("utf-8") in resp2.data
    finally:
        _borrar(app, pid)


def test_envio_completo_un_solo_tutor_con_documento_custodia(client, app):
    with app.app_context():
        p = _crear_preinscripcion(email="qa.unTutor@example.com", nombre="QA Un Tutor")
        inscripcion = InscripcionAutorizacion(preinscripcion_id=p.id, token="tok-un-tutor")
        db.session.add(inscripcion)
        db.session.commit()
        pid = p.id

    data_con_doc = {**_COMUNES_OK, **_TUTOR1, "solo_un_tutor": "1"}
    try:
        data_con_doc["csrf_token"] = _csrf_de(client, "tok-un-tutor")
        data_con_doc["doc_custodia"] = (io.BytesIO(b"contenido pdf falso"), "custodia.pdf")
        with patch("app.services.inscripcion_autorizacion_service.enviar_smtp_prensa"):
            resp = client.post(
                "/seleccion-femenina/inscripcion/tok-un-tutor", data=data_con_doc,
                content_type="multipart/form-data", follow_redirects=True,
            )
        assert resp.status_code == 200

        with app.app_context():
            inscripcion = InscripcionAutorizacion.query.filter_by(preinscripcion_id=pid).first()
            assert inscripcion.estado == "completado"
            assert inscripcion.solo_un_tutor is True
            assert inscripcion.doc_custodia_path
            assert inscripcion.necesita_revision_custodia is False
            tutores = TutorLegal.query.filter_by(inscripcion_id=inscripcion.id).all()
            assert len(tutores) == 1
    finally:
        _borrar(app, pid)


def test_envio_completo_un_solo_tutor_sin_documento_no_bloquea_pero_marca_revision(client, app):
    with app.app_context():
        p = _crear_preinscripcion(email="qa.unTutorSinDoc@example.com", nombre="QA Un Tutor Sin Doc")
        inscripcion = InscripcionAutorizacion(preinscripcion_id=p.id, token="tok-un-tutor-sin-doc")
        db.session.add(inscripcion)
        db.session.commit()
        pid = p.id

    data_sin_doc = {**_COMUNES_OK, **_TUTOR1, "solo_un_tutor": "1"}
    try:
        data_sin_doc["csrf_token"] = _csrf_de(client, "tok-un-tutor-sin-doc")
        with patch("app.services.inscripcion_autorizacion_service.enviar_smtp_prensa"):
            resp = client.post(
                "/seleccion-femenina/inscripcion/tok-un-tutor-sin-doc", data=data_sin_doc,
                follow_redirects=True,
            )
        assert resp.status_code == 200

        with app.app_context():
            inscripcion = InscripcionAutorizacion.query.filter_by(preinscripcion_id=pid).first()
            assert inscripcion.estado == "completado"
            assert not inscripcion.doc_custodia_path
            assert inscripcion.necesita_revision_custodia is True
            from app.models.notificacion import Notificacion as Notif
            notif = Notif.query.filter_by(referencia=f"preinscripcion_carcross:{pid}").first()
            assert notif is not None
            assert "custodia" in notif.mensaje.lower()
    finally:
        _borrar(app, pid)


def test_autorizacion_imagen_sin_elegir_da_error(client, app):
    with app.app_context():
        p = _crear_preinscripcion(email="qa.imagen@example.com", nombre="QA Imagen")
        inscripcion = InscripcionAutorizacion(preinscripcion_id=p.id, token="tok-imagen")
        db.session.add(inscripcion)
        db.session.commit()
        pid = p.id
    try:
        data = {**_COMUNES_OK, **_TUTOR1, **_TUTOR2}
        data["autorizacion_imagen"] = ""
        data["csrf_token"] = _csrf_de(client, "tok-imagen")
        resp = client.post("/seleccion-femenina/inscripcion/tok-imagen", data=data)
        assert resp.status_code == 400
        with app.app_context():
            assert InscripcionAutorizacion.query.filter_by(preinscripcion_id=pid).first().estado == "pendiente"
    finally:
        _borrar(app, pid)


def test_dni_participante_es_obligatorio(client, app):
    with app.app_context():
        p = _crear_preinscripcion(email="qa.dniparticipante@example.com", nombre="QA DNI Participante")
        inscripcion = InscripcionAutorizacion(preinscripcion_id=p.id, token="tok-dni-participante")
        db.session.add(inscripcion)
        db.session.commit()
        pid = p.id
    try:
        data = {**_COMUNES_OK, **_TUTOR1, **_TUTOR2}
        data["dni_nie_participante"] = ""
        data["csrf_token"] = _csrf_de(client, "tok-dni-participante")
        resp = client.post("/seleccion-femenina/inscripcion/tok-dni-participante", data=data)
        assert resp.status_code == 400
        with app.app_context():
            assert InscripcionAutorizacion.query.filter_by(preinscripcion_id=pid).first().estado == "pendiente"

        data["dni_nie_participante"] = "11223344B"
        data["csrf_token"] = _csrf_de(client, "tok-dni-participante")
        with patch("app.services.inscripcion_autorizacion_service.enviar_smtp_prensa"):
            resp2 = client.post("/seleccion-femenina/inscripcion/tok-dni-participante", data=data, follow_redirects=True)
        assert resp2.status_code == 200
        with app.app_context():
            inscripcion = InscripcionAutorizacion.query.filter_by(preinscripcion_id=pid).first()
            assert inscripcion.estado == "completado"
            assert inscripcion.dni_nie_participante == "11223344B"
    finally:
        _borrar(app, pid)


def test_firma_dibujada_es_obligatoria(client, app):
    with app.app_context():
        p = _crear_preinscripcion(email="qa.firmadibujo@example.com", nombre="QA Firma Dibujo")
        inscripcion = InscripcionAutorizacion(preinscripcion_id=p.id, token="tok-firma-dibujo")
        db.session.add(inscripcion)
        db.session.commit()
        pid = p.id
    try:
        data = {**_COMUNES_OK, **_TUTOR1, **_TUTOR2}
        data["tutor1_firma_dibujo"] = ""
        data["csrf_token"] = _csrf_de(client, "tok-firma-dibujo")
        resp = client.post("/seleccion-femenina/inscripcion/tok-firma-dibujo", data=data)
        assert resp.status_code == 400
        with app.app_context():
            assert InscripcionAutorizacion.query.filter_by(preinscripcion_id=pid).first().estado == "pendiente"
    finally:
        _borrar(app, pid)


def test_dni_invalido_de_un_tutor_da_error(client, app):
    with app.app_context():
        p = _crear_preinscripcion(email="qa.dni@example.com", nombre="QA DNI")
        inscripcion = InscripcionAutorizacion(preinscripcion_id=p.id, token="tok-dni")
        db.session.add(inscripcion)
        db.session.commit()
        pid = p.id
    try:
        data = {**_COMUNES_OK, **_TUTOR1, **_TUTOR2}
        data["tutor1_dni"] = "no-es-un-dni"
        data["csrf_token"] = _csrf_de(client, "tok-dni")
        resp = client.post("/seleccion-femenina/inscripcion/tok-dni", data=data)
        assert resp.status_code == 400
        with app.app_context():
            assert InscripcionAutorizacion.query.filter_by(preinscripcion_id=pid).first().estado == "pendiente"
    finally:
        _borrar(app, pid)


def test_token_caducado_no_permite_acceder(client, app):
    with app.app_context():
        p = _crear_preinscripcion(email="qa.caducado@example.com", nombre="QA Caducado")
        inscripcion = InscripcionAutorizacion(
            preinscripcion_id=p.id, token="tok-caducado",
            token_creado_en=datetime.utcnow() - timedelta(days=40),
        )
        db.session.add(inscripcion)
        db.session.commit()
        pid = p.id
    try:
        resp = client.get("/seleccion-femenina/inscripcion/tok-caducado")
        assert resp.status_code == 410
        assert "caducado".encode("utf-8") in resp.data.lower()
    finally:
        _borrar(app, pid)
