from datetime import datetime
from app.extensions import db


class Socio(db.Model):
    __tablename__ = "socios"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    apellido = db.Column(db.String(100), default="")
    email = db.Column(db.String(150), default="")
    telefono = db.Column(db.String(20), default="")
    dni = db.Column(db.String(20), default="")
    tipo = db.Column(db.String(50), default="regular")  # regular, premium, familiar, vip
    fecha_alta = db.Column(db.Date, nullable=True)
    activo = db.Column(db.Boolean, default=True, nullable=False)
    fecha_baja = db.Column(db.DateTime, nullable=True)
    notas = db.Column(db.Text, default="")
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellido}".strip()

    def desactivar(self):
        self.activo = False
        self.fecha_baja = datetime.utcnow()

    def activar(self):
        self.activo = True
        self.fecha_baja = None

    def to_dict(self):
        return {
            "id": self.id,
            "nombre": self.nombre_completo,
            "email": self.email,
            "telefono": self.telefono,
            "tipo": self.tipo,
            "activo": self.activo,
            "fecha_alta": self.fecha_alta.isoformat() if self.fecha_alta else None,
        }

    def __repr__(self):
        return f"<Socio {self.nombre_completo}>"
