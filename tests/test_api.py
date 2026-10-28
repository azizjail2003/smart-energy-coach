import pytest


def assert_error(response, code):
    assert response.status_code == 400
    error = response.get_json()["error"]
    assert error["code"] == code
    assert error["message"]


def test_kpis_for_library(client):
    data = client.get("/api/kpis?building=library").get_json()
    assert data["building"] == {"id": "library", "name": "Library", "data": "reference"}
    assert data["date"] == "2024-05-14"
    assert data["category"] == "all"
    kpis = data["kpis"]
    assert (kpis["energy"]["display"], kpis["co2"]["display"], kpis["cost"]["display"]) == ("15.7", "6.0", "€5.50")
    assert kpis["energy"]["unit"] == "kWh"
    assert kpis["energy"]["change_pct"] == -6
    assert kpis["savings"]["display"] == "€0.35"
    assert kpis["savings"]["co2_display"] == "1.0"
    assert kpis["savings"]["scope"] == "building"


def test_kpis_for_category_keep_savings_building_wide(client):
    kpis = client.get("/api/kpis?building=library&category=heating").get_json()["kpis"]
    assert kpis["energy"]["value"] == 7.5
    assert kpis["cost"]["display"] == "€2.62"
    assert kpis["savings"]["value"] == 0.35
    assert kpis["savings"]["scope"] == "building"


def test_score(client):
    data = client.get("/api/score?building=library").get_json()
    assert data["label"] == "Building score"
    assert data["scope"] == "building"
    assert data["reference_score"] == 82
    assert 81.5 <= data["score"] <= 82.5
    assert data["display"] == f"{data['score']:.1f}"
    assert data["target"] == 90
    assert data["components"]["energy"] == {"value": 0.86, "display": "0.86", "weight": 0.4}
    assert data["measured_at"].endswith(("+01:00", "+02:00"))


def test_hourly_with_comparison_and_limit(client):
    data = client.get("/api/hourly?building=library&day=2024-05-14&category=heating&compare=1").get_json()
    assert data["day"] == "2024-05-14"
    assert data["comparison_day"] == "2024-05-07"
    assert data["unit"] == "kWh"
    assert data["limit_kwh"] == 2.0
    assert len(data["timestamps"]) == 24
    chart = data["chart"]
    assert chart["labels"][13] == "13:00"
    assert [dataset["key"] for dataset in chart["datasets"]] == ["primary", "comparison"]
    assert chart["datasets"][0]["data"][13] == 2.4
    assert chart["limit"] == {"value": 2.0, "label": "Limit: 2.0 kWh"}
    assert chart["above_limit"] == [13]
    assert "Peak 2.40 kWh at 13:00" in chart["summary"]


def test_hourly_defaults(client):
    data = client.get("/api/hourly?building=library").get_json()
    assert data["day"] == "2024-05-14"
    assert data["category"] == "all"
    assert data["limit_kwh"] is None
    assert data["comparison_day"] is None
    assert len(data["chart"]["datasets"]) == 1


def test_hourly_comparison_outside_fixtures_is_omitted(client):
    data = client.get("/api/hourly?building=library&day=2024-04-16&compare=1").get_json()
    assert data["comparison_day"] is None
    assert len(data["chart"]["datasets"]) == 1


def test_aggregates_week(client):
    data = client.get("/api/aggregates?building=library").get_json()
    assert data["period"] == "week"
    assert (data["start"], data["end"]) == ("2024-05-08", "2024-05-14")
    assert data["total_kwh"] == 103.3
    assert [(row["id"], row["share_pct"]) for row in data["categories"]] == [
        ("heating", 48), ("lighting", 20), ("servers", 22), ("other", 10),
    ]
    assert data["chart"]["datasets"][0]["data"] == [48, 20, 22, 10]
    assert sum(data["daily_chart"]["datasets"][0]["data"]) == pytest.approx(103.3)


def test_aggregates_periods(client):
    today = client.get("/api/aggregates?building=library&period=today").get_json()
    assert today["total_kwh"] == 15.7
    assert today["daily_chart"] is None
    month = client.get("/api/aggregates?building=lab-building&period=30d").get_json()
    assert month["building"]["data"] == "demo"
    assert len(month["daily_chart"]["labels"]) == 30
    assert month["start"] == "2024-04-15"


def test_alerts(client):
    data = client.get("/api/alerts?building=library").get_json()
    assert data["limits_kwh"] == {"heating": 2.0, "lighting": 0.8, "servers": 3.5, "other": 1.0}
    first = data["alerts"][0]
    assert first["time"] == "2024-05-14T13:00:00+02:00"
    assert first["time_label"] == "Today 13:00"
    assert first["message"] == "Heating above limit: 2.4 kWh"
    assert [alert["time_label"] for alert in data["alerts"]] == ["Today 13:00", "Yesterday 02:10", "Mon 6 May, 18:40"]


@pytest.mark.parametrize("url, code", [
    ("/api/kpis", "missing_parameter"),
    ("/api/kpis?building=mensa", "invalid_parameter"),
    ("/api/kpis?building=library&category=cooling", "invalid_parameter"),
    ("/api/score?building=", "invalid_parameter"),
    ("/api/hourly?building=library&day=14.05.2024", "invalid_parameter"),
    ("/api/hourly?building=library&day=2024-5-14", "invalid_parameter"),
    ("/api/hourly?building=library&day=2024-02-30", "invalid_parameter"),
    ("/api/hourly?building=library&day=2023-01-01", "invalid_parameter"),
    ("/api/hourly?building=library&compare=yes", "invalid_parameter"),
    ("/api/aggregates?building=library&period=year", "invalid_parameter"),
    ("/api/alerts", "missing_parameter"),
])
def test_invalid_query_parameters(client, url, code):
    assert_error(client.get(url), code)


def test_unknown_api_route_returns_json(client):
    response = client.get("/api/unknown")
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "not_found"


def test_coach_status(client):
    data = client.get("/api/coach/status").get_json()
    assert (data["status"], data["label"]) == ("online", "Online")
    assert data["checked_at"]


def test_coach_ask(client, csrf_token):
    response = client.post(
        "/api/coach/ask",
        json={"question": "  How can we reduce energy use in the afternoon?  ", "tone": "encouraging", "building": "library"},
        headers={"X-CSRFToken": csrf_token},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["question"] == "How can we reduce energy use in the afternoon?"
    assert data["answer"].startswith("Lower the heating by 1 °C between 13:00 and 17:00.")
    assert (data["source"], data["response_time_s"], data["building"]) == ("OpenAI", 2.1, "library")


def test_coach_ask_requires_csrf_token(client):
    response = client.post("/api/coach/ask", json={"question": "Hi", "tone": "strict", "building": "library"})
    assert_error(response, "csrf_failed")


@pytest.mark.parametrize("payload", [
    {"tone": "strict"},
    {"question": "   ", "tone": "strict"},
    {"question": "x" * 501, "tone": "strict"},
    {"question": 42, "tone": "strict"},
    {"question": "Hi", "tone": "friendly"},
    {"question": "Hi", "tone": ["strict"]},
    {"question": "Hi", "tone": "strict", "building": "mensa"},
])
def test_coach_ask_rejects_invalid_payloads(client, csrf_token, payload):
    response = client.post("/api/coach/ask", json=payload, headers={"X-CSRFToken": csrf_token})
    assert_error(response, "invalid_parameter")


def test_coach_ask_rejects_non_json(client, csrf_token):
    response = client.post("/api/coach/ask", data="question=Hi", headers={"X-CSRFToken": csrf_token},
                           content_type="application/x-www-form-urlencoded")
    assert_error(response, "invalid_request")
