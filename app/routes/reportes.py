"""Reporte de asistencia en tabla (y su Excel) para todos los roles.

Quién ve qué:
  director y administrador -> cualquier sección
  docente                  -> las secciones donde dicta algún curso
  alumno                   -> solo su propia fila
  padre                    -> solo la fila del hijo elegido
"""
import calendar
from datetime import date

from flask import Blueprint, abort, g, render_template, request, send_file

from .. import reporte_asistencia as ra
from ..auth import login_required
from ..db import get_db
from ..siagie import _ascii
from . import padre

bp = Blueprint("reportes", __name__, url_prefix="/reportes")

PERSONAL = ("docente", "director", "admin")


@bp.before_request
@login_required()
def con_sesion():
    """Todas las vistas exigen sesión; el alcance se decide según el rol."""


def _fecha(nombre):
    try:
        return date.fromisoformat(request.args.get(nombre, "")).isoformat()
    except ValueError:
        return None


def _secciones_del_personal():
    db = get_db()
    if g.usuario["rol"] == "docente":
        return db.execute(
            "SELECT DISTINCT s.* FROM secciones s JOIN asignaciones a ON a.seccion_id = s.id "
            "WHERE a.docente_id = ? ORDER BY s.anio DESC, s.grado, s.seccion",
            (g.usuario["id"],)).fetchall()
    return db.execute("SELECT * FROM secciones ORDER BY anio DESC, grado, seccion").fetchall()


def _alcance():
    """(sección, alumnos visibles o None = todos, secciones elegibles, hijo, hijos)."""
    rol = g.usuario["rol"]
    db = get_db()
    if rol in PERSONAL:
        secciones = _secciones_del_personal()
        if not secciones:
            return None, None, [], None, None
        pedida = request.args.get("seccion", type=int)
        seccion = next((s for s in secciones if s["id"] == pedida), None) if pedida else secciones[0]
        return seccion or abort(404), None, secciones, None, None

    if rol == "alumno":
        alumno_id, hijo, hijos = g.usuario["id"], None, None
    else:  # padre
        hijos = padre._hijos()
        if not hijos:
            return None, None, [], None, []
        hijo = padre._hijo_elegido(hijos)
        alumno_id = hijo["id"]
    seccion = db.execute("SELECT s.* FROM secciones s JOIN alumnos al ON al.seccion_id = s.id "
                         "WHERE al.usuario_id = ?", (alumno_id,)).fetchone()
    return seccion, {alumno_id}, [], hijo, hijos


@bp.route("/asistencia")
def asistencia():
    seccion, visibles, secciones, hijo, hijos = _alcance()
    if seccion is None:
        return render_template("reportes/asistencia.html", seccion=None, secciones=secciones,
                               hijo=hijo, hijos=hijos)
    datos = ra.matriz(seccion["id"], _fecha("desde"), _fecha("hasta"), alumno_ids=visibles)
    meses = [{"nombre": nombre, "desde": f"{a}-{m:02d}-01",
              "hasta": f"{a}-{m:02d}-{calendar.monthrange(a, m)[1]:02d}"}
             for a, m, nombre in ra.meses_registrados(seccion["id"])]
    return render_template("reportes/asistencia.html", seccion=seccion, secciones=secciones,
                           datos=datos, meses=meses, individual=visibles is not None,
                           calendario=ra.calendario(datos) if visibles is not None else None,
                           # al imprimir el año completo, un mes por hoja (no caben 150 columnas)
                           impresion=ra.por_mes(datos) if visibles is None and len(datos["meses"]) > 1 else [],
                           hijo=hijo, hijos=hijos, filtrado=bool(request.args.get("desde")
                                                                 or request.args.get("hasta")))


@bp.route("/asistencia.xlsx")
def asistencia_excel():
    seccion, visibles, _, hijo, _ = _alcance()
    if seccion is None:
        abort(404)
    datos = ra.matriz(seccion["id"], _fecha("desde"), _fecha("hasta"), alumno_ids=visibles)
    if visibles is None:
        titulo, nombre = "REGISTRO DE ASISTENCIA", f'{seccion["grado"]}{seccion["seccion"]}'
    else:
        titulo = "REGISTRO DE ASISTENCIA DEL ESTUDIANTE"
        nombre = datos["filas"][0]["nombre"].split(",")[0] if datos["filas"] else "alumno"
    archivo = ra.excel(seccion, datos, titulo)
    return send_file(archivo, as_attachment=True,
                     download_name=f"Asistencia_{_ascii(nombre)}_{seccion['anio']}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
