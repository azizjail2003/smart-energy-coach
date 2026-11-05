"""Error handling in S2 (Homework Assignment 4): the error classes and how the app answers each error."""
import pytest

from subsystems.s2_web import create_app
from subsystems.s2_web.errors import ErrorHandler, InvalidInputError, S2Error, ServiceUnavailableError
from subsystems.s2_web.services.analytics import MockAnalyticsService
from subsystems.s2_web.services.coach import MockAICoach


def s1_is_down(*args, **kwargs):
    raise ServiceUnavailableError("The analytics service (S1) did not answer.")


def s3_is_down(*args, **kwargs):
    raise ServiceUnavailableError("The AI coach (S3) did not answer.")


# -- The error classes ---------------------------------------------------------------

def test_errors_share_one_base_class():
    assert issubclass(InvalidInputError, S2Error)
    assert issubclass(ServiceUnavailableError, S2Error)
    assert issubclass(S2Error, Exception)


def test_each_error_has_its_status_and_code():
    assert (InvalidInputError("x").status, InvalidInputError("x").code) == (400, "invalid_parameter")
    assert (ServiceUnavailableError("x").status, ServiceUnavailableError("x").code) == (503, "service_unavailable")


def test_error_keeps_its_message_and_accepts_a_specific_code():
    error = InvalidInputError("'building' is required.", code="missing_parameter")
    assert error.message == str(error) == "'building' is required."
    assert error.code == "missing_parameter"


def test_one_except_catches_every_s2_error():
    for error in (InvalidInputError("bad input"), ServiceUnavailableError("S1 is down")):
        with pytest.raises(S2Error):
            raise error


def test_error_handler_is_registered_on_the_app(app):
    assert isinstance(ErrorHandler(), ErrorHandler)
    assert S2Error in app.error_handler_spec[None][None]


# -- Invalid input: 400 --------------------------------------------------------------

def test_missing_parameter_returns_400(client):
    response = client.get("/api/kpis")
    assert response.status_code == 400
    assert response.get_json() == {"error": {"code": "missing_parameter", "message": "'building' is required."}}


def test_unknown_building_returns_400(client):
    response = client.get("/api/kpis?building=mensa")
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_parameter"


def test_bad_date_returns_400(client):
    response = client.get("/api/hourly?building=library&day=14.05.2024")
    assert response.status_code == 400
    assert response.get_json()["error"]["message"] == "'day' must be a date in YYYY-MM-DD format."


def test_unknown_building_on_a_page_shows_the_error_page(client):
    response = client.get("/?building=mensa")
    assert response.status_code == 400
    assert b"Unknown building &#39;mensa&#39;." in response.data
    assert b"Go to dashboard" in response.data


def test_form_without_security_token_returns_400(client):
    response = client.post("/settings", data={"heating": "2.0"})
    assert response.status_code == 400
    assert b"Form expired" in response.data


# -- Wrong address or method: 404 and 405 ------------------------------------------

def test_unknown_page_returns_404(client):
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    assert b"Page not found" in response.data


def test_wrong_method_returns_405(client):
    response = client.get("/api/coach/ask")
    assert response.status_code == 405
    assert response.get_json()["error"]["code"] == "method_not_allowed"


# -- Unexpected crash: 500 without details -----------------------------------------

def test_crash_shows_a_friendly_page_without_details():
    app = create_app({"SECRET_KEY": "test-secret"})

    @app.get("/boom")
    def boom():
        raise RuntimeError("secret internal detail")

    response = app.test_client().get("/boom")
    assert response.status_code == 500
    assert b"Something went wrong" in response.data
    assert b"secret internal detail" not in response.data
    assert b"Traceback" not in response.data


# -- Another subsystem is down: 503 -------------------------------------------------

def test_analytics_down_returns_503(client, monkeypatch):
    monkeypatch.setattr(MockAnalyticsService, "get_kpis", s1_is_down)
    api = client.get("/api/kpis?building=library")
    assert api.status_code == 503
    assert api.get_json()["error"] == {
        "code": "service_unavailable", "message": "The analytics service (S1) did not answer.",
    }
    page = client.get("/")
    assert page.status_code == 503
    assert b"Service unavailable" in page.data


def test_ai_coach_down_returns_503(client, monkeypatch):
    monkeypatch.setattr(MockAICoach, "ask", s3_is_down)
    html = client.get("/coach").get_data(as_text=True)
    token = html.split('name="csrf-token" content="')[1].split('"')[0]
    response = client.post(
        "/api/coach/ask",
        json={"question": "How can we save energy?", "tone": "strict", "building": "library"},
        headers={"X-CSRFToken": token},
    )
    assert response.status_code == 503
    assert response.get_json()["error"]["message"] == "The AI coach (S3) did not answer."
