"""Bitácora de acciones (tabla auditoria)."""
from flask import g, request

from .db import get_db
from .utils import ahora

ACCIONES = {
    "login": "Inicio de sesión",
    "login_fallido": "Intento fallido",
    "login_bloqueado": "Acceso bloqueado",
    "logout": "Cierre de sesión",
    "clave": "Cambio de contraseña",
    "usuario": "Usuarios",
    "seccion": "Secciones",
    "curso": "Cursos y competencias",
    "asignacion": "Asignaciones",
    "horario": "Horarios",
    "notas": "Notas",
    "asistencia": "Asistencia",
    "agenda": "Agenda",
    "configuracion": "Configuración",
    "respaldo": "Respaldo",
}


def ip_cliente():
    """IP del visitante. En Render la app está detrás de un proxy que envía X-Forwarded-For."""
    return request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()


def registrar(accion, detalle="", usuario_id=None):
    """Guarda un evento y confirma la transacción. Llamar después de que la acción tuvo éxito."""
    if usuario_id is None and g.get("usuario"):
        usuario_id = g.usuario["id"]
    db = get_db()
    db.execute("INSERT INTO auditoria(fecha, usuario_id, accion, detalle, ip) VALUES (?,?,?,?,?)",
               (ahora(), usuario_id, accion, (detalle or "")[:300], ip_cliente()))
    db.commit()
