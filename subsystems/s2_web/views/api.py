import re
from datetime import datetime

from flask import Blueprint, jsonify, request

from subsystems.s2_web.catalog import BUILDINGS, CATEGORIES, DEFAULT_BUILDING, PERIOD_DAYS, TIMEZONE
from subsystems.s2_web.errors import InvalidInputError
from subsystems.s2_web.presenter import iso
from subsystems.s2_web.services import get_coach_view, get_page_view

bp = Blueprint("api", __name__, url_prefix="/api")

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def query_choice(name, allowed, default=None, required=False):
    value = request.args.get(name)
    if value is None:
        if required:
            raise InvalidInputError(f"'{name}' is required.", code="missing_parameter")
        return default
    if value not in allowed:
        raise InvalidInputError(f"'{name}' must be one of: {', '.join(allowed)}.")
    return value


def query_date(name, default):
    value = request.args.get(name)
    if value is None:
        return default
    try:
        if not DATE_PATTERN.match(value):
            raise ValueError
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise InvalidInputError(f"'{name}' must be a date in YYYY-MM-DD format.") from None


@bp.get("/kpis")
def kpis():
    building = query_choice("building", BUILDINGS, required=True)
    category = query_choice("category", CATEGORIES)
    return jsonify(get_page_view().api_kpis(building, category))


@bp.get("/score")
def score():
    building = query_choice("building", BUILDINGS, required=True)
    return jsonify(get_page_view().api_score(building))


@bp.get("/hourly")
def hourly():
    building = query_choice("building", BUILDINGS, required=True)
    category = query_choice("category", CATEGORIES)
    compare = query_choice("compare", ("0", "1"), default="0") == "1"
    day = query_date("day", None)
    try:
        return jsonify(get_page_view().api_hourly(building, day, category, compare))
    except ValueError as error:
        raise InvalidInputError(str(error)) from None


@bp.get("/aggregates")
def aggregates():
    building = query_choice("building", BUILDINGS, required=True)
    period = query_choice("period", PERIOD_DAYS, default="week")
    return jsonify(get_page_view().api_aggregates(building, period))


@bp.get("/alerts")
def alerts():
    building = query_choice("building", BUILDINGS, required=True)
    return jsonify(get_page_view().api_alerts(building))


@bp.post("/coach/ask")
def coach_ask():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise InvalidInputError("Send a JSON object with 'question', 'tone' and 'building'.", code="invalid_request")

    try:
        result = get_coach_view().ask(
            payload.get("question"), payload.get("tone"), payload.get("building", DEFAULT_BUILDING),
        )
    except ValueError as error:
        raise InvalidInputError(str(error)) from None
    return jsonify(**result, answered_at=iso(datetime.now(TIMEZONE)))


@bp.get("/coach/status")
def coach_status():
    return jsonify(**get_coach_view().status(), checked_at=iso(datetime.now(TIMEZONE)))
