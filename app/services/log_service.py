def registrar_log(accion, entidad=None, entidad_id=None, detalle="", origen="manual"):
    """Registra una acción en el log de actividad. Nunca interrumpe el flujo principal."""
    try:
        from flask import request as _req
        from flask_login import current_user
        from app.models.log import Log
        from app.extensions import db

        usuario_id = None
        usuario_nombre = "Sistema"
        try:
            if current_user and current_user.is_authenticated:
                usuario_id = current_user.id
                usuario_nombre = current_user.nombre
        except Exception:
            pass

        try:
            ip = _req.remote_addr or ""
        except Exception:
            ip = ""

        log = Log(
            usuario_id=usuario_id,
            usuario_nombre=usuario_nombre,
            accion=accion,
            entidad=entidad,
            entidad_id=entidad_id,
            detalle=str(detalle)[:500] if detalle else "",
            ip=ip,
            origen=origen,
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        pass
