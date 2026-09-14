"""
Genera el PDF de la Inscripción y Autorización General del Proceso de
Selección ya firmada — mismo patrón que app/services/firmables_pdf.py,
para poder descargarla desde el CRM igual que los otros 3 firmables.
"""
import base64
import io

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from xml.sax.saxutils import escape

ROJO = colors.HexColor("#AD1726")
NEGRO = colors.HexColor("#0D0D0D")

# Texto íntegro de las cláusulas firmadas — mismo contenido que se muestra en
# app/templates/seleccion_femenina/inscripcion_form.html (secciones 4 a 10),
# para que el PDF descargado deje constancia completa de lo que se firmó, no
# solo de los datos rellenados. Cada tupla es (título de la sección, lista de
# párrafos en ese apartado).
CLAUSULAS_INSCRIPCION = [
    ("4. Fases del proceso para las que se otorga esta autorización", [
        "Este documento formaliza la inscripción oficial de la participante (posterior a la preinscripción "
        "informativa ya realizada) y autoriza su participación en la totalidad del proceso de selección, "
        "compuesto por las siguientes fases: 1) Preinscripción de las interesadas (ya completada). "
        "2) Inscripción formal vía email/CRM (el presente documento). 3) Entrevista personal. "
        "4) Pruebas físicas. 5) Pruebas psicofísicas. 6) Pruebas de conducción.",
    ]),
    ("5. Autorización de participación", [
        "Mediante la firma del presente documento, ambos progenitores/tutores legales autorizan expresamente "
        "a la menor arriba identificada a participar en la totalidad de las fases descritas en el punto 4, "
        "incluyendo la entrevista personal y las pruebas físicas, psicofísicas y de conducción que se "
        "celebrarán en el Circuito La Dehesa (Alcolea del Pinar, Guadalajara) en las fechas comunicadas por "
        "la organización.",
    ]),
    ("6. Declaración responsable de experiencia previa de conducción/pilotaje", [
        "Declaro que la información aportada es veraz, siendo consciente de que no puede participar en este "
        "proceso quien disponga de licencia federativa de competición en vigor o trayectoria profesional/"
        "semiprofesional acreditada, conforme al punto 4 de las Bases Legales del concurso.",
    ]),
    ("7. Tratamiento de datos personales durante todo el proceso", [
        "Se informa a los progenitores/tutores legales de que, a lo largo del proceso de selección, se "
        "recogerán y tratarán los siguientes datos de la participante: notas y valoración escrita del "
        "entrevistador durante la entrevista personal; resultados y valoraciones de las pruebas físicas, "
        "psicofísicas y de conducción.",
        "Estos datos se tratarán conforme a lo establecido en la Política de Privacidad del proyecto, siendo "
        "CD Autoclub La Dehesa el responsable del tratamiento, con la finalidad exclusiva de gestionar el "
        "proceso de selección. Se conservarán durante el desarrollo del proceso y se eliminarán en el plazo "
        "indicado en dicha política una vez finalizado, salvo que la candidata resulte seleccionada, en cuyo "
        "caso se conservarán conforme a las condiciones del programa y, en su caso, del contrato o "
        "precontrato posterior con el club.",
    ]),
    ("8. Autorización de captación y uso de imagen", [
        "Se informa a los progenitores/tutores legales de que durante la ponencia, la entrevista, las "
        "pruebas de selección y, en su caso, la posterior participación en el Campeonato de España de "
        "Rallycross (CERX), se realizarán fotografías y/o vídeos de la participante, con la finalidad de "
        "difundir el proyecto en las redes sociales y canales de comunicación de CD Autoclub La Dehesa y de "
        "las entidades impulsoras y colaboradoras (Delegación de Igualdad de la JCCM, Instituto de la Mujer "
        "de Castilla-La Mancha, Motorsport Ibérica, Feeling Experience).",
        "Esta autorización es independiente del resto de consentimientos de este documento y puede ser "
        "revocada en cualquier momento, sin que ello afecte a la participación de la menor en el proceso, "
        "dirigiéndose por escrito a info@autoclubladehesa.com.",
    ]),
    ("9. Compromisos y deberes de la participante y su entorno familiar", [
        "Al inscribirse en el proceso de selección, la participante y sus progenitores/tutores legales "
        "asumen los siguientes compromisos:",
        "a) Participar en todas las pruebas del programa de selección conforme al calendario establecido "
        "por la organización.",
        "b) Asumir los valores del Autoclub, así como su código de conducta y disciplina deportiva, "
        "incluyendo: comportamiento respetuoso en el paddock, principios de juego limpio, uso responsable de "
        "redes sociales en relación con el proyecto, y respeto a los compromisos con los patrocinadores de "
        "la escudería. Estos compromisos alcanzan tanto a la participante como a su entorno familiar "
        "directo, en aquello que razonablemente pueda afectar a la imagen del proyecto.",
        "c) Participación en el CERX, en caso de resultar seleccionada al finalizar el proceso, conforme a "
        "las condiciones descritas en el Anexo II.",
        "d) Compromiso de prioridad con Autoclub La Dehesa durante la temporada 2027, limitado a autocross y "
        "rallycross, en caso de resultar seleccionada: la piloto se compromete a no competir en pruebas "
        "oficiales de autocross o rallycross bajo los colores de otra escudería distinta de Autoclub La "
        "Dehesa durante dicha temporada, salvo autorización expresa y por escrito del club. Este compromiso "
        "está directamente vinculado a la formación, equipamiento, acompañamiento técnico y plaza de "
        "competición recibidos como parte del programa y el premio. Este compromiso se limita exclusivamente "
        "a las disciplinas de autocross y rallycross y no restringe en ningún caso la participación de la "
        "piloto, de forma amateur o profesional, en cualquier otra disciplina del motorsport (rally, "
        "circuito, karting, resistencia u otras), ni con Autoclub La Dehesa ni con cualquier otra escudería "
        "o equipo. El incumplimiento de este compromiso de prioridad por parte de la piloto seleccionada "
        "conllevará una penalización económica de 2.000 € (dos mil euros), a cargo de sus progenitores/"
        "tutores legales firmantes del presente documento, a abonar a CD Autoclub La Dehesa en concepto de "
        "resarcimiento por los costes de formación, equipamiento, acompañamiento técnico y plaza de "
        "competición asumidos por la organización como parte del programa y el premio. Esta penalización no "
        "será exigible cuando el incumplimiento se deba a una causa de fuerza mayor debidamente justificada "
        "(entre otras, lesión o enfermedad grave, u otras circunstancias sobrevenidas ajenas a la voluntad de "
        "la piloto y su familia).",
        "e) Cumplir con las directrices de la organización durante todo el proceso de selección, con "
        "especial atención a las normas de seguridad comunicadas por el personal técnico en cada fase.",
        "Anexo I — El programa de selección cubre: mecánicos, vehículos (Yacar de carcross) utilizados "
        "durante las pruebas, evaluadores, entrevistadores, instalaciones (Circuito La Dehesa), material "
        "necesario para las pruebas, uso del circuito. El programa de selección NO cubre: desplazamiento de "
        "la participante y su familia hasta la sede de las pruebas, manutención y alojamiento durante los "
        "días de pruebas, equipamiento personal de la participante (salvo el que la organización decida "
        "proporcionar), y cualquier gasto médico no derivado directamente de un incidente ocurrido durante "
        "las pruebas y cubierto por el seguro de la organización.",
        "Anexo II — El premio cubre: equipo (mono, casco u otro material específico de competición, según se "
        "determine), vehículo de competición, inscripción en la prueba oficial del CERX (Motorland), "
        "formación específica previa a la competición, dirección deportiva durante la prueba, y traslado y "
        "alojamiento durante la prueba del CERX para dos personas: la piloto ganadora y un/a acompañante "
        "tutor/a. Traslados y alojamiento de personas adicionales (más allá de la piloto y un/a tutor/a) "
        "corren por cuenta de la familia.",
    ]),
    ("10. Aceptación de las Bases Legales del concurso", [
        "Declaro haber leído y acepto en su integridad las Bases Legales del concurso «Selección Femenina de "
        "Pilotos de Carcross», en representación de la menor arriba identificada.",
    ]),
]


def _estilos():
    hoja = getSampleStyleSheet()
    hoja.add(ParagraphStyle("TituloDoc", parent=hoja["Title"], fontSize=15, textColor=NEGRO, spaceAfter=4))
    hoja.add(ParagraphStyle("Cuerpo", parent=hoja["BodyText"], fontSize=9.5, leading=13, spaceAfter=6))
    hoja.add(ParagraphStyle("Etiqueta", parent=hoja["BodyText"], fontSize=9, textColor=colors.HexColor("#555555")))
    hoja.add(ParagraphStyle("Apartado", parent=hoja["BodyText"], fontSize=10, leading=13, spaceBefore=8, spaceAfter=3, textColor=NEGRO))
    return hoja


def _si_no(valor):
    if valor is True:
        return "Sí"
    if valor is False:
        return "No"
    return "—"


def generar_pdf_inscripcion(preinscripcion, inscripcion):
    """inscripcion: InscripcionAutorizacion ya completada, con .tutores
    cargados. Devuelve los bytes del PDF."""
    hoja = _estilos()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=18 * mm, bottomMargin=16 * mm, leftMargin=18 * mm, rightMargin=18 * mm,
    )
    elementos = []

    elementos.append(Paragraph("Inscripción y Autorización General del Proceso de Selección", hoja["TituloDoc"]))
    elementos.append(Paragraph(
        f"Selección Femenina de Pilotos de Carcross · "
        f"Completado el {inscripcion.completado_en.strftime('%d/%m/%Y %H:%M') if inscripcion.completado_en else '—'}",
        hoja["Etiqueta"],
    ))
    elementos.append(Spacer(1, 8))

    datos_participante = [
        ["Participante", preinscripcion.nombre_completo],
        ["Fecha de nacimiento", preinscripcion.fecha_nacimiento.strftime("%d/%m/%Y") if preinscripcion.fecha_nacimiento else "—"],
        ["DNI/NIE", inscripcion.dni_nie_participante or "—"],
        ["Localidad", preinscripcion.localidad or "—"],
        ["Email", preinscripcion.email or "—"],
        ["Teléfono", preinscripcion.telefono or "—"],
    ]
    tabla = Table(datos_participante, colWidths=[110, 320])
    tabla.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#555555")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elementos.append(tabla)
    elementos.append(Spacer(1, 10))

    elementos.append(Paragraph("<b>Contacto de emergencia</b>", hoja["Cuerpo"]))
    elementos.append(Paragraph(
        f"{inscripcion.emergencia_nombre or '—'} · {inscripcion.emergencia_telefono or '—'} "
        f"({inscripcion.emergencia_relacion or '—'})",
        hoja["Cuerpo"],
    ))

    elementos.append(Paragraph("<b>Experiencia previa</b>", hoja["Cuerpo"]))
    elementos.append(Paragraph(
        f"Conducción: {escape(inscripcion.experiencia_conduccion or '—')}<br/>"
        f"Competición: {escape(inscripcion.experiencia_competicion or '—')}<br/>"
        f"Licencia federativa: {_si_no(inscripcion.licencia_federativa)}"
        + (f" — {escape(inscripcion.licencia_federativa_detalle)}" if inscripcion.licencia_federativa and inscripcion.licencia_federativa_detalle else ""),
        hoja["Cuerpo"],
    ))

    elementos.append(Spacer(1, 6))
    elementos.append(Paragraph("<b>Consentimientos y autorizaciones</b>", hoja["Cuerpo"]))
    filas_consentimientos = [
        ["Autorización de participación en el proceso", _si_no(inscripcion.consiente_participacion)],
        ["Tratamiento de datos personales del proceso", _si_no(inscripcion.consiente_datos_personales)],
        ["Autorización de imagen", "Autoriza" if inscripcion.autorizacion_imagen == "autoriza"
            else ("No autoriza" if inscripcion.autorizacion_imagen == "no_autoriza" else "—")],
        ["Aceptación de las Bases Legales", _si_no(inscripcion.acepta_bases_legales)],
        ["Aceptación de compromisos y deberes", _si_no(inscripcion.acepta_compromisos)],
    ]
    tabla_consent = Table(filas_consentimientos, colWidths=[300, 130])
    tabla_consent.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    elementos.append(tabla_consent)

    if inscripcion.solo_un_tutor:
        elementos.append(Spacer(1, 6))
        elementos.append(Paragraph(
            "Firma un único progenitor/tutor legal (custodia exclusiva u otra situación legal)"
            + (" — documento acreditativo adjunto en el CRM." if inscripcion.doc_custodia_path else " — SIN documento acreditativo adjunto."),
            hoja["Cuerpo"],
        ))

    elementos.append(Spacer(1, 14))
    elementos.append(Paragraph("<b>Texto íntegro de las cláusulas firmadas</b>", hoja["Cuerpo"]))
    for titulo, parrafos in CLAUSULAS_INSCRIPCION:
        elementos.append(Paragraph(escape(titulo), hoja["Apartado"]))
        for parrafo in parrafos:
            elementos.append(Paragraph(escape(parrafo), hoja["Cuerpo"]))

    elementos.append(Spacer(1, 12))
    elementos.append(Paragraph("<b>Firmas</b>", hoja["Cuerpo"]))
    for t in inscripcion.tutores:
        elementos.append(Paragraph(
            f"<b>Tutor/a {t.numero}:</b> {escape(t.nombre_completo)} ({escape(t.dni_nie)}) — "
            f"{escape(t.email)} · {escape(t.telefono)} · {escape(t.relacion_menor or '—')}<br/>"
            f"Firmado el {t.firma_en.strftime('%d/%m/%Y %H:%M') if t.firma_en else '—'} desde IP {t.firma_ip or '—'}",
            hoja["Cuerpo"],
        ))
        if t.firma_dibujo and t.firma_dibujo.startswith("data:image"):
            try:
                header, b64data = t.firma_dibujo.split(",", 1)
                img_bytes = base64.b64decode(b64data)
                img = Image(io.BytesIO(img_bytes), width=140, height=45)
                elementos.append(img)
            except Exception:
                pass
        elementos.append(Spacer(1, 6))

    doc.build(elementos)
    return buf.getvalue()
