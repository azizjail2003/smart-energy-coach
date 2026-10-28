from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from app import presenter
from app.catalog import (
    BUILDINGS, CATEGORIES, COACH_STATUSES, DEFAULT_BUILDING, HISTORY_PERIODS, MAX_QUESTION_LENGTH, TONES,
)
from app.forms import ScenarioForm, ThresholdForm
from app.services import get_analytics, get_coach

bp = Blueprint("pages", __name__)


def selected_building():
    """Building from the URL, remembered in the session for the next page."""
    building = request.args.get("building")
    if building is None:
        building = session.get("building", DEFAULT_BUILDING)
        return building if building in BUILDINGS else DEFAULT_BUILDING
    if building not in BUILDINGS:
        abort(400, description=f"Unknown building '{building}'.")
    session["building"] = building
    return building


def optional_choice(name, allowed, default=None):
    value = request.args.get(name, default)
    if value is not None and value not in allowed:
        abort(400, description=f"Unknown {name} '{value}'.")
    return value


@bp.get("/")
def dashboard():
    building = selected_building()
    category = optional_choice("category", CATEGORIES)
    analytics, coach = get_analytics(), get_coach()

    kpis = analytics.get_kpis(building)
    todays_alerts = [alert for alert in analytics.get_alerts(building) if alert["time"].date() == kpis["date"]]
    banner = presenter.alert_banner(todays_alerts[0]) if todays_alerts else None
    advice = coach.ask("What should we change today?", "encouraging", building)
    headline, detail = presenter.split_advice(advice["answer"])

    return render_template(
        "dashboard.html",
        page="dashboard",
        building=building,
        category=category,
        categories=CATEGORIES,
        kpis=presenter.kpi_cards(kpis, category, analytics.get_daily_trend(building, category=category)),
        score=presenter.score_payload(analytics.get_score(building)),
        banner=banner,
        coach_status=coach.status(),
        coach_status_label=COACH_STATUSES[coach.status()],
        advice_headline=headline,
        advice_detail=detail,
        report_day=kpis["date"].isoformat(),
    )


@bp.get("/history")
def history():
    building = selected_building()
    period = optional_choice("period", HISTORY_PERIODS, "today")
    category = optional_choice("category", CATEGORIES)
    analytics = get_analytics()
    report_date = analytics.get_kpis(building)["date"]

    return render_template(
        "history.html",
        page="history",
        building=building,
        period=period,
        periods=HISTORY_PERIODS,
        category=category,
        categories=CATEGORIES,
        alerts=presenter.alert_rows(analytics.get_alerts(building), report_date),
        weeks=presenter.week_rows(analytics.get_week_comparison(building)),
        report_day=report_date.isoformat(),
    )


@bp.route("/scenarios", methods=["GET", "POST"])
def scenarios():
    building = selected_building()
    form = ScenarioForm()
    rows = summary = None

    if form.validate_on_submit() or request.method == "GET":
        heating, lighting = form.heating_change.data, form.lighting_reduction.data
        result = get_analytics().estimate_scenario(building, heating, lighting)
        rows = presenter.scenario_rows(result)
        summary = presenter.scenario_summary(heating, lighting, result)

    status = 400 if form.errors else 200
    return render_template(
        "scenarios.html", page="scenarios", building=building, form=form, rows=rows, summary=summary,
    ), status


@bp.get("/coach")
def coach():
    building = selected_building()
    coach = get_coach()
    status = coach.status()
    return render_template(
        "coach.html",
        page="coach",
        building=building,
        tones=TONES,
        status=status,
        status_label=COACH_STATUSES[status],
        tips=coach.tips(building),
        max_length=MAX_QUESTION_LENGTH,
    )


@bp.route("/settings", methods=["GET", "POST"])
def settings():
    building = selected_building()
    analytics = get_analytics()
    form = ThresholdForm(data=analytics.get_limits(building))

    if form.validate_on_submit():
        analytics.save_limits(building, {name: form[name].data for name in CATEGORIES})
        flash("Limits saved for this session.", "success")
        return redirect(url_for("pages.settings", building=building))

    status = 400 if form.errors else 200
    return render_template("settings.html", page="settings", building=building, form=form), status
