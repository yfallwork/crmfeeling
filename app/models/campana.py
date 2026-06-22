from datetime import datetime
from app.extensions import db


class PlantillaWA(db.Model):
    """Plantillas de mensaje WhatsApp reutilizables."""
    __tablename__ = "plantillas_wa"

    id             = db.Column(db.Integer, primary_key=True)
    nombre         = db.Column(db.String(150), nullable=False)
    descripcion    = db.Column(db.Text, default="")
    cuerpo         = db.Column(db.Text, default="")
    activo         = db.Column(db.Boolean, default=True)
    creado_en      = db.Column(db.DateTime, default=datetime.utcnow)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def campanas_count(self):
        return Campana.query.filter_by(plantilla_wa_id=self.id).count()


ESTADOS_CAMPANA = {
    "borrador":   ("Borrador",    "bi-pencil-square",         "#6B7280"),
    "programada": ("Programada",  "bi-clock-fill",            "#F59E0B"),
    "enviando":   ("Enviando…",   "bi-arrow-clockwise",       "#3B82F6"),
    "enviada":    ("Enviada",     "bi-check-circle-fill",     "#10B981"),
    "error":      ("Con errores", "bi-exclamation-triangle",  "#EF4444"),
}


class Campana(db.Model):
    __tablename__ = "campanas"

    id                 = db.Column(db.Integer, primary_key=True)
    nombre             = db.Column(db.String(200), nullable=False)
    descripcion        = db.Column(db.Text, default="")
    canal              = db.Column(db.String(20), default="email")   # email | whatsapp | ambos
    segmento           = db.Column(db.String(20), default="todos")   # clientes | empresas | todos
    plantilla_email_id = db.Column(db.Integer,
                                   db.ForeignKey("plantillas_email.id", ondelete="SET NULL"),
                                   nullable=True)
    plantilla_wa_id    = db.Column(db.Integer,
                                   db.ForeignKey("plantillas_wa.id", ondelete="SET NULL"),
                                   nullable=True)
    fecha_envio        = db.Column(db.DateTime, nullable=True)
    estado             = db.Column(db.String(20), default="borrador")
    creado_en          = db.Column(db.DateTime, default=datetime.utcnow)
    enviado_en         = db.Column(db.DateTime, nullable=True)
    total_enviados     = db.Column(db.Integer, default=0)
    total_errores      = db.Column(db.Integer, default=0)

    plantilla_email = db.relationship("PlantillaEmail", foreign_keys=[plantilla_email_id])
    plantilla_wa    = db.relationship("PlantillaWA",    foreign_keys=[plantilla_wa_id])
    campana_tags    = db.relationship("CampanaTag", back_populates="campana",
                                      cascade="all, delete-orphan")
    logs            = db.relationship("CampanaLog", back_populates="campana",
                                      cascade="all, delete-orphan",
                                      order_by="CampanaLog.enviado_en.desc()")

    @property
    def estado_label(self):
        return ESTADOS_CAMPANA.get(self.estado, (self.estado, "bi-dot", "#6B7280"))[0]

    @property
    def estado_icono(self):
        return ESTADOS_CAMPANA.get(self.estado, (self.estado, "bi-dot", "#6B7280"))[1]

    @property
    def estado_color(self):
        return ESTADOS_CAMPANA.get(self.estado, (self.estado, "bi-dot", "#6B7280"))[2]

    @property
    def tags_incluidas(self):
        return [ct.tag for ct in self.campana_tags if ct.modo == "incluir"]

    @property
    def tags_excluidas(self):
        return [ct.tag for ct in self.campana_tags if ct.modo == "excluir"]

    @property
    def esta_programada(self):
        return self.estado == "programada" and self.fecha_envio is not None


class CampanaTag(db.Model):
    __tablename__ = "campana_tags"

    id         = db.Column(db.Integer, primary_key=True)
    campana_id = db.Column(db.Integer,
                           db.ForeignKey("campanas.id", ondelete="CASCADE"), nullable=False)
    tag_id     = db.Column(db.Integer,
                           db.ForeignKey("tags.id", ondelete="CASCADE"), nullable=False)
    modo       = db.Column(db.String(10), default="incluir")   # incluir | excluir

    campana = db.relationship("Campana", back_populates="campana_tags")
    tag     = db.relationship("Tag")


class CampanaLog(db.Model):
    __tablename__ = "campana_logs"

    id             = db.Column(db.Integer, primary_key=True)
    campana_id     = db.Column(db.Integer,
                               db.ForeignKey("campanas.id", ondelete="CASCADE"), nullable=False)
    entidad        = db.Column(db.String(20), default="")    # cliente | empresa
    entidad_id     = db.Column(db.Integer, nullable=True)
    entidad_nombre = db.Column(db.String(200), default="")
    entidad_email  = db.Column(db.String(200), default="")
    canal          = db.Column(db.String(20), default="email")
    estado         = db.Column(db.String(20), default="ok")  # ok | error | omitido
    error_msg      = db.Column(db.Text, default="")
    enviado_en     = db.Column(db.DateTime, default=datetime.utcnow)

    campana = db.relationship("Campana", back_populates="logs")

    _ESTADOS = {
        "ok":      ("#10B981", "bi-check-circle-fill"),
        "error":   ("#EF4444", "bi-x-circle-fill"),
        "omitido": ("#9CA3AF", "bi-dash-circle"),
    }

    @property
    def estado_color(self):
        return self._ESTADOS.get(self.estado, ("#9CA3AF", "bi-dot"))[0]

    @property
    def estado_icono(self):
        return self._ESTADOS.get(self.estado, ("#9CA3AF", "bi-dot"))[1]
