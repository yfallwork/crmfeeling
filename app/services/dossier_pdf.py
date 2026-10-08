"""
Dossier completo de una piloto: une en un único PDF la Inscripción y
Autorización General y los 3 firmables (aptitud médica, asunción de riesgo,
disclaimer de la prueba de conducción) ya firmados, cada uno con su texto
íntegro, los datos declarados y las firmas — reutilizando los generadores
de app/services/inscripcion_pdf.py y app/services/firmables_pdf.py.
"""
import io

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak

from app.services.inscripcion_pdf import elementos_inscripcion, _estilos
from app.services.firmables_pdf import elementos_documento
from app.services.firmables_textos import TIPOS_FIRMABLE_KEYS


def generar_pdf_dossier(preinscripcion):
    """Devuelve los bytes del PDF con todo lo firmado por la familia de
    `preinscripcion` hasta el momento (inscripción + firmables vigentes).
    Si no hay nada firmado todavía, el PDF solo contiene una portada
    indicándolo — nunca lanza una excepción por falta de documentos."""
    hoja = _estilos()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=18 * mm, bottomMargin=16 * mm, leftMargin=18 * mm, rightMargin=18 * mm,
    )
    elementos = []

    elementos.append(Paragraph(f"Dossier de autorizaciones — {preinscripcion.nombre_completo}", hoja["TituloDoc"]))
    elementos.append(Paragraph(
        "Selección Femenina de Pilotos de Carcross — todos los documentos firmados por la familia, "
        "con su texto íntegro, los datos declarados y las firmas.",
        hoja["Etiqueta"],
    ))

    hay_contenido = False

    inscripcion = preinscripcion.inscripcion_autorizacion
    if inscripcion and inscripcion.completo:
        elementos.append(PageBreak())
        elementos.extend(elementos_inscripcion(preinscripcion, inscripcion, hoja))
        hay_contenido = True

    from app.models.firmable import DocumentoFirmado
    for tipo in TIPOS_FIRMABLE_KEYS:
        documento = (DocumentoFirmado.query
                     .filter_by(preinscripcion_id=preinscripcion.id, tipo=tipo, vigente=True)
                     .order_by(DocumentoFirmado.version.desc()).first())
        if not documento:
            continue
        elementos.append(PageBreak())
        elementos.extend(elementos_documento(preinscripcion, documento, hoja))
        hay_contenido = True

    if not hay_contenido:
        elementos.append(Spacer(1, 20))
        elementos.append(Paragraph(
            "Todavía no hay ningún documento firmado por la familia para esta piloto.",
            hoja["Cuerpo"],
        ))

    doc.build(elementos)
    return buf.getvalue()
