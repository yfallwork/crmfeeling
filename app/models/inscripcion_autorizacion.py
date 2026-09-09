from datetime import datetime, timedelta
from app.extensions import db

# Días de validez del enlace de inscripción antes de caducar por sí solo
# (además de invalidarse en el momento en que se completa el formulario).
DIAS_VALIDEZ_TOKEN = 30

ESTADOS_INSCRIPCION_AUTORIZACION = ["pendiente", "completado"]


class InscripcionAutorizacion(db.Model):
    """Formulario de 'Inscripción y Autorización General del Proceso de
    Selección' — sustituye al papel firmado por ambos progenitores/tutores
    legales antes de la fase de entrevistas. Uno por candidata (1:1 con
    PreinscripcionCarcross), accesible públicamente solo mediante `token`."""
    __tablename__ = "inscripciones_autorizacion"

    id                = db.Column(db.Integer, primary_key=True)
    preinscripcion_id = db.Column(db.Integer, db.ForeignKey("preinscripciones_carcross.id", ondelete="CASCADE"),
                                   nullable=False, unique=True, index=True)

    token             = db.Column(db.String(64), unique=True, nullable=False, index=True)
    token_creado_en   = db.Column(db.DateTime, default=datetime.utcnow)
    token_usado_en    = db.Column(db.DateTime, nullable=True)  # se rellena al completar: invalida el enlace

    estado            = db.Column(db.String(20), default="pendiente", nullable=False)
    completado_en     = db.Column(db.DateTime, nullable=True)

    solo_un_tutor     = db.Column(db.Boolean, default=False, nullable=False)
    doc_custodia_path = db.Column(db.String(300), nullable=True)  # ruta relativa a static/, si solo_un_tutor

    # --- Punto 1: datos de la participante (algunos precargados desde la
    # preinscripción y corregibles aquí; dni_nie es nuevo, no existía) ---
    dni_nie_participante  = db.Column(db.String(20), default="")

    # --- Punto 3: contacto de emergencia ---
    emergencia_nombre    = db.Column(db.String(150), default="")
    emergencia_telefono  = db.Column(db.String(30), default="")
    emergencia_relacion  = db.Column(db.String(100), default="")

    # --- Punto 6: declaración responsable de aptitud médica ---
    tiene_condicion_medica  = db.Column(db.Boolean, nullable=True)  # None = aún no declarado
    condicion_medica_detalle = db.Column(db.Text, default="")

    # --- Punto 7: experiencia previa de conducción/pilotaje ---
    experiencia_conduccion   = db.Column(db.Text, default="")
    experiencia_competicion  = db.Column(db.Text, default="")
    licencia_federativa      = db.Column(db.Boolean, nullable=True)
    licencia_federativa_detalle = db.Column(db.String(200), default="")

    # --- Checkboxes de consentimiento: independientes entre sí, cada uno
    # auditable/revocable por separado (nunca un único "aceptado_todo") ---
    consiente_participacion    = db.Column(db.Boolean, default=False, nullable=False)  # punto 5
    consiente_datos_salud      = db.Column(db.Boolean, default=False, nullable=False)  # punto 6
    consiente_datos_personales = db.Column(db.Boolean, default=False, nullable=False)  # punto 8
    # Punto 9: mutuamente excluyente, sin default -> "" hasta que se elige.
    autorizacion_imagen        = db.Column(db.String(20), default="")  # "autoriza" | "no_autoriza"
    acepta_bases_legales       = db.Column(db.Boolean, default=False, nullable=False)  # punto 12
    acepta_compromisos         = db.Column(db.Boolean, default=False, nullable=False)  # punto 10

    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    preinscripcion = db.relationship(
        "PreinscripcionCarcross",
        backref=db.backref("inscripcion_autorizacion", uselist=False, cascade="all, delete-orphan"),
    )
    tutores = db.relationship(
        "TutorLegal", backref="inscripcion", cascade="all, delete-orphan",
        order_by="TutorLegal.numero",
    )

    @property
    def token_expirado(self):
        limite = (self.token_creado_en or self.creado_en) + timedelta(days=DIAS_VALIDEZ_TOKEN)
        return datetime.utcnow() > limite

    @property
    def token_valido(self):
        return self.estado == "pendiente" and not self.token_usado_en and not self.token_expirado

    @property
    def tutores_requeridos(self):
        return 1 if self.solo_un_tutor else 2

    @property
    def completo(self):
        return self.estado == "completado"

    @property
    def necesita_revision_custodia(self):
        """El documento de custodia es opcional al enviar el formulario —
        si el tutor firmante marcó 'solo hay un tutor' pero no lo adjuntó,
        el equipo tiene que pedírselo y revisarlo aparte antes de dar la
        inscripción por completamente válida."""
        return self.completo and self.solo_un_tutor and not self.doc_custodia_path


class TutorLegal(db.Model):
    """Un registro por cada progenitor/tutor legal firmante. IP, user-agent
    y fecha/hora de firma se fijan una sola vez al firmar y no se tocan más
    (son la prueba de la firma electrónica simple) — no exponer edición de
    estos tres campos desde ningún formulario ni endpoint de escritura."""
    __tablename__ = "tutores_legales"

    id             = db.Column(db.Integer, primary_key=True)
    inscripcion_id = db.Column(db.Integer, db.ForeignKey("inscripciones_autorizacion.id", ondelete="CASCADE"),
                                nullable=False, index=True)
    numero         = db.Column(db.Integer, nullable=False)  # 1 o 2

    nombre_completo = db.Column(db.String(150), nullable=False)
    dni_nie         = db.Column(db.String(20), nullable=False)
    relacion_menor  = db.Column(db.String(100), default="")
    email           = db.Column(db.String(150), nullable=False)
    telefono        = db.Column(db.String(30), nullable=False)

    # Firma electrónica simple — inmutable una vez registrada.
    firmado          = db.Column(db.Boolean, default=False, nullable=False)
    firma_ip         = db.Column(db.String(45), nullable=True)
    firma_user_agent = db.Column(db.String(300), nullable=True)
    firma_en         = db.Column(db.DateTime, nullable=True)
    # Firma dibujada a mano (trazo sobre canvas), como data URL PNG en base64.
    # Es un refuerzo visual del consentimiento — la prueba legal de la firma
    # sigue siendo el checkbox + IP + user-agent + fecha/hora de arriba.
    firma_dibujo     = db.Column(db.Text, nullable=True)

    __table_args__ = (db.UniqueConstraint("inscripcion_id", "numero", name="uq_tutor_inscripcion_numero"),)
