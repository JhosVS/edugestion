from functools import wraps

from flask import (Blueprint, abort, current_app, flash, g, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from .ajustes import ajustes
from .auditoria import registrar
from .db import get_db
from .utils import ahora

bp = Blueprint("auth", __name__)

INICIO_POR_ROL = {
    "alumno": "alumno.inicio",
    "docente": "docente.inicio",
    "director": "director.inicio",
    "admin": "admin.inicio",
}


def login_required(*roles):
    """Exige sesión iniciada y, si se indican, uno de los roles: login_required("director", "admin")."""
    def decorador(vista):
        @wraps(vista)
        def envoltura(*args, **kwargs):
            if g.usuario is None:
                return redirect(url_for("auth.login"))
            if roles and g.usuario["rol"] not in roles:
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


def _bloqueado(correo):
    """True si el correo acumuló demasiados intentos fallidos en los últimos minutos."""
    cfg = current_app.config
    fallos = get_db().execute(
        "SELECT COUNT(*) FROM auditoria WHERE accion = 'login_fallido' AND detalle = ? "
        "AND fecha >= ?", (correo, ahora(minutes=-cfg["BLOQUEO_MINUTOS"]))).fetchone()[0]
    return fallos >= cfg["INTENTOS_MAXIMOS"]


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
        if _bloqueado(correo):
            registrar("login_bloqueado", correo)
            flash(f"Demasiados intentos fallidos. Espera {current_app.config['BLOQUEO_MINUTOS']} "
                  "minutos e inténtalo de nuevo.", "error")
        else:
            db = get_db()
            u = db.execute("SELECT * FROM usuarios WHERE correo = ? AND activo = 1",
                           (correo,)).fetchone()
            if u and check_password_hash(u["clave_hash"], clave):
                session.clear()
                session["usuario_id"] = u["id"]
                db.execute("UPDATE usuarios SET ultimo_acceso = ? WHERE id = ?", (ahora(), u["id"]))
                registrar("login", usuario_id=u["id"])
                return redirect(url_for(INICIO_POR_ROL[u["rol"]]))
            registrar("login_fallido", correo)
            flash("Correo o contraseña incorrectos.", "error")

    demo = []
    if ajustes()["mostrar_demo"] == "1":  # solo las cuentas de prueba que existen y están activas
        activas = {r[0] for r in get_db().execute("SELECT correo FROM usuarios WHERE activo = 1")}
        demo = [c for c in current_app.config["CREDENCIALES_DEMO"] if c[1] in activas]
    return render_template("auth/login.html", credenciales=demo)


@bp.route("/logout")
def logout():
    if g.usuario is not None:
        registrar("logout")
    session.clear()
    flash("Sesión cerrada.", "ok")
    return redirect(url_for("auth.login"))


@bp.route("/cuenta", methods=["GET", "POST"])
@login_required()
def cuenta():
    """Cada usuario cambia su propia contraseña."""
    if request.method == "POST":
        db = get_db()
        actual = request.form.get("actual", "")
        nueva = request.form.get("nueva", "")
        hash_actual = db.execute("SELECT clave_hash FROM usuarios WHERE id = ?",
                                 (g.usuario["id"],)).fetchone()[0]
        if not check_password_hash(hash_actual, actual):
            flash("La contraseña actual no es correcta.", "error")
        elif len(nueva) < 6:
            flash("La nueva contraseña debe tener al menos 6 caracteres.", "error")
        elif nueva != request.form.get("confirmar", ""):
            flash("La confirmación no coincide con la nueva contraseña.", "error")
        else:
            db.execute("UPDATE usuarios SET clave_hash = ? WHERE id = ?",
                       (generate_password_hash(nueva), g.usuario["id"]))
            registrar("clave", "Cambió su propia contraseña")
            flash("Contraseña actualizada.", "ok")
            return redirect(url_for("auth.cuenta"))
    return render_template("auth/cuenta.html")
