from datetime import datetime, timedelta
from app.extensions import db

# Días de validez del enlace de firmables antes de caducar por sí solo,
# igual que el enlace de Inscripción y Autorización General.
DIAS_VALIDEZ_TOKEN_FIRMABLES = 30

MOTIVOS_SOLO_UN_TUTOR = [
    ("custodia_exclusiva", "Custodia exclusiva o tutela única"),
    ("patria_potestad_compartida", "Ambos conservan la patria potestad, pero hoy solo puede asistir uno"),
]
MOTIVOS_SOLO_UN_TUTOR_KEYS = [m[0] for m in MOTIVOS_SOLO_UN_TUTOR]


class SesionFirmables(db.Model):
    """Una sesión agrupa los 3 documentos firmables (o su corrección) de
    una piloto, rellenados a través del mismo enlace de un solo uso —
    presencialmente (el staff lo abre y entrega el dispositivo) o en
    remoto (por email o copiando el enlace). Agrupa las versiones creadas
    en la sesión para poder enviar la copia por email de una sola vez al
    terminar."""
    __tablename__ = "sesiones_firmables"

    id                = db.Column(db.Integer, primary_key=True)
    preinscripcion_id = db.Column(db.Integer, db.ForeignKey("preinscripciones_carcross.id", ondelete="CASCADE"),
                                   nullable=False, index=True)

    # "" hasta que se elige (no None: la columna ya existía como NOT NULL
    # en bases de datos desplegadas antes de que el enlace se pudiera crear
    # sin conocer el modo de antemano — usar cadena vacía evita tener que
    # alterar esa restricción, SQLite no admite quitar NOT NULL sin recrear
    # la tabla). "" | "ambos" | "solo_uno".
    modo_tutores      = db.Column(db.String(20), default="", nullable=False)
    motivo_solo_uno   = db.Column(db.String(40), default="")  # ver MOTIVOS_SOLO_UN_TUTOR
    doc_custodia_path = db.Column(db.String(300), nullable=True)

    # Enlace de un solo uso, igual que el de Inscripción y Autorización
    # General: permite completar el wizard tanto presencialmente (el staff
    # lo abre en el dispositivo y se lo entrega a la familia) como en
    # remoto (se envía por email o se copia el enlace para WhatsApp, etc.).
    token           = db.Column(db.String(64), unique=True, nullable=True, index=True)
    token_creado_en = db.Column(db.DateTime, nullable=True)

    usuario_staff_id  = db.Column(db.Integer, db.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    ip                = db.Column(db.String(45), default="")  # dispositivo desde el que se firmó

    estado            = db.Column(db.String(20), default="en_progreso", nullable=False)  # en_progreso | completada
    iniciada_en       = db.Column(db.DateTime, default=datetime.utcnow)
    completada_en     = db.Column(db.DateTime, nullable=True)

    preinscripcion = db.relationship("PreinscripcionCarcross", backref=db.backref(
        "sesiones_firmables", cascade="all, delete-orphan", lazy="dynamic",
        order_by="SesionFirmables.iniciada_en.desc()",
    ))
    usuario_staff = db.relationship("Usuario", foreign_keys=[usuario_staff_id])
    documentos = db.relationship("DocumentoFirmado", backref="sesion", cascade="all, delete-orphan")

    @property
    def token_expirado(self):
        if not self.token_creado_en:
            return False
        return datetime.utcnow() > self.token_creado_en + timedelta(days=DIAS_VALIDEZ_TOKEN_FIRMABLES)

    @property
    def token_valido(self):
        return self.estado == "en_progreso" and not self.token_expirado

    @property
    def requiere_documento_custodia(self):
        return self.modo_tutores == "solo_uno" and self.motivo_solo_uno == "custodia_exclusiva"

    @property
    def invoca_articulo_156(self):
        return self.modo_tutores == "solo_uno" and self.motivo_solo_uno == "patria_potestad_compartida"

    @property
    def tutores_requeridos(self):
        return 1 if self.modo_tutores == "solo_uno" else 2


class DocumentoFirmado(db.Model):
    """Una versión concreta de uno de los 3 documentos firmables para una
    piloto. Un documento firmado nunca se edita: una corrección crea una
    fila nueva con version+1 y marca la anterior vigente=False."""
    __tablename__ = "documentos_firmados"

    id                = db.Column(db.Integer, primary_key=True)
    preinscripcion_id = db.Column(db.Integer, db.ForeignKey("preinscripciones_carcross.id", ondelete="CASCADE"),
                                   nullable=False, index=True)
    sesion_id         = db.Column(db.Integer, db.ForeignKey("sesiones_firmables.id", ondelete="CASCADE"), nullable=False)

    tipo              = db.Column(db.String(40), nullable=False, index=True)  # ver TIPOS_FIRMABLE_KEYS
    version           = db.Column(db.Integer, default=1, nullable=False)
    vigente           = db.Column(db.Boolean, default=True, nullable=False, index=True)

    # Aptitud médica
    tiene_condicion_medica   = db.Column(db.Boolean, nullable=True)
    condicion_medica_detalle = db.Column(db.Text, default="")

    # Disclaimer conducción (3 checkboxes del documento + firma opcional de la propia participante)
    checkbox_1          = db.Column(db.Boolean, default=False, nullable=False)
    checkbox_2          = db.Column(db.Boolean, default=False, nullable=False)
    checkbox_3          = db.Column(db.Boolean, default=False, nullable=False)
    participante_firma  = db.Column(db.Boolean, default=False, nullable=False)

    # Presunción de consentimiento art. 156 CC (modo solo_uno / patria potestad compartida)
    art156_invocado     = db.Column(db.Boolean, default=False, nullable=False)

    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    firmas = db.relationship("FirmaTutorDocumento", backref="documento", cascade="all, delete-orphan")

    __table_args__ = (db.UniqueConstraint("preinscripcion_id", "tipo", "version", name="uq_doc_preinsc_tipo_version"),)


class FirmaTutorDocumento(db.Model):
    """Firma electrónica simple de un progenitor/tutor sobre un documento
    concreto — nombre/DNI tecleados por la propia persona, no autocompletados
    por el staff. IP es la del dispositivo del organizador (firma presencial,
    dispositivo compartido), no un identificador del firmante."""
    __tablename__ = "firmas_tutor_documento"

    id           = db.Column(db.Integer, primary_key=True)
    documento_id = db.Column(db.Integer, db.ForeignKey("documentos_firmados.id", ondelete="CASCADE"),
                              nullable=False, index=True)
    numero       = db.Column(db.Integer, nullable=False)  # 1 o 2

    nombre_completo       = db.Column(db.String(150), nullable=False)
    dni_nie                = db.Column(db.String(20), nullable=False)
    verificacion_ultimos4  = db.Column(db.String(10), default="")

    firma_en      = db.Column(db.DateTime, default=datetime.utcnow)
    ip            = db.Column(db.String(45), default="")  # dispositivo del organizador
    usuario_staff_id = db.Column(db.Integer, db.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)

    usuario_staff = db.relationship("Usuario", foreign_keys=[usuario_staff_id])

    __table_args__ = (db.UniqueConstraint("documento_id", "numero", name="uq_firma_documento_numero"),)
