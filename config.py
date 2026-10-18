import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-cambiar-en-produccion")
    DATABASE = BASE_DIR / "database" / "edugestion.db"
    SESSION_COOKIE_SAMESITE = "Lax"

    # Solo para pruebas / exposición académica. Poner en False al usar datos reales.
    MOSTRAR_CREDENCIALES_DEMO = True
    CREDENCIALES_DEMO = [
        ("Director", "director@edugestion.test", "director123"),
        ("Docente", "docente@edugestion.test", "docente123"),
        ("Alumno", "alumno@edugestion.test", "alumno123"),
    ]