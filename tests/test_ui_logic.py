import re
from datetime import date

from app import presenter


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
