import os

from app import create_app
from app.db import init_db

app = create_app()

with app.app_context():
    init_db()  # crea database/edugestion.db con datos de prueba si no existe

if __name__ == "__main__":  # solo al ejecutar `python run.py` en tu PC
    app.run(debug=not os.environ.get("RENDER"))