"""Unit tests for Subsystem 1: Energy Simulation and Analytics."""

from datetime import datetime
import time

import pytest

from subsystems.s1_analytics import (
    AnalyticsService,
    EnergyReading,
    EnergySimulator,
    ScoreCalculator,
)


def test_co2_and_cost_calculation():
    calculator = ScoreCalculator()

    assert calculator.calc_co2(10.0) == 3.8
    assert calculator.calc_cost(10.0) == 3.5
    assert calculator.calc_co2(0.0) == 0.0
    assert calculator.calc_cost(0.0) == 0.0


def test_comfort_score_at_ideal_temp():
    calculator = ScoreCalculator()

    assert calculator.calc_comfort(21.0) == 1.0
    assert calculator.calc_comfort(26.0) == 0.5
    assert calculator.calc_comfort(16.0) == 0.5
    assert calculator.calc_comfort(35.0) == 0.0

    result = calculator.calc_sustainability_score(2.0, 21.0)
    assert 0 <= result["score"] <= 100
    assert {"score", "E", "C", "K"} <= result.keys()


def test_reading_validation_rejects_negative_kwh():
    def reading(**overrides):
        values = {
            "timestamp": "2026-10-28 14:30",
            "device_type": "Lighting",
            "kwh": 1.0,
            "room_temp": 21.0,
            "co2_kg": 0.38,
            "sustainability_score": 80,
        }
        values.update(overrides)
        return EnergyReading(**values)

    with pytest.raises(ValueError):
        reading(kwh=-5.0).validate()
    with pytest.raises(ValueError):
        reading(room_temp=50.0).validate()
    with pytest.raises(ValueError):
        reading(room_temp=-2.0).validate()
    with pytest.raises(ValueError):
        reading(device_type="Toaster").validate()


def test_scenario_reduces_energy_when_heating_lowered(tmp_path):
    service = AnalyticsService(str(tmp_path / "scenario.db"))
    service.seed_if_empty(days=14)
    summary = service.get_dashboard_summary()

    result = service.simulate_scenario(
        summary, heating_delta_c=-1.0, light_reduction_pct=20.0
    )

    assert result["after_kwh"] < result["before_kwh"]
    assert result["after_cost"] <= result["before_cost"]
    assert result["after_co2"] <= result["before_co2"]


def test_seed_and_summary_with_temp_db(tmp_path):
    db_file = str(tmp_path / "energy_test.db")
    service = AnalyticsService(db_file)

    started = time.perf_counter()
    inserted = service.seed_if_empty(days=14)
    elapsed = time.perf_counter() - started

    assert inserted == 1344
    assert service.seed_if_empty() == 0

    summary = service.get_dashboard_summary()
    required_keys = {
        "energy_today",
        "co2_today",
        "cost_today",
        "savings_eur",
        "savings_co2",
        "score",
        "E",
        "C",
        "K",
        "room_temp",
        "by_device",
        "alerts",
        "recent_rows",
    }
    assert required_keys <= summary.keys()
    assert len(summary["by_device"]) == 4



def test_fixed_seed_determinism():
    reference = datetime(2026, 11, 3, 12, 0)
    first = EnergySimulator(seed=42).seed_history(days=14, reference_time=reference)
    second = EnergySimulator(seed=42).seed_history(days=14, reference_time=reference)

    assert len(first) == len(second) == 1344
    assert [reading.to_dict() for reading in first] == [
        reading.to_dict() for reading in second
    ]


def test_week_over_week_and_time_aggregations(tmp_path):
    service = AnalyticsService(str(tmp_path / "aggregates.db"))
    assert service.seed_if_empty(days=14) == 1344

    comparison = service.compute_week_over_week()
    aggregates = service.get_aggregates()
    summary = service.get_dashboard_summary()

    assert comparison["this_week"]["energy_kwh"] > 0
    assert comparison["last_week"]["energy_kwh"] > 0
    assert set(comparison["change_pct"]) == {"energy_kwh", "co2_kg", "cost_eur"}
    assert len(aggregates["hourly_series"]) == 24
    assert len(aggregates["last_week_hourly_series"]) == 24
    assert len(aggregates["by_device_week"]) == 4
    assert summary["week_over_week"] == comparison
    assert "daily_totals" in summary and "weekly_totals" in summary


def test_building_isolation(tmp_path):
    service = AnalyticsService(str(tmp_path / "buildings.db"))

    assert service.seed_if_empty(days=1, building_id="library") == 96
    assert service.seed_if_empty(days=1, building_id="central_office") == 96
    library = service.get_dashboard_summary("library")
    office = service.get_dashboard_summary("central_office")

    assert library["building_id"] == "library"
    assert office["building_id"] == "central_office"
    assert all(row["building_id"] == "library" for row in library["recent_rows"])
    assert all(row["building_id"] == "central_office" for row in office["recent_rows"])


def test_alert_monitor_loads_building_limits(tmp_path):
    service = AnalyticsService(str(tmp_path / "limits.db"))
    service.repository.save_limit("library", "Heating", 0.01)
    reading = EnergyReading(
        "2026-10-28 14:00", "Heating", 1.0, 21.0, 0.38, 80, "library"
    )
    service.save_reading(reading)

    limits = service.alert_monitor.get_limits_for_building("library")
    alerts = service.check_alerts("library", recent_rows=[reading.to_dict()])

    assert limits["Heating"] == 0.01
    assert any(alert["building_id"] == "library" for alert in alerts)

def test_single_calculation_performance_under_50ms():
    simulator = EnergySimulator()

    started = time.perf_counter()
    reading = simulator.generate_reading("Heating")
    elapsed = time.perf_counter() - started

    assert reading.device_type == "Heating"
    assert elapsed < 0.050


def test_live_step_and_alert_fallback_safety(tmp_path):
    service = AnalyticsService(str(tmp_path / "live.db"))

    results = service.simulate_live_step()

    assert len(results) == 4
    assert len(service.get_dashboard_summary()["recent_rows"]) == 4
    assert isinstance(service.check_alerts(limits=None), list)
    alerts = service.check_alerts(limits={"Heating": 0.01})
    assert any(alert["device_type"] == "Heating" for alert in alerts)


def test_uml_method_signature_compatibility(tmp_path):
    simulator = EnergySimulator()
    reading = simulator.generate_reading("Lighting", 14)
    service = AnalyticsService(str(tmp_path / "uml.db"))

    result = service.simulate_scenario(-1.5, 25.0)

    assert reading.device_type == "Lighting"
    assert reading.timestamp.endswith(" 14:00")
    assert {
        "before_kwh",
        "after_kwh",
        "before_co2",
        "after_co2",
        "before_cost",
        "after_cost",
        "before_score",
        "after_score",
    } == set(result)
