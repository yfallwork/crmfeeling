from datetime import datetime
from app.extensions import db

ESTADOS = ["pendiente", "reservado", "disfrutado", "cancelado"]

ESTADO_COLORES = {
    "pendiente":  "#F59E0B",
    "reservado":  "#AD1726",
    "disfrutado": "#10B981",
    "cancelado":  "#6B7280",
}


class Reserva(db.Model):
    __tablename__ = "reservas"

    id = db.Column(db.Integer, primary_key=True)

    # Exactamente uno de los dos estará relleno
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas_tb.id"), nullable=True)

    tipo_experiencia_id = db.Column(db.Integer, db.ForeignKey("tipos_experiencia.id"), nullable=False)

    fecha_compra   = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_disfrute = db.Column(db.DateTime, nullable=True)

    estado   = db.Column(db.String(20),  default="pendiente")
    precio   = db.Column(db.Float,       default=0.0)
    horario  = db.Column(db.String(20),  default="")
    variante = db.Column(db.String(150), default="")
    notas    = db.Column(db.Text,        default="")

    # Team Building extras
    num_participantes = db.Column(db.Integer,    default=1)
    nombre_grupo      = db.Column(db.String(150), default="")

    # WooCommerce
    woo_order_id     = db.Column(db.Integer, nullable=True, unique=True)
    woo_order_status = db.Column(db.String(30), default="")

    creado_en      = db.Column(db.DateTime, default=datetime.utcnow)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    cliente        = db.relationship("Cliente",         foreign_keys=[cliente_id], back_populates="reservas")
    empresa        = db.relationship("Empresa",         foreign_keys=[empresa_id])
    tipo_experiencia = db.relationship("TipoExperiencia", back_populates="reservas")

    # ── Propiedades de conveniencia ────────────────────────────────────────────

    @property
    def es_teambuilding(self):
        return self.empresa_id is not None

    @property
    def nombre_reservante(self):
        if self.cliente:
            return self.cliente.nombre_completo
        if self.empresa:
            return self.empresa.nombre
        return "—"

    @property
    def color(self):
        return ESTADO_COLORES.get(self.estado, "#6B7280")

    @property
    def dias_hasta_disfrute(self):
        if self.fecha_disfrute:
            delta = self.fecha_disfrute.date() - datetime.utcnow().date()
            return delta.days
        return None

    def to_calendar_event(self):
        horario_str = f" · {self.horario}" if self.horario else ""
        titulo = f"{self.nombre_reservante}{horario_str}"
        if self.es_teambuilding:
            titulo = f"[TB] {titulo}"
        return {
            "id": str(self.id),
            "title": titulo,
            "start": self.fecha_disfrute.isoformat() if self.fecha_disfrute else None,
            "color": self.color,
            "extendedProps": {
                "estado": self.estado,
                "cliente": self.nombre_reservante,
                "experiencia": self.tipo_experiencia.nombre,
                "variante": self.variante or "",
                "horario": self.horario or "",
                "telefono": self.cliente.telefono if self.cliente else (self.empresa.telefono if self.empresa else ""),
                "reserva_id": self.id,
                "es_teambuilding": self.es_teambuilding,
            },
        }

    def to_dict(self):
        return {
            "id": self.id,
            "cliente": self.nombre_reservante,
            "cliente_id": self.cliente_id,
            "empresa_id": self.empresa_id,
            "es_teambuilding": self.es_teambuilding,
            "experiencia": self.tipo_experiencia.nombre,
            "variante": self.variante or "",
            "horario": self.horario or "",
            "tipo_experiencia_id": self.tipo_experiencia_id,
            "fecha_compra": self.fecha_compra.isoformat() if self.fecha_compra else None,
            "fecha_disfrute": self.fecha_disfrute.isoformat() if self.fecha_disfrute else None,
            "estado": self.estado,
            "precio": self.precio,
            "woo_order_id": self.woo_order_id,
            "num_participantes": self.num_participantes,
            "nombre_grupo": self.nombre_grupo,
        }

    def __repr__(self):
        return f"<Reserva #{self.id} {self.estado}>"
