import re
import sqlite3
from pathlib import Path

import click
from flask import current_app, g
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash

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


def _reconstruir_usuarios(db, schema):
    """Recrea `usuarios` con el CHECK de roles y columnas actuales (SQLite no permite
    modificar un CHECK). Las claves foráneas se apagan para que DROP TABLE no borre
    en cascada alumnos, notas y asistencias."""
    crear = re.search(r"CREATE TABLE IF NOT EXISTS usuarios \(.*?\n\);", schema, re.S).group()
    db.commit()
    db.executescript(
        "PRAGMA foreign_keys = OFF; BEGIN;"
        + crear.replace("IF NOT EXISTS usuarios", "usuarios_nueva")
        + "INSERT INTO usuarios_nueva(id, nombres, apellidos, correo, clave_hash, rol, activo, creado_en) "
          "SELECT id, nombres, apellidos, correo, clave_hash, rol, activo, creado_en FROM usuarios;"
          "DROP TABLE usuarios; ALTER TABLE usuarios_nueva RENAME TO usuarios;"
          "COMMIT; PRAGMA foreign_keys = ON;")


def _migrar(db, schema):
    """Cambios de esquema para bases creadas con una versión anterior."""
    sql_usuarios = db.execute("SELECT sql FROM sqlite_master WHERE name = 'usuarios'").fetchone()[0]
    if "'admin'" not in sql_usuarios:
        _reconstruir_usuarios(db, schema)

    columnas = {c["name"] for c in db.execute("PRAGMA table_info(alumnos)")}
    if "dni" not in columnas:
        db.execute("ALTER TABLE alumnos ADD COLUMN dni TEXT")
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_alumnos_dni ON alumnos(dni)")


def init_db():
    """Crea las tablas y, si no hay usuarios, carga los datos de prueba."""
    db = get_db()
    schema = SCHEMA.read_text(encoding="utf-8")
    db.executescript(schema)
    _migrar(db, schema)
    if db.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] == 0:
        cargar_datos(db)
    db.commit()


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(crear_admin)


@click.command("crear-admin")
@click.option("--correo", prompt="Correo")
@click.option("--nombres", prompt="Nombres")
@click.option("--apellidos", prompt="Apellidos")
@click.password_option("--clave", prompt="Contraseña", confirmation_prompt="Repite la contraseña")
@with_appcontext
def crear_admin(correo, nombres, apellidos, clave):
    """Crea una cuenta de administrador: flask --app run crear-admin"""
    if len(clave) < 6:
        raise click.ClickException("La contraseña debe tener al menos 6 caracteres.")
    init_db()
    db = get_db()
    try:
        db.execute("INSERT INTO usuarios(nombres, apellidos, correo, clave_hash, rol) "
                   "VALUES (?,?,?,?, 'admin')", (nombres.strip(), apellidos.strip(),
                                                  correo.strip().lower(), generate_password_hash(clave)))
        db.commit()
    except sqlite3.IntegrityError:
        raise click.ClickException("Ese correo ya está registrado.")
    click.echo(f"Administrador {correo.strip().lower()} creado.")