"""
Verifica el wizard de los 3 documentos firmables (aptitud médica, asunción
de riesgo, disclaimer de conducción) y el módulo de notas de entrevista:
selección ambos/solo un tutor, validaciones, firma con verificación de
DNI, generación de PDF, envío de copia, versionado sin sobrescritura, y
autoguardado de las notas de entrevista.
"""
import io
import re
from datetime import datetime, timedelta
from unittest.mock import patch

from app.extensions import db
from app.models.preinscripcion_carcross import PreinscripcionCarcross, MailingSeleccionFemenina
from app.models.firmable import SesionFirmables, DocumentoFirmado, FirmaTutorDocumento
from app.models.entrevista import EntrevistaPiloto


def _crear_preinscripcion(email="qa.firmables@example.com", nombre="QA Firmables", fecha_nac=None):
    p = PreinscripcionCarcross(
        nombre_completo=nombre, fecha_nacimiento=fecha_nac or datetime(2010, 5, 1).date(),
        localidad="Guadalajara", email=email, telefono="600111222",
        estado="pendiente", acepta_privacidad=True,
    )
    db.session.add(p)
    db.session.commit()
    return p


def _borrar(app, pid):
    with app.app_context():
        for sesion in SesionFirmables.query.filter_by(preinscripcion_id=pid).all():
            for doc in DocumentoFirmado.query.filter_by(sesion_id=sesion.id).all():
                FirmaTutorDocumento.query.filter_by(documento_id=doc.id).delete()
                DocumentoFirmado.query.filter_by(id=doc.id).delete()
            SesionFirmables.query.filter_by(id=sesion.id).delete()
        EntrevistaPiloto.query.filter_by(preinscripcion_id=pid).delete()
        MailingSeleccionFemenina.query.filter_by(preinscripcion_id=pid).delete()
        PreinscripcionCarcross.query.filter_by(id=pid).delete()
        db.session.commit()


def _csrf(html):
    m = re.search(r'csrf_token" value="([^"]+)"', html)
    assert m
    return m.group(1)


def _firma_tutor(n, nombre="Progenitora Uno", dni="12345678A"):
    return {
        f"tutor{n}_nombre": nombre, f"tutor{n}_dni": dni,
        f"tutor{n}_verificacion": dni[-4:], f"tutor{n}_firma": "1",
    }


def _preparar_enlace(auth_client, auth_csrf_token, pid, app):
    """Genera (vía la ruta de staff) el enlace de firmables y devuelve el
    token — mismo mecanismo que el botón "Generar enlace" del CRM."""
    auth_client.post(
        f"/autoclub/seleccion-femenina/{pid}/firmables/preparar-enlace",
        data={"csrf_token": auth_csrf_token}, follow_redirects=True,
    )
    with app.app_context():
        return SesionFirmables.query.filter_by(preinscripcion_id=pid, estado="en_progreso").first().token


def test_generar_enlace_no_duplica_sesion_pendiente(auth_client, auth_csrf_token, app):
    with app.app_context():
        p = _crear_preinscripcion(email="qa.enlace@example.com", nombre="QA Enlace")
        pid = p.id
    try:
        token1 = _preparar_enlace(auth_client, auth_csrf_token, pid, app)
        token2 = _preparar_enlace(auth_client, auth_csrf_token, pid, app)
        assert token1 == token2
        with app.app_context():
            assert SesionFirmables.query.filter_by(preinscripcion_id=pid).count() == 1
    finally:
        _borrar(app, pid)


def test_enviar_por_email_registra_envio_en_historial(auth_client, auth_csrf_token, app):
    with app.app_context():
        p = _crear_preinscripcion(email="qa.enviarfirmables@example.com", nombre="QA Enviar Firmables")
        pid = p.id
    try:
        with patch("app.services.firmables_service.enviar_smtp_prensa") as mock_smtp:
            resp = auth_client.post(
                f"/autoclub/seleccion-femenina/{pid}/firmables/enviar-email",
                data={"csrf_token": auth_csrf_token}, follow_redirects=True,
            )
        assert resp.status_code == 200
        assert mock_smtp.called
        with app.app_context():
            sesion = SesionFirmables.query.filter_by(preinscripcion_id=pid).first()
            assert sesion is not None and sesion.token
            mailing = MailingSeleccionFemenina.query.filter_by(preinscripcion_id=pid).first()
            assert mailing is not None and mailing.enviado_ok is True
    finally:
        _borrar(app, pid)


def test_token_de_firmables_inexistente_da_404(client):
    resp = client.get("/seleccion-femenina/firmables/token-que-no-existe")
    assert resp.status_code == 404


def test_token_de_firmables_caducado_no_permite_acceder(auth_client, auth_csrf_token, app):
    with app.app_context():
        p = _crear_preinscripcion(email="qa.firmablescaducado@example.com", nombre="QA Firmables Caducado")
        pid = p.id
    try:
        token = _preparar_enlace(auth_client, auth_csrf_token, pid, app)
        with app.app_context():
            sesion = SesionFirmables.query.filter_by(preinscripcion_id=pid).first()
            sesion.token_creado_en = datetime.utcnow() - timedelta(days=40)
            db.session.commit()

        resp = auth_client.get(f"/seleccion-femenina/firmables/{token}")
        assert resp.status_code == 410
        assert "caducado".encode("utf-8") in resp.data.lower()
    finally:
        _borrar(app, pid)


def test_flujo_completo_ambos_tutores_genera_3_documentos_y_envia_copia(auth_client, auth_csrf_token, app):
    with app.app_context():
        p = _crear_preinscripcion()
        pid = p.id
    try:
        token = _preparar_enlace(auth_client, auth_csrf_token, pid, app)

        # Modo de tutores: "ambos"
        resp = auth_client.post(
            f"/seleccion-femenina/firmables/{token}",
            data={"csrf_token": auth_csrf_token, "modo_tutores": "ambos"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        with app.app_context():
            sesion = SesionFirmables.query.filter_by(preinscripcion_id=pid).first()
            assert sesion is not None and sesion.modo_tutores == "ambos"

        # Paso 1: aptitud médica
        data1 = {"csrf_token": auth_csrf_token, "tiene_condicion_medica": "no"}
        data1.update(_firma_tutor(1, "Madre Uno", "11111111A"))
        data1.update(_firma_tutor(2, "Padre Dos", "22222222B"))
        resp = auth_client.post(
            f"/seleccion-femenina/firmables/{token}/paso/1",
            data=data1, follow_redirects=True,
        )
        assert resp.status_code == 200

        # Paso 2: asunción de riesgo
        data2 = {"csrf_token": auth_csrf_token}
        data2.update(_firma_tutor(1, "Madre Uno", "11111111A"))
        data2.update(_firma_tutor(2, "Padre Dos", "22222222B"))
        resp = auth_client.post(
            f"/seleccion-femenina/firmables/{token}/paso/2",
            data=data2, follow_redirects=True,
        )
        assert resp.status_code == 200

        # Paso 3: disclaimer de conducción
        data3 = {"csrf_token": auth_csrf_token, "checkbox_1": "1", "checkbox_2": "1", "checkbox_3": "1"}
        data3.update(_firma_tutor(1, "Madre Uno", "11111111A"))
        data3.update(_firma_tutor(2, "Padre Dos", "22222222B"))
        with patch("app.services.firmables_service.enviar_smtp_prensa") as mock_smtp:
            resp = auth_client.post(
                f"/seleccion-femenina/firmables/{token}/paso/3",
                data=data3, follow_redirects=True,
            )
        assert resp.status_code == 200
        assert "Autorizaciones completadas".encode("utf-8") in resp.data
        assert mock_smtp.called

        with app.app_context():
            sesion = SesionFirmables.query.filter_by(preinscripcion_id=pid).first()
            assert sesion.estado == "completada"
            docs = DocumentoFirmado.query.filter_by(preinscripcion_id=pid).all()
            assert len(docs) == 3
            for d in docs:
                assert d.vigente is True
                assert d.version == 1
                firmas = FirmaTutorDocumento.query.filter_by(documento_id=d.id).all()
                assert len(firmas) == 2

        # El enlace ya usado no vuelve a mostrar el wizard
        resp = auth_client.get(f"/seleccion-femenina/firmables/{token}")
        assert resp.status_code == 200
        assert "Autorizaciones completadas".encode("utf-8") in resp.data

        # La lista de estado (staff) ya muestra los 3 como completados
        resp = auth_client.get(f"/autoclub/seleccion-femenina/{pid}/firmables")
        assert resp.status_code == 200
        assert resp.data.count(b"Completado") == 3
    finally:
        _borrar(app, pid)


def test_verificacion_ultimos_4_digitos_incorrecta_da_error(auth_client, auth_csrf_token, app):
    with app.app_context():
        p = _crear_preinscripcion(email="qa.verif@example.com", nombre="QA Verificacion")
        pid = p.id
    try:
        token = _preparar_enlace(auth_client, auth_csrf_token, pid, app)
        auth_client.post(
            f"/seleccion-femenina/firmables/{token}",
            data={"csrf_token": auth_csrf_token, "modo_tutores": "solo_uno", "motivo_solo_uno": "patria_potestad_compartida"},
            follow_redirects=True,
        )

        data = {
            "csrf_token": auth_csrf_token, "tiene_condicion_medica": "no", "art156": "1",
            "tutor1_nombre": "Madre Sola", "tutor1_dni": "33333333C",
            "tutor1_verificacion": "0000",  # no coincide con los últimos 4 del DNI
            "tutor1_firma": "1",
        }
        resp = auth_client.post(f"/seleccion-femenina/firmables/{token}/paso/1", data=data)
        assert resp.status_code == 200
        assert "no coinciden".encode("utf-8") in resp.data
        with app.app_context():
            assert DocumentoFirmado.query.filter_by(preinscripcion_id=pid).count() == 0
    finally:
        _borrar(app, pid)


def test_solo_un_tutor_custodia_exclusiva_exige_documento(auth_client, auth_csrf_token, app):
    with app.app_context():
        p = _crear_preinscripcion(email="qa.custodiafirmable@example.com", nombre="QA Custodia Firmable")
        pid = p.id
    try:
        token = _preparar_enlace(auth_client, auth_csrf_token, pid, app)
        resp = auth_client.post(
            f"/seleccion-femenina/firmables/{token}",
            data={"csrf_token": auth_csrf_token, "modo_tutores": "solo_uno", "motivo_solo_uno": "custodia_exclusiva"},
        )
        assert resp.status_code == 200
        assert "documento acreditativo".encode("utf-8") in resp.data
        with app.app_context():
            assert not SesionFirmables.query.filter_by(preinscripcion_id=pid).first().modo_tutores

        resp2 = auth_client.post(
            f"/seleccion-femenina/firmables/{token}",
            data={
                "csrf_token": auth_csrf_token, "modo_tutores": "solo_uno", "motivo_solo_uno": "custodia_exclusiva",
                "doc_custodia": (io.BytesIO(b"pdf falso"), "custodia.pdf"),
            },
            content_type="multipart/form-data", follow_redirects=True,
        )
        assert resp2.status_code == 200
        with app.app_context():
            sesion = SesionFirmables.query.filter_by(preinscripcion_id=pid).first()
            assert sesion is not None
            assert sesion.doc_custodia_path
            assert sesion.tutores_requeridos == 1
    finally:
        _borrar(app, pid)


def test_solo_un_tutor_sin_checkbox_art156_da_error(auth_client, auth_csrf_token, app):
    with app.app_context():
        p = _crear_preinscripcion(email="qa.art156@example.com", nombre="QA Art156")
        pid = p.id
    try:
        token = _preparar_enlace(auth_client, auth_csrf_token, pid, app)
        auth_client.post(
            f"/seleccion-femenina/firmables/{token}",
            data={"csrf_token": auth_csrf_token, "modo_tutores": "solo_uno", "motivo_solo_uno": "patria_potestad_compartida"},
            follow_redirects=True,
        )

        data = {"csrf_token": auth_csrf_token, "tiene_condicion_medica": "no"}
        data.update(_firma_tutor(1, "Tutor Solo", "44444444D"))
        # sin art156
        resp = auth_client.post(f"/seleccion-femenina/firmables/{token}/paso/1", data=data)
        assert resp.status_code == 200
        assert "artículo 156".encode("utf-8") in resp.data
        with app.app_context():
            assert DocumentoFirmado.query.filter_by(preinscripcion_id=pid).count() == 0
    finally:
        _borrar(app, pid)


def test_pdf_de_un_documento_firmado_se_descarga(auth_client, auth_csrf_token, app):
    with app.app_context():
        p = _crear_preinscripcion(email="qa.pdf@example.com", nombre="QA PDF")
        pid = p.id
    try:
        token = _preparar_enlace(auth_client, auth_csrf_token, pid, app)
        auth_client.post(
            f"/seleccion-femenina/firmables/{token}",
            data={"csrf_token": auth_csrf_token, "modo_tutores": "solo_uno", "motivo_solo_uno": "patria_potestad_compartida"},
            follow_redirects=True,
        )

        data = {"csrf_token": auth_csrf_token, "tiene_condicion_medica": "no", "art156": "1"}
        data.update(_firma_tutor(1, "Tutor Solo", "55555555E"))
        auth_client.post(f"/seleccion-femenina/firmables/{token}/paso/1", data=data)

        with app.app_context():
            doc = DocumentoFirmado.query.filter_by(preinscripcion_id=pid, tipo="aptitud_medica").first()
            doc_id = doc.id

        resp = auth_client.get(f"/autoclub/seleccion-femenina/{pid}/firmables/documento/{doc_id}/pdf")
        assert resp.status_code == 200
        assert resp.mimetype == "application/pdf"
        assert resp.data[:4] == b"%PDF"
    finally:
        _borrar(app, pid)


def test_correccion_crea_nueva_version_sin_borrar_la_anterior(auth_client, auth_csrf_token, app):
    with app.app_context():
        p = _crear_preinscripcion(email="qa.version@example.com", nombre="QA Version")
        pid = p.id
    try:
        # Primera sesión completa (solo un tutor, simplifica el test)
        for _ in range(2):
            token = _preparar_enlace(auth_client, auth_csrf_token, pid, app)
            auth_client.post(
                f"/seleccion-femenina/firmables/{token}",
                data={"csrf_token": auth_csrf_token, "modo_tutores": "solo_uno", "motivo_solo_uno": "patria_potestad_compartida"},
                follow_redirects=True,
            )

            for paso, extra in [(1, {"tiene_condicion_medica": "no"}), (2, {}), (3, {"checkbox_1": "1", "checkbox_2": "1", "checkbox_3": "1"})]:
                data = {"csrf_token": auth_csrf_token, "art156": "1", **extra}
                data.update(_firma_tutor(1, "Tutor Solo", "66666666F"))
                with patch("app.services.firmables_service.enviar_smtp_prensa"):
                    auth_client.post(f"/seleccion-femenina/firmables/{token}/paso/{paso}",
                                      data=data, follow_redirects=True)

        with app.app_context():
            docs = (DocumentoFirmado.query.filter_by(preinscripcion_id=pid, tipo="aptitud_medica")
                    .order_by(DocumentoFirmado.version).all())
            assert len(docs) == 2
            assert docs[0].version == 1 and docs[0].vigente is False
            assert docs[1].version == 2 and docs[1].vigente is True
    finally:
        _borrar(app, pid)


def test_entrevista_autoguardado_guarda_notas_y_valoraciones(auth_client, auth_csrf_token, app):
    with app.app_context():
        p = _crear_preinscripcion(email="qa.entrevista@example.com", nombre="QA Entrevista")
        pid = p.id
    try:
        resp = auth_client.post(
            f"/autoclub/seleccion-femenina/{pid}/entrevista/autoguardar",
            json={"notas": {"b1_1": "Sí, disponibilidad total.", "b2_8": "Le apasiona desde pequeña."},
                  "valoracion_bloque1": "alta", "valoracion_bloque2": "media"},
            headers={"X-CSRFToken": auth_csrf_token},
        )
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

        with app.app_context():
            e = EntrevistaPiloto.query.filter_by(preinscripcion_id=pid).first()
            assert e is not None
            assert e.nota("b1_1") == "Sí, disponibilidad total."
            assert e.nota("b2_8") == "Le apasiona desde pequeña."
            assert e.valoracion_bloque1 == "alta"
            assert e.valoracion_bloque2 == "media"
            assert e.fecha_entrevista is not None
            assert e.realizada_por_id is not None

        # Vuelve a guardar (segunda vez) — no duplica el registro
        auth_client.post(
            f"/autoclub/seleccion-femenina/{pid}/entrevista/autoguardar",
            json={"notas": {"b1_1": "Actualizado."}},
            headers={"X-CSRFToken": auth_csrf_token},
        )
        with app.app_context():
            assert EntrevistaPiloto.query.filter_by(preinscripcion_id=pid).count() == 1
            assert EntrevistaPiloto.query.filter_by(preinscripcion_id=pid).first().nota("b1_1") == "Actualizado."

        resp2 = auth_client.get(f"/autoclub/seleccion-femenina/{pid}/entrevista")
        assert resp2.status_code == 200
        assert "Actualizado.".encode("utf-8") in resp2.data
    finally:
        _borrar(app, pid)


def test_entrevista_ignora_claves_desconocidas(auth_client, auth_csrf_token, app):
    with app.app_context():
        p = _crear_preinscripcion(email="qa.entrevistaclaves@example.com", nombre="QA Claves")
        pid = p.id
    try:
        resp = auth_client.post(
            f"/autoclub/seleccion-femenina/{pid}/entrevista/autoguardar",
            json={"notas": {"clave_invalida": "no debería guardarse", "b1_2": "sí debería"}},
            headers={"X-CSRFToken": auth_csrf_token},
        )
        assert resp.status_code == 200
        with app.app_context():
            e = EntrevistaPiloto.query.filter_by(preinscripcion_id=pid).first()
            assert "clave_invalida" not in e.notas
            assert e.nota("b1_2") == "sí debería"
    finally:
        _borrar(app, pid)
