"""Ajustes del sistema que el administrador edita desde Configuración.

Los valores guardados en la tabla `configuracion` reemplazan a los por defecto.
"""
from datetime import date

from flask import current_app, g

from .db import get_db


def _por_defecto():
    cfg = current_app.config
    return {
        "institucion": cfg["INSTITUCION"],
        "lugar": "Cerro de Pasco",
        "codigo_modular": cfg["CODIGO_MODULAR"],
        "anio_lectivo": str(date.today().year),
        "bimestre_actual": "1",
        "mostrar_demo": "1" if cfg["MOSTRAR_CREDENCIALES_DEMO"] else "0",
    }


def ajustes():
    """Ajustes vigentes (se leen una vez por petición)."""
    if "ajustes" not in g:
        guardados = {r["clave"]: r["valor"] for r in
                     get_db().execute("SELECT clave, valor FROM configuracion")}
        g.ajustes = {**_por_defecto(), **guardados}
    return g.ajustes


def guardar(valores):
    db = get_db()
    for clave, valor in valores.items():
        db.execute("INSERT INTO configuracion(clave, valor) VALUES (?,?) "
                   "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor", (clave, valor))
    db.commit()
    g.pop("ajustes", None)


def bimestre_actual():
    return int(ajustes()["bimestre_actual"])


def init_app(app):
    @app.context_processor
    def inyectar_ajustes():
        return {"ajustes": ajustes()}
