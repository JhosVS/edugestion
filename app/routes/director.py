from flask import Blueprint, render_template

from ..auth import login_required

bp = Blueprint("director", __name__, url_prefix="/director")


@bp.route("/")
@login_required("director")
def inicio():
    return render_template("placeholder.html", titulo="Inicio de director")