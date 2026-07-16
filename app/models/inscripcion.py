from datetime import datetime
from app.extensions import db


class Inscripcion(db.Model):
    __tablename__ = "inscripciones"
    id = db.Column(db.Integer, primary_key=True)
    nombre_prueba = db.Column(db.String(200), nullable=False)
    fecha_prueba = db.Column(db.Date)  # fecha de inicio de la prueba
    fecha_fin = db.Column(db.Date, nullable=True)  # fecha de fin, si la prueba dura varios días
    campeonato = db.Column(db.String(50))
    piloto_id = db.Column(db.Integer, db.ForeignKey("pilotos.id"), nullable=False, index=True)
    vehiculo_id = db.Column(db.Integer, db.ForeignKey("vehiculos.id"), nullable=True, index=True)
    concursante = db.Column(db.String(200))
    fecha_plazo = db.Column(db.Date, nullable=True)
    estado = db.Column(db.String(20), default="pendiente")
    justificante_filename = db.Column(db.String(200))
    notas = db.Column(db.Text)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    piloto = db.relationship("Piloto", backref=db.backref("inscripciones", lazy="dynamic"))
    vehiculo = db.relationship("Vehiculo", backref=db.backref("inscripciones", lazy="dynamic"))

    @property
    def rango_fechas(self):
        """Texto legible del/de los día(s) de la prueba."""
        if not self.fecha_prueba:
            return "Sin fecha"
        if self.fecha_fin and self.fecha_fin != self.fecha_prueba:
            return f"{self.fecha_prueba.strftime('%d/%m/%Y')} – {self.fecha_fin.strftime('%d/%m/%Y')}"
        return self.fecha_prueba.strftime("%d/%m/%Y")

    @property
    def duracion_dias(self):
        if self.fecha_prueba and self.fecha_fin and self.fecha_fin >= self.fecha_prueba:
            return (self.fecha_fin - self.fecha_prueba).days + 1
        return 1

    @property
    def num_pilotos(self):
        return 1 + self.participantes.count()

    @property
    def estados_individuales(self):
        """Estado del piloto principal + el de cada piloto adicional."""
        return [self.estado] + [p.estado for p in self.participantes]

    @property
    def estado_grupo(self):
        """Estado que se muestra como global de la inscripción: si todos los
        pilotos están en el mismo estado, ese; si no coinciden (p.ej. uno
        enviado y otro no), 'parcial'."""
        estados = set(self.estados_individuales)
        if len(estados) == 1:
            return estados.pop()
        return "parcial"
