from datetime import date

from flask import (Blueprint, abort, flash, g, redirect, render_template, request, send_file,
                   url_for)

from ..ajustes import bimestre_actual
from ..auditoria import registrar
from ..auth import login_required
from ..consultas import DIAS_SEMANA, avance_notas, horario
from ..db import get_db
from ..siagie import generar_excel

bp = Blueprint("docente", __name__, url_prefix="/docente")

ESTADOS = {"P": "Presente", "T": "Tardanza", "F": "Falta"}
CALIFICATIVOS = ("AD", "A", "B", "C")

ALUMNOS_SQL = ("SELECT u.id, u.apellidos || ', ' || u.nombres AS nombre FROM alumnos al "
               "JOIN usuarios u ON u.id = al.usuario_id WHERE al.seccion_id = ? AND u.activo = 1 "
               "ORDER BY u.apellidos, u.nombres")


# --------------------------------------------------------------------------
# Ayudas
# --------------------------------------------------------------------------
def _bimestre():
    b = request.values.get("bimestre", type=int)
    return b if b in (1, 2, 3, 4) else bimestre_actual()


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
    db = get_db()
    cursos = avance_notas(db, bimestre, g.usuario["id"])
    return render_template("docente/inicio.html", cursos=cursos, bimestre=bimestre,
                           n_secciones=len({c["seccion_id"] for c in cursos}),
                           bloques=horario(db, docente_id=g.usuario["id"]), dias=DIAS_SEMANA)


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
        registrar("asistencia", f'{seccion["grado"]} "{seccion["seccion"]}", {fecha}: '
                                f'{len(alumnos)} alumnos')
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

    previos = {(r["alumno_id"], r["competencia_id"]): r["calificativo"] for r in db.execute(
        "SELECT k.alumno_id, k.competencia_id, k.calificativo FROM calificaciones k "
        "JOIN competencias co ON co.id = k.competencia_id "
        "WHERE co.curso_id = ? AND k.bimestre = ?", (asig["curso_id"], bimestre))}

    if request.method == "POST":
        cambios = 0
        for a in alumnos:
            for c in competencias:
                valor = request.form.get(f"n_{a['id']}_{c['id']}", "")
                cambios += valor != previos.get((a["id"], c["id"]), "")
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
        if cambios:
            registrar("notas", f'{asig["curso"]} {asig["grado"]} "{asig["seccion"]}", bimestre '
                               f'{bimestre}: {cambios} calificativos modificados')
        flash("Calificativos guardados.", "ok")
        return redirect(url_for("docente.notas_asignacion", asignacion_id=asignacion_id,
                                bimestre=bimestre))

    return render_template("docente/notas.html", asig=asig, bimestre=bimestre, alumnos=alumnos,
                           competencias=competencias, previos=previos,
                           calificativos=CALIFICATIVOS)

@bp.route("/notas/<int:asignacion_id>/siagie")
@login_required("docente")
def notas_siagie(asignacion_id):
    asig = _asignacion_del_docente(asignacion_id)
    archivo, nombre, _ = generar_excel(get_db(), asig["seccion_id"], _bimestre(), asignacion_id)
    return send_file(archivo, as_attachment=True, download_name=nombre)


# --------------------------------------------------------------------------
# Agenda: tareas y avisos por sección
# --------------------------------------------------------------------------
@bp.route("/agenda", methods=["GET", "POST"])
@login_required("docente")
def agenda():
    db = get_db()
    if request.method == "POST":
        seccion = _seccion_del_docente(request.form.get("seccion_id", type=int))
        titulo = request.form.get("titulo", "").strip()
        try:
            fecha = date.fromisoformat(request.form.get("fecha", "")).isoformat()
        except ValueError:
            fecha = None
        if titulo and fecha:
            db.execute("INSERT INTO agenda(seccion_id, titulo, descripcion, fecha, creado_por) "
                       "VALUES (?,?,?,?,?)", (seccion["id"], titulo[:120],
                                              request.form.get("descripcion", "").strip()[:500],
                                              fecha, g.usuario["id"]))
            db.commit()
            registrar("agenda", f'{seccion["grado"]} "{seccion["seccion"]}": {titulo[:120]} ({fecha})')
            flash("Actividad agregada a la agenda.", "ok")
        else:
            flash("Escribe un título y una fecha válida.", "error")
        return redirect(url_for("docente.agenda"))

    secciones = db.execute(
        "SELECT DISTINCT s.id, s.grado, s.seccion FROM asignaciones a "
        "JOIN secciones s ON s.id = a.seccion_id WHERE a.docente_id = ? "
        "ORDER BY s.grado, s.seccion", (g.usuario["id"],)).fetchall()
    entradas = db.execute(
        "SELECT ag.id, ag.titulo, ag.descripcion, ag.fecha, s.grado, s.seccion FROM agenda ag "
        "JOIN secciones s ON s.id = ag.seccion_id WHERE ag.creado_por = ? AND ag.fecha >= ? "
        "ORDER BY ag.fecha, s.grado, s.seccion", (g.usuario["id"], date.today().isoformat())).fetchall()
    return render_template("docente/agenda.html", secciones=secciones, entradas=entradas,
                           hoy=date.today().isoformat())


@bp.route("/agenda/<int:agenda_id>/eliminar", methods=["POST"])
@login_required("docente")
def agenda_eliminar(agenda_id):
    db = get_db()
    if db.execute("DELETE FROM agenda WHERE id = ? AND creado_por = ?",
                  (agenda_id, g.usuario["id"])).rowcount:
        registrar("agenda", f"Eliminó la actividad {agenda_id}")
    db.commit()
    flash("Actividad eliminada.", "ok")
    return redirect(url_for("docente.agenda"))
