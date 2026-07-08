from datetime import datetime
from app.extensions import db


class Cliente(db.Model):
    __tablename__ = "clientes"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    apellido = db.Column(db.String(100), default="")
    email = db.Column(db.String(150), unique=True, nullable=False)
    telefono = db.Column(db.String(20), default="")
    dni = db.Column(db.String(20), default="")
    fuente = db.Column(db.String(20), default="manual")  # woocommerce / manual
    woo_customer_id = db.Column(db.Integer, nullable=True)
    notas = db.Column(db.Text, default="")
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    reservas = db.relationship("Reserva", back_populates="cliente", lazy="dynamic", cascade="all, delete-orphan")

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellido}".strip()

    @property
    def total_reservas(self):
        return self.reservas.count()

    @property
    def reservas_pendientes(self):
        return self.reservas.filter_by(estado="pendiente").count()

    def to_dict(self):
        return {
            "id": self.id,
            "nombre": self.nombre_completo,
            "email": self.email,
            "telefono": self.telefono,
            "fuente": self.fuente,
            "total_reservas": self.total_reservas,
            "creado_en": self.creado_en.isoformat() if self.creado_en else None,
        }

    def __repr__(self):
        return f"<Cliente {self.email}>"
