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
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False)
    tipo_experiencia_id = db.Column(db.Integer, db.ForeignKey("tipos_experiencia.id"), nullable=False)

    fecha_compra = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_disfrute = db.Column(db.DateTime, nullable=True)

    estado = db.Column(db.String(20), default="pendiente")
    precio = db.Column(db.Float, default=0.0)
    horario = db.Column(db.String(20), default="")       # "10:00-12:00"
    variante = db.Column(db.String(150), default="")     # pa_escoge-tu-experiencia
    notas = db.Column(db.Text, default="")

    # WooCommerce
    woo_order_id = db.Column(db.Integer, nullable=True, unique=True)
    woo_order_status = db.Column(db.String(30), default="")

    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    cliente = db.relationship("Cliente", back_populates="reservas")
    tipo_experiencia = db.relationship("TipoExperiencia", back_populates="reservas")

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
        titulo = f"{self.cliente.nombre_completo}{horario_str}"
        return {
            "id": str(self.id),
            "title": titulo,
            "start": self.fecha_disfrute.isoformat() if self.fecha_disfrute else None,
            "color": self.color,
            "extendedProps": {
                "estado": self.estado,
                "cliente": self.cliente.nombre_completo,
                "experiencia": self.tipo_experiencia.nombre,
                "variante": self.variante or "",
                "horario": self.horario or "",
                "telefono": self.cliente.telefono,
                "reserva_id": self.id,
            },
        }

    def to_dict(self):
        return {
            "id": self.id,
            "cliente": self.cliente.nombre_completo,
            "cliente_id": self.cliente_id,
            "experiencia": self.tipo_experiencia.nombre,
            "variante": self.variante or "",
            "horario": self.horario or "",
            "tipo_experiencia_id": self.tipo_experiencia_id,
            "fecha_compra": self.fecha_compra.isoformat() if self.fecha_compra else None,
            "fecha_disfrute": self.fecha_disfrute.isoformat() if self.fecha_disfrute else None,
            "estado": self.estado,
            "precio": self.precio,
            "woo_order_id": self.woo_order_id,
        }

    def __repr__(self):
        return f"<Reserva #{self.id} {self.estado}>"
