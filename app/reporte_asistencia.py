"""Reporte de asistencia en tabla: una fila por alumno y una columna por día de clases,
desde el primer hasta el último registro (o el rango pedido). También genera el Excel.

Los días que se muestran son los que tienen algún registro en la sección: así no
aparecen fines de semana, feriados ni vacaciones.
"""
import calendar
from datetime import date
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .ajustes import ajustes
from .db import get_db

MESES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto",
         "Setiembre", "Octubre", "Noviembre", "Diciembre"]
INICIAL_DIA = "LMMJVSD"
ESTADOS = {"P": "Presente", "T": "Tardanza", "F": "Falta"}


def _pct(p, t, f):
    total = p + t + f
    return round(100 * (p + t) / total, 1) if total else None


def rango_registrado(seccion_id):
    """Primera y última fecha con asistencia en la sección (o (None, None))."""
    f = get_db().execute(
        "SELECT MIN(x.fecha), MAX(x.fecha) FROM asistencias x "
        "JOIN alumnos al ON al.usuario_id = x.alumno_id WHERE al.seccion_id = ?",
        (seccion_id,)).fetchone()
    return f[0], f[1]


def matriz(seccion_id, desde=None, hasta=None, alumno_ids=None):
    """Tabla de la sección. alumno_ids limita las filas (vista del padre o del alumno)."""
    db = get_db()
    inicio, fin = rango_registrado(seccion_id)
    desde, hasta = desde or inicio, hasta or fin
    alumnos = db.execute(
        "SELECT u.id, al.dni, u.apellidos || ', ' || u.nombres AS nombre FROM alumnos al "
        "JOIN usuarios u ON u.id = al.usuario_id WHERE al.seccion_id = ? AND u.activo = 1 "
        "ORDER BY u.apellidos, u.nombres", (seccion_id,)).fetchall()
    if alumno_ids is not None:
        alumnos = [a for a in alumnos if a["id"] in alumno_ids]

    registros = {}
    if desde and hasta:
        for r in db.execute(
                "SELECT x.alumno_id, x.fecha, x.estado FROM asistencias x "
                "JOIN alumnos al ON al.usuario_id = x.alumno_id "
                "WHERE al.seccion_id = ? AND x.fecha BETWEEN ? AND ?", (seccion_id, desde, hasta)):
            registros[(r["alumno_id"], r["fecha"])] = r["estado"]
    fechas = sorted({f for _, f in registros})

    filas = []
    for a in alumnos:
        estados = [registros.get((a["id"], f)) for f in fechas]
        c = {k: estados.count(k) for k in ESTADOS}
        filas.append({"id": a["id"], "dni": a["dni"], "nombre": a["nombre"], "estados": estados,
                      **c, "pct": _pct(c["P"], c["T"], c["F"])})

    dias = []
    for i, f in enumerate(fechas):
        d = date.fromisoformat(f)
        col = [fila["estados"][i] for fila in filas]
        dias.append({"fecha": f, "dia": d.day, "inicial": INICIAL_DIA[d.weekday()], "mes": d.month,
                     "asistieron": sum(e in ("P", "T") for e in col),
                     "faltaron": col.count("F")})

    meses = []  # para la fila de cabecera que agrupa los días por mes
    for d in dias:
        if meses and meses[-1]["mes"] == d["mes"]:
            meses[-1]["dias"] += 1
        else:
            meses.append({"mes": d["mes"], "nombre": MESES[d["mes"]], "dias": 1})

    t = {k: sum(f[k] for f in filas) for k in ESTADOS}
    return {"desde": desde, "hasta": hasta, "inicio": inicio, "fin": fin, "dias": dias,
            "meses": meses, "filas": filas, "totales": {**t, "pct": _pct(t["P"], t["T"], t["F"])}}


def calendario(datos):
    """Vista de un solo alumno: una fila por mes y una columna por día (1 a 31)."""
    if not datos["filas"] or not datos["dias"]:
        return []
    a = datos["filas"][0]
    por_fecha = {d["fecha"]: e for d, e in zip(datos["dias"], a["estados"])}
    clases = set(por_fecha)
    meses = []
    for anio, mes in sorted({(int(d["fecha"][:4]), d["mes"]) for d in datos["dias"]}):
        ultimo = calendar.monthrange(anio, mes)[1]
        celdas = []
        for dia in range(1, 32):
            if dia > ultimo:
                celdas.append({"dia": dia, "tipo": "nohay"})
                continue
            f = date(anio, mes, dia)
            iso = f.isoformat()
            celdas.append({"dia": dia, "fecha": iso, "estado": por_fecha.get(iso),
                           "inicial": INICIAL_DIA[f.weekday()],
                           "tipo": "clase" if iso in clases else "finde" if f.weekday() >= 5 else "sin"})
        est = [c.get("estado") for c in celdas]
        c = {k: est.count(k) for k in ESTADOS}
        meses.append({"nombre": MESES[mes], "celdas": celdas, **c, "pct": _pct(c["P"], c["T"], c["F"])})
    return meses


def por_mes(datos):
    """Los datos partidos en un bloque por mes (para imprimir un mes por hoja)."""
    bloques = []
    for m in datos["meses"]:
        fechas = [d["fecha"] for d in datos["dias"] if d["mes"] == m["mes"]]
        bloques.append(recortar(datos, fechas[0], fechas[-1]))
    return bloques


def meses_registrados(seccion_id):
    """Meses con asistencia, para los accesos rápidos: [(año, mes, nombre)]."""
    return [(int(r[0][:4]), int(r[0][5:]), MESES[int(r[0][5:])]) for r in get_db().execute(
        "SELECT DISTINCT substr(x.fecha, 1, 7) FROM asistencias x "
        "JOIN alumnos al ON al.usuario_id = x.alumno_id WHERE al.seccion_id = ? ORDER BY 1",
        (seccion_id,))]


# --------------------------------------------------------------------------
# Excel
# --------------------------------------------------------------------------
BORDE = Border(*(Side(style="thin", color="BFBFBF"),) * 4)
CENTRO = Alignment(horizontal="center", vertical="center")
CABECERA = PatternFill("solid", fgColor="1F4E78")
FONDO = {"T": PatternFill("solid", fgColor="FCE4A8"), "F": PatternFill("solid", fgColor="F4B6B6")}
BLANCO = Font(bold=True, color="FFFFFF")


def _encabezado(ws, seccion, titulo, desde, hasta):
    cfg = ajustes()
    ws["A1"] = titulo
    ws["A1"].font = Font(bold=True, size=13)
    datos = [("Institución educativa", f'{cfg["institucion"]} - {cfg["lugar"]}'),
             ("Grado y sección", f'{seccion["grado"]} "{seccion["seccion"]}" · {seccion["anio"]}'),
             ("Período", f"{_fecha(desde)} al {_fecha(hasta)}" if desde else "Sin registros")]
    for i, (k, v) in enumerate(datos, start=2):
        ws.cell(i, 1, k).font = Font(bold=True)
        ws.cell(i, 3, v)


def _fecha(iso):
    return date.fromisoformat(iso).strftime("%d/%m/%Y")


def _celda(ws, fila, col, valor, cabecera=False, fondo=None):
    c = ws.cell(fila, col, valor)
    c.border = BORDE
    if cabecera:
        c.fill, c.font, c.alignment = CABECERA, BLANCO, CENTRO
    elif fondo:
        c.fill = fondo
    return c


def _hoja_detalle(ws, seccion, datos, titulo):
    """Hoja con una columna por día, agrupados por mes."""
    _encabezado(ws, seccion, titulo, datos["desde"], datos["hasta"])
    f_mes, f_dia, f_ini = 6, 7, 8
    fijas = ["N.°", "DNI", "Apellidos y nombres"]
    for i, t in enumerate(fijas, start=1):
        _celda(ws, f_mes, i, t, cabecera=True)
        ws.merge_cells(start_row=f_mes, start_column=i, end_row=f_ini, end_column=i)
    col = len(fijas) + 1
    for m in datos["meses"]:
        _celda(ws, f_mes, col, m["nombre"], cabecera=True)
        if m["dias"] > 1:
            ws.merge_cells(start_row=f_mes, start_column=col, end_row=f_mes, end_column=col + m["dias"] - 1)
        col += m["dias"]
    for j, d in enumerate(datos["dias"]):
        _celda(ws, f_dia, len(fijas) + 1 + j, d["dia"], cabecera=True)
        _celda(ws, f_ini, len(fijas) + 1 + j, d["inicial"], cabecera=True)
    col_tot = len(fijas) + len(datos["dias"]) + 1
    for k, t in enumerate(["P", "T", "F", "% asist."]):
        _celda(ws, f_mes, col_tot + k, t, cabecera=True)
        ws.merge_cells(start_row=f_mes, start_column=col_tot + k, end_row=f_ini, end_column=col_tot + k)

    fila = f_ini + 1
    for n, a in enumerate(datos["filas"], start=1):
        _celda(ws, fila, 1, n).alignment = CENTRO
        _celda(ws, fila, 2, a["dni"] or "")
        _celda(ws, fila, 3, a["nombre"])
        for j, e in enumerate(a["estados"]):
            _celda(ws, fila, len(fijas) + 1 + j, e or "", fondo=FONDO.get(e)).alignment = CENTRO
        for k, v in enumerate([a["P"], a["T"], a["F"], a["pct"]]):
            c = _celda(ws, fila, col_tot + k, v)
            c.alignment = CENTRO
        ws.cell(fila, col_tot + 3).number_format = '0.0"%"'
        fila += 1

    # totales por día
    for etiqueta, clave in (("Asistieron", "asistieron"), ("Faltaron", "faltaron")):
        _celda(ws, fila, 3, etiqueta).font = Font(bold=True)
        for j, d in enumerate(datos["dias"]):
            _celda(ws, fila, len(fijas) + 1 + j, d[clave]).alignment = CENTRO
        fila += 1
    ws.cell(fila + 1, 1, "Leyenda: P = Presente · T = Tardanza · F = Falta · "
                         "(vacío) = sin registro. Las tardanzas cuentan como asistencia.").font = \
        Font(italic=True, color="666666")

    ws.column_dimensions["A"].width = 5
    ws.column_dimensions["B"].width = 11
    ws.column_dimensions["C"].width = 34
    for j in range(len(datos["dias"])):
        ws.column_dimensions[get_column_letter(len(fijas) + 1 + j)].width = 3.6
    for k in range(4):
        ws.column_dimensions[get_column_letter(col_tot + k)].width = 8
    ws.freeze_panes = ws.cell(f_ini + 1, len(fijas) + 1)
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_title_rows = f"{f_mes}:{f_ini}"


def _hoja_resumen(ws, seccion, datos):
    """Hoja con el total de cada alumno por mes."""
    _encabezado(ws, seccion, "RESUMEN DE ASISTENCIA POR MES", datos["desde"], datos["hasta"])
    f_cab = 6
    cab = ["N.°", "DNI", "Apellidos y nombres"] + [m["nombre"] for m in datos["meses"]] + \
          ["Faltas", "Tardanzas", "% asist."]
    for i, t in enumerate(cab, start=1):
        _celda(ws, f_cab, i, t, cabecera=True)
    meses_idx = {}
    for j, d in enumerate(datos["dias"]):
        meses_idx.setdefault(d["mes"], []).append(j)
    fila = f_cab + 1
    for n, a in enumerate(datos["filas"], start=1):
        valores = [n, a["dni"] or "", a["nombre"]]
        for m in datos["meses"]:
            est = [a["estados"][j] for j in meses_idx[m["mes"]]]
            valores.append(_pct(est.count("P"), est.count("T"), est.count("F")))
        valores += [a["F"], a["T"], a["pct"]]
        for i, v in enumerate(valores, start=1):
            c = _celda(ws, fila, i, v)
            if i > 3:
                c.alignment = CENTRO
            if 3 < i <= 3 + len(datos["meses"]) or i == len(valores):
                c.number_format = '0.0"%"'
        fila += 1
    ws.column_dimensions["A"].width = 5
    ws.column_dimensions["B"].width = 11
    ws.column_dimensions["C"].width = 34
    for i in range(4, len(cab) + 1):
        ws.column_dimensions[get_column_letter(i)].width = 11
    ws.freeze_panes = ws.cell(f_cab + 1, 4)
    ws.page_setup.orientation = "landscape"


def excel(seccion, datos, titulo="REGISTRO DE ASISTENCIA"):
    """Libro con: resumen por mes, el detalle del período y una hoja por mes."""
    wb = Workbook()
    _hoja_resumen(wb.active, seccion, datos)
    wb.active.title = "Resumen"
    _hoja_detalle(wb.create_sheet("Detalle"), seccion, datos, titulo)
    for m, sub in zip(datos["meses"], por_mes(datos)):
        _hoja_detalle(wb.create_sheet(m["nombre"]), seccion, sub, f"{titulo} - {m['nombre'].upper()}")
    salida = BytesIO()
    wb.save(salida)
    salida.seek(0)
    return salida


def recortar(datos, desde, hasta):
    """Los mismos datos limitados a un rango de fechas (sin volver a consultar)."""
    idx = [j for j, d in enumerate(datos["dias"]) if desde <= d["fecha"] <= hasta]
    filas = []
    for a in datos["filas"]:
        est = [a["estados"][j] for j in idx]
        c = {k: est.count(k) for k in ESTADOS}
        filas.append({**a, "estados": est, **c, "pct": _pct(c["P"], c["T"], c["F"])})
    dias = [datos["dias"][j] for j in idx]
    meses = []
    for d in dias:
        if meses and meses[-1]["mes"] == d["mes"]:
            meses[-1]["dias"] += 1
        else:
            meses.append({"mes": d["mes"], "nombre": MESES[d["mes"]], "dias": 1})
    return {**datos, "desde": desde, "hasta": hasta, "dias": dias, "meses": meses, "filas": filas}
