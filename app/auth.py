from functools import wraps

from flask import (Blueprint, abort, current_app, flash, g, redirect,
                   render_template, request, session, url_for)
from werkzeug.security import check_password_hash

from .db import get_db

bp = Blueprint("auth", __name__)

INICIO_POR_ROL = {
    "alumno": "alumno.inicio",
    "docente": "docente.inicio",
    "director": "director.inicio",
}


def login_required(rol=None):
    """Exige sesión iniciada y, opcionalmente, un rol concreto."""
    def decorador(vista):
        @wraps(vista)
        def envoltura(*args, **kwargs):
            if g.usuario is None:
                return redirect(url_for("auth.login"))
            if rol and g.usuario["rol"] != rol:
                abort(403)
            return vista(*args, **kwargs)
        return envoltura
    return decorador


@bp.before_app_request
def cargar_usuario():
    g.usuario = None
    uid = session.get("usuario_id")
    if uid is not None:
        g.usuario = get_db().execute(
            "SELECT id, nombres, apellidos, correo, rol FROM usuarios "
            "WHERE id = ? AND activo = 1", (uid,)).fetchone()
        if g.usuario is None:  # usuario borrado o desactivado
            session.clear()


@bp.route("/")
def raiz():
    if g.usuario is None:
        return redirect(url_for("auth.login"))
    return redirect(url_for(INICIO_POR_ROL[g.usuario["rol"]]))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.usuario is not None:
        return redirect(url_for(INICIO_POR_ROL[g.usuario["rol"]]))

    if request.method == "POST":
        correo = request.form.get("correo", "").strip().lower()
        clave = request.form.get("clave", "")
        u = get_db().execute(
            "SELECT * FROM usuarios WHERE correo = ? AND activo = 1", (correo,)).fetchone()
        if u and check_password_hash(u["clave_hash"], clave):
            session.clear()
            session["usuario_id"] = u["id"]
            return redirect(url_for(INICIO_POR_ROL[u["rol"]]))
        flash("Correo o contraseña incorrectos.", "error")

    cfg = current_app.config
    demo = cfg["CREDENCIALES_DEMO"] if cfg["MOSTRAR_CREDENCIALES_DEMO"] else []
    return render_template("auth/login.html", credenciales=demo)


@bp.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada.", "ok")
    return redirect(url_for("auth.login"))