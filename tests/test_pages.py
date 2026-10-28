from pathlib import Path

import pytest

from app import create_app

PAGES = ["/", "/history", "/scenarios", "/coach", "/settings"]


@pytest.mark.parametrize("path", PAGES)
@pytest.mark.parametrize("building", ["library", "lecture-hall-a", "lab-building"])
def test_pages_respond(client, path, building):
    response = client.get(f"{path}?building={building}")
    assert response.status_code == 200
    assert b'name="csrf-token"' in response.data


def test_dashboard_shows_reference_figures(client):
    html = client.get("/").get_data(as_text=True)
    for text in ("15.7", "6.0", "€5.50", "€0.35", "Heating is above the limit at 13:00.", "Target:</dt><dd>90"):
        assert text in html
    assert '<span data-score-value>82</span> / 100' in html
    assert "Lower the heating by 1 °C between 13:00 and 17:00." in html


def test_history_shows_alerts_and_week_comparison(client):
    html = client.get("/history?period=7d").get_data(as_text=True)
    for text in ("Today 13:00", "Yesterday 02:10", "Mon 6 May, 18:40", "109.9", "103.3", "38.50", "36.15", "−6%"):
        assert text in html


def test_building_choice_is_remembered(client):
    client.get("/?building=lab-building")
    html = client.get("/history").get_data(as_text=True)
    assert '<option value="lab-building" selected>' in html
    assert "demonstration data" in html


@pytest.mark.parametrize("url", ["/?building=mensa", "/?category=cooling", "/history?period=year"])
def test_invalid_page_parameters(client, url):
    response = client.get(url)
    assert response.status_code == 400
    assert b"Invalid request" in response.data


def test_not_found_page(client):
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    assert b"Page not found" in response.data
    assert b"Go to dashboard" in response.data


def test_scenario_reference_values(client, csrf_token):
    response = client.post("/scenarios", data={"csrf_token": csrf_token, "heating_change": "-1", "lighting_reduction": "20"})
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    for text in ("14.6", "5.6", "5.11", "87", "−1.1 (−7%)", "−0.39 (−7%)", "+5"):
        assert text in html
    assert "could save about 1.1 kWh per day (−7%) and increase the score to 87." in html


@pytest.mark.parametrize("heating, lighting, message", [
    ("-0.7", "20", "Use steps of 0.5."),
    ("-4", "20", "Enter a value from −3 to +3 °C."),
    ("", "20", "Enter a heating change."),
    ("nan", "20", "Enter a number."),
    ("-1", "55", "Enter a value from 0 to 50%."),
    ("-1", "12", "Use steps of 5."),
])
def test_scenario_validation(client, csrf_token, heating, lighting, message):
    response = client.post("/scenarios", data={"csrf_token": csrf_token, "heating_change": heating, "lighting_reduction": lighting})
    assert response.status_code == 400
    assert message in response.get_data(as_text=True)
    assert 'aria-invalid="true"' in response.get_data(as_text=True)


def test_settings_save_limits_for_session(client, csrf_token):
    limits = {"heating": "2.5", "lighting": "0.8", "servers": "3.5", "other": "1.0"}
    response = client.post("/settings", data={"csrf_token": csrf_token, **limits}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Limits saved for this session." in response.data
    assert b'value="2.5"' in response.data

    alerts = client.get("/api/alerts?building=library").get_json()
    assert alerts["limits_kwh"]["heating"] == 2.5
    assert all(alert["category"] != "heating" for alert in alerts["alerts"])


def test_settings_limits_survive_a_new_app_instance(client, csrf_token):
    limits = {"heating": "1.5", "lighting": "0.8", "servers": "3.5", "other": "1.0"}
    client.post("/settings", data={"csrf_token": csrf_token, **limits})
    cookie = client.get_cookie("session").value

    # A second app with the same secret key stands in for another Gunicorn worker.
    other_worker = create_app({"TESTING": True, "SECRET_KEY": "test-secret"}).test_client()
    other_worker.set_cookie("session", cookie)
    assert other_worker.get("/api/alerts?building=library").get_json()["limits_kwh"]["heating"] == 1.5


def test_settings_validation(client, csrf_token):
    response = client.post("/settings", data={"csrf_token": csrf_token, "heating": "", "lighting": "0.85",
                                              "servers": "25", "other": "1"})
    html = response.get_data(as_text=True)
    assert response.status_code == 400
    for text in ("Enter a limit for heating.", "Use steps of 0.1.", "Enter a value from 0.1 to 20 kWh/h.", "Limits not saved."):
        assert text in html
    assert client.get("/api/alerts?building=library").get_json()["limits_kwh"]["heating"] == 2.0


@pytest.mark.parametrize("path", ["/settings", "/scenarios"])
def test_forms_reject_missing_csrf_token(client, path):
    response = client.post(path, data={"heating": "2.0", "lighting": "0.8", "servers": "3.5", "other": "1.0",
                                       "heating_change": "-1", "lighting_reduction": "20"})
    assert response.status_code == 400
    assert b"Form expired" in response.data


def test_forms_reject_wrong_csrf_token(client):
    response = client.post("/settings", data={"csrf_token": "forged", "heating": "2.0", "lighting": "0.8",
                                              "servers": "3.5", "other": "1.0"})
    assert response.status_code == 400


def test_server_errors_hide_details():
    app = create_app({"SECRET_KEY": "test-secret"})

    @app.get("/boom")
    def boom():
        raise RuntimeError("secret internal detail")

    response = app.test_client().get("/boom")
    assert response.status_code == 500
    assert b"Something went wrong" in response.data
    assert b"secret internal detail" not in response.data
    assert b"Traceback" not in response.data


def test_debug_is_off_by_default(app, monkeypatch):
    assert app.debug is False


def test_secret_key_is_required(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app()


def test_use_mock_false_needs_adapters(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "x")
    monkeypatch.setenv("USE_MOCK", "false")
    with pytest.raises(RuntimeError, match="USE_MOCK"):
        create_app()


def test_views_do_not_import_mock_data():
    views = Path(__file__).resolve().parent.parent / "app" / "views"
    for source in views.glob("*.py"):
        assert "mock_data" not in source.read_text(), source.name
