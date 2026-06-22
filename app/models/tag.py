from datetime import datetime
from app.extensions import db


class Tag(db.Model):
    __tablename__ = "tags"

    id    = db.Column(db.Integer, primary_key=True)
    slug  = db.Column(db.String(60), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text, default="")

    tipo     = db.Column(db.String(20), default="sistematica")  # sistematica | dinamica
    entidad  = db.Column(db.String(20), default="cliente")      # cliente | empresa
    segmento = db.Column(db.String(5),  default="b2c")          # b2c | b2b

    color = db.Column(db.String(7),  default="#6B7280")
    icono = db.Column(db.String(50), default="bi-tag-fill")

    # Sistemáticas: qué evento del sistema/WooCommerce dispara esta etiqueta
    trigger_evento = db.Column(db.String(150), default="")
    # Dinámicas: descripción de la lógica SQL del filtro
    filtro_descripcion = db.Column(db.Text, default="")
    # Temporales: días sin reserva no-cancelada para activar la etiqueta
    tiempo_sin_reserva_dias = db.Column(db.Integer, nullable=True)
    # Criterio VIP: umbrales configurables para asignación automática
    criterio_min_gasto     = db.Column(db.Float,   nullable=True)  # € mínimo acumulado
    criterio_min_reservas  = db.Column(db.Integer, nullable=True)  # nº mínimo de experiencias (B2C)
    criterio_min_empleados = db.Column(db.Integer, nullable=True)  # nº mínimo de empleados (B2B)

    activo       = db.Column(db.Boolean,  default=True)
    creado_en    = db.Column(db.DateTime, default=datetime.utcnow)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    asignaciones_clientes = db.relationship(
        "ClienteTag", back_populates="tag", cascade="all, delete-orphan", lazy="dynamic"
    )
    asignaciones_empresas = db.relationship(
        "EmpresaTag", back_populates="tag", cascade="all, delete-orphan", lazy="dynamic"
    )

    @property
    def total_asignaciones(self):
        return self.asignaciones_clientes.count() + self.asignaciones_empresas.count()

    @property
    def tipo_label(self):
        labels = {"sistematica": "Sistemática", "dinamica": "Dinámica", "temporal": "Temporal"}
        return labels.get(self.tipo, self.tipo.capitalize())

    @property
    def segmento_label(self):
        return "B2C · Particulares" if self.segmento == "b2c" else "B2B · Empresas"

    def __repr__(self):
        return f"<Tag {self.slug}>"


class ClienteTag(db.Model):
    __tablename__ = "cliente_tags"

    cliente_id  = db.Column(db.Integer, db.ForeignKey("clientes.id",   ondelete="CASCADE"), primary_key=True)
    tag_id      = db.Column(db.Integer, db.ForeignKey("tags.id",       ondelete="CASCADE"), primary_key=True)
    asignado_en = db.Column(db.DateTime, default=datetime.utcnow)
    origen      = db.Column(db.String(20), default="manual")  # manual | sistema | webhook

    tag     = db.relationship("Tag",     back_populates="asignaciones_clientes")
    cliente = db.relationship("Cliente", foreign_keys=[cliente_id])


class EmpresaTag(db.Model):
    __tablename__ = "empresa_tags"

    empresa_id  = db.Column(db.Integer, db.ForeignKey("empresas_tb.id", ondelete="CASCADE"), primary_key=True)
    tag_id      = db.Column(db.Integer, db.ForeignKey("tags.id",        ondelete="CASCADE"), primary_key=True)
    asignado_en = db.Column(db.DateTime, default=datetime.utcnow)
    origen      = db.Column(db.String(20), default="manual")  # manual | sistema | webhook

    tag     = db.relationship("Tag",     back_populates="asignaciones_empresas")
    empresa = db.relationship("Empresa", foreign_keys=[empresa_id])
