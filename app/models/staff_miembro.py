from datetime import datetime
from app.extensions import db

TIPOS_STAFF = ["Mecánico", "Representante"]

inscripcion_staff = db.Table(
    "inscripcion_staff",
    db.Column("inscripcion_id", db.Integer, db.ForeignKey("inscripciones.id", ondelete="CASCADE"), primary_key=True),
    db.Column("staff_id",       db.Integer, db.ForeignKey("staff_miembros.id", ondelete="CASCADE"), primary_key=True),
)


class StaffMiembro(db.Model):
    __tablename__ = "staff_miembros"

    id         = db.Column(db.Integer, primary_key=True)
    nombre     = db.Column(db.String(100), nullable=False)
    apellidos  = db.Column(db.String(150), nullable=False)
    tipo       = db.Column(db.String(20), nullable=False, default="Mecánico")  # Mecánico | Representante
    telefono   = db.Column(db.String(20))
    email      = db.Column(db.String(150))
    dni        = db.Column(db.String(20))
    notas      = db.Column(db.Text)
    activo     = db.Column(db.Boolean, default=True)
    creado_en  = db.Column(db.DateTime, default=datetime.utcnow)

    inscripciones = db.relationship(
        "Inscripcion",
        secondary=inscripcion_staff,
        backref=db.backref("staff", lazy="dynamic"),
    )

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellidos}".strip()
