def registrar_marketing_log(evento, resultado="ok", rule_id=None, rule_nombre="",
                            accion_tipo="", tag_id=None, tag_nombre="",
                            entidad="", entidad_id=None, entidad_nombre="",
                            detalle="", origen="manual",
                            campana_id=None, campana_nombre=""):
    """Registra un evento de automatización de marketing. Nunca interrumpe el flujo principal."""
    try:
        from flask_login import current_user
        from app.models.marketing_log import MarketingLog
        from app.extensions import db

        usuario_nombre = "Sistema"
        try:
            if current_user and current_user.is_authenticated:
                usuario_nombre = current_user.nombre
        except Exception:
            pass

        log = MarketingLog(
            evento=evento,
            resultado=resultado,
            rule_id=rule_id,
            rule_nombre=str(rule_nombre)[:150] if rule_nombre else "",
            accion_tipo=str(accion_tipo)[:20] if accion_tipo else "",
            tag_id=tag_id,
            tag_nombre=str(tag_nombre)[:100] if tag_nombre else "",
            entidad=str(entidad)[:20] if entidad else "",
            entidad_id=entidad_id,
            entidad_nombre=str(entidad_nombre)[:200] if entidad_nombre else "",
            detalle=str(detalle)[:1000] if detalle else "",
            origen=str(origen)[:20] if origen else "manual",
            usuario_nombre=usuario_nombre,
            campana_id=campana_id,
            campana_nombre=str(campana_nombre)[:200] if campana_nombre else "",
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        pass


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
