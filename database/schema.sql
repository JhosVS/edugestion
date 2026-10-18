PRAGMA foreign_keys = ON;

-- ============================================================
--  USUARIOS (alumnos, docentes y director comparten esta tabla)
-- ============================================================
CREATE TABLE IF NOT EXISTS usuarios (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nombres     TEXT NOT NULL,
    apellidos   TEXT NOT NULL,
    correo      TEXT NOT NULL UNIQUE COLLATE NOCASE,
    clave_hash  TEXT NOT NULL,
    rol         TEXT NOT NULL CHECK (rol IN ('alumno', 'docente', 'director')),
    activo      INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    creado_en   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
--  ESTRUCTURA ACADÉMICA
-- ============================================================
CREATE TABLE IF NOT EXISTS secciones (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    anio     INTEGER NOT NULL,
    grado    TEXT NOT NULL,
    seccion  TEXT NOT NULL,
    UNIQUE (anio, grado, seccion)
);

-- Un alumno es un usuario con rol 'alumno' que pertenece a una sección.
CREATE TABLE IF NOT EXISTS alumnos (
    usuario_id  INTEGER PRIMARY KEY REFERENCES usuarios(id) ON DELETE CASCADE,
    seccion_id  INTEGER NOT NULL REFERENCES secciones(id)
);

CREATE TABLE IF NOT EXISTS cursos (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre  TEXT NOT NULL UNIQUE
);

-- Competencias de cada curso (la evaluación del CNEB es por competencia).
CREATE TABLE IF NOT EXISTS competencias (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    curso_id  INTEGER NOT NULL REFERENCES cursos(id) ON DELETE CASCADE,
    nombre    TEXT NOT NULL,
    UNIQUE (curso_id, nombre)
);

-- Qué docente dicta qué curso en qué sección.
CREATE TABLE IF NOT EXISTS asignaciones (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    docente_id  INTEGER NOT NULL REFERENCES usuarios(id),
    curso_id    INTEGER NOT NULL REFERENCES cursos(id),
    seccion_id  INTEGER NOT NULL REFERENCES secciones(id),
    UNIQUE (curso_id, seccion_id)
);

-- ============================================================
--  REGISTROS DIARIOS Y NOTAS
-- ============================================================
-- Asistencia diaria por alumno: P = Presente, T = Tardanza, F = Falta.
CREATE TABLE IF NOT EXISTS asistencias (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    alumno_id       INTEGER NOT NULL REFERENCES alumnos(usuario_id) ON DELETE CASCADE,
    fecha           TEXT NOT NULL,                       -- formato AAAA-MM-DD
    estado          TEXT NOT NULL CHECK (estado IN ('P', 'T', 'F')),
    registrado_por  INTEGER REFERENCES usuarios(id),
    UNIQUE (alumno_id, fecha)
);

-- Calificativo por competencia y bimestre: AD, A, B, C.
CREATE TABLE IF NOT EXISTS calificaciones (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    alumno_id       INTEGER NOT NULL REFERENCES alumnos(usuario_id) ON DELETE CASCADE,
    competencia_id  INTEGER NOT NULL REFERENCES competencias(id) ON DELETE CASCADE,
    bimestre        INTEGER NOT NULL CHECK (bimestre BETWEEN 1 AND 4),
    calificativo    TEXT NOT NULL CHECK (calificativo IN ('AD', 'A', 'B', 'C')),
    registrado_por  INTEGER REFERENCES usuarios(id),
    actualizado_en  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (alumno_id, competencia_id, bimestre)
);

-- ============================================================
--  PRÓXIMAMENTE (esquema listo, sin pantallas todavía)
-- ============================================================
CREATE TABLE IF NOT EXISTS horarios (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    asignacion_id  INTEGER NOT NULL REFERENCES asignaciones(id) ON DELETE CASCADE,
    dia_semana     INTEGER NOT NULL CHECK (dia_semana BETWEEN 1 AND 5),  -- 1 = lunes
    hora_inicio    TEXT NOT NULL,                                        -- HH:MM
    hora_fin       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agenda (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    seccion_id   INTEGER NOT NULL REFERENCES secciones(id) ON DELETE CASCADE,
    titulo       TEXT NOT NULL,
    descripcion  TEXT,
    fecha        TEXT NOT NULL,
    creado_por   INTEGER REFERENCES usuarios(id)
);

-- ============================================================
--  ÍNDICES
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_alumnos_seccion      ON alumnos(seccion_id);
CREATE INDEX IF NOT EXISTS idx_asistencias_fecha    ON asistencias(fecha);
CREATE INDEX IF NOT EXISTS idx_calif_bimestre       ON calificaciones(bimestre);
CREATE INDEX IF NOT EXISTS idx_asignaciones_docente ON asignaciones(docente_id);