"""Menú lateral por rol: (endpoint, texto, icono)."""
from flask import g

MENUS = {
    "alumno": [
        ("alumno.inicio", "Inicio", "inicio"),
        ("alumno.cursos", "Cursos", "cursos"),
        ("alumno.libreta", "Libreta", "libreta"),
        ("alumno.asistencia", "Asistencia", "asistencia"),
    ],
    "docente": [
        ("docente.inicio", "Inicio", "inicio"),
        ("docente.asistencia", "Asistencia", "asistencia"),
        ("docente.notas", "Notas", "libreta"),
    ],
    # Se completa en el paso 4
    "director": [("director.inicio", "Inicio", "inicio")],
}


def init_app(app):
    @app.context_processor
    def inyectar_menu():
        usuario = g.get("usuario")
        return {"menu": MENUS.get(usuario["rol"], []) if usuario else []}