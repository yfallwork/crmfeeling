from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, request
from flask_login import login_user, logout_user, current_user
from app.utils import safe_next_url

vista_bp = Blueprint("vista", __name__)


def _vista_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("vista.login", next=request.path))
        return f(*args, **kwargs)
    return decorated


@vista_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("vista.index"))
    error = None
    if request.method == "POST":
        from app.models.usuario import Usuario
        ident = request.form.get("email", "").strip()
        pwd   = request.form.get("password", "")
        user  = (Usuario.query.filter_by(username=ident, activo=True).first()
                 or Usuario.query.filter_by(email=ident, activo=True).first())
        if user and user.check_password(pwd):
            login_user(user, remember=True)
            next_page = safe_next_url(request.args.get("next"))
            return redirect(next_page or url_for("vista.index"))
        error = "Usuario o contraseña incorrectos"
    return render_template("vista/login.html", error=error)


@vista_bp.route("/")
@_vista_required
def index():
    from app.models.experiencia import TipoExperiencia
    tipos = TipoExperiencia.query.filter_by(activo=True).order_by(TipoExperiencia.nombre).all()
    return render_template("vista/index.html", usuario=current_user, tipos_experiencia=tipos)


@vista_bp.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("vista.login"))
