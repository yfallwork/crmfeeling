from datetime import datetime
from app.extensions import db

TIPOS_INVITACION = [
    ("institucion",   "Institución"),
    ("patrocinador",  "Patrocinador"),
    ("vip",           "VIP"),
    ("otro",          "Otro"),
]
TIPOS_INVITACION_KEYS = [t[0] for t in TIPOS_INVITACION]
TIPOS_INVITACION_LABELS = dict(TIPOS_INVITACION)


class Invitacion(db.Model):
    __tablename__ = "invitaciones"

    id     = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    email  = db.Column(db.String(150), nullable=False, index=True)
    tipo   = db.Column(db.String(20), nullable=False, default="otro")
    notas  = db.Column(db.Text, nullable=True)

    token        = db.Column(db.String(60), unique=True, nullable=False, index=True)
    woo_order_id = db.Column(db.Integer, nullable=True)
    qr_path      = db.Column(db.String(300), nullable=True)  # relativo a static/

    email_enviado    = db.Column(db.Boolean, default=False, nullable=False)
    email_enviado_en = db.Column(db.DateTime, nullable=True)
    email_error      = db.Column(db.Text, nullable=True)

    creado_en     = db.Column(db.DateTime, default=datetime.utcnow)
    creado_por_id = db.Column(db.Integer, db.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)

    creado_por = db.relationship("Usuario", foreign_keys=[creado_por_id])

    @property
    def tipo_label(self):
        return TIPOS_INVITACION_LABELS.get(self.tipo, self.tipo)

    @property
    def entrada_evento(self):
        """La entrada de WooCommerce sincronizada por el webhook para este
        token (única fuente de verdad para saber si ya se escaneó). Puede
        no existir todavía justo tras crear la invitación, mientras
        WooCommerce no ha llamado al webhook o no ha corrido la
        sincronización periódica."""
        from app.models.evento import EntradaEvento
        return EntradaEvento.query.filter_by(token_pase=self.token).first()

    @property
    def usado(self):
        entrada = self.entrada_evento
        return bool(entrada and entrada.escaneada)

    @property
    def fecha_uso(self):
        entrada = self.entrada_evento
        return entrada.escaneada_en if entrada and entrada.escaneada else None

    @property
    def estado_label(self):
        if self.usado:
            return "QR usado"
        if not self.email_enviado:
            return "Envío pendiente" if not self.email_error else "Envío fallido"
        return "QR no usado"
