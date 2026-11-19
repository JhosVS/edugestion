from flask import Flask


def create_app():
    app = Flask(__name__)
    app.config.from_object("config.Config")

    from . import ajustes, auditoria, auth, csrf, db, estadisticas, menu, utils
    db.init_app(app)
    csrf.init_app(app)
    ajustes.init_app(app)
    menu.init_app(app)
    app.jinja_env.filters["fecha_corta"] = utils.fecha_corta
    app.jinja_env.filters["fecha_hora"] = utils.fecha_hora
    app.jinja_env.globals["acciones_nombre"] = auditoria.ACCIONES
    app.jinja_env.globals["grafico_linea"] = estadisticas.grafico_linea
    app.register_blueprint(auth.bp)

    from .routes import admin, alumno, director, docente, gestion, padre, reportes
    app.register_blueprint(alumno.bp)
    app.register_blueprint(padre.bp)
    app.register_blueprint(docente.bp)
    app.register_blueprint(director.bp)
    app.register_blueprint(gestion.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(reportes.bp)

    return app