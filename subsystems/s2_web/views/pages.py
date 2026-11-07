from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

from subsystems.s2_web.catalog import BUILDINGS, CATEGORIES, DEFAULT_BUILDING, HISTORY_PERIODS
from subsystems.s2_web.errors import InvalidInputError
from subsystems.s2_web.forms import ScenarioForm, ThresholdForm
from subsystems.s2_web.services import get_coach_view, get_page_view

bp = Blueprint("pages", __name__)


def selected_building():
    """Building from the URL, remembered in the session for the next page."""
    building = request.args.get("building")
    if building is None:
        building = session.get("building", DEFAULT_BUILDING)
        return building if building in BUILDINGS else DEFAULT_BUILDING
    if building not in BUILDINGS:
        raise InvalidInputError(f"Unknown building '{building}'.")
    session["building"] = building
    return building


def optional_choice(name, allowed, default=None):
    value = request.args.get(name, default)
    if value is not None and value not in allowed:
        raise InvalidInputError(f"Unknown {name} '{value}'.")
    return value


@bp.get("/")
def dashboard():
    building = selected_building()
    category = optional_choice("category", CATEGORIES)
    return render_template("dashboard.html", **get_page_view().index(building, category))


@bp.get("/history")
def history():
    building = selected_building()
    period = optional_choice("period", HISTORY_PERIODS, "today")
    category = optional_choice("category", CATEGORIES)
    return render_template("history.html", **get_page_view().history(building, period, category))


@bp.route("/scenarios", methods=["GET", "POST"])
def scenarios():
    building = selected_building()
    form = ScenarioForm()
    context = {"page": "scenarios", "building": building, "form": form, "rows": None, "summary": None}

    if form.validate_on_submit() or request.method == "GET":
        context = get_page_view().scenarios(building, form)

    status = 400 if form.errors else 200
    return render_template("scenarios.html", **context), status


@bp.get("/coach")
def coach():
    building = selected_building()
    return render_template("coach.html", **get_coach_view().page(building))


@bp.route("/settings", methods=["GET", "POST"])
def settings():
    building = selected_building()
    form = ThresholdForm()
    view = get_page_view()

    if form.validate_on_submit():
        view.settings(building, form, save=True)
        flash("Limits saved for this session." if current_app.config["USE_MOCK"] else "Limits saved.", "success")
        return redirect(url_for("pages.settings", building=building))

    status = 400 if form.errors else 200
    return render_template("settings.html", **view.settings(building, form)), status
