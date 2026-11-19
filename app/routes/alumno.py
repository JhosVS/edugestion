from datetime import date

from flask import Blueprint, g, render_template

from .. import estadisticas, estudiante
from ..auth import login_required
from ..consultas import DIAS_SEMANA, horario
from ..db import get_db

bp = Blueprint("alumno", __name__, url_prefix="/alumno")


@bp.route("/")
@login_required("alumno")
def inicio():
    uid = g.usuario["id"]
    perfil = estudiante.perfil(uid)
    return render_template("alumno/inicio.html", perfil=perfil,
                           asistencia=estudiante.resumen_asistencia(uid),
                           conteo=estudiante.conteo_calificativos(uid),
                           proximas=estudiante.agenda(perfil["seccion_id"], limite=3),
                           datos=estadisticas.panel(alumno_id=uid))


@bp.route("/cursos")
@login_required("alumno")
def cursos():
    perfil = estudiante.perfil(g.usuario["id"])
    return render_template("alumno/cursos.html", perfil=perfil,
                           cursos=estudiante.cursos(perfil["seccion_id"]),
                           bloques=horario(get_db(), seccion_id=perfil["seccion_id"]),
                           dias=DIAS_SEMANA)


@bp.route("/libreta")
@login_required("alumno")
def libreta():
    perfil = estudiante.perfil(g.usuario["id"])
    return render_template("alumno/libreta.html", perfil=perfil,
                           cursos=estudiante.libreta(perfil["id"], perfil["seccion_id"]))


@bp.route("/asistencia")
@login_required("alumno")
def asistencia():
    uid = g.usuario["id"]
    return render_template("alumno/asistencia.html", resumen=estudiante.resumen_asistencia(uid),
                           registros=estudiante.ultimas_asistencias(uid))


@bp.route("/agenda")
@login_required("alumno")
def agenda():
    perfil = estudiante.perfil(g.usuario["id"])
    return render_template("alumno/agenda.html", entradas=estudiante.agenda(perfil["seccion_id"]),
                           hoy=date.today().isoformat())
