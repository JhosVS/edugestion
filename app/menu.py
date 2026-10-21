"""Menú lateral por rol: (endpoint, texto, icono)."""
from flask import g, request

MENUS = {
    "alumno": [
        ("alumno.inicio", "Inicio", "inicio"),
        ("alumno.cursos", "Cursos", "cursos"),
        ("alumno.libreta", "Libreta", "libreta"),
        ("alumno.asistencia", "Asistencia", "asistencia"),
        ("alumno.agenda", "Agenda", "agenda"),
    ],
    "docente": [
        ("docente.inicio", "Inicio", "inicio"),
        ("docente.asistencia", "Asistencia", "asistencia"),
        ("docente.notas", "Notas", "libreta"),
        ("docente.agenda", "Agenda", "agenda"),
    ],
    "director": [
        ("director.inicio", "Inicio", "inicio"),
        ("director.asistencia", "Asistencia", "asistencia"),
        ("director.rendimiento", "Rendimiento", "rendimiento"),
        ("director.siagie", "SIAGIE", "siagie"),
        ("gestion.inicio", "Gestión", "gestion"),
    ],
}

# Blueprints que ocupan un solo ítem del menú: cualquiera de sus vistas lo resalta.
BLUEPRINTS_DE_UN_ITEM = {"gestion"}


def menu_activo(endpoint):
    """Resalta la vista actual y sus vistas hijas (docente.asistencia -> docente.asistencia_seccion)."""
    actual = request.endpoint or ""
    blueprint = endpoint.split(".")[0]
    return actual.startswith(endpoint) or (
        blueprint in BLUEPRINTS_DE_UN_ITEM and request.blueprint == blueprint)


def init_app(app):
    @app.context_processor
    def inyectar_menu():
        usuario = g.get("usuario")
        return {"menu": MENUS.get(usuario["rol"], []) if usuario else [],
                "menu_activo": menu_activo}