from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app.extensions import db, login_manager


class Usuario(UserMixin, db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=True)
    email = db.Column(db.String(150), unique=True, nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    rol = db.Column(db.String(20), default="gestor")  # admin / gestor
    activo = db.Column(db.Boolean, default=True)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def es_admin(self):
        return self.rol == "admin"

    def __repr__(self):
        return f"<Usuario {self.email}>"


@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))
