"""
Textos íntegros de los 3 documentos firmables — copiados literalmente de
autorizaciones/*.md (fuente de verdad legal, no resumir ni parafrasear).
Se usan tanto en la pantalla del wizard (scrollable) como en el PDF
adjunto al email de confirmación.
"""

TIPOS_FIRMABLE = [
    ("aptitud_medica", "Declaración Responsable de Aptitud Médica"),
    ("asuncion_riesgo", "Declaración de Asunción de Riesgo de la Actividad"),
    ("disclaimer_conduccion", "Disclaimer y Normas de Seguridad — Prueba de Conducción"),
]
TIPOS_FIRMABLE_KEYS = [t[0] for t in TIPOS_FIRMABLE]
TIPOS_FIRMABLE_LABELS = dict(TIPOS_FIRMABLE)

TEXTO_APTITUD_MEDICA = """Declaración Responsable de Aptitud Médica
Selección Femenina de Pilotos de Carcross — Castilla-La Mancha

(Documento a firmar por ambos progenitores/tutores legales el día de las entrevistas)

Declaración

El/la abajo firmante, en calidad de progenitor/tutor legal de la menor arriba identificada, declara bajo su responsabilidad la opción marcada sobre la aptitud médica de la participante (ver más abajo), y además declara que:

- La participante no ha consumido alcohol, drogas, estimulantes, medicamentos o cualquier otra sustancia que pueda alterar su comportamiento o disminuir sus facultades para la conducción, ni las tomará durante las horas previas ni durante el desarrollo de las pruebas.
- En caso de que la participante deba tomar alguna medicación durante el proceso de selección, se compromete a comunicarlo de inmediato a la organización.
- No se aporta ni se exige justificante médico para esta declaración, siendo responsabilidad exclusiva de los progenitores/tutores legales la veracidad de lo aquí manifestado.
- Es consciente de que ocultar información médica relevante puede poner en riesgo la seguridad de la participante durante las pruebas, y exonera a la organización de responsabilidad derivada de datos omitidos o inexactos en esta declaración.

Esta declaración se recoge con la única finalidad de garantizar la seguridad de la participante durante el proceso de selección, y se trata conforme a lo establecido en la Política de Privacidad del proyecto, como dato de categoría especial (art. 9 RGPD), con acceso restringido al personal técnico y sanitario estrictamente necesario."""

TEXTO_ASUNCION_RIESGO = """Declaración de Asunción de Riesgo de la Actividad
Selección Femenina de Pilotos de Carcross — Castilla-La Mancha

(Documento a firmar por ambos progenitores/tutores legales el día de las entrevistas, previo a la participación de la menor en las pruebas físicas, psicofísicas y de conducción)

Declaración

El/la abajo firmante, en calidad de progenitor/tutor legal de la menor arriba identificada, declara ser plenamente consciente de que:

- La conducción de un vehículo, incluso en circuito cerrado y en condiciones controladas, y la participación en pruebas físicas y psicofísicas asociadas al motorsport, constituyen actividades de riesgo que pueden provocar, en caso de accidente, lesiones graves e incluso la muerte.
- Asume voluntariamente, en representación de la menor, dicho riesgo y las posibles consecuencias derivadas de su participación en el proceso de selección.
- Ha podido conocer y valorar, junto con la menor, la naturaleza de las pruebas a realizar (físicas, psicofísicas y de conducción), así como las normas de seguridad comunicadas por la organización.
- La menor se obliga a adaptar su conducción, esfuerzo físico y comportamiento a las indicaciones del personal técnico de la organización (CD Autoclub La Dehesa) en todo momento durante el proceso.
- Es consciente de que el incumplimiento de las normas de seguridad comunicadas por la organización puede ser motivo de exclusión inmediata del proceso de selección.

Esta declaración se otorga como complemento a la Declaración Responsable de Aptitud Médica y al documento de Inscripción y Autorización General del Proceso de Selección ya firmados, y no sustituye a ninguno de ellos.

(Nota: para la jornada específica de pruebas de conducción del 26 de septiembre de 2026, esta declaración general de riesgo se complementa y detalla en el documento "Disclaimer y Normas de Seguridad — Prueba de Conducción", que recoge las normas técnicas concretas de circulación en pista, equipamiento y procedimiento en caso de incidente.)"""

TEXTO_DISCLAIMER_CONDUCCION = """Disclaimer y Normas de Seguridad — Prueba de Conducción
Selección Femenina de Pilotos de Carcross — 26 de septiembre de 2026
Circuito La Dehesa, Alcolea del Pinar (Guadalajara)

(Documento a firmar por la participante —si tiene 16 años o más, junto con su tutor/a— y por ambos progenitores/tutores legales, presencialmente el día de la prueba o con antelación suficiente)

Requisitos para la participación

Al tratarse de un proceso dirigido exclusivamente a menores de edad (14 a 18 años), la participación en la prueba de conducción exige en todo caso la autorización previa y la presencia de su progenitor/tutor legal, quien deberá encontrarse en las instalaciones durante el desarrollo de la actividad.

La participante no debe padecer enfermedad, lesión o condición física o psíquica que le impida participar en la actividad con plenas facultades, conforme a lo declarado en la Declaración Responsable de Aptitud Médica ya suscrita. No podrá haber consumido alcohol, drogas, estimulantes, medicamentos o cualquier otra sustancia que pueda alterar su comportamiento o disminuir sus facultades para la conducción, ni durante las horas previas a la actividad ni durante su desarrollo. En caso de haber tomado sustancias de esta índole, la participante o su tutor/a deberán comunicarlo de inmediato a la organización y esta se abstendrá de permitir el uso del vehículo.

Seguro. La participación en la prueba de conducción está cubierta por la póliza de responsabilidad civil y accidentes contratada por CD Autoclub La Dehesa para todas las participantes del proceso de selección, conforme a lo indicado en las Bases Legales del concurso.

Normas de seguridad de obligado cumplimiento

La participante y su progenitor/tutor legal declaran haber sido informados y conocer las siguientes normas mínimas de seguridad, cuyo incumplimiento será motivo de exclusión inmediata del proceso de selección:

Equipamiento personal. Es responsabilidad de la participante utilizar en todo momento el equipamiento de protección facilitado por la organización, en perfecto estado de uso. El equipamiento mínimo obligatorio es: casco correctamente ajustado, guantes y mono.

Conducción en pista. Está prohibido circular en sentido contrario en cualquier circunstancia. Es obligatorio mantener en todo momento una velocidad adecuada a las posibilidades de la conductora y a las condiciones de la pista. La prueba tiene como objeto la evaluación de las habilidades de conducción y la seguridad, no la consecución de velocidades máximas. Ante bandera amarilla, la participante deberá reducir la velocidad de forma inmediata y extremar las medidas de seguridad. Está terminantemente prohibida la celebración de carreras o competiciones no supervisadas dentro de la prueba.

En caso de avería o accidente. La participante no deberá salir del vehículo ni invadir la pista andando en ninguna circunstancia. Deberá apartar el vehículo fuera de la trazada por sus propios medios si ello es posible sin abandonar el habitáculo, y ponerse de inmediato a disposición del personal organizador. Cualquier salida de pista, colisión, impacto, avería o incidente deberá comunicarse de forma inmediata a la organización, cumplimentándose en ese mismo momento la correspondiente declaración de incidente.

En el paddock y zonas auxiliares. Se circulará siempre a baja velocidad y con extrema precaución. El abandono de la pista se realizará únicamente por las salidas habilitadas a tal efecto.

Imágenes y grabaciones

La captación y el uso de imágenes y grabaciones de la participante durante la prueba de conducción se rigen por la Autorización de Captación y Uso de Imagen ya firmada por sus progenitores/tutores legales como parte del documento de Inscripción y Autorización General del Proceso de Selección. Este disclaimer no amplía ni sustituye dicha autorización: si la familia marcó "no autorizo", esa decisión se mantiene también para la jornada de la prueba de conducción.

Responsabilidad de la participante y su familia

Asunción de riesgos. El progenitor/tutor legal declara ser plenamente consciente de que la conducción de un vehículo, incluso en circuito cerrado y en condiciones controladas, constituye una actividad de riesgo que puede provocar, en caso de accidente, lesiones graves. Asume voluntariamente dicho riesgo en representación de la menor, en los términos ya recogidos en la Declaración de Asunción de Riesgo de la Actividad.

Responsabilidad por daños al vehículo. En caso de que la participante ocasione daños al vehículo por una conducción imprudente o por incumplimiento de las normas de seguridad de este documento —y no por el desgaste o riesgo ordinario propio de una actividad de aprendizaje de conducción—, el progenitor/tutor legal podrá ser requerido a hacerse cargo de los costes de reparación, de acuerdo con presupuesto detallado emitido por el taller designado por la organización.

Responsabilidad por daños a terceros e instalaciones. La participante y su familia responden frente a la organización y frente a terceros por los daños y lesiones que se originen como consecuencia del incumplimiento de las normas de seguridad de este documento, así como por los daños causados por imprudencia, culpa o negligencia claramente imputable a la conducción.

Comunicación de incidentes. En caso de accidente, deberá informarse a la organización de forma inmediata, así como de los daños o lesiones producidos en el momento del percance.

Exoneración de responsabilidad de la organización

El progenitor/tutor legal exime a CD Autoclub La Dehesa, Feeling Experience y demás entidades colaboradoras e impulsoras del proyecto, así como a sus socios, administradores, representantes, trabajadores y/o colaboradores, de responsabilidad civil o penal derivada de la participación en esta prueba, salvo en los supuestos de dolo o negligencia grave imputable a la organización, y sin perjuicio de la cobertura de la póliza de seguro contratada conforme a lo indicado anteriormente.

Cancelaciones y exclusiones

Si por razones de accidente, avería o comportamiento inadecuado de las participantes la organización se viese obligada a suspender la prueba o parte de ella, esto no generará derecho a compensación, sin perjuicio de que la organización ofrezca, si es posible, una nueva fecha para la participante afectada.

Será motivo de exclusión inmediata del proceso de selección cualquiera de las siguientes conductas: incumplimiento de las normas de seguridad establecidas en este documento; conducción inadecuada o imprudente a juicio de la organización; desobediencia a las instrucciones del personal técnico; celebración de carreras o competiciones no supervisadas; uso o sospecha de uso de sustancias, alcohol y/o drogas.

Los datos personales obtenidos en este documento serán tratados conforme a la Política de Privacidad del proyecto, siendo CD Autoclub La Dehesa el responsable del tratamiento. Puede ejercer sus derechos de acceso, rectificación, supresión, limitación, oposición y portabilidad dirigiéndose por escrito a info@autoclubladehesa.com."""

TEXTOS_FIRMABLE = {
    "aptitud_medica": TEXTO_APTITUD_MEDICA,
    "asuncion_riesgo": TEXTO_ASUNCION_RIESGO,
    "disclaimer_conduccion": TEXTO_DISCLAIMER_CONDUCCION,
}

ART156_TEXTO = (
    "Declaro que actúo con el conocimiento y el consentimiento del otro progenitor/tutor legal "
    "de la menor, en virtud de la presunción de consentimiento para los actos relativos a los "
    "hijos menores prevista en el artículo 156 del Código Civil, y asumo la responsabilidad de "
    "que dicho consentimiento es real."
)
