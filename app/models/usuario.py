import json
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app.extensions import db, login_manager

# Módulos de la app que se pueden restringir por usuario. La clave debe
# coincidir con el nombre del blueprint (request.blueprint) para poder
# usarse directamente como gate de acceso en el before_request.
MODULOS = [
    ("clientes",     "Clientes",       "bi-people"),
    ("reservas",     "Reservas",       "bi-calendar-check"),
    ("calendario",   "Calendario",     "bi-calendar3"),
    ("estadisticas", "Estadísticas",   "bi-bar-chart-line"),
    ("agenda",       "Agenda social",  "bi-megaphone"),
    ("teambuilding", "Team Building",  "bi-buildings"),
    ("marketing",    "Marketing",      "bi-bullseye"),
    ("autoclub",     "AutoClub",       "bi-shield-check"),
    ("woocommerce",  "WooCommerce",    "bi-shop"),
    ("logs",         "Actividad",      "bi-journal-text"),
    ("configuracion", "Configuración", "bi-gear"),
]
MODULOS_KEYS = [m[0] for m in MODULOS]

# Secciones internas del blueprint de AutoClub que también se pueden
# restringir por usuario, independientemente del permiso general al módulo
# "autoclub". La clave se compara contra el prefijo de la URL (/autoclub/<key>).
AUTOCLUB_SECCIONES = [
    ("socios",         "Socios",          "bi-person-badge"),
    ("patrocinadores", "Patrocinadores",  "bi-building"),
    ("notas",          "Notas",           "bi-journal-text"),
    ("pilotos",        "Pilotos",         "bi-person-badge-fill"),
    ("vehiculos",      "Vehículos",       "bi-car-front-fill"),
    ("inscripciones",  "Inscripciones",   "bi-clipboard-check-fill"),
    ("gastos",         "Gastos",          "bi-cash-coin"),
    ("staff",          "Staff",           "bi-people-fill"),
    ("calendario",     "Calendario",      "bi-calendar3-event-fill"),
    ("prensa",         "Prensa",          "bi-newspaper"),
    ("informacion",    "Información",     "bi-info-circle-fill"),
    ("seguimiento",    "Seguimiento",     "bi-activity"),
]
AUTOCLUB_SECCIONES_KEYS = [s[0] for s in AUTOCLUB_SECCIONES]


class Usuario(UserMixin, db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=True)
    email = db.Column(db.String(150), unique=True, nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    rol = db.Column(db.String(20), default="gestor")  # admin / gestor / vista
    activo = db.Column(db.Boolean, default=True)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    # Objeto JSON {"modulos": [...], "autoclub_secciones": [...]} con las
    # claves a las que tiene acceso. NULL/vacío = sin restricciones definidas
    # todavía = acceso total (así ninguna cuenta existente pierde acceso al
    # añadir esta columna). Una clave ausente dentro del objeto (p.ej. sin
    # "autoclub_secciones" aunque sí haya "modulos") también se trata como
    # acceso total a esa parte, por el mismo motivo.
    permisos_json = db.Column(db.Text, nullable=True)

    def _permisos(self):
        if not self.permisos_json:
            return {}
        try:
            datos = json.loads(self.permisos_json)
        except (TypeError, ValueError):
            return {}
        return datos if isinstance(datos, dict) else {}

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def es_admin(self):
        return self.rol == "admin"

    @property
    def modulos_permitidos(self):
        """Claves de módulos accesibles. Admin: todos siempre. Sin
        restricción definida: todos (comportamiento por defecto/legacy)."""
        if self.rol == "admin":
            return list(MODULOS_KEYS)
        return self._permisos().get("modulos", list(MODULOS_KEYS))

    @property
    def autoclub_secciones_permitidas(self):
        """Igual que modulos_permitidos pero para las secciones internas
        de AutoClub (solo relevante si ya tiene acceso al módulo autoclub)."""
        if self.rol == "admin":
            return list(AUTOCLUB_SECCIONES_KEYS)
        return self._permisos().get("autoclub_secciones", list(AUTOCLUB_SECCIONES_KEYS))

    def puede_acceder(self, modulo_key):
        return modulo_key in self.modulos_permitidos

    def puede_acceder_autoclub(self, seccion_key):
        return seccion_key in self.autoclub_secciones_permitidas

    def __repr__(self):
        return f"<Usuario {self.email}>"


@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))
