"""
Genera el PDF de un documento firmado (texto íntegro + datos de firma) para
adjuntarlo al email de confirmación y para poder descargarlo desde el CRM.
"""
import io

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from xml.sax.saxutils import escape

from app.services.firmables_textos import TEXTOS_FIRMABLE, TIPOS_FIRMABLE_LABELS, ART156_TEXTO

ROJO = colors.HexColor("#AD1726")
NEGRO = colors.HexColor("#0D0D0D")


def _estilos():
    hoja = getSampleStyleSheet()
    hoja.add(ParagraphStyle("TituloDoc", parent=hoja["Title"], fontSize=15, textColor=NEGRO, spaceAfter=4))
    hoja.add(ParagraphStyle("Cuerpo", parent=hoja["BodyText"], fontSize=9.5, leading=13, spaceAfter=8))
    hoja.add(ParagraphStyle("Etiqueta", parent=hoja["BodyText"], fontSize=9, textColor=colors.HexColor("#555555")))
    return hoja


def generar_pdf_documento(preinscripcion, documento):
    """documento: instancia de DocumentoFirmado ya guardada, con .firmas
    cargadas. Devuelve los bytes del PDF."""
    hoja = _estilos()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=18 * mm, bottomMargin=16 * mm, leftMargin=18 * mm, rightMargin=18 * mm,
    )
    elementos = []

    titulo = TIPOS_FIRMABLE_LABELS.get(documento.tipo, documento.tipo)
    elementos.append(Paragraph(escape(titulo), hoja["TituloDoc"]))
    elementos.append(Paragraph(
        f"Selección Femenina de Pilotos de Carcross — versión {documento.version} · "
        f"{documento.creado_en.strftime('%d/%m/%Y %H:%M') if documento.creado_en else ''}",
        hoja["Etiqueta"],
    ))
    elementos.append(Spacer(1, 8))

    datos_participante = [
        ["Participante", preinscripcion.nombre_completo],
        ["Fecha de nacimiento", preinscripcion.fecha_nacimiento.strftime("%d/%m/%Y") if preinscripcion.fecha_nacimiento else "—"],
    ]
    insc = preinscripcion.inscripcion_autorizacion
    if insc and insc.dni_nie_participante:
        datos_participante.append(["DNI/NIE", insc.dni_nie_participante])
    tabla = Table(datos_participante, colWidths=[110, 320])
    tabla.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#555555")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elementos.append(tabla)
    elementos.append(Spacer(1, 10))

    # Campos específicos del tipo de documento
    if documento.tipo == "aptitud_medica":
        datos_fisicos = [
            ["Altura", f"{preinscripcion.altura_cm} cm" if preinscripcion.altura_cm else "—"],
            ["Peso", f"{preinscripcion.peso_kg} kg" if preinscripcion.peso_kg else "—"],
            ["Talla de camiseta", preinscripcion.talla_camiseta or "—"],
            ["Talla de zapatillas", preinscripcion.talla_zapatillas or "—"],
        ]
        tabla_fisicos = Table(datos_fisicos, colWidths=[110, 320])
        tabla_fisicos.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#555555")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        elementos.append(Paragraph("<b>Datos físicos (para el equipamiento)</b>", hoja["Cuerpo"]))
        elementos.append(tabla_fisicos)
        elementos.append(Spacer(1, 8))
        if documento.tiene_condicion_medica:
            elementos.append(Paragraph(
                "☑ Declara que la participante <b>presenta</b> la(s) siguiente(s) condición(es) médica(s), "
                f"alergia(s) o limitación(es): {escape(documento.condicion_medica_detalle or '—')}",
                hoja["Cuerpo"],
            ))
        else:
            elementos.append(Paragraph(
                "☑ Declara que la participante <b>no padece</b> enfermedad, lesión ni condición física "
                "o psíquica que le impida participar con plenas facultades.",
                hoja["Cuerpo"],
            ))
    if documento.tipo == "disclaimer_conduccion":
        marcas = [
            (documento.checkbox_1, "Haber leído íntegramente el presente documento, comprender su contenido y aceptarlo en su totalidad."),
            (documento.checkbox_2, "Haber recibido información verbal sobre las normas de seguridad, el funcionamiento de la prueba y las responsabilidades que asume la participante."),
            (documento.checkbox_3, "Suscribir el presente documento de forma libre, voluntaria y con plena capacidad jurídica, en representación de la menor."),
        ]
        for marcado, texto in marcas:
            elementos.append(Paragraph(f"{'☑' if marcado else '☐'} {escape(texto)}", hoja["Cuerpo"]))
        if documento.participante_firma:
            elementos.append(Paragraph("☑ La participante (16 años o más) también firma este documento.", hoja["Cuerpo"]))

    if documento.art156_invocado:
        elementos.append(Spacer(1, 4))
        elementos.append(Paragraph(f"☑ {escape(ART156_TEXTO)}", hoja["Cuerpo"]))

    elementos.append(Spacer(1, 10))
    elementos.append(Paragraph("<b>Firmas</b>", hoja["Cuerpo"]))
    filas_firmas = [["Tutor/a", "DNI/NIE", "Fecha y hora", "Supervisado por"]]
    for f in sorted(documento.firmas, key=lambda x: x.numero):
        filas_firmas.append([
            f.nombre_completo, f.dni_nie,
            f.firma_en.strftime("%d/%m/%Y %H:%M") if f.firma_en else "—",
            f.usuario_staff.nombre if f.usuario_staff else "—",
        ])
    tabla_firmas = Table(filas_firmas, colWidths=[140, 90, 100, 100])
    tabla_firmas.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    elementos.append(tabla_firmas)
    elementos.append(Paragraph(
        "Firma electrónica simple registrada mediante enlace personal enviado a la familia (o de forma "
        "presencial en un dispositivo del organizador) — la IP registrada corresponde al dispositivo "
        "desde el que se completó la firma.",
        ParagraphStyle("Nota", parent=hoja["Etiqueta"], fontSize=7.5, spaceBefore=4),
    ))

    elementos.append(Spacer(1, 14))
    elementos.append(Paragraph("<b>Texto íntegro del documento</b>", hoja["Cuerpo"]))
    texto = TEXTOS_FIRMABLE.get(documento.tipo, "")
    for parrafo in texto.split("\n\n"):
        parrafo = parrafo.strip()
        if parrafo:
            elementos.append(Paragraph(escape(parrafo).replace("\n", "<br/>"), hoja["Cuerpo"]))

    doc.build(elementos)
    return buf.getvalue()
