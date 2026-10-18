from flask import Blueprint, g, render_template

from ..auth import login_required
from ..db import get_db

bp = Blueprint("alumno", __name__, url_prefix="/alumno")


def _perfil():
    return get_db().execute(
        "SELECT s.id AS seccion_id, s.anio, s.grado, s.seccion "
        "FROM alumnos a JOIN secciones s ON s.id = a.seccion_id "
        "WHERE a.usuario_id = ?", (g.usuario["id"],)).fetchone()


def _resumen_asistencia(alumno_id):
    filas = get_db().execute(
        "SELECT estado, COUNT(*) AS n FROM asistencias WHERE alumno_id = ? GROUP BY estado",
        (alumno_id,)).fetchall()
    c = {"P": 0, "T": 0, "F": 0}
    c.update({f["estado"]: f["n"] for f in filas})
    total = sum(c.values())
    # Una tardanza cuenta como asistencia (el alumno vino, pero tarde).
    pct = round(100 * (c["P"] + c["T"]) / total) if total else None
    return {**c, "total": total, "pct": pct}


@bp.route("/")
@login_required("alumno")
def inicio():
    db = get_db()
    filas = db.execute(
        "SELECT calificativo, COUNT(*) AS n FROM calificaciones "
        "WHERE alumno_id = ? GROUP BY calificativo", (g.usuario["id"],)).fetchall()
    conteo = {"AD": 0, "A": 0, "B": 0, "C": 0}
    conteo.update({f["calificativo"]: f["n"] for f in filas})
    return render_template("alumno/inicio.html", perfil=_perfil(),
                           asistencia=_resumen_asistencia(g.usuario["id"]),
                           conteo=conteo)


@bp.route("/cursos")
@login_required("alumno")
def cursos():
    return render_template("proximamente.html", titulo="Cursos", icono_nombre="cursos",
                           texto="Aquí verás tus cursos con sus horarios.")


@bp.route("/libreta")
@login_required("alumno")
def libreta():
    db = get_db()
    perfil = _perfil()
    filas = db.execute(
        "SELECT c.id AS curso_id, c.nombre AS curso, "
        "       u.nombres || ' ' || u.apellidos AS docente, "
        "       co.id AS comp_id, co.nombre AS competencia "
        "FROM asignaciones a "
        "JOIN cursos c ON c.id = a.curso_id "
        "JOIN usuarios u ON u.id = a.docente_id "
        "JOIN competencias co ON co.curso_id = c.id "
        "WHERE a.seccion_id = ? ORDER BY c.nombre, co.id", (perfil["seccion_id"],)).fetchall()

    notas = {}
    for n in db.execute("SELECT competencia_id, bimestre, calificativo FROM calificaciones "
                        "WHERE alumno_id = ?", (g.usuario["id"],)):
        notas.setdefault(n["competencia_id"], {})[n["bimestre"]] = n["calificativo"]

    cursos = {}
    for f in filas:
        curso = cursos.setdefault(f["curso_id"], {
            "nombre": f["curso"], "docente": f["docente"], "competencias": []})
        curso["competencias"].append({
            "nombre": f["competencia"], "notas": notas.get(f["comp_id"], {})})

    return render_template("alumno/libreta.html", perfil=perfil, cursos=list(cursos.values()))


@bp.route("/asistencia")
@login_required("alumno")
def asistencia():
    registros = get_db().execute(
        "SELECT fecha, estado FROM asistencias WHERE alumno_id = ? "
        "ORDER BY fecha DESC LIMIT 30", (g.usuario["id"],)).fetchall()
    return render_template("alumno/asistencia.html",
                           resumen=_resumen_asistencia(g.usuario["id"]), registros=registros)