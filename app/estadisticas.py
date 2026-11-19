"""Datos para los paneles de asistencia y notas de cada rol.

El alcance define qué alumnos se cuentan:
  alumno_id    -> un alumno (vista del alumno y del padre)
  seccion_ids  -> varias secciones (vista del docente)
  (ninguno)    -> toda la institución (director y administrador)
Siempre se cuentan solo los alumnos activos del año lectivo configurado.
"""
from .ajustes import ajustes
from .db import get_db

MESES = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Set", "Oct", "Nov", "Dic"]
NIVELES = ("AD", "A", "B", "C")


def _filtro(alumno_id=None, seccion_ids=None):
    """Condición SQL sobre `al` (alumnos) y `u` (usuarios) y sus parámetros."""
    if alumno_id is not None:
        return "al.usuario_id = ?", [alumno_id]
    if seccion_ids is not None:
        if not seccion_ids:
            return "0", []
        return f"al.seccion_id IN ({','.join('?' * len(seccion_ids))})", list(seccion_ids)
    return "1", []


def asistencia_mensual(alumno_id=None, seccion_ids=None):
    """Por mes del año lectivo: presentes, tardanzas, faltas y % de asistencia."""
    cond, params = _filtro(alumno_id, seccion_ids)
    filas = get_db().execute(
        "SELECT CAST(strftime('%m', x.fecha) AS INTEGER) AS mes, "
        " SUM(x.estado = 'P') AS p, SUM(x.estado = 'T') AS t, SUM(x.estado = 'F') AS f "
        "FROM asistencias x JOIN alumnos al ON al.usuario_id = x.alumno_id "
        "JOIN usuarios u ON u.id = al.usuario_id "
        f"WHERE u.activo = 1 AND strftime('%Y', x.fecha) = ? AND {cond} "
        "GROUP BY mes ORDER BY mes", [ajustes()["anio_lectivo"], *params]).fetchall()
    meses = []
    for f in filas:
        total = f["p"] + f["t"] + f["f"]
        meses.append({"mes": MESES[f["mes"]], "p": f["p"], "t": f["t"], "f": f["f"],
                      "total": total, "pct": round(100 * (f["p"] + f["t"]) / total, 1)})
    return meses


def asistencia_total(meses):
    p, t, f = (sum(m[k] for m in meses) for k in ("p", "t", "f"))
    total = p + t + f
    return {"p": p, "t": t, "f": f, "total": total,
            "pct": round(100 * (p + t) / total, 1) if total else None}


def asistencia_por_seccion(seccion_ids=None):
    """% de asistencia del año por sección (para comparar secciones)."""
    cond, params = _filtro(seccion_ids=seccion_ids)
    filas = get_db().execute(
        "SELECT s.id, s.grado, s.seccion, SUM(x.estado != 'F') AS asistio, COUNT(*) AS total, "
        " SUM(x.estado = 'F') AS f "
        "FROM asistencias x JOIN alumnos al ON al.usuario_id = x.alumno_id "
        "JOIN usuarios u ON u.id = al.usuario_id JOIN secciones s ON s.id = al.seccion_id "
        f"WHERE u.activo = 1 AND strftime('%Y', x.fecha) = ? AND {cond} "
        "GROUP BY s.id ORDER BY s.grado, s.seccion", [ajustes()["anio_lectivo"], *params]).fetchall()
    return [{"nombre": f'{f["grado"]} "{f["seccion"]}"', "pct": round(100 * f["asistio"] / f["total"], 1),
             "f": f["f"], "total": f["total"]} for f in filas]


def _reparto(fila):
    total = sum(fila[n] for n in NIVELES)
    return {"total": total, "cuentas": {n: fila[n] for n in NIVELES},
            "pct": {n: (100 * fila[n] / total if total else 0) for n in NIVELES},
            "logro": round(100 * (fila["AD"] + fila["A"]) / total) if total else None}


def _consulta_notas(agrupar, alumno_id=None, seccion_ids=None, docente_id=None, bimestre=None):
    cond, params = _filtro(alumno_id, seccion_ids)
    union_docente = ("JOIN asignaciones a ON a.curso_id = co.curso_id AND a.seccion_id = al.seccion_id "
                     "AND a.docente_id = ? " if docente_id else "")
    extra = [docente_id] if docente_id else []
    filtro_b = "AND k.bimestre = ? " if bimestre else ""
    return get_db().execute(
        f"SELECT {agrupar} AS grupo, " + ", ".join(f"SUM(k.calificativo = '{n}') AS {n}" for n in NIVELES) + " "
        "FROM calificaciones k JOIN alumnos al ON al.usuario_id = k.alumno_id "
        "JOIN usuarios u ON u.id = al.usuario_id JOIN competencias co ON co.id = k.competencia_id "
        "JOIN cursos c ON c.id = co.curso_id JOIN secciones s ON s.id = al.seccion_id "
        f"{union_docente}WHERE u.activo = 1 AND {cond} {filtro_b}"
        f"GROUP BY grupo ORDER BY grupo",
        [*extra, *params, *([bimestre] if bimestre else [])]).fetchall()


def notas_por_bimestre(**alcance):
    """Reparto AD/A/B/C de cada bimestre con notas registradas."""
    return [{"nombre": f"Bimestre {f['grupo']}", **_reparto(f)}
            for f in _consulta_notas("k.bimestre", **alcance)]


def ultimo_bimestre_con_notas(**alcance):
    b = [f["grupo"] for f in _consulta_notas("k.bimestre", **alcance)]
    return max(b) if b else None


def notas_por_curso(bimestre, por_seccion=False, **alcance):
    """Reparto AD/A/B/C por área (o por área y sección) en un bimestre."""
    agrupar = "c.nombre || ' · ' || s.grado || ' \"' || s.seccion || '\"'" if por_seccion else "c.nombre"
    return [{"nombre": f["grupo"], **_reparto(f)}
            for f in _consulta_notas(agrupar, bimestre=bimestre, **alcance)]


def grafico_linea(meses, ancho=480, alto=220):
    """Coordenadas SVG del % de asistencia por mes. El eje Y empieza en un múltiplo de 5
    por debajo del mes más bajo (no en 0) para que se vean las variaciones."""
    if not meses:
        return None
    izq, der, arriba, abajo = 40, 48, 14, 28
    minimo = min(m["pct"] for m in meses)
    piso = max(0, min(90, int(minimo // 5) * 5 - 5))
    paso = 5 if 100 - piso <= 25 else 10
    alto_util, ancho_util = alto - arriba - abajo, ancho - izq - der

    def y(v):
        return arriba + alto_util * (100 - v) / (100 - piso)

    n = len(meses)
    puntos = [{**m, "x": izq + (ancho_util * i / (n - 1) if n > 1 else ancho_util / 2), "y": y(m["pct"])}
              for i, m in enumerate(meses)]
    camino = " ".join(f"{'M' if i == 0 else 'L'}{p['x']:.1f},{p['y']:.1f}" for i, p in enumerate(puntos))
    base = y(piso)
    area = f"{camino} L{puntos[-1]['x']:.1f},{base:.1f} L{puntos[0]['x']:.1f},{base:.1f} Z"
    menor = min(puntos, key=lambda p: p["pct"])
    return {"ancho": ancho, "alto": alto, "izq": izq, "der": ancho - der, "base": base,
            "puntos": puntos, "linea": camino, "area": area,
            "ticks": [{"valor": v, "y": y(v)} for v in range(piso, 101, paso)],
            # etiquetas directas solo en el último mes y en el mes más bajo
            "etiquetados": [puntos[-1]] + ([menor] if menor is not puntos[-1] else [])}


def panel(alumno_id=None, seccion_ids=None, docente_id=None, por_seccion=False):
    """Todo lo que necesita el macro de panel, para un alcance."""
    alcance = {"alumno_id": alumno_id, "seccion_ids": seccion_ids}
    meses = asistencia_mensual(**alcance)
    notas_alcance = {**alcance, "docente_id": docente_id}
    ultimo = ultimo_bimestre_con_notas(**notas_alcance)
    return {
        "meses": meses,
        "asistencia": asistencia_total(meses),
        "bimestres": notas_por_bimestre(**notas_alcance),
        "ultimo": ultimo,
        "cursos": notas_por_curso(ultimo, por_seccion=por_seccion, **notas_alcance) if ultimo else [],
    }
