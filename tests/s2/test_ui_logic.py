import re
from datetime import date

import pytest

from subsystems.s2_web import presenter


def path_points(path):
    """All x,y pairs in an SVG path string."""
    return [(float(x), float(y)) for x, y in re.findall(r"(-?[\d.]+),(-?[\d.]+)", path)]


def test_sparkline_spans_the_box_and_marks_today():
    spark = presenter.sparkline([1, 3, 2, 5], ["a", "b", "c", "d"], str)
    points = path_points(spark["line"])
    assert points[0] == (0.0, 38.0)  # lowest value at the bottom padding
    assert points[-1] == (192.0, 6.0)  # highest value at the top padding, 8 units before the edge
    assert (spark["end_x"], spark["end_y"]) == (96.0, round(6 / 44 * 100, 2))
    assert spark["area"].startswith(spark["line"])
    assert spark["area"].endswith("L192.0,44 L0,44 Z")


def test_sparkline_with_flat_values_stays_inside_the_box():
    spark = presenter.sparkline([4, 4, 4], ["a", "b", "c"], str)
    for x, y in path_points(spark["line"]):
        assert 0 <= x <= 200 and 0 <= y <= 44


def test_sparkline_label_lists_every_day_with_its_unit():
    spark = presenter.sparkline([5.5, 5.11], ["Mon 13 May", "Tue 14 May"], presenter.euro)
    assert spark["label"] == "Last 2 days: Mon 13 May €5.50, Tue 14 May €5.11"


def test_kpi_cards_include_a_sparkline_per_card():
    kpis = {
        "energy_kwh": 15.7, "co2_kg": 6.0, "cost_eur": 5.5, "change_pct": -6,
        "savings": {"eur": 0.35, "co2_kg": 1.0, "change_pct": -6}, "by_category": {},
    }
    trend = [
        {"date": date(2024, 5, 13), "energy_kwh": 17.6, "co2_kg": 6.69, "cost_eur": 6.16, "savings_eur": 0.0},
        {"date": date(2024, 5, 14), "energy_kwh": 15.7, "co2_kg": 6.0, "cost_eur": 5.5, "savings_eur": 0.35},
    ]
    cards = presenter.kpi_cards(kpis, trend=trend)
    assert set(cards) == {"energy", "co2", "cost", "savings"}
    assert cards["energy"]["spark"]["label"].endswith("Tue 14 May 15.7 kWh")
    assert cards["savings"]["spark"]["label"].endswith("Tue 14 May €0.35")
    assert "spark" not in presenter.kpi_cards(kpis)["energy"]


@pytest.mark.parametrize("value, band", [
    (0, "red"), (59.9, "red"), (60, "amber"), (80, "amber"), (80.1, "green"), (100, "green"),
])
def test_score_band_follows_report_thresholds(value, band):
    assert presenter.score_band(value)["band"] == band


def test_score_band_needle_spans_the_half_circle():
    assert presenter.score_band(0)["needle_deg"] == -90
    assert presenter.score_band(50)["needle_deg"] == 0
    assert presenter.score_band(100)["needle_deg"] == 90
    assert presenter.score_band(130)["needle_deg"] == 90  # clamped to the dial


def test_money_keeps_the_sign_in_front():
    assert presenter.money(2.35) == "€2.35"
    assert presenter.money(-0.2) == "−€0.20"
    assert presenter.money(-0.001) == "€0.00"


def test_week_savings_compare_with_last_week():
    weeks = {
        "last_week": {"energy_kwh": 109.9, "co2_kg": 41.8, "cost_eur": 38.50},
        "this_week": {"energy_kwh": 103.3, "co2_kg": 39.3, "cost_eur": 36.15},
    }
    assert presenter.week_savings(weeks) == {
        "eur": 2.35, "co2_kg": 2.5, "display": "€2.35", "co2_display": "2.5", "negative": False,
    }
    worse = {"last_week": weeks["this_week"], "this_week": weeks["last_week"]}
    assert presenter.week_savings(worse)["display"] == "−€2.35"
    assert presenter.week_savings(worse)["negative"] is True


def test_score_and_parts_carry_tooltip_text():
    from datetime import datetime, timezone
    score = {
        "live": 82.1, "reference": 82, "target": 90,
        "weights": {"energy": 0.40, "carbon": 0.35, "comfort": 0.25},
        "components": {"energy": 0.86, "carbon": 0.81, "comfort": 0.78},
        "measured_at": datetime(2024, 5, 14, 12, 0, tzinfo=timezone.utc),
    }
    payload = presenter.score_payload(score)
    assert "Red below 60" in payload["help"]
    assert payload["components"]["energy"]["help"].startswith("E, weight 0.40")
    assert payload["components"]["carbon"]["help"].startswith("C, weight 0.35")
    assert payload["components"]["comfort"]["help"].startswith("K, weight 0.25")


def test_co2_card_explains_the_factor():
    kpis = {
        "energy_kwh": 15.7, "co2_kg": 6.0, "cost_eur": 5.5, "change_pct": -6,
        "savings": {"eur": 0.35, "co2_kg": 1.0, "change_pct": -6}, "by_category": {},
    }
    assert "0.38 kg CO₂ per kWh" in presenter.kpi_cards(kpis)["co2"]["help"]
