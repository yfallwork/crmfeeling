from datetime import datetime
from app.extensions import db


class Vehiculo(db.Model):
    __tablename__ = "vehiculos"
    id = db.Column(db.Integer, primary_key=True)
    tipo_vehiculo = db.Column(db.String(20), nullable=False)
    categoria = db.Column(db.String(50))
    cc_chasis_marca = db.Column(db.String(100))
    cc_chasis_modelo = db.Column(db.String(100))
    cc_num_chasis = db.Column(db.String(100))
    cc_pasaporte_rfeda = db.Column(db.String(100))
    cc_pasaporte_autonomico = db.Column(db.String(100))
    cc_num_homologacion = db.Column(db.String(100))
    cc_motor_marca = db.Column(db.String(100))
    cc_motor_modelo = db.Column(db.String(100))
    cc_motor_anio = db.Column(db.String(10))
    cc_cilindrada = db.Column(db.Integer)
    cc_num_motor = db.Column(db.String(100))
    div_marca = db.Column(db.String(100))
    div_modelo = db.Column(db.String(100))
    div_num_bastidor = db.Column(db.String(100))
    div_pasaporte_rfeda = db.Column(db.String(100))
    div_pasaporte_autonomico = db.Column(db.String(100))
    div_homologacion = db.Column(db.String(100))
    div_motor_disposicion = db.Column(db.String(20))
    div_motor_aspiracion = db.Column(db.String(20))
    div_cilindrada = db.Column(db.Integer)
    div_factor_correccion = db.Column(db.Float)
    div_traccion = db.Column(db.String(20))
    arnes_marca = db.Column(db.String(100))
    arnes_homologacion = db.Column(db.String(100))
    arnes_caducidad = db.Column(db.Date)
    asiento_marca = db.Column(db.String(100))
    asiento_homologacion = db.Column(db.String(100))
    asiento_caducidad = db.Column(db.Date)
    extincion_marca = db.Column(db.String(100))
    extincion_tipo = db.Column(db.String(20))
    extincion_revision = db.Column(db.Date)
    deposito_marca = db.Column(db.String(100))
    deposito_caducidad = db.Column(db.Date)
    red_estado = db.Column(db.String(100))
    red_homologacion = db.Column(db.String(100))
    dorsal = db.Column(db.String(10))
    num_transponder = db.Column(db.String(50))
    piloto_id = db.Column(db.Integer, db.ForeignKey("pilotos.id"), nullable=True, index=True)
    piloto = db.relationship("Piloto", backref=db.backref("vehiculos", lazy="dynamic"))
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    activo = db.Column(db.Boolean, default=True)

    @property
    def nombre_display(self):
        if self.tipo_vehiculo == "car_cross":
            partes = [self.cc_chasis_marca, self.cc_chasis_modelo]
        else:
            partes = [self.div_marca, self.div_modelo]
        return " ".join(p for p in partes if p) or "Sin nombre"
