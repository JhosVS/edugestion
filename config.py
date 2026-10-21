import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")  # lee .env si existe; las variables de Render tienen prioridad

EN_RENDER = bool(os.environ.get("RENDER"))  # Render define esta variable automáticamente
SECRET_KEY = os.environ.get("SECRET_KEY")
if EN_RENDER and not SECRET_KEY:
    raise RuntimeError("Falta la variable de entorno SECRET_KEY en Render.")


class Config:
    SECRET_KEY = SECRET_KEY or "dev-cambiar-en-produccion"  # la clave de desarrollo solo sirve en tu PC
    DATABASE = BASE_DIR / "database" / "edugestion.db"
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = EN_RENDER  # cookie solo por HTTPS en producción

    # Valores iniciales; el administrador los cambia desde Configuración (app/ajustes.py).
    INSTITUCION = os.environ.get("INSTITUCION", "I.E. César Vallejo")
    CODIGO_MODULAR = os.environ.get("CODIGO_MODULAR", "")

    # Solo para pruebas / exposición académica. Se puede ocultar con MOSTRAR_DEMO=0
    # o desde Configuración.
    MOSTRAR_CREDENCIALES_DEMO = os.environ.get("MOSTRAR_DEMO", "1") == "1"
    CREDENCIALES_DEMO = [
        ("Administrador", "admin@edugestion.test", "admin123"),
        ("Director", "director@edugestion.test", "director123"),
        ("Docente", "docente@edugestion.test", "docente123"),
        ("Alumno", "alumno@edugestion.test", "alumno123"),
    ]

    # Seguridad del inicio de sesión: tras INTENTOS_MAXIMOS fallos en BLOQUEO_MINUTOS,
    # el correo queda bloqueado durante ese mismo tiempo.
    INTENTOS_MAXIMOS = 5
    BLOQUEO_MINUTOS = 15
    CSRF_ACTIVADO = True  # las pruebas automáticas pueden apagarlo
