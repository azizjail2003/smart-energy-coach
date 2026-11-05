"""Error handling for the S2 web interface.

S2 raises its own exceptions, all based on S2Error. The ErrorHandler class
catches them, and any other failure, and answers with a friendly page or a
JSON error message. Users never see a stack trace.
"""
from flask import jsonify, render_template, request
from flask_wtf.csrf import CSRFError
from werkzeug.exceptions import HTTPException


class S2Error(Exception):
    """Base class for every error that S2 raises on purpose."""

    status = 500
    code = "server_error"

    def __init__(self, message, code=None):
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code


class InvalidInputError(S2Error):
    """The user sent a value S2 cannot use, such as an unknown building or a bad date."""

    status = 400
    code = "invalid_parameter"


class ServiceUnavailableError(S2Error):
    """S1 (analytics) or S3 (AI coach) did not answer."""

    status = 503
    code = "service_unavailable"


class ErrorHandler:
    """Turns errors into a friendly HTML page, or a JSON message for /api/ requests."""

    PAGES = {
        400: ("Invalid request", "The request could not be processed. Check the address or the form and try again."),
        404: ("Page not found", "The page you are looking for does not exist or has been moved."),
        405: ("Method not allowed", "This address does not support that kind of request."),
        500: ("Something went wrong", "The server could not complete the request. Try again in a moment."),
        503: ("Service unavailable", "Part of the system is not responding. Try again in a moment."),
    }
    CODES = {400: "bad_request", 404: "not_found", 405: "method_not_allowed", 500: "server_error"}

    def __init__(self, app=None):
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """Register one Flask handler per kind of error."""
        app.register_error_handler(S2Error, self.handle_s2_error)
        app.register_error_handler(CSRFError, self.handle_csrf_error)
        app.register_error_handler(HTTPException, self.handle_http_error)
        app.register_error_handler(Exception, self.handle_unexpected_error)
        self.logger = app.logger

    def respond(self, status, code, message, title=None):
        """JSON for the API, the error page for everything else."""
        if request.path.startswith("/api/"):
            return jsonify(error={"code": code, "message": message}), status
        title = title or self.PAGES.get(status, self.PAGES[500])[0]
        return render_template("error.html", status=status, title=title, message=message), status

    def handle_s2_error(self, error):
        if error.status >= 500:
            self.logger.error("%s: %s", type(error).__name__, error.message)
        return self.respond(error.status, error.code, error.message)

    def handle_csrf_error(self, error):
        return self.respond(
            400, "csrf_failed", "The security token is missing or invalid. Reload the page and try again.",
            title="Form expired",
        )

    def handle_http_error(self, error):
        title, message = self.PAGES.get(error.code, (error.name, error.description))
        return self.respond(error.code, self.CODES.get(error.code, "http_error"), message, title)

    def handle_unexpected_error(self, error):
        # Log the details for the team, but show the user only a general message.
        self.logger.exception("Unhandled error")
        return self.respond(500, "server_error", self.PAGES[500][1])
