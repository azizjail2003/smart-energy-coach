import os

from flask import Flask, jsonify, render_template, request, session
from flask_wtf.csrf import CSRFError, CSRFProtect
from werkzeug.exceptions import HTTPException

from subsystems.s2_web.catalog import APP_VERSION, BUILDINGS, COACH_STATUSES, DEFAULT_BUILDING
from subsystems.s2_web.services import get_analytics

csrf = CSRFProtect()

ERROR_PAGES = {
    400: ("Invalid request", "The request could not be processed. Check the address or the form and try again."),
    404: ("Page not found", "The page you are looking for does not exist or has been moved."),
    405: ("Method not allowed", "This address does not support that kind of request."),
    500: ("Something went wrong", "The server could not complete the request. Try again in a moment."),
}
ERROR_CODES = {400: "bad_request", 404: "not_found", 405: "method_not_allowed", 500: "server_error"}


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

    register_error_handlers(app)

    @app.context_processor
    def layout_context():
        building = session.get("building", DEFAULT_BUILDING)
        if building not in BUILDINGS:
            building = DEFAULT_BUILDING
        kpis = get_analytics().get_kpis(building)
        report_date = kpis["date"]
        return {
            "app_version": APP_VERSION,
            "buildings": BUILDINGS,
            "current_building": building,
            "building_source": kpis["source"],
            "report_date": report_date,
            "report_date_display": f"{report_date:%a}, {report_date.day} {report_date:%B %Y}",
        }

    return app


def error_response(status, code, message, title=None):
    if request.path.startswith("/api/"):
        return jsonify(error={"code": code, "message": message}), status
    title = title or ERROR_PAGES.get(status, ERROR_PAGES[500])[0]
    return render_template("error.html", status=status, title=title, message=message), status


def register_error_handlers(app):
    @app.errorhandler(CSRFError)
    def csrf_error(error):
        return error_response(
            400, "csrf_failed", "The security token is missing or invalid. Reload the page and try again.",
            title="Form expired",
        )

    @app.errorhandler(HTTPException)
    def http_error(error):
        title, message = ERROR_PAGES.get(error.code, (error.name, error.description))
        # abort(400, description=...) passes a specific reason; keep it instead of the generic text.
        if error.description != type(error).description:
            message = error.description
        return error_response(error.code, ERROR_CODES.get(error.code, "http_error"), message, title)

    @app.errorhandler(Exception)
    def unexpected_error(error):
        app.logger.exception("Unhandled error")
        return error_response(500, "server_error", ERROR_PAGES[500][1])
