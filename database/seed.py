"""Datos de prueba para el prototipo (NO usar datos reales de estudiantes).

Simula una I.E. de primaria del año 2026: 1° a 6° grado con dos secciones cada uno,
de 20 a 30 alumnos por sección, sus familias (padres con cuenta), docentes de aula y
especialistas, horarios sin cruces, asistencia diaria y calificativos por competencia.
Todos los nombres y DNI son inventados. La semilla es fija: siempre se generan los
mismos datos.
"""
import random
import unicodedata
from datetime import date, timedelta

from werkzeug.security import generate_password_hash

# =============================================================================
# Calendario escolar 2026 (ajustable)
# =============================================================================
ANIO = 2026
INICIO_CLASES = date(2026, 3, 9)
FIN_ASISTENCIA = date(2026, 11, 20)  # último día con asistencia registrada
VACACIONES = [(date(2026, 6, 1), date(2026, 6, 12)),   # vacaciones de junio
              (date(2026, 8, 3), date(2026, 8, 14))]   # vacaciones de agosto
BIMESTRES = {1: (date(2026, 3, 9), date(2026, 5, 29)),
             2: (date(2026, 6, 15), date(2026, 7, 31)),
             3: (date(2026, 8, 17), date(2026, 10, 9)),
             4: (date(2026, 10, 12), date(2026, 12, 18))}
FERIADOS = {date(2026, 4, 2), date(2026, 4, 3), date(2026, 5, 1), date(2026, 6, 29),
            date(2026, 7, 23), date(2026, 7, 28), date(2026, 7, 29), date(2026, 8, 6),
            date(2026, 10, 8), date(2026, 12, 8), date(2026, 12, 25)}

GRADOS = ["1°", "2°", "3°", "4°", "5°", "6°"]
SECCIONES = ["A", "B"]
ALUMNOS_POR_SECCION = (20, 30)

# Bloques diarios de primaria (5 días x 3 bloques = 15 por semana y sección)
BLOQUES = [("08:00", "09:30"), ("09:45", "11:15"), ("11:30", "13:00")]

# Áreas del CNEB para primaria: competencias y bloques semanales (suman 15)
CURSOS = {
    "Matemática": (3, ["Resuelve problemas de cantidad",
                       "Resuelve problemas de regularidad, equivalencia y cambio",
                       "Resuelve problemas de forma, movimiento y localización",
                       "Resuelve problemas de gestión de datos e incertidumbre"]),
    "Comunicación": (4, ["Se comunica oralmente en su lengua materna",
                         "Lee diversos tipos de textos escritos en su lengua materna",
                         "Escribe diversos tipos de textos en su lengua materna"]),
    "Personal Social": (2, ["Construye su identidad",
                            "Convive y participa democráticamente en la búsqueda del bien común",
                            "Construye interpretaciones históricas",
                            "Gestiona responsablemente el espacio y el ambiente",
                            "Gestiona responsablemente los recursos económicos"]),
    "Ciencia y Tecnología": (2, ["Indaga mediante métodos científicos para construir sus conocimientos",
                                 "Explica el mundo físico basándose en conocimientos científicos",
                                 "Diseña y construye soluciones tecnológicas para resolver problemas"]),
    "Arte y Cultura": (1, ["Aprecia de manera crítica manifestaciones artístico-culturales",
                           "Crea proyectos desde los lenguajes artísticos"]),
    "Educación Física": (2, ["Se desenvuelve de manera autónoma a través de su motricidad",
                             "Asume una vida saludable",
                             "Interactúa a través de sus habilidades sociomotrices"]),
    "Educación Religiosa": (1, ["Construye su identidad como persona humana, amada por Dios",
                                "Asume la experiencia del encuentro personal y comunitario con Dios"]),
}
CURSOS_DEL_TUTOR = ["Matemática", "Comunicación", "Personal Social", "Ciencia y Tecnología",
                    "Arte y Cultura"]

# =============================================================================
# Nombres (frecuentes en la sierra central del Perú)
# =============================================================================
NOMBRES_M = ["Luis", "Jorge", "Pedro", "Diego", "Mateo", "Bruno", "José", "Juan", "Carlos",
             "Miguel", "Ángel", "Jhon", "Kevin", "Brayan", "Josué", "Alexander", "Fabricio",
             "Sebastián", "Thiago", "Gael", "Santiago", "Joaquín", "Adrián", "Renzo", "Franco",
             "Jesús", "David", "Daniel", "Eduardo", "Rodrigo", "Elías", "Samuel", "Jhoel", "Leonel"]
NOMBRES_F = ["Ana", "María", "Rosa", "Lucía", "Carla", "Sofía", "Valeria", "Camila", "Luz",
             "Milagros", "Yuliana", "Nayeli", "Ximena", "Fiorella", "Danna", "Kiara", "Alexa",
             "Brigitte", "Mía", "Valentina", "Isabella", "Zoe", "Abigail", "Dayana", "Ruth",
             "Gabriela", "Andrea", "Rocío", "Flor", "Maribel", "Yesenia", "Sheyla", "Noemí"]
NOMBRES_ADULTO_M = ["Juan", "Carlos", "Víctor", "Wilber", "Edwin", "Marco", "Raúl", "Hugo",
                    "Fredy", "Teodoro", "Néstor", "Elmer", "Isaac", "Alberto", "Rubén", "César",
                    "Walter", "Óscar", "Félix", "Germán", "Jaime", "Percy", "Richard", "Abel"]
NOMBRES_ADULTO_F = ["Elena", "Carmen", "Gladys", "Norma", "Lidia", "Marleny", "Yolanda", "Olga",
                    "Edith", "Silvia", "Nelly", "Doris", "Rosario", "Marisol", "Betty", "Miriam",
                    "Haydée", "Judith", "Pilar", "Susana", "Victoria", "Irma", "Martha", "Juana"]
APELLIDOS = ["Quispe", "Huamán", "Cóndor", "Poma", "Ticllas", "Paucar", "Yauri", "Rojas", "Salazar",
             "Chávez", "Mendoza", "Ramos", "Lozano", "Aliaga", "Castro", "Ccori", "Huaraca", "Ataucusi",
             "Espinoza", "Rivera", "Torres", "Flores", "Gómez", "Vega", "Soto", "León", "Cruz",
             "Bravo", "Ríos", "Lazo", "Inga", "Llanos", "Maylle", "Ricra", "Tolentino", "Basilio",
             "Atencio", "Bonilla", "Campos", "Carhuaricra", "Damián", "Esteban", "Falcón", "García",
             "Huatuco", "Jurado", "Lavado", "Malpartida", "Nolasco", "Ortega", "Palacios", "Rivas",
             "Santiago", "Tucto", "Ureta", "Valverde", "Zevallos", "Alania", "Berrospi", "Cajahuamán"]

AGENDA = [
    ("Práctica de Matemática", "Problemas de cantidad: repasar las páginas del cuaderno de trabajo."),
    ("Lectura del cuento del mes", "Traer el libro leído y una ficha de resumen."),
    ("Feria de Ciencias", "Presentación de los proyectos por equipos."),
    ("Reunión de padres de familia", "Entrega de informes del bimestre, 6:00 p. m., aula de la sección."),
    ("Exposición de Personal Social", "Tema: costumbres de mi comunidad. 5 minutos por grupo."),
    ("Taller de Arte", "Traer témperas, pincel y cartulina."),
    ("Evaluación de Comunicación", "Comprensión lectora, unidades 5 y 6."),
]


def _ascii(texto):
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()


def dias_de_clase():
    """Días hábiles entre el inicio de clases y FIN_ASISTENCIA, sin vacaciones ni feriados."""
    d, dias = INICIO_CLASES, []
    while d <= FIN_ASISTENCIA:
        en_vacaciones = any(i <= d <= f for i, f in VACACIONES)
        if d.weekday() < 5 and not en_vacaciones and d not in FERIADOS:
            dias.append(d)
        d += timedelta(days=1)
    return dias


def bimestre_de(d):
    for b, (i, f) in BIMESTRES.items():
        if d <= f:
            return b if d >= i else max(b - 1, 1)  # en vacaciones: el bimestre anterior
    return 4


def cargar_datos(db):
    rnd = random.Random(42)
    claves = {r: generate_password_hash(c) for r, c in [
        ("admin", "admin123"), ("director", "director123"), ("docente", "docente123"),
        ("alumno", "alumno123"), ("padre", "padre123")]}
    correos_usados = set()

    def usuario(nombres, apellidos, rol, correo=None):
        if correo is None:  # nombre.apellido@edugestion.test, sin repetir
            base = f"{_ascii(nombres.split()[0])}.{_ascii(apellidos.split()[0])}"
            correo, n = f"{base}@edugestion.test", 1
            while correo in correos_usados:
                n += 1
                correo = f"{base}{n}@edugestion.test"
        correos_usados.add(correo)
        return db.execute("INSERT INTO usuarios(nombres, apellidos, correo, clave_hash, rol) "
                          "VALUES (?,?,?,?,?)", (nombres, apellidos, correo, claves[rol], rol)).lastrowid

    def apellido():
        return rnd.choice(APELLIDOS)

    # ------------------------------------------------------------- personal
    usuario("Director", "de Prueba", "director", "director@edugestion.test")
    tutores = {}  # (grado, sección) -> docente de aula
    nombres_fijos = {("1°", "A"): ("Carmen", "Rivera Flores", "docente@edugestion.test"),
                     ("1°", "B"): ("Raúl", "Espinoza Meza", "docente2@edugestion.test")}
    for g in GRADOS:
        for s in SECCIONES:
            if (g, s) in nombres_fijos:
                nom, ape, correo = nombres_fijos[(g, s)]
            else:
                nom = rnd.choice(NOMBRES_ADULTO_F + NOMBRES_ADULTO_M)
                ape, correo = f"{apellido()} {apellido()}", None
            tutores[(g, s)] = usuario(nom, ape, "docente", correo)
    prof_ef = [usuario("Walter", "Inga Basilio", "docente"),      # Educación Física 1° a 3°
               usuario("Judith", "Tolentino Ricra", "docente")]   # Educación Física 4° a 6°
    prof_religion = usuario("Abel", "Huatuco Lavado", "docente")

    # ------------------------------------------------------------- estructura académica
    secciones = {}
    for g in GRADOS:
        for s in SECCIONES:
            secciones[(g, s)] = db.execute("INSERT INTO secciones(anio, grado, seccion) VALUES (?,?,?)",
                                           (ANIO, g, s)).lastrowid
    cursos, competencias = {}, {}
    for nombre, (_, comps) in CURSOS.items():
        cursos[nombre] = db.execute("INSERT INTO cursos(nombre) VALUES (?)", (nombre,)).lastrowid
        competencias[nombre] = [db.execute("INSERT INTO competencias(curso_id, nombre) VALUES (?,?)",
                                           (cursos[nombre], c)).lastrowid for c in comps]

    # ------------------------------------------------------------- asignaciones
    asignaciones = {}  # (grado, sección, curso) -> (id, docente)
    for (g, s), sid in secciones.items():
        for nombre in CURSOS:
            if nombre == "Educación Física":
                docente = prof_ef[GRADOS.index(g) // 3]
            elif nombre == "Educación Religiosa":
                docente = prof_religion
            else:
                docente = tutores[(g, s)]
            aid = db.execute("INSERT INTO asignaciones(docente_id, curso_id, seccion_id) VALUES (?,?,?)",
                             (docente, cursos[nombre], sid)).lastrowid
            asignaciones[(g, s, nombre)] = (aid, docente)

    # ------------------------------------------------------------- horarios sin cruces
    # Casillas 0..14 = (día, bloque). Primero los especialistas (comparten docente entre
    # secciones), luego las áreas del tutor en las casillas libres, repartidas por días.
    ocupado_docente = {}
    for (g, s) in secciones:
        libres = list(range(15))
        for nombre in ("Educación Física", "Educación Religiosa"):
            aid, docente = asignaciones[(g, s, nombre)]
            usados = ocupado_docente.setdefault(docente, set())
            dias_usados = set()
            for _ in range(CURSOS[nombre][0]):
                casilla = next(c for c in sorted(libres, key=lambda c: (c // 3 in dias_usados, c))
                               if c not in usados)
                libres.remove(casilla)
                usados.add(casilla)
                dias_usados.add(casilla // 3)
                db.execute("INSERT INTO horarios(asignacion_id, dia_semana, hora_inicio, hora_fin) "
                           "VALUES (?,?,?,?)", (aid, casilla // 3 + 1, *BLOQUES[casilla % 3]))
        # áreas del tutor: se recorren las casillas libres alternando días
        pendientes = [n for n in CURSOS_DEL_TUTOR for _ in range(CURSOS[n][0])]
        libres.sort(key=lambda c: (c % 3, c // 3))  # primero todos los primeros bloques
        for casilla, nombre in zip(libres, pendientes):
            aid, _ = asignaciones[(g, s, nombre)]
            db.execute("INSERT INTO horarios(asignacion_id, dia_semana, hora_inicio, hora_fin) "
                       "VALUES (?,?,?,?)", (aid, casilla // 3 + 1, *BLOQUES[casilla % 3]))

    # ------------------------------------------------------------- familias y alumnos
    capacidad = {k: rnd.randint(*ALUMNOS_POR_SECCION) for k in secciones}
    dnis = iter(rnd.sample(range(70_000_000, 79_999_999), 2000))
    alumnos = []  # dicts con id, sección y perfil para generar asistencia y notas
    primera_familia = True

    def nuevo_alumno(g, s, paterno, materno, correo=None):
        mujer = rnd.random() < 0.5
        nombre = rnd.choice(NOMBRES_F if mujer else NOMBRES_M)
        if rnd.random() < 0.3:
            nombre += " " + rnd.choice([n for n in (NOMBRES_F if mujer else NOMBRES_M) if n != nombre])
        uid = usuario(nombre, f"{paterno} {materno}", "alumno", correo)
        db.execute("INSERT INTO alumnos(usuario_id, seccion_id, dni) VALUES (?,?,?)",
                   (uid, secciones[(g, s)], str(next(dnis))))
        capacidad[(g, s)] -= 1
        # Perfil oculto: nivel académico y tendencia a faltar (para datos coherentes)
        tipo = rnd.random()
        faltas = rnd.uniform(0.01, 0.04) if tipo < 0.85 else (
            rnd.uniform(0.05, 0.10) if tipo < 0.97 else rnd.uniform(0.12, 0.20))
        alumnos.append({"id": uid, "g": g, "s": s, "nivel": rnd.gauss(0, 1),
                        "faltas": faltas, "tardanzas": rnd.uniform(0.01, 0.07)})
        return uid

    while any(c > 0 for c in capacidad.values()):
        con_cupo = [k for k, c in capacidad.items() if c > 0]
        grados_libres = sorted({g for g, _ in con_cupo})
        n_hijos = min(rnd.choices([1, 2, 3], weights=[70, 25, 5])[0], len(grados_libres))
        if primera_familia:  # familia de demostración: hijos en 1° A y 4° B
            elegidos = [("1°", "A"), ("4°", "B")]
        else:
            grados = rnd.sample(grados_libres, n_hijos)
            elegidos = [rnd.choice([k for k in con_cupo if k[0] == g]) for g in grados]
        paterno, materno = apellido(), apellido()
        hijos = []
        for i, (g, s) in enumerate(elegidos):
            correo = "alumno@edugestion.test" if primera_familia and i == 0 else None
            hijos.append(nuevo_alumno(g, s, paterno, materno, correo))

        # Madre (siempre) y padre (en el 75 % de las familias), cada uno con cuenta
        madre = usuario(rnd.choice(NOMBRES_ADULTO_F), f"{materno} {apellido()}", "padre",
                        "padre@edugestion.test" if primera_familia else None)
        responsables = [(madre, "Madre")]
        if rnd.random() < 0.75:
            responsables.append((usuario(rnd.choice(NOMBRES_ADULTO_M), f"{paterno} {apellido()}",
                                         "padre"), "Padre"))
        elif rnd.random() < 0.3:  # a veces un familiar es el apoderado
            responsables.append((usuario(rnd.choice(NOMBRES_ADULTO_F + NOMBRES_ADULTO_M),
                                         f"{apellido()} {apellido()}", "padre"), "Apoderado"))
        for padre, parentesco in responsables:
            for h in hijos:
                db.execute("INSERT INTO apoderados(padre_id, alumno_id, parentesco) VALUES (?,?,?)",
                           (padre, h, parentesco))
        primera_familia = False

    # ------------------------------------------------------------- asistencia diaria
    dias = dias_de_clase()
    filas = []
    for a in alumnos:
        tutor = tutores[(a["g"], a["s"])]
        for d in dias:
            frio = 1.4 if d.month in (5, 6, 7) else 1.0  # más faltas en los meses de helada
            r = rnd.random()
            estado = "F" if r < a["faltas"] * frio else ("T" if r < a["faltas"] * frio + a["tardanzas"] else "P")
            filas.append((a["id"], d.isoformat(), estado, tutor))
    db.executemany("INSERT INTO asistencias(alumno_id, fecha, estado, registrado_por) VALUES (?,?,?,?)",
                   filas)

    # ------------------------------------------------------------- calificativos
    # Solo bimestres cerrados al FIN_ASISTENCIA (1 a 3), completos. El bimestre en curso
    # queda sin notas: los docentes las registran desde el sistema.
    actual = bimestre_de(FIN_ASISTENCIA)
    cerrados = [b for b in BIMESTRES if BIMESTRES[b][1] < FIN_ASISTENCIA]
    filas = []
    for (g, s, nombre), (aid, docente) in asignaciones.items():
        dificultad = {c: rnd.gauss(0, 0.3) for c in competencias[nombre]}
        for a in (x for x in alumnos if (x["g"], x["s"]) == (g, s)):
            for b in cerrados:
                for comp in competencias[nombre]:
                    puntaje = (a["nivel"] - dificultad[comp] + 0.12 * (b - 1)  # mejora en el año
                               - 6 * max(a["faltas"] - 0.04, 0) + rnd.gauss(0, 0.55))
                    nota = "AD" if puntaje > 1.15 else "A" if puntaje > -0.25 else "B" if puntaje > -1.2 else "C"
                    filas.append((a["id"], comp, b, nota, docente))
    db.executemany("INSERT INTO calificaciones(alumno_id, competencia_id, bimestre, calificativo, "
                   "registrado_por) VALUES (?,?,?,?,?)", filas)

    # ------------------------------------------------------------- agenda
    hoy = date.today()
    for (g, s), sid in secciones.items():
        for dias_adelante, (titulo, desc) in zip((-12, -5, 2, 6, 13),
                                                 rnd.sample(AGENDA, 5)):
            db.execute("INSERT INTO agenda(seccion_id, titulo, descripcion, fecha, creado_por) "
                       "VALUES (?,?,?,?,?)", (sid, titulo, desc,
                                              (hoy + timedelta(days=dias_adelante)).isoformat(),
                                              tutores[(g, s)]))

    # ------------------------------------------------------------- configuración y administrador
    db.executemany("INSERT INTO configuracion(clave, valor) VALUES (?,?)",
                   [("anio_lectivo", str(ANIO)), ("bimestre_actual", str(actual))])
    usuario("Administrador", "del Sistema", "admin", "admin@edugestion.test")
