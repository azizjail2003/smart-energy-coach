from datetime import date, timedelta

import pytest

from app.services import mock_data
from app.services.analytics import MockAnalyticsService
from app.services.coach import MockAICoach

DEMO_DATE = date(2024, 5, 14)


@pytest.fixture
def analytics():
    return MockAnalyticsService(state={})


def daily_total(analytics, building, day):
    return round(sum(kwh for _, kwh in analytics.get_hourly(building, day)), 1)


def test_library_kpis_match_report(analytics):
    kpis = analytics.get_kpis("library")
    assert kpis["date"] == DEMO_DATE
    assert (kpis["energy_kwh"], kpis["co2_kg"], kpis["cost_eur"]) == (15.7, 6.0, 5.50)
    assert kpis["savings"] == {"eur": 0.35, "co2_kg": 1.0, "change_pct": -6}
    assert kpis["change_pct"] == -6


@pytest.mark.parametrize("building", mock_data.BUILDINGS)
def test_category_kpis_add_up_to_building_totals(analytics, building):
    kpis = analytics.get_kpis(building)
    for key, decimals in (("energy_kwh", 1), ("co2_kg", 1), ("cost_eur", 2)):
        total = sum(values[key] for values in kpis["by_category"].values())
        assert round(total, decimals) == kpis[key]


@pytest.mark.parametrize("building", mock_data.BUILDINGS)
def test_reference_score_follows_formula(building):
    score = mock_data.BUILDINGS[building]["score"]
    weighted = sum(weight * score[name] for name, weight in mock_data.SCORE_WEIGHTS.items())
    assert round(100 * weighted) == score["value"]


def test_library_score_and_live_variation(analytics):
    for _ in range(200):
        score = analytics.get_score("library")
        assert score["reference"] == 82
        assert score["target"] == 90
        assert 81.5 <= score["live"] <= 82.5
        assert score["measured_at"].tzinfo is not None
    assert score["components"] == {"energy": 0.86, "carbon": 0.81, "comfort": 0.78}


def test_library_hourly_profile(analytics):
    total = analytics.get_hourly("library", DEMO_DATE)
    heating = analytics.get_hourly("library", DEMO_DATE, "heating")
    assert len(total) == 24
    assert total[0][0].isoformat() == "2024-05-14T00:00:00+02:00"
    assert round(sum(kwh for _, kwh in total), 1) == 15.7
    assert max(heating, key=lambda point: point[1]) == (heating[13][0], 2.4)
    assert all(kwh <= 0.35 for _, kwh in total[:6])
    assert total[7][1] > total[6][1]
    assert total[19][1] < total[18][1]


def test_hourly_data_is_deterministic(analytics):
    day = DEMO_DATE - timedelta(days=3)
    assert analytics.get_hourly("lab-building", day) == analytics.get_hourly("lab-building", day)
    assert MockAnalyticsService().get_hourly("library", day, "servers") == analytics.get_hourly("library", day, "servers")


@pytest.mark.parametrize("building", mock_data.BUILDINGS)
def test_category_series_add_up_to_total(analytics, building):
    total = analytics.get_hourly(building, DEMO_DATE)
    parts = [analytics.get_hourly(building, DEMO_DATE, name) for name in ("heating", "lighting", "servers", "other")]
    for hour in range(24):
        assert round(sum(part[hour][1] for part in parts), 2) == total[hour][1]


@pytest.mark.parametrize("building", mock_data.BUILDINGS)
def test_daily_totals_match_weekly_figures(analytics, building):
    data = mock_data.BUILDINGS[building]
    this_week = [DEMO_DATE - timedelta(days=offset) for offset in range(7)]
    last_week = [day - timedelta(days=7) for day in this_week]
    assert round(sum(daily_total(analytics, building, day) for day in this_week), 1) == data["this_week"]["energy_kwh"]
    assert round(sum(daily_total(analytics, building, day) for day in last_week), 1) == data["last_week"]["energy_kwh"]
    assert round(sum(data["week_by_category_kwh"].values()), 1) == data["this_week"]["energy_kwh"]


def test_library_week_breakdown(analytics):
    week = analytics.get_aggregates("library")
    total = sum(week.values())
    assert round(total, 1) == 103.3
    shares = {name: round(kwh / total * 100) for name, kwh in week.items()}
    assert shares == {"heating": 48, "lighting": 20, "servers": 22, "other": 10}
    assert analytics.get_aggregates("library", "week", "servers") == {"servers": 22.7}


def test_library_week_comparison(analytics):
    weeks = analytics.get_week_comparison("library")
    assert weeks["last_week"] == {"energy_kwh": 109.9, "co2_kg": 41.8, "cost_eur": 38.50}
    assert weeks["this_week"] == {"energy_kwh": 103.3, "co2_kg": 39.3, "cost_eur": 36.15}


def test_library_reference_scenario(analytics):
    result = analytics.estimate_scenario("library", -1.0, 20)
    assert result["before"] == {"energy_kwh": 15.7, "co2_kg": 6.0, "cost_eur": 5.50, "score": 82}
    assert result["after"] == {"energy_kwh": 14.6, "co2_kg": 5.6, "cost_eur": 5.11, "score": 87}


def test_scenario_without_changes_keeps_values(analytics):
    result = analytics.estimate_scenario("library", 0, 0)
    assert result["after"] == result["before"]


def test_library_default_alerts(analytics):
    alerts = analytics.get_alerts("library")
    summary = [(alert["time"].strftime("%Y-%m-%d %H:%M"), alert["category"], alert["value_kwh"], alert["limit_kwh"])
               for alert in alerts]
    assert summary == [
        ("2024-05-14 13:00", "heating", 2.4, 2.0),
        ("2024-05-13 02:10", "servers", 3.8, 3.5),
        ("2024-05-06 18:40", "lighting", 1.1, 0.8),
    ]


def test_saved_limits_change_alerts_and_stay_per_building():
    state = {}
    analytics = MockAnalyticsService(state)
    analytics.save_limits("library", {"heating": 2.5, "lighting": 0.8, "servers": 3.5, "other": 0.5})

    reloaded = MockAnalyticsService(state)
    assert reloaded.get_limits("library")["heating"] == 2.5
    assert reloaded.get_limits("lab-building")["heating"] == 2.0
    categories = [alert["category"] for alert in reloaded.get_alerts("library", limit=50)]
    assert "heating" not in categories
    assert "other" in categories


def test_alert_count_is_limited(analytics):
    analytics.save_limits("library", {"heating": 0.1})
    assert len(analytics.get_alerts("library", limit=4)) == 4


def test_invalid_inputs_raise_value_error(analytics):
    with pytest.raises(ValueError):
        analytics.get_kpis("unknown")
    with pytest.raises(ValueError):
        analytics.get_hourly("library", date(2024, 1, 1))
    with pytest.raises(ValueError):
        analytics.get_aggregates("library", "year")
    with pytest.raises(ValueError):
        analytics.save_limits("library", {"cooling": 1.0})


def test_demo_buildings_do_not_copy_library_figures(analytics):
    library = analytics.get_kpis("library")
    for building in ("lecture-hall-a", "lab-building"):
        kpis = analytics.get_kpis(building)
        assert kpis["source"] == "demo"
        assert kpis["energy_kwh"] != library["energy_kwh"]
        assert analytics.get_aggregates(building) != analytics.get_aggregates("library")


def test_coach_reference_answer():
    coach = MockAICoach()
    answer = coach.ask("How can we reduce energy use in the afternoon?", "encouraging", "library")
    assert answer == {
        "answer": "Lower the heating by 1 °C between 13:00 and 17:00. This saves about 1.1 kWh per day (−7%) "
        "and keeps the rooms comfortable.",
        "source": "OpenAI",
        "response_time_s": 2.1,
    }
    assert coach.status() == "online"
    assert coach.tips("library") == [
        "Lower heating 1 °C, 13:00–17:00",
        "Turn off lab lights after 20:00",
        "Check server room at night",
    ]


def test_coach_topics_and_tones():
    coach = MockAICoach()
    assert "lights" in coach.ask("What about the lights?", "strict", "library")["answer"]
    assert "server room" in coach.ask("Servers at night?", "analytical", "library")["answer"]
    with pytest.raises(ValueError):
        coach.ask("Hello", "friendly", "library")


def test_coach_fallback_uses_backup_tip():
    answer = MockAICoach(status="fallback").ask("Anything?", "strict", "library")
    assert answer["source"] == "Backup tips"
    assert "Lower heating 1 °C" in answer["answer"]
    with pytest.raises(ValueError):
        MockAICoach(status="broken")
