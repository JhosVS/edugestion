"""Protección CSRF: cada formulario POST lleva un token secreto ligado a la sesión.
Así otra página web no puede enviar formularios en nombre de un usuario conectado."""
import hmac
import secrets

from flask import current_app, flash, redirect, request, session, url_for
from markupsafe import Markup


def _token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def csrf_campo():
    """Uso en plantillas: {{ csrf_campo() }} dentro de cada <form method="post">."""
    return Markup(f'<input type="hidden" name="_csrf" value="{_token()}">')


def init_app(app):
    app.jinja_env.globals["csrf_campo"] = csrf_campo

    @app.before_request
    def verificar_csrf():
        if request.method != "POST" or not current_app.config["CSRF_ACTIVADO"]:
            return None
        enviado = request.form.get("_csrf", "")
        if enviado and hmac.compare_digest(enviado, session.get("csrf", "")):
            return None
        flash("El formulario expiró. Vuelve a intentarlo.", "error")
        volver = request.referrer or ""
        return redirect(volver if volver.startswith(request.host_url) else url_for("auth.raiz"))
