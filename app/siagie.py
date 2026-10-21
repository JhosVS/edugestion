"""Excel de calificativos para la carga manual en el SIAGIE.

FORMATO PROVISIONAL: la disposición (encabezado, columnas y fila inicial) está
en las constantes de abajo para ajustarla a la plantilla oficial del colegio.
Una hoja por curso; filas = alumnos activos, columnas = competencias.
"""
import re
import unicodedata
from io import BytesIO

from flask import current_app
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

CALIFICATIVOS = ("AD", "A", "B", "C")
COLUMNAS_FIJAS = ("N.°", "DNI / Código", "Apellidos y nombres")
FILA_CABECERA = 7  # las filas 1 a 5 son el encabezado institucional

NEGRITA = Font(bold=True)
TITULO = Font(bold=True, size=13)
FONDO_CABECERA = PatternFill("solid", fgColor="1F4E78")
FONDO_FALTA = PatternFill("solid", fgColor="FFF2CC")  # calificativo sin registrar
BORDE = Border(*(Side(style="thin", color="999999"),) * 4)
CENTRO = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _ascii(texto):
    """'1° Matemática' -> '1Matematica' (para el nombre del archivo)."""
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]", "", sin_tildes)


def _alumnos(db, seccion_id):
    return db.execute(
        "SELECT u.id, al.dni, u.apellidos || ', ' || u.nombres AS nombre FROM alumnos al "
        "JOIN usuarios u ON u.id = al.usuario_id WHERE al.seccion_id = ? AND u.activo = 1 "
        "ORDER BY u.apellidos, u.nombres", (seccion_id,)).fetchall()


def _hoja(wb, db, asig, alumnos, bimestre):
    """Llena una hoja con los calificativos de una asignación. Devuelve los faltantes."""
    ws = wb.create_sheet(re.sub(r"[\[\]:*?/\\]", "", asig["curso"])[:31])
    cfg = current_app.config
    competencias = db.execute("SELECT id, nombre FROM competencias WHERE curso_id = ? ORDER BY id",
                              (asig["curso_id"],)).fetchall()
    notas = {(r["alumno_id"], r["competencia_id"]): r["calificativo"] for r in db.execute(
        "SELECT k.alumno_id, k.competencia_id, k.calificativo FROM calificaciones k "
        "JOIN competencias co ON co.id = k.competencia_id "
        "WHERE co.curso_id = ? AND k.bimestre = ?", (asig["curso_id"], bimestre))}

    # --- Encabezado institucional ---
    ws["A1"] = "REGISTRO DE CALIFICATIVOS PARA CARGA EN SIAGIE"
    ws["A1"].font = TITULO
    datos = [("Institución educativa", cfg["INSTITUCION"]),
             ("Código modular", cfg["CODIGO_MODULAR"] or "—"),
             ("Año / Grado y sección", f'{asig["anio"]} / {asig["grado"]} "{asig["seccion"]}"'),
             ("Área / Bimestre", f'{asig["curso"]} / Bimestre {bimestre}'),
             ("Docente", asig["docente"])]
    for fila, (etiqueta, valor) in enumerate(datos, start=2):
        ws.cell(fila, 2, etiqueta).font = NEGRITA
        ws.cell(fila, 3, valor)

    # --- Tabla ---
    cabecera = list(COLUMNAS_FIJAS) + [c["nombre"] for c in competencias]
    for col, texto in enumerate(cabecera, start=1):
        celda = ws.cell(FILA_CABECERA, col, texto)
        celda.font, celda.fill = Font(bold=True, color="FFFFFF"), FONDO_CABECERA
        celda.alignment, celda.border = CENTRO, BORDE
    ws.row_dimensions[FILA_CABECERA].height = 60

    faltantes = 0
    for n, a in enumerate(alumnos, start=1):
        fila = FILA_CABECERA + n
        for col, valor in enumerate((n, a["dni"] or "", a["nombre"]), start=1):
            ws.cell(fila, col, valor).border = BORDE
        for col, c in enumerate(competencias, start=len(COLUMNAS_FIJAS) + 1):
            nota = notas.get((a["id"], c["id"]))
            celda = ws.cell(fila, col, nota)
            celda.alignment, celda.border = CENTRO, BORDE
            if nota is None:
                celda.fill = FONDO_FALTA
                faltantes += 1

    # Si alguien corrige el Excel a mano, solo se aceptan AD, A, B o C.
    if competencias and alumnos:
        dv = DataValidation(type="list", formula1=f'"{",".join(CALIFICATIVOS)}"', allow_blank=True)
        dv.add(f"{get_column_letter(len(COLUMNAS_FIJAS) + 1)}{FILA_CABECERA + 1}:"
               f"{get_column_letter(len(cabecera))}{FILA_CABECERA + len(alumnos)}")
        ws.add_data_validation(dv)

    if faltantes:
        nota_fila = FILA_CABECERA + len(alumnos) + 2
        ws.cell(nota_fila, 1, f"Faltan {faltantes} calificativos (celdas resaltadas).").font = \
            Font(bold=True, color="C00000")

    ws.column_dimensions["A"].width = 6
    ws.column_dimensions["B"].width = 14
    ws.column_dimensions["C"].width = 34
    for col in range(len(COLUMNAS_FIJAS) + 1, len(cabecera) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 18
    ws.freeze_panes = ws.cell(FILA_CABECERA + 1, len(COLUMNAS_FIJAS) + 1)
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    return faltantes


def generar_excel(db, seccion_id, bimestre, asignacion_id=None):
    """Excel de una sección (todos sus cursos o solo `asignacion_id`).

    Devuelve (archivo en memoria, nombre sugerido, calificativos faltantes).
    """
    asignaciones = db.execute(
        "SELECT a.id, a.curso_id, c.nombre AS curso, s.anio, s.grado, s.seccion, "
        " u.nombres || ' ' || u.apellidos AS docente "
        "FROM asignaciones a JOIN cursos c ON c.id = a.curso_id "
        "JOIN secciones s ON s.id = a.seccion_id JOIN usuarios u ON u.id = a.docente_id "
        "WHERE a.seccion_id = ? AND (? IS NULL OR a.id = ?) ORDER BY c.nombre",
        (seccion_id, asignacion_id, asignacion_id)).fetchall()
    alumnos = _alumnos(db, seccion_id)

    wb = Workbook()
    wb.remove(wb.active)
    faltantes = sum(_hoja(wb, db, a, alumnos, bimestre) for a in asignaciones)
    if not asignaciones:
        wb.create_sheet("Sin cursos")["A1"] = "La sección no tiene cursos asignados."

    archivo = BytesIO()
    wb.save(archivo)
    archivo.seek(0)

    s = asignaciones[0] if asignaciones else db.execute(
        "SELECT anio, grado, seccion FROM secciones WHERE id = ?", (seccion_id,)).fetchone()
    curso = f'_{_ascii(asignaciones[0]["curso"])[:12]}' if asignacion_id and asignaciones else ""
    nombre = f'SIAGIE_{s["anio"]}_{_ascii(s["grado"] + s["seccion"])}{curso}_B{bimestre}.xlsx'
    return archivo, nombre, faltantes
