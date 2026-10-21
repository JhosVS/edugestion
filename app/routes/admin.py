"""Panel del administrador: estado del sistema, configuración, auditoría y respaldos.
La gestión de datos (usuarios, secciones, cursos...) está en gestion.py, compartida con el director."""
import csv
import os
import re
import sqlite3
import tempfile
from datetime import date
from io import BytesIO, StringIO

from flask import (Blueprint, Response, current_app, flash, redirect, render_template, request,
                   send_file, url_for)

from ..ajustes import ajustes, guardar
from ..auditoria import ACCIONES, registrar
from ..auth import login_required
from ..db import get_db
from ..utils import ahora

bp = Blueprint("admin", __name__, url_prefix="/admin")

POR_PAGINA = 50


@bp.before_request
@login_required("admin")
def solo_admin():
    """Todas las vistas de este Blueprint exigen el rol admin."""


# --------------------------------------------------------------------------
# Panel: estado del sistema
# --------------------------------------------------------------------------
@bp.route("/")
def inicio():
    db = get_db()
    roles = {r["rol"]: r for r in db.execute(
        "SELECT rol, SUM(activo) AS activos, COUNT(*) AS total FROM usuarios GROUP BY rol")}
    hace_24h = ahora(hours=-24)
    eventos = {r["accion"]: r["n"] for r in db.execute(
        "SELECT accion, COUNT(*) AS n FROM auditoria WHERE fecha >= ? GROUP BY accion", (hace_24h,))}
    datos = {
        "secciones": db.execute("SELECT COUNT(*) FROM secciones").fetchone()[0],
        "cursos": db.execute("SELECT COUNT(*) FROM cursos").fetchone()[0],
        "calificaciones": db.execute("SELECT COUNT(*) FROM calificaciones").fetchone()[0],
        "asistencias": db.execute("SELECT COUNT(*) FROM asistencias").fetchone()[0],
        "auditoria": db.execute("SELECT COUNT(*) FROM auditoria").fetchone()[0],
    }
    nunca = db.execute(
        "SELECT nombres || ' ' || apellidos AS nombre, rol, correo FROM usuarios "
        "WHERE activo = 1 AND ultimo_acceso IS NULL AND rol != 'alumno' ORDER BY rol, apellidos"
    ).fetchall()

    avisos = []
    if current_app.config["SECRET_KEY"] == "dev-cambiar-en-produccion":
        avisos.append("Se está usando la clave secreta de desarrollo. Define SECRET_KEY en el archivo "
                      ".env o en Render.")
    if ajustes()["mostrar_demo"] == "1":
        avisos.append("Las credenciales de prueba se muestran en la pantalla de inicio de sesión. "
                      "Ocúltalas en Configuración antes de usar el sistema con datos reales.")
    if eventos.get("login_bloqueado"):
        avisos.append(f"Hubo {eventos['login_bloqueado']} intentos sobre cuentas bloqueadas en las "
                      "últimas 24 horas. Revisa la auditoría.")

    ultimo_respaldo = db.execute("SELECT MAX(fecha) FROM auditoria WHERE accion = 'respaldo'"
                                 ).fetchone()[0]
    recientes = _consulta_auditoria({}, limite=10)
    return render_template("admin/inicio.html", roles=roles, eventos=eventos, datos=datos,
                           nunca=nunca, avisos=avisos, recientes=recientes,
                           tamano=_tamano_bd(), ultimo_respaldo=ultimo_respaldo)


def _tamano_bd():
    try:
        kb = os.path.getsize(current_app.config["DATABASE"]) / 1024
    except OSError:
        return "—"
    return f"{kb / 1024:.1f} MB" if kb >= 1024 else f"{kb:.0f} KB"


# --------------------------------------------------------------------------
# Configuración institucional
# --------------------------------------------------------------------------
@bp.route("/configuracion", methods=["GET", "POST"])
def configuracion():
    if request.method == "POST":
        f = request.form
        nuevos = {
            "institucion": f.get("institucion", "").strip()[:120],
            "lugar": f.get("lugar", "").strip()[:80],
            "codigo_modular": f.get("codigo_modular", "").strip(),
            "anio_lectivo": f.get("anio_lectivo", "").strip(),
            "bimestre_actual": f.get("bimestre_actual", ""),
            "mostrar_demo": "1" if f.get("mostrar_demo") else "0",
        }
        errores = []
        if not nuevos["institucion"]:
            errores.append("Escribe el nombre de la institución.")
        if nuevos["codigo_modular"] and not re.fullmatch(r"\d{6,10}", nuevos["codigo_modular"]):
            errores.append("El código modular debe tener solo dígitos (6 a 10).")
        if not (nuevos["anio_lectivo"].isdigit() and 2000 <= int(nuevos["anio_lectivo"]) <= 2100):
            errores.append("El año lectivo no es válido.")
        if nuevos["bimestre_actual"] not in ("1", "2", "3", "4"):
            errores.append("Elige el bimestre actual.")
        if errores:
            for e in errores:
                flash(e, "error")
        else:
            antes = ajustes()
            cambios = [k for k, v in nuevos.items() if antes.get(k) != v]
            guardar(nuevos)
            if cambios:
                registrar("configuracion", "Cambió: " + ", ".join(cambios))
            flash("Configuración guardada.", "ok")
            return redirect(url_for("admin.configuracion"))
    return render_template("admin/configuracion.html")


# --------------------------------------------------------------------------
# Auditoría
# --------------------------------------------------------------------------
def _filtros():
    a = request.args
    def fecha(nombre):
        try:
            return date.fromisoformat(a.get(nombre, "")).isoformat()
        except ValueError:
            return None
    accion = a.get("accion", "")
    return {"accion": accion if accion in ACCIONES else "", "texto": a.get("texto", "").strip(),
            "desde": fecha("desde"), "hasta": fecha("hasta")}


def _consulta_auditoria(f, limite, desplazamiento=0):
    texto = f"%{f.get('texto', '')}%"
    return get_db().execute(
        "SELECT a.fecha, a.accion, a.detalle, a.ip, u.nombres || ' ' || u.apellidos AS usuario, "
        " u.rol FROM auditoria a LEFT JOIN usuarios u ON u.id = a.usuario_id "
        "WHERE (? = '' OR a.accion = ?) "
        " AND (? IS NULL OR a.fecha >= ?) AND (? IS NULL OR a.fecha < date(?, '+1 day')) "
        " AND (? = '%%' OR COALESCE(u.nombres || ' ' || u.apellidos || ' ' || u.correo, '') LIKE ? "
        "      OR a.detalle LIKE ? OR a.ip LIKE ?) "
        "ORDER BY a.id DESC LIMIT ? OFFSET ?",
        (f.get("accion", ""), f.get("accion", ""), f.get("desde"), f.get("desde"), f.get("hasta"),
         f.get("hasta"), texto, texto, texto, texto, limite, desplazamiento)).fetchall()


@bp.route("/auditoria")
def auditoria():
    f = _filtros()
    pagina = max(request.args.get("pagina", 1, type=int), 1)
    filas = _consulta_auditoria(f, POR_PAGINA + 1, (pagina - 1) * POR_PAGINA)
    return render_template("admin/auditoria.html", filas=filas[:POR_PAGINA], f=f, pagina=pagina,
                           hay_mas=len(filas) > POR_PAGINA, acciones=ACCIONES)


@bp.route("/auditoria.csv")
def auditoria_csv():
    salida = StringIO()
    w = csv.writer(salida)
    w.writerow(["Fecha", "Usuario", "Rol", "Acción", "Detalle", "IP"])
    for r in _consulta_auditoria(_filtros(), limite=10000):
        w.writerow([r["fecha"], r["usuario"] or "", r["rol"] or "", ACCIONES.get(r["accion"], r["accion"]),
                    r["detalle"] or "", r["ip"] or ""])
    # BOM para que Excel reconozca las tildes
    return Response("﻿" + salida.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=auditoria.csv"})


# --------------------------------------------------------------------------
# Respaldo de la base de datos
# --------------------------------------------------------------------------
@bp.route("/respaldo")
def respaldo():
    historial = get_db().execute(
        "SELECT a.fecha, u.nombres || ' ' || u.apellidos AS usuario FROM auditoria a "
        "LEFT JOIN usuarios u ON u.id = a.usuario_id WHERE a.accion = 'respaldo' "
        "ORDER BY a.id DESC LIMIT 10").fetchall()
    return render_template("admin/respaldo.html", historial=historial, tamano=_tamano_bd())


@bp.route("/respaldo/descargar", methods=["POST"])
def respaldo_descargar():
    """Copia consistente con la API de respaldo de SQLite (segura aunque haya escrituras)."""
    fd, ruta = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        destino = sqlite3.connect(ruta)
        get_db().backup(destino)
        destino.close()
        with open(ruta, "rb") as archivo:
            datos = BytesIO(archivo.read())
    finally:
        os.remove(ruta)
    registrar("respaldo", "Descargó una copia de la base de datos")
    nombre = f"edugestion_respaldo_{ahora().replace(':', '').replace(' ', '_')[:15]}.db"
    return send_file(datos, as_attachment=True, download_name=nombre,
                     mimetype="application/vnd.sqlite3")
