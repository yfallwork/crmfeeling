from datetime import datetime
from app.extensions import db

# Estados de pedido de WooCommerce que consideramos "entrada válida para
# entrar al evento". Los demás (pending, on-hold, cancelled, refunded,
# failed, trash) bloquean el acceso hasta que se aprueben.

# Solo "completed" genera de verdad el token/QR en WooCommerce — "processing"
# es un estado intermedio (pago confirmado, pendiente de aprobación) que
# todavía no se puede escanear. Ver requiere_aprobacion_manual() en
# evento_sync.py para cuándo pasa de processing a completed.
ESTADOS_PEDIDO_VALIDOS = ("completed",)

ESTADO_PEDIDO_LABELS = {
    "pending":    "Pendiente de pago",
    "processing": "En proceso",
    "on-hold":    "En espera",
    "completed":  "Completado",
    "cancelled":  "Cancelado",
    "refunded":   "Reembolsado",
    "failed":     "Fallido",
    "trash":      "Papelera",
}


class Evento(db.Model):
    __tablename__ = "eventos"

    id         = db.Column(db.Integer, primary_key=True)
    nombre     = db.Column(db.String(150), nullable=False)
    slug       = db.Column(db.String(80), unique=True, nullable=False)
    fecha      = db.Column(db.Date, nullable=True)
    lugar      = db.Column(db.String(150), default="")
    # IDs de producto de WooCommerce (separados por comas) que pertenecen a
    # este evento — así un pedido solo se asigna al evento cuyo producto
    # coincide, en vez de mezclarse con entradas de otras ediciones vendidas
    # en la misma tienda. Si un evento no tiene ninguno configurado, se usa
    # como respaldo el único evento marcado como "activo".
    woo_producto_ids = db.Column(db.Text, default="")
    activo     = db.Column(db.Boolean, default=True, nullable=False)
    creado_en  = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def producto_ids_lista(self):
        if not self.woo_producto_ids:
            return []
        return [p.strip() for p in self.woo_producto_ids.split(",") if p.strip()]

    entradas = db.relationship(
        "EntradaEvento", backref="evento", lazy="dynamic",
        cascade="all, delete-orphan",
    )

    @property
    def total_entradas(self):
        return self.entradas.count()

    @property
    def total_validas(self):
        return self.entradas.filter(
            EntradaEvento.estado_pedido.in_(ESTADOS_PEDIDO_VALIDOS)
        ).count()

    @property
    def total_escaneadas(self):
        return self.entradas.filter_by(escaneada=True).count()


class EntradaEvento(db.Model):
    __tablename__ = "entradas_evento"

    id              = db.Column(db.Integer, primary_key=True)
    evento_id       = db.Column(db.Integer, db.ForeignKey("eventos.id", ondelete="CASCADE"), nullable=False, index=True)

    # Identificación del pedido de WooCommerce
    woo_order_id    = db.Column(db.Integer, unique=True, nullable=True, index=True)
    woo_order_numero = db.Column(db.String(30), default="")
    estado_pedido   = db.Column(db.String(30), default="pending", index=True)  # pending/processing/completed/cancelled/refunded/on-hold/failed
    # Fecha en la que el cliente hizo el pedido en WooCommerce (date_created
    # del pedido) — no confundir con creado_en, que es cuándo entró en el
    # CRM. Es la que se usa para ordenar el listado de entradas.
    fecha_pedido    = db.Column(db.DateTime, nullable=True, index=True)

    # Token del QR que WooCommerce genera al aprobar el pedido (llega en
    # meta_data.token_pase). Sin token todavía no se puede escanear.
    token_pase      = db.Column(db.String(120), unique=True, nullable=True, index=True)

    # Datos del cliente / titular del pase
    nombre_cliente  = db.Column(db.String(150), default="")
    email_cliente   = db.Column(db.String(150), default="")
    telefono_cliente = db.Column(db.String(30), default="")
    tipo_pase       = db.Column(db.String(120), default="")  # nombre del producto/línea comprado

    # Campos específicos de pases de prensa (meta_data de WooCommerce)
    dni_prensa          = db.Column(db.String(20), default="")
    medio_comunicacion  = db.Column(db.String(150), default="")
    cargo_prensa        = db.Column(db.String(100), default="")
    carne_prensa        = db.Column(db.String(60), default="")
    portfolio_redes     = db.Column(db.String(300), default="")

    # Campos específicos de pases institucionales (meta_data de WooCommerce)
    cargo_institucional = db.Column(db.String(100), default="")
    institucion         = db.Column(db.String(150), default="")
    cif_institucion     = db.Column(db.String(20), default="")
    num_acompanantes    = db.Column(db.Integer, default=0)

    # Volcado íntegro del meta_data del pedido, por si hace falta consultar
    # algún campo no promovido a columna propia.
    meta_data_json  = db.Column(db.Text, nullable=True)

    # Control de acceso el día del evento
    escaneada           = db.Column(db.Boolean, default=False, nullable=False, index=True)
    escaneada_en         = db.Column(db.DateTime, nullable=True)
    escaneada_por_id     = db.Column(db.Integer, db.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)

    creado_en       = db.Column(db.DateTime, default=datetime.utcnow)
    actualizado_en  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    escaneada_por = db.relationship("Usuario", foreign_keys=[escaneada_por_id])

    @property
    def es_valida(self):
        return self.estado_pedido in ESTADOS_PEDIDO_VALIDOS

    @property
    def estado_label(self):
        return ESTADO_PEDIDO_LABELS.get(self.estado_pedido, self.estado_pedido)

    def to_dict(self):
        return {
            "id": self.id,
            "evento": self.evento.nombre if self.evento else "",
            "nombre_cliente": self.nombre_cliente,
            "email_cliente": self.email_cliente,
            "telefono_cliente": self.telefono_cliente,
            "tipo_pase": self.tipo_pase,
            "estado_pedido": self.estado_pedido,
            "estado_label": self.estado_label,
            "es_valida": self.es_valida,
            "dni_prensa": self.dni_prensa,
            "medio_comunicacion": self.medio_comunicacion,
            "cargo_prensa": self.cargo_prensa,
            "carne_prensa": self.carne_prensa,
            "cargo_institucional": self.cargo_institucional,
            "institucion": self.institucion,
            "cif_institucion": self.cif_institucion,
            "num_acompanantes": self.num_acompanantes,
            "escaneada": self.escaneada,
            "escaneada_en": self.escaneada_en.strftime("%d/%m/%Y %H:%M") if self.escaneada_en else None,
            "escaneada_por": self.escaneada_por.nombre if self.escaneada_por else None,
            "woo_order_id": self.woo_order_id,
            "fecha_pedido": self.fecha_pedido.strftime("%d/%m/%Y %H:%M") if self.fecha_pedido else None,
        }
