import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
EN_RENDER = bool(os.environ.get("RENDER"))  # Render define esta variable automáticamente


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-cambiar-en-produccion")
    DATABASE = BASE_DIR / "database" / "edugestion.db"
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = EN_RENDER  # cookie solo por HTTPS en producción

    # Solo para pruebas / exposición académica. En Render se puede ocultar con MOSTRAR_DEMO=0.
    MOSTRAR_CREDENCIALES_DEMO = os.environ.get("MOSTRAR_DEMO", "1") == "1"
    CREDENCIALES_DEMO = [
        ("Director", "director@edugestion.test", "director123"),
        ("Docente", "docente@edugestion.test", "docente123"),
        ("Alumno", "alumno@edugestion.test", "alumno123"),
    ]