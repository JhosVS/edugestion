"""Módulo de padres de familia: consultan la libreta, la asistencia, el horario y la agenda
de cada hijo vinculado (tabla apoderados). Es de solo lectura."""
from datetime import date

from flask import Blueprint, abort, g, redirect, render_template, request, session, url_for

from .. import estadisticas, estudiante
from ..auth import login_required
from ..consultas import DIAS_SEMANA, horario
from ..db import get_db

bp = Blueprint("padre", __name__, url_prefix="/padre")


@bp.before_request
@login_required("padre")
def solo_padre():
    """Todas las vistas de este Blueprint exigen el rol padre."""


def _hijos():
    """Hijos activos vinculados al padre que inició sesión."""
    return get_db().execute(
        "SELECT al.usuario_id AS id, u.nombres, u.apellidos, ap.parentesco, "
        " s.id AS seccion_id, s.anio, s.grado, s.seccion "
        "FROM apoderados ap JOIN alumnos al ON al.usuario_id = ap.alumno_id "
        "JOIN usuarios u ON u.id = al.usuario_id JOIN secciones s ON s.id = al.seccion_id "
        "WHERE ap.padre_id = ? AND u.activo = 1 ORDER BY u.apellidos, u.nombres",
        (g.usuario["id"],)).fetchall()


def _hijo_elegido(hijos):
    """El hijo pedido con ?hijo=, si no el último consultado, si no el primero.
    Pedir un alumno que no es su hijo responde 404: así no se revela si existe."""
    pedido = request.args.get("hijo", type=int)
    if pedido is not None:
        hijo = next((h for h in hijos if h["id"] == pedido), None) or abort(404)
    else:
        hijo = next((h for h in hijos if h["id"] == session.get("hijo")), hijos[0])
    session["hijo"] = hijo["id"]
    return hijo


def _vista_hijo(plantilla, **datos):
    """Renderiza una pantalla del alumno con los datos del hijo elegido."""
    hijos = _hijos()
    if not hijos:
        return redirect(url_for("padre.inicio"))
    hijo = _hijo_elegido(hijos)
    return render_template(plantilla, hijo=hijo, hijos=hijos, perfil=hijo,
                           **{k: f(hijo) for k, f in datos.items()})


@bp.route("/")
def inicio():
    resumenes = [{
        "hijo": h,
        "asistencia": estudiante.resumen_asistencia(h["id"]),
        "conteo": estudiante.conteo_calificativos(h["id"]),
        "proximas": estudiante.agenda(h["seccion_id"], limite=3),
        "datos": estadisticas.panel(alumno_id=h["id"]),
    } for h in _hijos()]
    return render_template("padre/inicio.html", resumenes=resumenes)


@bp.route("/libreta")
def libreta():
    return _vista_hijo("alumno/libreta.html",
                       cursos=lambda h: estudiante.libreta(h["id"], h["seccion_id"]))


@bp.route("/asistencia")
def asistencia():
    return _vista_hijo("alumno/asistencia.html",
                       resumen=lambda h: estudiante.resumen_asistencia(h["id"]),
                       registros=lambda h: estudiante.ultimas_asistencias(h["id"]))


@bp.route("/cursos")
def cursos():
    return _vista_hijo("alumno/cursos.html",
                       cursos=lambda h: estudiante.cursos(h["seccion_id"]),
                       bloques=lambda h: horario(get_db(), seccion_id=h["seccion_id"]),
                       dias=lambda h: DIAS_SEMANA)


@bp.route("/agenda")
def agenda():
    return _vista_hijo("alumno/agenda.html",
                       entradas=lambda h: estudiante.agenda(h["seccion_id"]),
                       hoy=lambda h: date.today().isoformat())
