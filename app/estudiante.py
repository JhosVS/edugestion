"""Información de un estudiante. La consultan el propio alumno y sus padres o apoderados."""
from datetime import date

from .db import get_db


def perfil(alumno_id):
    return get_db().execute(
        "SELECT al.usuario_id AS id, u.nombres, u.apellidos, s.id AS seccion_id, s.anio, s.grado, "
        " s.seccion FROM alumnos al JOIN usuarios u ON u.id = al.usuario_id "
        "JOIN secciones s ON s.id = al.seccion_id WHERE al.usuario_id = ?", (alumno_id,)).fetchone()


def resumen_asistencia(alumno_id):
    filas = get_db().execute(
        "SELECT estado, COUNT(*) AS n FROM asistencias WHERE alumno_id = ? GROUP BY estado",
        (alumno_id,)).fetchall()
    c = {"P": 0, "T": 0, "F": 0}
    c.update({f["estado"]: f["n"] for f in filas})
    total = sum(c.values())
    # Una tardanza cuenta como asistencia (el alumno vino, pero tarde).
    pct = round(100 * (c["P"] + c["T"]) / total) if total else None
    return {**c, "total": total, "pct": pct}


def ultimas_asistencias(alumno_id, limite=30):
    return get_db().execute(
        "SELECT fecha, estado FROM asistencias WHERE alumno_id = ? "
        "ORDER BY fecha DESC LIMIT ?", (alumno_id, limite)).fetchall()


def conteo_calificativos(alumno_id):
    conteo = {"AD": 0, "A": 0, "B": 0, "C": 0}
    conteo.update({f["calificativo"]: f["n"] for f in get_db().execute(
        "SELECT calificativo, COUNT(*) AS n FROM calificaciones "
        "WHERE alumno_id = ? GROUP BY calificativo", (alumno_id,))})
    return conteo


def libreta(alumno_id, seccion_id):
    """Cursos de la sección con sus competencias y el calificativo de cada bimestre."""
    db = get_db()
    filas = db.execute(
        "SELECT c.id AS curso_id, c.nombre AS curso, "
        "       u.nombres || ' ' || u.apellidos AS docente, "
        "       co.id AS comp_id, co.nombre AS competencia "
        "FROM asignaciones a "
        "JOIN cursos c ON c.id = a.curso_id "
        "JOIN usuarios u ON u.id = a.docente_id "
        "JOIN competencias co ON co.curso_id = c.id "
        "WHERE a.seccion_id = ? ORDER BY c.nombre, co.id", (seccion_id,)).fetchall()

    notas = {}
    for n in db.execute("SELECT competencia_id, bimestre, calificativo FROM calificaciones "
                        "WHERE alumno_id = ?", (alumno_id,)):
        notas.setdefault(n["competencia_id"], {})[n["bimestre"]] = n["calificativo"]

    cursos = {}
    for f in filas:
        curso = cursos.setdefault(f["curso_id"], {
            "nombre": f["curso"], "docente": f["docente"], "competencias": []})
        curso["competencias"].append({
            "nombre": f["competencia"], "notas": notas.get(f["comp_id"], {})})
    return list(cursos.values())


def cursos(seccion_id):
    return get_db().execute(
        "SELECT c.nombre AS curso, u.nombres || ' ' || u.apellidos AS docente, "
        " (SELECT GROUP_CONCAT(co.nombre, '|') FROM competencias co "
        "   WHERE co.curso_id = c.id) AS competencias "
        "FROM asignaciones a JOIN cursos c ON c.id = a.curso_id "
        "JOIN usuarios u ON u.id = a.docente_id WHERE a.seccion_id = ? ORDER BY c.nombre",
        (seccion_id,)).fetchall()


def agenda(seccion_id, limite=-1):
    """Actividades de la sección desde hoy (limite=-1: todas)."""
    return get_db().execute(
        "SELECT ag.titulo, ag.descripcion, ag.fecha, u.nombres || ' ' || u.apellidos AS docente "
        "FROM agenda ag LEFT JOIN usuarios u ON u.id = ag.creado_por "
        "WHERE ag.seccion_id = ? AND ag.fecha >= ? ORDER BY ag.fecha LIMIT ?",
        (seccion_id, date.today().isoformat(), limite)).fetchall()
