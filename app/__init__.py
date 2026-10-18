from flask import Flask


def create_app():
    app = Flask(__name__)
    app.config.from_object("config.Config")

    from . import auth, db, menu, utils
    db.init_app(app)
    menu.init_app(app)
    app.jinja_env.filters["fecha_corta"] = utils.fecha_corta
    app.register_blueprint(auth.bp)

    from .routes import alumno, director, docente
    app.register_blueprint(alumno.bp)
    app.register_blueprint(docente.bp)
    app.register_blueprint(director.bp)

    return app