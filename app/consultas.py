"""Consultas que usan más de un rol (docente, director y alumno)."""

DIAS_SEMANA = {1: "Lunes", 2: "Martes", 3: "Miércoles", 4: "Jueves", 5: "Viernes"}


def avance_notas(db, bimestre, docente_id=None):
    """Avance del registro de notas por curso y sección.

    esperados  = alumnos activos de la sección x competencias del curso
    registrados = calificativos ya guardados en ese bimestre
    Si se pasa docente_id, solo devuelve los cursos de ese docente.
    """
    filas = db.execute(
        "SELECT a.id, c.nombre AS curso, s.id AS seccion_id, s.grado, s.seccion, "
        " u.nombres || ' ' || u.apellidos AS docente, "
        " (SELECT COUNT(*) FROM alumnos al JOIN usuarios ua ON ua.id = al.usuario_id "
        "   WHERE al.seccion_id = s.id AND ua.activo = 1) * "
        " (SELECT COUNT(*) FROM competencias co WHERE co.curso_id = c.id) AS esperados, "
        " (SELECT COUNT(*) FROM calificaciones k "
        "   JOIN alumnos al ON al.usuario_id = k.alumno_id "
        "   JOIN usuarios ua ON ua.id = al.usuario_id "
        "   JOIN competencias co ON co.id = k.competencia_id "
        "  WHERE al.seccion_id = s.id AND co.curso_id = c.id AND k.bimestre = ? "
        "    AND ua.activo = 1) AS registrados "
        "FROM asignaciones a JOIN cursos c ON c.id = a.curso_id "
        "JOIN secciones s ON s.id = a.seccion_id JOIN usuarios u ON u.id = a.docente_id "
        "WHERE (? IS NULL OR a.docente_id = ?) "
        "ORDER BY s.grado, s.seccion, c.nombre", (bimestre, docente_id, docente_id)).fetchall()
    return [dict(f, pct=round(100 * f["registrados"] / f["esperados"]) if f["esperados"] else 0)
            for f in filas]


def horario(db, seccion_id=None, docente_id=None):
    """Bloques del horario de una sección o de un docente, por día y hora."""
    return db.execute(
        "SELECT h.id, h.dia_semana, h.hora_inicio, h.hora_fin, c.nombre AS curso, "
        " s.grado, s.seccion, u.nombres || ' ' || u.apellidos AS docente "
        "FROM horarios h JOIN asignaciones a ON a.id = h.asignacion_id "
        "JOIN cursos c ON c.id = a.curso_id JOIN secciones s ON s.id = a.seccion_id "
        "JOIN usuarios u ON u.id = a.docente_id "
        "WHERE (? IS NULL OR a.seccion_id = ?) AND (? IS NULL OR a.docente_id = ?) "
        "ORDER BY h.dia_semana, h.hora_inicio",
        (seccion_id, seccion_id, docente_id, docente_id)).fetchall()
