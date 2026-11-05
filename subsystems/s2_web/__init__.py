import os

from flask import Flask, session
from flask_wtf.csrf import CSRFProtect

from subsystems.s2_web.catalog import APP_VERSION, BUILDINGS, COACH_STATUSES, DEFAULT_BUILDING
from subsystems.s2_web.errors import ErrorHandler, ServiceUnavailableError
from subsystems.s2_web.services import get_analytics

csrf = CSRFProtect()


def env_flag(name, default):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY"),
        DEBUG=env_flag("FLASK_DEBUG", False),
        USE_MOCK=env_flag("USE_MOCK", True),
        COACH_STATUS=os.environ.get("MOCK_COACH_STATUS", "online"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        # The token stays valid for the whole browser session, so a dashboard left open can still post.
        WTF_CSRF_TIME_LIMIT=None,
    )
    if test_config:
        app.config.update(test_config)

    if not app.config["SECRET_KEY"]:
        raise RuntimeError("SECRET_KEY is not set. Export a long random value before starting the app.")
    if not app.config["USE_MOCK"]:
        raise RuntimeError(
            "USE_MOCK is false, but no adapters for the real S1 and S3 services exist yet. "
            "Set USE_MOCK=true or add the adapters in subsystems/s2_web/services/__init__.py."
        )
    if app.config["COACH_STATUS"] not in COACH_STATUSES:
        raise RuntimeError(f"MOCK_COACH_STATUS must be one of: {', '.join(COACH_STATUSES)}.")

    app.json.sort_keys = False
    csrf.init_app(app)

    from subsystems.s2_web.views import api, pages
    app.register_blueprint(pages.bp)
    app.register_blueprint(api.bp)

    ErrorHandler(app)

    @app.context_processor
    def layout_context():
        building = session.get("building", DEFAULT_BUILDING)
        if building not in BUILDINGS:
            building = DEFAULT_BUILDING
        context = {"app_version": APP_VERSION, "buildings": BUILDINGS, "current_building": building,
                   "building_source": None, "report_date": None, "report_date_display": ""}
        try:
            kpis = get_analytics().get_kpis(building)
        except (ServiceUnavailableError, ConnectionError, TimeoutError):
            return context  # the error page still renders while S1 is down, just without the date
        report_date = kpis["date"]
        context.update(
            building_source=kpis["source"],
            report_date=report_date,
            report_date_display=f"{report_date:%a}, {report_date.day} {report_date:%B %Y}",
        )
        return context

    return app
