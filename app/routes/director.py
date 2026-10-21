from datetime import date

from flask import Blueprint, abort, render_template, request, send_file

from ..ajustes import bimestre_actual
from ..auth import login_required
from ..consultas import avance_notas
from ..db import get_db
from ..siagie import generar_excel

bp = Blueprint("director", __name__, url_prefix="/director")


def _bimestre():
    b = request.args.get("bimestre", type=int)
    return b if b in (1, 2, 3, 4) else bimestre_actual()


def _fecha_opcional(nombre):
    """Lee ?desde= / ?hasta= (AAAA-MM-DD). Si falta o es inválida, devuelve None."""
    try:
        return date.fromisoformat(request.args.get(nombre, "")).isoformat()
    except ValueError:
        return None


def _nivel(pct):
    """Color del chip: P (verde) >= 90 %, T (naranja) >= 80 %, F (rojo) por debajo."""
    return "P" if pct >= 90 else "T" if pct >= 80 else "F"


@bp.route("/")
@login_required("director")
def inicio():
    db = get_db()
    bimestre = _bimestre()
    avance = avance_notas(db, bimestre)
    esperados = sum(f["esperados"] for f in avance)
    registrados = sum(f["registrados"] for f in avance)

    c = {"P": 0, "T": 0, "F": 0}
    c.update({f["estado"]: f["n"] for f in db.execute(
        "SELECT estado, COUNT(*) AS n FROM asistencias GROUP BY estado")})
    total = sum(c.values())

    resumen = {
        "alumnos": db.execute("SELECT COUNT(*) FROM alumnos").fetchone()[0],
        "docentes": db.execute(
            "SELECT COUNT(*) FROM usuarios WHERE rol = 'docente' AND activo = 1").fetchone()[0],
        "asistencia": round(100 * (c["P"] + c["T"]) / total) if total else None,
        "avance": round(100 * registrados / esperados) if esperados else 0,
    }
    return render_template("director/inicio.html", resumen=resumen, avance=avance,
                           bimestre=bimestre)


@bp.route("/asistencia")
@login_required("director")
def asistencia():
    db = get_db()
    desde, hasta = _fecha_opcional("desde"), _fecha_opcional("hasta")
    rango = (desde, desde, hasta, hasta)
    filtro = "AND (? IS NULL OR x.fecha >= ?) AND (? IS NULL OR x.fecha <= ?)"

    filas = db.execute(
        "SELECT s.id, s.grado, s.seccion, COUNT(DISTINCT al.usuario_id) AS alumnos, "
        " COALESCE(SUM(x.estado = 'P'), 0) AS p, COALESCE(SUM(x.estado = 'T'), 0) AS t, "
        " COALESCE(SUM(x.estado = 'F'), 0) AS f "
        "FROM secciones s JOIN alumnos al ON al.seccion_id = s.id "
        f"LEFT JOIN asistencias x ON x.alumno_id = al.usuario_id {filtro} "
        "GROUP BY s.id ORDER BY s.grado, s.seccion", rango).fetchall()

    secciones = []
    for f in filas:
        total = f["p"] + f["t"] + f["f"]
        pct = round(100 * (f["p"] + f["t"]) / total) if total else None
        secciones.append(dict(f, pct=pct, nivel=_nivel(pct) if total else "T"))

    p, t, falt = (sum(s[k] for s in secciones) for k in ("p", "t", "f"))
    total = p + t + falt
    general = {"p": p, "t": t, "f": falt,
               "pct": round(100 * (p + t) / total) if total else None}

    mas_faltas = db.execute(
        "SELECT u.apellidos || ', ' || u.nombres AS nombre, s.grado, s.seccion, "
        " SUM(x.estado = 'F') AS faltas, SUM(x.estado = 'T') AS tardanzas "
        "FROM asistencias x JOIN alumnos al ON al.usuario_id = x.alumno_id "
        "JOIN usuarios u ON u.id = al.usuario_id JOIN secciones s ON s.id = al.seccion_id "
        f"WHERE 1 = 1 {filtro} GROUP BY al.usuario_id HAVING faltas > 0 "
        "ORDER BY faltas DESC, tardanzas DESC, nombre LIMIT 5", rango).fetchall()

    return render_template("director/asistencia.html", secciones=secciones, general=general,
                           mas_faltas=mas_faltas, desde=desde, hasta=hasta)


@bp.route("/rendimiento")
@login_required("director")
def rendimiento():
    db = get_db()
    bimestre = _bimestre()
    filas = db.execute(
        "SELECT s.grado, s.seccion, c.nombre AS curso, "
        " COALESCE(SUM(k.calificativo = 'AD'), 0) AS AD, COALESCE(SUM(k.calificativo = 'A'), 0) AS A, "
        " COALESCE(SUM(k.calificativo = 'B'), 0) AS B, COALESCE(SUM(k.calificativo = 'C'), 0) AS C, "
        " COUNT(k.id) AS total "
        "FROM asignaciones a JOIN secciones s ON s.id = a.seccion_id "
        "JOIN cursos c ON c.id = a.curso_id "
        "LEFT JOIN competencias co ON co.curso_id = c.id "
        "LEFT JOIN alumnos al ON al.seccion_id = s.id "
        "LEFT JOIN calificaciones k ON k.alumno_id = al.usuario_id "
        " AND k.competencia_id = co.id AND k.bimestre = ? "
        "GROUP BY a.id ORDER BY s.grado, s.seccion, c.nombre", (bimestre,)).fetchall()

    cursos = []
    for f in filas:
        total = f["total"]
        segmentos = [(k, f[k], 100 * f[k] / total if total else 0) for k in ("AD", "A", "B", "C")]
        bajo = round(100 * (f["B"] + f["C"]) / total) if total else None
        cursos.append(dict(f, segmentos=segmentos, bajo=bajo))

    en_riesgo = db.execute(
        "SELECT u.apellidos || ', ' || u.nombres AS nombre, s.grado, s.seccion, "
        " SUM(k.calificativo = 'C') AS n_c, SUM(k.calificativo = 'B') AS n_b "
        "FROM calificaciones k JOIN alumnos al ON al.usuario_id = k.alumno_id "
        "JOIN usuarios u ON u.id = al.usuario_id JOIN secciones s ON s.id = al.seccion_id "
        "WHERE k.bimestre = ? GROUP BY al.usuario_id HAVING n_c > 0 "
        "ORDER BY n_c DESC, n_b DESC, nombre LIMIT 5", (bimestre,)).fetchall()

    return render_template("director/rendimiento.html", cursos=cursos, en_riesgo=en_riesgo,
                           bimestre=bimestre)

@bp.route("/siagie")
@login_required("director")
def siagie():
    db = get_db()
    bimestre = _bimestre()
    secciones = {}
    for f in avance_notas(db, bimestre):  # suma el avance de todos los cursos de cada sección
        s = secciones.setdefault(f["seccion_id"], {"id": f["seccion_id"], "grado": f["grado"],
                                                   "seccion": f["seccion"], "cursos": 0,
                                                   "esperados": 0, "registrados": 0})
        s["cursos"] += 1
        s["esperados"] += f["esperados"]
        s["registrados"] += f["registrados"]
    for s in secciones.values():
        s["pct"] = round(100 * s["registrados"] / s["esperados"]) if s["esperados"] else 0
    return render_template("director/siagie.html", secciones=list(secciones.values()),
                           bimestre=bimestre)


@bp.route("/siagie/<int:seccion_id>")
@login_required("director")
def siagie_seccion(seccion_id):
    db = get_db()
    if db.execute("SELECT 1 FROM secciones WHERE id = ?", (seccion_id,)).fetchone() is None:
        abort(404)
    archivo, nombre, _ = generar_excel(db, seccion_id, _bimestre())
    return send_file(archivo, as_attachment=True, download_name=nombre)
