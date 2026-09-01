from datetime import datetime
from app.extensions import db

_META = {
    "login":               ("#3B82F6", "bi-box-arrow-in-right", "Inicio de sesión"),
    "login_fallido":       ("#EF4444", "bi-x-circle",           "Login fallido"),
    "logout":              ("#6B7280", "bi-box-arrow-right",     "Cierre de sesión"),
    "crear":               ("#10B981", "bi-plus-circle-fill",    "Creación"),
    "editar":              ("#F59E0B", "bi-pencil-fill",         "Edición"),
    "eliminar":            ("#EF4444", "bi-trash-fill",          "Eliminación"),
    "cambiar_estado":      ("#8B5CF6", "bi-arrow-repeat",        "Cambio de estado"),
    "asignar_fecha":       ("#06B6D4", "bi-calendar-check-fill", "Fecha asignada"),
    "sync_woo":            ("#7C3AED", "bi-shop-window",         "Sync WooCommerce"),
    "webhook":             ("#6366F1", "bi-lightning-fill",      "Webhook WooCommerce"),
    "crear_experiencia":   ("#10B981", "bi-star-fill",           "Nueva experiencia"),
    "eliminar_experiencia":("#EF4444", "bi-star",                "Experiencia eliminada"),
}


class Log(db.Model):
    __tablename__ = "logs"

    id             = db.Column(db.Integer, primary_key=True)
    fecha          = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    usuario_id     = db.Column(db.Integer, db.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    usuario_nombre = db.Column(db.String(100), default="Sistema")
    accion         = db.Column(db.String(30),  nullable=False, index=True)
    entidad        = db.Column(db.String(30),  nullable=True)
    entidad_id     = db.Column(db.Integer,     nullable=True)
    detalle        = db.Column(db.Text,        default="")
    ip             = db.Column(db.String(45),  default="")
    origen         = db.Column(db.String(20),  default="manual", index=True)

    usuario = db.relationship("Usuario", foreign_keys=[usuario_id])

    @property
    def color(self):
        return _META.get(self.accion, ("#9CA3AF", "bi-dot", self.accion))[0]

    @property
    def icono(self):
        return _META.get(self.accion, ("#9CA3AF", "bi-dot", self.accion))[1]

    @property
    def accion_label(self):
        return _META.get(self.accion, ("#9CA3AF", "bi-dot", self.accion))[2]

    @property
    def entidad_label(self):
        return {
            "cliente":      "Cliente",
            "reserva":      "Reserva",
            "sistema":      "Sistema",
            "experiencia":  "Experiencia",
            "socio":        "Socio",
            "patrocinador": "Patrocinador",
            "empresa":      "Empresa TB",
            "tag":          "Etiqueta",
            "plantilla":    "Plantilla email",
            "rule":         "Norma",
            "evento":       "Evento",
            "entrada_evento": "Entrada de evento",
            "invitacion":   "Invitación",
        }.get(self.entidad or "", self.entidad or "")
