import sqlite3
from pathlib import Path

from flask import current_app, g

from database.seed import cargar_datos

SCHEMA = Path(__file__).resolve().parent.parent / "database" / "schema.sql"


def get_db():
    """Una conexión por petición, con claves foráneas activadas."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def _migrar(db):
    """Cambios de esquema para bases creadas con una versión anterior."""
    columnas = {c["name"] for c in db.execute("PRAGMA table_info(alumnos)")}
    if "dni" not in columnas:
        db.execute("ALTER TABLE alumnos ADD COLUMN dni TEXT")
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_alumnos_dni ON alumnos(dni)")


def init_db():
    """Crea las tablas y, si no hay usuarios, carga los datos de prueba."""
    db = get_db()
    db.executescript(SCHEMA.read_text(encoding="utf-8"))
    _migrar(db)
    if db.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] == 0:
        cargar_datos(db)
    db.commit()


def init_app(app):
    app.teardown_appcontext(close_db)