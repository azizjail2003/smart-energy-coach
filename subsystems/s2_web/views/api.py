import re
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

from subsystems.s2_web import presenter
from subsystems.s2_web.catalog import (
    BUILDINGS, CATEGORIES, COACH_STATUSES, DEFAULT_BUILDING, MAX_QUESTION_LENGTH, PERIOD_DAYS, TIMEZONE, TONES,
)
from subsystems.s2_web.services import get_analytics, get_coach

bp = Blueprint("api", __name__, url_prefix="/api")

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ApiError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


@bp.errorhandler(ApiError)
def api_error(error):
    return jsonify(error={"code": error.code, "message": error.message}), 400


def query_choice(name, allowed, default=None, required=False):
    value = request.args.get(name)
    if value is None:
        if required:
            raise ApiError("missing_parameter", f"'{name}' is required.")
        return default
    if value not in allowed:
        raise ApiError("invalid_parameter", f"'{name}' must be one of: {', '.join(allowed)}.")
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
        raise ApiError("invalid_parameter", f"'{name}' must be a date in YYYY-MM-DD format.") from None


def building_context(analytics, building):
    kpis = analytics.get_kpis(building)
    return kpis, presenter.building_info(building, kpis["source"])


@bp.get("/kpis")
def kpis():
    building = query_choice("building", BUILDINGS, required=True)
    category = query_choice("category", CATEGORIES)
    analytics = get_analytics()
    kpis, info = building_context(analytics, building)
    trend = analytics.get_daily_trend(building, category=category)
    return jsonify(
        building=info,
        date=kpis["date"].isoformat(),
        category=category or "all",
        kpis=presenter.kpi_cards(kpis, category, trend),
    )


@bp.get("/score")
def score():
    building = query_choice("building", BUILDINGS, required=True)
    analytics = get_analytics()
    _, info = building_context(analytics, building)
    return jsonify(building=info, **presenter.score_payload(analytics.get_score(building)))


@bp.get("/hourly")
def hourly():
    building = query_choice("building", BUILDINGS, required=True)
    category = query_choice("category", CATEGORIES)
    compare = query_choice("compare", ("0", "1"), default="0") == "1"
    analytics = get_analytics()
    kpis, info = building_context(analytics, building)
    day = query_date("day", kpis["date"])

    try:
        points = analytics.get_hourly(building, day, category)
    except ValueError as error:
        raise ApiError("invalid_parameter", str(error)) from None

    comparison_day = day - timedelta(days=7)
    comparison = None
    if compare:
        try:
            comparison = analytics.get_hourly(building, comparison_day, category)
        except ValueError:
            comparison = None  # no fixture for that week; the chart shows only the selected day

    limit = analytics.get_limits(building)[category] if category else None
    label = "Today" if day == kpis["date"] else presenter.day_label(day)
    return jsonify(
        building=info,
        day=day.isoformat(),
        category=category or "all",
        unit="kWh",
        interval="1h",
        timestamps=[presenter.iso(moment) for moment, _ in points],
        comparison_day=comparison_day.isoformat() if comparison else None,
        limit_kwh=limit,
        chart=presenter.hourly_chart(points, label, comparison, "Last week", limit),
    )


@bp.get("/aggregates")
def aggregates():
    building = query_choice("building", BUILDINGS, required=True)
    period = query_choice("period", PERIOD_DAYS, default="week")
    analytics = get_analytics()
    kpis, info = building_context(analytics, building)

    end = kpis["date"]
    days = [end - timedelta(days=offset) for offset in range(PERIOD_DAYS[period] - 1, -1, -1)]
    rows = presenter.category_rows(analytics.get_aggregates(building, period))
    daily_chart = None
    if len(days) > 1:
        totals = []
        for day in days:
            readings = [kwh for _, kwh in analytics.get_hourly(building, day) if kwh is not None]
            totals.append((day, round(sum(readings), 1)))
        daily_chart = presenter.daily_chart(totals)

    return jsonify(
        building=info,
        period=period,
        start=days[0].isoformat(),
        end=end.isoformat(),
        unit="kWh",
        total_kwh=round(sum(row["kwh"] for row in rows), 1),
        categories=rows,
        chart=presenter.category_chart(rows),
        daily_chart=daily_chart,
    )


@bp.get("/alerts")
def alerts():
    building = query_choice("building", BUILDINGS, required=True)
    analytics = get_analytics()
    kpis, info = building_context(analytics, building)
    return jsonify(
        building=info,
        unit="kWh",
        limits_kwh=analytics.get_limits(building),
        alerts=presenter.alert_rows(analytics.get_alerts(building), kpis["date"]),
    )


@bp.post("/coach/ask")
def coach_ask():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ApiError("invalid_request", "Send a JSON object with 'question', 'tone' and 'building'.")

    question = payload.get("question")
    if not isinstance(question, str) or not question.strip():
        raise ApiError("invalid_parameter", "'question' must be a non-empty text.")
    question = question.strip()
    if len(question) > MAX_QUESTION_LENGTH:
        raise ApiError("invalid_parameter", f"'question' must be at most {MAX_QUESTION_LENGTH} characters.")

    tone = payload.get("tone")
    if not isinstance(tone, str) or tone not in TONES:
        raise ApiError("invalid_parameter", f"'tone' must be one of: {', '.join(TONES)}.")

    building = payload.get("building", DEFAULT_BUILDING)
    if not isinstance(building, str) or building not in BUILDINGS:
        raise ApiError("invalid_parameter", f"'building' must be one of: {', '.join(BUILDINGS)}.")

    result = get_coach().ask(question, tone, building)
    return jsonify(
        building=building,
        question=question,
        tone=tone,
        answer=result["answer"],
        source=result["source"],
        response_time_s=result["response_time_s"],
        answered_at=presenter.iso(datetime.now(TIMEZONE)),
    )


@bp.get("/coach/status")
def coach_status():
    status = get_coach().status()
    return jsonify(
        status=status,
        label=COACH_STATUSES[status],
        checked_at=presenter.iso(datetime.now(TIMEZONE)),
    )
