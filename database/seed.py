"""Datos de prueba para el prototipo (NO usar datos reales de estudiantes)."""
import random
from datetime import date, timedelta

from werkzeug.security import generate_password_hash

NOMBRES_ALUMNOS = [
    ("Ana", "Quispe Rojas"), ("Luis", "Huamán Cóndor"), ("María", "Salazar Vega"),
    ("Pedro", "Chávez Lazo"), ("Rosa", "Poma Ticllas"), ("Diego", "Mendoza Ríos"),
    ("Lucía", "Paucar Gómez"), ("Jorge", "Ramos Bravo"), ("Carla", "Yauri Soto"),
    ("Mateo", "Lozano Cruz"), ("Sofía", "Aliaga Torres"), ("Bruno", "Castro León"),
]

CURSOS = {
    "Matemática": ["Resuelve problemas de cantidad",
                   "Resuelve problemas de regularidad, equivalencia y cambio"],
    "Comunicación": ["Se comunica oralmente", "Lee diversos tipos de textos",
                     "Escribe diversos tipos de textos"],
    "Ciencia y Tecnología": ["Indaga mediante métodos científicos",
                             "Explica el mundo físico basándose en conocimientos"],
    "Personal Social": ["Construye su identidad", "Convive y participa democráticamente"],
}


def cargar_datos(db):
    """Inserta usuarios, secciones, cursos y algunos registros de ejemplo."""
    rnd = random.Random(42)  # semilla fija: siempre los mismos datos de prueba

    def usuario(nombres, apellidos, correo, clave, rol):
        cur = db.execute(
            "INSERT INTO usuarios(nombres, apellidos, correo, clave_hash, rol) VALUES (?,?,?,?,?)",
            (nombres, apellidos, correo, generate_password_hash(clave), rol))
        return cur.lastrowid

    # --- Personal ---
    usuario("Director", "de Prueba", "director@edugestion.test", "director123", "director")
    doc1 = usuario("Carmen", "Rivera Flores", "docente@edugestion.test", "docente123", "docente")
    doc2 = usuario("Raúl", "Espinoza Meza", "docente2@edugestion.test", "docente123", "docente")

    # --- Secciones, cursos y competencias ---
    secciones = []
    for letra in ("A", "B"):
        secciones.append(db.execute(
            "INSERT INTO secciones(anio, grado, seccion) VALUES (2026, '1°', ?)", (letra,)).lastrowid)

    cursos = {}
    competencias = []
    for nombre, comps in CURSOS.items():
        cid = db.execute("INSERT INTO cursos(nombre) VALUES (?)", (nombre,)).lastrowid
        cursos[nombre] = cid
        for c in comps:
            competencias.append(db.execute(
                "INSERT INTO competencias(curso_id, nombre) VALUES (?,?)", (cid, c)).lastrowid)

    # --- Asignaciones docente-curso-sección y horario (2 bloques por semana, sin cruces) ---
    bloques = [("08:00", "09:30"), ("09:45", "11:15"), ("11:30", "13:00"), ("14:00", "15:30")]
    docente_de = {"Matemática": doc1, "Comunicación": doc1,
                  "Ciencia y Tecnología": doc2, "Personal Social": doc2}
    for si, sec in enumerate(secciones):
        for ci, (nombre, docente) in enumerate(docente_de.items()):
            asig = db.execute("INSERT INTO asignaciones(docente_id, curso_id, seccion_id) "
                              "VALUES (?,?,?)", (docente, cursos[nombre], sec)).lastrowid
            inicio, fin = bloques[(ci + 2 * si) % 4]
            for dia in ((1, 3) if ci < 2 else (2, 4)):
                db.execute("INSERT INTO horarios(asignacion_id, dia_semana, hora_inicio, hora_fin) "
                           "VALUES (?,?,?,?)", (asig, dia, inicio, fin))

    # --- Alumnos (6 por sección). El primero es alumno@edugestion.test ---
    alumnos = []
    for i, (nom, ape) in enumerate(NOMBRES_ALUMNOS):
        correo = "alumno@edugestion.test" if i == 0 else f"alumno{i + 1}@edugestion.test"
        uid = usuario(nom, ape, correo, "alumno123", "alumno")
        db.execute("INSERT INTO alumnos(usuario_id, seccion_id, dni) VALUES (?,?,?)",
                   (uid, secciones[i // 6], f"{70000001 + i}"))  # DNI ficticio
        alumnos.append(uid)

    # --- Agenda: algunos pendientes próximos ---
    for sec in secciones:
        for dias, titulo, desc in [(2, "Práctica de Matemática", "Problemas de cantidad, páginas 20 a 24."),
                                   (6, "Exposición de Comunicación", "Tema libre, 5 minutos por grupo.")]:
            db.execute("INSERT INTO agenda(seccion_id, titulo, descripcion, fecha, creado_por) "
                       "VALUES (?,?,?,?,?)",
                       (sec, titulo, desc, (date.today() + timedelta(days=dias)).isoformat(), doc1))

    # --- Asistencias de los últimos 5 días hábiles ---
    dia, cargados = date.today(), 0
    while cargados < 5:
        if dia.weekday() < 5:
            for a in alumnos:
                estado = rnd.choices(["P", "T", "F"], weights=[85, 8, 7])[0]
                db.execute("INSERT INTO asistencias(alumno_id, fecha, estado, registrado_por) "
                           "VALUES (?,?,?,?)", (a, dia.isoformat(), estado, doc1))
            cargados += 1
        dia -= timedelta(days=1)

    # --- Calificaciones del bimestre 1 (avance parcial, para el panel) ---
    for comp in competencias:
        for a in alumnos:
            if rnd.random() < 0.7:
                db.execute("INSERT INTO calificaciones(alumno_id, competencia_id, bimestre, "
                           "calificativo, registrado_por) VALUES (?,?,1,?,?)",
                           (a, comp, rnd.choices(["AD", "A", "B", "C"], weights=[10, 50, 30, 10])[0], doc1))

    # --- Administrador (al final para no cambiar los id de los demás usuarios) ---
    usuario("Administrador", "del Sistema", "admin@edugestion.test", "admin123", "admin")
