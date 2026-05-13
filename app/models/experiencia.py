from datetime import datetime
from app.extensions import db


class TipoExperiencia(db.Model):
    __tablename__ = "tipos_experiencia"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    descripcion = db.Column(db.Text, default="")
    duracion_minutos = db.Column(db.Integer, default=60)
    precio_base = db.Column(db.Float, default=0.0)
    activo = db.Column(db.Boolean, default=True)
    color = db.Column(db.String(7), default="#2563EB")  # hex para el calendario
    woo_product_id = db.Column(db.Integer, nullable=True)  # ID del producto en WooCommerce
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    reservas = db.relationship("Reserva", back_populates="tipo_experiencia", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "nombre": self.nombre,
            "duracion_minutos": self.duracion_minutos,
            "precio_base": self.precio_base,
            "color": self.color,
        }

    def __repr__(self):
        return f"<TipoExperiencia {self.nombre}>"
