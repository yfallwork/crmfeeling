from datetime import datetime
from app.extensions import db

TIPOS_COMUNICACION = {
    "confirmacion":      ("Confirmación",      "bi-envelope-check", "#0369A1"),
    "recordatorio":      ("Recordatorio",       "bi-bell",           "#B45309"),
    "auto_recordatorio": ("Recordatorio auto",  "bi-robot",          "#7C3AED"),
}

CANALES = {
    "email":    ("Email",    "bi-envelope"),
    "whatsapp": ("WhatsApp", "bi-whatsapp"),
}


class ComunicacionLog(db.Model):
    __tablename__ = "comunicaciones_log"

    id         = db.Column(db.Integer, primary_key=True)
    reserva_id = db.Column(db.Integer, db.ForeignKey("reservas.id", ondelete="CASCADE"), nullable=False)
    tipo       = db.Column(db.String(30), nullable=False)   # confirmacion | recordatorio | auto_recordatorio
    canal      = db.Column(db.String(20), nullable=False)   # email | whatsapp
    ok         = db.Column(db.Boolean,   default=False)
    error      = db.Column(db.Text,      default="")
    enviado_en = db.Column(db.DateTime,  default=datetime.utcnow)

    reserva = db.relationship("Reserva", backref=db.backref(
        "comunicaciones", lazy="dynamic", order_by="ComunicacionLog.enviado_en.desc()",
        cascade="all, delete-orphan",
    ))

    @property
    def tipo_label(self):
        return TIPOS_COMUNICACION.get(self.tipo, (self.tipo, "bi-send", "#555"))[0]

    @property
    def tipo_icon(self):
        return TIPOS_COMUNICACION.get(self.tipo, (self.tipo, "bi-send", "#555"))[1]

    @property
    def tipo_color(self):
        return TIPOS_COMUNICACION.get(self.tipo, (self.tipo, "bi-send", "#555"))[2]

    @property
    def canal_label(self):
        return CANALES.get(self.canal, (self.canal, "bi-send"))[0]

    @property
    def canal_icon(self):
        return CANALES.get(self.canal, (self.canal, "bi-send"))[1]

    def __repr__(self):
        return f"<ComunicacionLog reserva={self.reserva_id} {self.tipo}/{self.canal} ok={self.ok}>"
