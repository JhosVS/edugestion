from datetime import date

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from ..auth import login_required
from ..db import get_db

bp = Blueprint("docente", __name__, url_prefix="/docente")

ESTADOS = {"P": "Presente", "T": "Tardanza", "F": "Falta"}
CALIFICATIVOS = ("AD", "A", "B", "C")

ALUMNOS_SQL = ("SELECT u.id, u.apellidos || ', ' || u.nombres AS nombre FROM alumnos al "
               "JOIN usuarios u ON u.id = al.usuario_id WHERE al.seccion_id = ? "
               "ORDER BY u.apellidos, u.nombres")


# --------------------------------------------------------------------------
# Ayudas
# --------------------------------------------------------------------------
def _bimestre():
    b = request.values.get("bimestre", 1, type=int)
    return b if b in (1, 2, 3, 4) else 1


def _fecha():
    """Fecha pedida (AAAA-MM-DD); si es inválida o futura, usa hoy."""
    try:
        d = date.fromisoformat(request.values.get("fecha", ""))
    except ValueError:
        d = date.today()
    return min(d, date.today()).isoformat()


def _seccion_del_docente(seccion_id):
    """La sección solo es válida si el docente dicta algún curso en ella."""
    s = get_db().execute(
        "SELECT * FROM secciones s WHERE s.id = ? AND EXISTS "
        "(SELECT 1 FROM asignaciones a WHERE a.seccion_id = s.id AND a.docente_id = ?)",
        (seccion_id, g.usuario["id"])).fetchone()
    return s or abort(404)


def _asignacion_del_docente(asignacion_id):
    a = get_db().execute(
        "SELECT a.id, a.curso_id, a.seccion_id, c.nombre AS curso, s.grado, s.seccion "
        "FROM asignaciones a JOIN cursos c ON c.id = a.curso_id "
        "JOIN secciones s ON s.id = a.seccion_id "
        "WHERE a.id = ? AND a.docente_id = ?", (asignacion_id, g.usuario["id"])).fetchone()
    return a or abort(404)


# --------------------------------------------------------------------------
# Inicio: resumen de cursos y avance de notas
# --------------------------------------------------------------------------
@bp.route("/")
@login_required("docente")
def inicio():
    bimestre = _bimestre()
    filas = get_db().execute(
        "SELECT a.id, c.nombre AS curso, s.id AS seccion_id, s.grado, s.seccion, "
        " (SELECT COUNT(*) FROM alumnos al WHERE al.seccion_id = s.id) * "
        " (SELECT COUNT(*) FROM competencias co WHERE co.curso_id = c.id) AS esperados, "
        " (SELECT COUNT(*) FROM calificaciones k "
        "   JOIN alumnos al ON al.usuario_id = k.alumno_id "
        "   JOIN competencias co ON co.id = k.competencia_id "
        "  WHERE al.seccion_id = s.id AND co.curso_id = c.id AND k.bimestre = ?) AS registrados "
        "FROM asignaciones a JOIN cursos c ON c.id = a.curso_id "
        "JOIN secciones s ON s.id = a.seccion_id WHERE a.docente_id = ? "
        "ORDER BY s.grado, s.seccion, c.nombre", (bimestre, g.usuario["id"])).fetchall()
    cursos = [dict(f, pct=round(100 * f["registrados"] / f["esperados"]) if f["esperados"] else 0)
              for f in filas]
    return render_template("docente/inicio.html", cursos=cursos, bimestre=bimestre,
                           n_secciones=len({c["seccion_id"] for c in cursos}))


# --------------------------------------------------------------------------
# Asistencia diaria (por sección)
# --------------------------------------------------------------------------
@bp.route("/asistencia")
@login_required("docente")
def asistencia():
    hoy = date.today().isoformat()
    secciones = get_db().execute(
        "SELECT DISTINCT s.id, s.grado, s.seccion, "
        " (SELECT COUNT(*) FROM alumnos al WHERE al.seccion_id = s.id) AS total, "
        " (SELECT COUNT(*) FROM asistencias x JOIN alumnos al ON al.usuario_id = x.alumno_id "
        "  WHERE al.seccion_id = s.id AND x.fecha = ?) AS hoy "
        "FROM asignaciones a JOIN secciones s ON s.id = a.seccion_id "
        "WHERE a.docente_id = ? ORDER BY s.grado, s.seccion", (hoy, g.usuario["id"])).fetchall()
    return render_template("docente/asistencia_lista.html", secciones=secciones)


@bp.route("/asistencia/<int:seccion_id>", methods=["GET", "POST"])
@login_required("docente")
def asistencia_seccion(seccion_id):
    db = get_db()
    seccion = _seccion_del_docente(seccion_id)
    fecha = _fecha()
    alumnos = db.execute(ALUMNOS_SQL, (seccion_id,)).fetchall()

    if request.method == "POST":
        for a in alumnos:
            estado = request.form.get(f"est_{a['id']}")
            if estado in ESTADOS:
                db.execute(
                    "INSERT INTO asistencias(alumno_id, fecha, estado, registrado_por) "
                    "VALUES (?,?,?,?) ON CONFLICT(alumno_id, fecha) DO UPDATE SET "
                    "estado = excluded.estado, registrado_por = excluded.registrado_por",
                    (a["id"], fecha, estado, g.usuario["id"]))
        db.commit()
        flash("Asistencia guardada.", "ok")
        return redirect(url_for("docente.asistencia_seccion", seccion_id=seccion_id, fecha=fecha))

    previos = {r["alumno_id"]: r["estado"] for r in db.execute(
        "SELECT alumno_id, estado FROM asistencias WHERE fecha = ? AND alumno_id IN "
        "(SELECT usuario_id FROM alumnos WHERE seccion_id = ?)", (fecha, seccion_id))}
    return render_template("docente/asistencia.html", seccion=seccion, alumnos=alumnos,
                           fecha=fecha, hoy=date.today().isoformat(),
                           previos=previos, estados=ESTADOS)


# --------------------------------------------------------------------------
# Notas por competencia (por curso y sección)
# --------------------------------------------------------------------------
@bp.route("/notas")
@login_required("docente")
def notas():
    asignaciones = get_db().execute(
        "SELECT a.id, c.nombre AS curso, s.grado, s.seccion FROM asignaciones a "
        "JOIN cursos c ON c.id = a.curso_id JOIN secciones s ON s.id = a.seccion_id "
        "WHERE a.docente_id = ? ORDER BY s.grado, s.seccion, c.nombre",
        (g.usuario["id"],)).fetchall()
    return render_template("docente/notas_lista.html", asignaciones=asignaciones)


@bp.route("/notas/<int:asignacion_id>", methods=["GET", "POST"])
@login_required("docente")
def notas_asignacion(asignacion_id):
    db = get_db()
    asig = _asignacion_del_docente(asignacion_id)
    bimestre = _bimestre()
    alumnos = db.execute(ALUMNOS_SQL, (asig["seccion_id"],)).fetchall()
    competencias = db.execute("SELECT id, nombre FROM competencias WHERE curso_id = ? ORDER BY id",
                              (asig["curso_id"],)).fetchall()

    if request.method == "POST":
        for a in alumnos:
            for c in competencias:
                valor = request.form.get(f"n_{a['id']}_{c['id']}", "")
                if valor in CALIFICATIVOS:
                    db.execute(
                        "INSERT INTO calificaciones(alumno_id, competencia_id, bimestre, "
                        "calificativo, registrado_por) VALUES (?,?,?,?,?) "
                        "ON CONFLICT(alumno_id, competencia_id, bimestre) DO UPDATE SET "
                        "calificativo = excluded.calificativo, "
                        "registrado_por = excluded.registrado_por, actualizado_en = datetime('now')",
                        (a["id"], c["id"], bimestre, valor, g.usuario["id"]))
                elif valor == "":  # "—" borra el calificativo
                    db.execute("DELETE FROM calificaciones WHERE alumno_id = ? "
                               "AND competencia_id = ? AND bimestre = ?", (a["id"], c["id"], bimestre))
        db.commit()
        flash("Calificativos guardados.", "ok")
        return redirect(url_for("docente.notas_asignacion", asignacion_id=asignacion_id,
                                bimestre=bimestre))

    previos = {(r["alumno_id"], r["competencia_id"]): r["calificativo"] for r in db.execute(
        "SELECT k.alumno_id, k.competencia_id, k.calificativo FROM calificaciones k "
        "JOIN competencias co ON co.id = k.competencia_id "
        "WHERE co.curso_id = ? AND k.bimestre = ?", (asig["curso_id"], bimestre))}
    return render_template("docente/notas.html", asig=asig, bimestre=bimestre, alumnos=alumnos,
                           competencias=competencias, previos=previos,
                           calificativos=CALIFICATIVOS)