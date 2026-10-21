"""Gestión de datos maestros (director y administrador): usuarios, secciones, cursos,
asignaciones docente-curso-sección y horarios. Solo un administrador gestiona
cuentas de administrador."""
import re
import sqlite3
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash

from ..ajustes import ajustes
from ..auditoria import registrar
from ..auth import login_required
from ..consultas import DIAS_SEMANA, horario
from ..db import get_db

bp = Blueprint("gestion", __name__, url_prefix="/director/gestion")

ROLES = {"alumno": "Alumno", "docente": "Docente", "director": "Director", "admin": "Administrador"}
HORA = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


@bp.before_request
@login_required("director", "admin")
def solo_director_o_admin():
    """Todas las vistas de este Blueprint exigen el rol director o admin."""


def _roles_visibles():
    """El director no ve ni crea cuentas de administrador (así no puede darse ese rol)."""
    if g.usuario["rol"] == "admin":
        return ROLES
    return {k: v for k, v in ROLES.items() if k != "admin"}


def _secciones():
    return get_db().execute("SELECT id, anio, grado, seccion FROM secciones "
                            "ORDER BY anio DESC, grado, seccion").fetchall()


def _seccion_elegida(secciones):
    """?seccion= de la URL; si falta o no existe, la primera sección."""
    sid = request.values.get("seccion", type=int)
    return next((s for s in secciones if s["id"] == sid), secciones[0] if secciones else None)


# --------------------------------------------------------------------------
# Portada
# --------------------------------------------------------------------------
@bp.route("/")
def inicio():
    db = get_db()
    conteo = {r["rol"]: r["n"] for r in db.execute(
        "SELECT rol, COUNT(*) AS n FROM usuarios WHERE activo = 1 GROUP BY rol")}
    total = {
        "alumnos": conteo.get("alumno", 0),
        "docentes": conteo.get("docente", 0),
        "secciones": db.execute("SELECT COUNT(*) FROM secciones").fetchone()[0],
        "cursos": db.execute("SELECT COUNT(*) FROM cursos").fetchone()[0],
        "sin_docente": db.execute(
            "SELECT COUNT(*) FROM secciones s CROSS JOIN cursos c WHERE NOT EXISTS "
            "(SELECT 1 FROM asignaciones a WHERE a.seccion_id = s.id AND a.curso_id = c.id)"
        ).fetchone()[0],
    }
    return render_template("gestion/inicio.html", total=total)


# --------------------------------------------------------------------------
# Usuarios
# --------------------------------------------------------------------------
@bp.route("/usuarios")
def usuarios():
    roles = _roles_visibles()
    rol = request.args.get("rol", "alumno")
    rol = rol if rol in roles else "alumno"
    lista = get_db().execute(
        "SELECT u.id, u.nombres, u.apellidos, u.correo, u.activo, al.dni, s.grado, s.seccion "
        "FROM usuarios u LEFT JOIN alumnos al ON al.usuario_id = u.id "
        "LEFT JOIN secciones s ON s.id = al.seccion_id WHERE u.rol = ? "
        "ORDER BY u.activo DESC, s.grado, s.seccion, u.apellidos, u.nombres", (rol,)).fetchall()
    return render_template("gestion/usuarios.html", usuarios=lista, rol=rol, roles=roles)


def _leer_usuario(actual):
    """Valida el formulario. Devuelve (datos, errores)."""
    f = request.form
    d = {k: f.get(k, "").strip() for k in ("nombres", "apellidos", "correo", "dni")}
    d["correo"] = d["correo"].lower()
    d["rol"] = actual["rol"] if actual else f.get("rol", "")
    d["clave"] = f.get("clave", "")
    d["seccion_id"] = f.get("seccion_id", type=int)
    d["activo"] = 1 if (actual is None or f.get("activo")) else 0

    errores = []
    if not (d["nombres"] and d["apellidos"] and d["correo"]):
        errores.append("Completa nombres, apellidos y correo.")
    elif not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", d["correo"]):
        errores.append("El correo no es válido.")
    if d["rol"] not in _roles_visibles():
        errores.append("Elige un rol.")
    if (actual is None or d["clave"]) and len(d["clave"]) < 6:
        errores.append("La contraseña debe tener al menos 6 caracteres.")
    if d["rol"] == "alumno":
        if d["seccion_id"] not in {s["id"] for s in _secciones()}:
            errores.append("Elige la sección del alumno.")
        if d["dni"] and not re.fullmatch(r"\d{8,14}", d["dni"]):
            errores.append("El DNI o código debe tener entre 8 y 14 dígitos.")
    if actual and actual["id"] == g.usuario["id"] and not d["activo"]:
        errores.append("No puedes desactivar tu propia cuenta.")
    return d, errores


def _form_usuario(actual=None):
    datos = dict(actual) if actual else {"rol": request.args.get("rol", "alumno"), "activo": 1}
    if request.method == "POST":
        d, errores = _leer_usuario(actual)
        if not errores:
            db = get_db()
            try:
                if actual is None:
                    uid = db.execute(
                        "INSERT INTO usuarios(nombres, apellidos, correo, clave_hash, rol) "
                        "VALUES (?,?,?,?,?)", (d["nombres"], d["apellidos"], d["correo"],
                                               generate_password_hash(d["clave"]), d["rol"])).lastrowid
                else:
                    uid = actual["id"]
                    db.execute("UPDATE usuarios SET nombres = ?, apellidos = ?, correo = ?, activo = ? "
                               "WHERE id = ?", (d["nombres"], d["apellidos"], d["correo"],
                                                d["activo"], uid))
                    if d["clave"]:
                        db.execute("UPDATE usuarios SET clave_hash = ? WHERE id = ?",
                                   (generate_password_hash(d["clave"]), uid))
                if d["rol"] == "alumno":
                    db.execute("INSERT INTO alumnos(usuario_id, seccion_id, dni) VALUES (?,?,?) "
                               "ON CONFLICT(usuario_id) DO UPDATE SET seccion_id = excluded.seccion_id, "
                               "dni = excluded.dni", (uid, d["seccion_id"], d["dni"] or None))
                db.commit()
            except sqlite3.IntegrityError:
                db.rollback()
                errores.append("El correo o el DNI ya está registrado.")
            else:
                nombre = f'{d["nombres"]} {d["apellidos"]} ({d["correo"]})'
                if actual is None:
                    registrar("usuario", f"Creó {ROLES[d['rol']].lower()}: {nombre}")
                else:
                    campos = ["nombres", "apellidos", "correo", "activo"]
                    if d["rol"] == "alumno":
                        campos += ["dni", "seccion_id"]
                    cambios = [c for c in campos if str(actual[c] or "") != str(d[c] or "")]
                    if d["clave"]:
                        cambios.append("contraseña")
                    registrar("usuario", f"Editó {nombre}: {', '.join(cambios) or 'sin cambios'}")
                flash("Usuario guardado.", "ok")
                return redirect(url_for("gestion.usuarios", rol=d["rol"]))
        for e in errores:
            flash(e, "error")
        datos = {**datos, **d}
    return render_template("gestion/usuario_form.html", u=datos, nuevo=actual is None,
                           roles=_roles_visibles(), secciones=_secciones())


@bp.route("/usuarios/nuevo", methods=["GET", "POST"])
def usuario_nuevo():
    return _form_usuario()


@bp.route("/usuarios/<int:usuario_id>", methods=["GET", "POST"])
def usuario_editar(usuario_id):
    u = get_db().execute(
        "SELECT u.id, u.nombres, u.apellidos, u.correo, u.rol, u.activo, al.dni, al.seccion_id "
        "FROM usuarios u LEFT JOIN alumnos al ON al.usuario_id = u.id WHERE u.id = ?",
        (usuario_id,)).fetchone()
    if u is None:
        abort(404)
    if u["rol"] not in _roles_visibles():
        abort(403)
    return _form_usuario(u)


# --------------------------------------------------------------------------
# Secciones
# --------------------------------------------------------------------------
@bp.route("/secciones", methods=["GET", "POST"])
def secciones():
    db = get_db()
    if request.method == "POST":
        anio = request.form.get("anio", type=int)
        grado = request.form.get("grado", "").strip()
        letra = request.form.get("seccion", "").strip().upper()
        if not (anio and 2000 <= anio <= 2100 and grado and letra):
            flash("Completa año, grado y sección.", "error")
        else:
            try:
                db.execute("INSERT INTO secciones(anio, grado, seccion) VALUES (?,?,?)",
                           (anio, grado[:20], letra[:5]))
                db.commit()
                registrar("seccion", f'Creó {anio} {grado} "{letra}"')
                flash(f'Sección {grado} "{letra}" creada.', "ok")
            except sqlite3.IntegrityError:
                flash("Esa sección ya existe.", "error")
        return redirect(url_for("gestion.secciones"))

    lista = db.execute(
        "SELECT s.*, (SELECT COUNT(*) FROM alumnos al JOIN usuarios u ON u.id = al.usuario_id "
        "  WHERE al.seccion_id = s.id AND u.activo = 1) AS alumnos, "
        " (SELECT COUNT(*) FROM asignaciones a WHERE a.seccion_id = s.id) AS cursos "
        "FROM secciones s ORDER BY s.anio DESC, s.grado, s.seccion").fetchall()
    return render_template("gestion/secciones.html", secciones=lista, anio=ajustes()["anio_lectivo"])


@bp.route("/secciones/<int:seccion_id>/eliminar", methods=["POST"])
def seccion_eliminar(seccion_id):
    db = get_db()
    ocupada = db.execute(
        "SELECT EXISTS(SELECT 1 FROM alumnos WHERE seccion_id = ?) "
        "OR EXISTS(SELECT 1 FROM asignaciones WHERE seccion_id = ?)",
        (seccion_id, seccion_id)).fetchone()[0]
    if ocupada:
        flash("No se puede eliminar: la sección tiene alumnos o cursos asignados.", "error")
    else:
        s = db.execute("SELECT anio, grado, seccion FROM secciones WHERE id = ?",
                       (seccion_id,)).fetchone() or abort(404)
        db.execute("DELETE FROM secciones WHERE id = ?", (seccion_id,))
        db.commit()
        registrar("seccion", f'Eliminó {s["anio"]} {s["grado"]} "{s["seccion"]}"')
        flash("Sección eliminada.", "ok")
    return redirect(url_for("gestion.secciones"))


# --------------------------------------------------------------------------
# Cursos y competencias
# --------------------------------------------------------------------------
@bp.route("/cursos", methods=["GET", "POST"])
def cursos():
    db = get_db()
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        if not nombre:
            flash("Escribe el nombre del curso.", "error")
        else:
            try:
                db.execute("INSERT INTO cursos(nombre) VALUES (?)", (nombre[:80],))
                db.commit()
                registrar("curso", f"Creó el curso {nombre[:80]}")
                flash(f"Curso {nombre} creado. Ahora agrégale sus competencias.", "ok")
            except sqlite3.IntegrityError:
                flash("Ese curso ya existe.", "error")
        return redirect(url_for("gestion.cursos"))

    lista = {}
    for f in db.execute(
            "SELECT c.id, c.nombre, co.id AS comp_id, co.nombre AS competencia, "
            " (SELECT COUNT(*) FROM calificaciones k WHERE k.competencia_id = co.id) AS notas, "
            " (SELECT COUNT(*) FROM asignaciones a WHERE a.curso_id = c.id) AS asignaciones "
            "FROM cursos c LEFT JOIN competencias co ON co.curso_id = c.id "
            "ORDER BY c.nombre, co.id"):
        curso = lista.setdefault(f["id"], {"id": f["id"], "nombre": f["nombre"],
                                           "asignaciones": f["asignaciones"], "competencias": []})
        if f["comp_id"]:
            curso["competencias"].append({"id": f["comp_id"], "nombre": f["competencia"],
                                          "notas": f["notas"]})
    return render_template("gestion/cursos.html", cursos=list(lista.values()))


@bp.route("/cursos/<int:curso_id>/eliminar", methods=["POST"])
def curso_eliminar(curso_id):
    db = get_db()
    en_uso = db.execute(
        "SELECT EXISTS(SELECT 1 FROM asignaciones WHERE curso_id = ?) OR EXISTS(SELECT 1 "
        "FROM calificaciones k JOIN competencias co ON co.id = k.competencia_id WHERE co.curso_id = ?)",
        (curso_id, curso_id)).fetchone()[0]
    if en_uso:
        flash("No se puede eliminar: el curso está asignado o ya tiene calificativos.", "error")
    else:
        c = db.execute("SELECT nombre FROM cursos WHERE id = ?", (curso_id,)).fetchone() or abort(404)
        db.execute("DELETE FROM cursos WHERE id = ?", (curso_id,))
        db.commit()
        registrar("curso", f"Eliminó el curso {c['nombre']}")
        flash("Curso eliminado.", "ok")
    return redirect(url_for("gestion.cursos"))


@bp.route("/cursos/<int:curso_id>/competencias", methods=["POST"])
def competencia_nueva(curso_id):
    db = get_db()
    nombre = request.form.get("nombre", "").strip()
    if not nombre:
        flash("Escribe el nombre de la competencia.", "error")
    else:
        try:
            db.execute("INSERT INTO competencias(curso_id, nombre) VALUES (?,?)",
                       (curso_id, nombre[:200]))
            db.commit()
            registrar("curso", f"Agregó la competencia '{nombre[:200]}' (curso {curso_id})")
            flash("Competencia agregada.", "ok")
        except sqlite3.IntegrityError:  # repetida o curso inexistente
            flash("No se pudo agregar: la competencia ya existe en ese curso.", "error")
    return redirect(url_for("gestion.cursos"))


@bp.route("/competencias/<int:competencia_id>/eliminar", methods=["POST"])
def competencia_eliminar(competencia_id):
    db = get_db()
    if db.execute("SELECT EXISTS(SELECT 1 FROM calificaciones WHERE competencia_id = ?)",
                  (competencia_id,)).fetchone()[0]:
        flash("No se puede eliminar: la competencia ya tiene calificativos registrados.", "error")
    else:
        co = db.execute("SELECT nombre FROM competencias WHERE id = ?",
                        (competencia_id,)).fetchone() or abort(404)
        db.execute("DELETE FROM competencias WHERE id = ?", (competencia_id,))
        db.commit()
        registrar("curso", f"Eliminó la competencia '{co['nombre']}'")
        flash("Competencia eliminada.", "ok")
    return redirect(url_for("gestion.cursos"))


# --------------------------------------------------------------------------
# Asignaciones: qué docente dicta cada curso en una sección
# --------------------------------------------------------------------------
@bp.route("/asignaciones", methods=["GET", "POST"])
def asignaciones():
    db = get_db()
    lista_secciones = _secciones()
    seccion = _seccion_elegida(lista_secciones)
    docentes = db.execute("SELECT id, nombres || ' ' || apellidos AS nombre FROM usuarios "
                          "WHERE rol = 'docente' AND activo = 1 ORDER BY apellidos").fetchall()

    if request.method == "POST" and seccion:
        validos = {d["id"] for d in docentes}
        for (curso_id,) in db.execute("SELECT id FROM cursos").fetchall():
            docente_id = request.form.get(f"doc_{curso_id}", type=int)
            if docente_id in validos:
                db.execute("INSERT INTO asignaciones(docente_id, curso_id, seccion_id) VALUES (?,?,?) "
                           "ON CONFLICT(curso_id, seccion_id) DO UPDATE SET docente_id = excluded.docente_id",
                           (docente_id, curso_id, seccion["id"]))
            elif request.form.get(f"doc_{curso_id}") == "":  # "Sin asignar" (borra también su horario)
                db.execute("DELETE FROM asignaciones WHERE curso_id = ? AND seccion_id = ?",
                           (curso_id, seccion["id"]))
        db.commit()
        registrar("asignacion", f'Guardó las asignaciones de {seccion["grado"]} "{seccion["seccion"]}"')
        flash("Asignaciones guardadas.", "ok")
        return redirect(url_for("gestion.asignaciones", seccion=seccion["id"]))

    filas = db.execute(
        "SELECT c.id, c.nombre, a.docente_id FROM cursos c "
        "LEFT JOIN asignaciones a ON a.curso_id = c.id AND a.seccion_id = ? ORDER BY c.nombre",
        (seccion["id"] if seccion else None,)).fetchall()
    return render_template("gestion/asignaciones.html", secciones=lista_secciones,
                           seccion=seccion, filas=filas, docentes=docentes)


# --------------------------------------------------------------------------
# Horarios por sección
# --------------------------------------------------------------------------
@bp.route("/horarios", methods=["GET", "POST"])
def horarios():
    db = get_db()
    lista_secciones = _secciones()
    seccion = _seccion_elegida(lista_secciones)

    if request.method == "POST" and seccion:
        f = request.form
        asig = db.execute("SELECT id, docente_id FROM asignaciones WHERE id = ? AND seccion_id = ?",
                          (f.get("asignacion_id", type=int), seccion["id"])).fetchone()
        dia, inicio, fin = f.get("dia", type=int), f.get("inicio", ""), f.get("fin", "")
        if not (asig and dia in DIAS_SEMANA and HORA.match(inicio) and HORA.match(fin)):
            flash("Completa curso, día y horas.", "error")
        elif fin <= inicio:
            flash("La hora de fin debe ser posterior a la de inicio.", "error")
        else:
            # Se cruza si empieza antes de que termine el otro y termina después de que empiece.
            cruce = db.execute(
                "SELECT c.nombre AS curso, s.grado, s.seccion FROM horarios h "
                "JOIN asignaciones a ON a.id = h.asignacion_id JOIN cursos c ON c.id = a.curso_id "
                "JOIN secciones s ON s.id = a.seccion_id "
                "WHERE h.dia_semana = ? AND h.hora_inicio < ? AND ? < h.hora_fin "
                " AND (a.seccion_id = ? OR a.docente_id = ?) "
                "ORDER BY a.seccion_id = ? DESC LIMIT 1",  # primero el cruce en la misma sección
                (dia, fin, inicio, seccion["id"], asig["docente_id"], seccion["id"])).fetchone()
            if cruce:
                flash(f'Se cruza con {cruce["curso"]} en {cruce["grado"]} "{cruce["seccion"]}".',
                      "error")
            else:
                db.execute("INSERT INTO horarios(asignacion_id, dia_semana, hora_inicio, hora_fin) "
                           "VALUES (?,?,?,?)", (asig["id"], dia, inicio, fin))
                db.commit()
                registrar("horario", f'{seccion["grado"]} "{seccion["seccion"]}": agregó '
                                     f'{DIAS_SEMANA[dia]} {inicio}-{fin}')
                flash("Bloque agregado al horario.", "ok")
        return redirect(url_for("gestion.horarios", seccion=seccion["id"]))

    sid = seccion["id"] if seccion else None
    asigs = db.execute(
        "SELECT a.id, c.nombre AS curso, u.nombres || ' ' || u.apellidos AS docente "
        "FROM asignaciones a JOIN cursos c ON c.id = a.curso_id "
        "JOIN usuarios u ON u.id = a.docente_id WHERE a.seccion_id = ? ORDER BY c.nombre",
        (sid,)).fetchall()
    return render_template("gestion/horarios.html", secciones=lista_secciones, seccion=seccion,
                           asignaciones=asigs, bloques=horario(db, seccion_id=sid) if sid else [],
                           dias=DIAS_SEMANA)


@bp.route("/horarios/<int:horario_id>/eliminar", methods=["POST"])
def horario_eliminar(horario_id):
    db = get_db()
    fila = db.execute("SELECT a.seccion_id FROM horarios h JOIN asignaciones a "
                      "ON a.id = h.asignacion_id WHERE h.id = ?", (horario_id,)).fetchone()
    if fila is None:
        abort(404)
    db.execute("DELETE FROM horarios WHERE id = ?", (horario_id,))
    db.commit()
    registrar("horario", f"Quitó un bloque del horario (sección {fila['seccion_id']})")
    flash("Bloque eliminado.", "ok")
    return redirect(url_for("gestion.horarios", seccion=fila["seccion_id"]))
