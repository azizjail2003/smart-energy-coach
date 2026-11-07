# S1 – Monitoring, Simulation & Analytics Engine

**Owner:** Abdelhamid Ahbane  
**Implementation:** `subsystems/s1_analytics.py` | **Shared Config:** `config.py` | **Test Suite:** `tests/test_s1_analytics.py`  
**Detailed Handoff Docs:** `docs/handoffs_s1/STAGE_1_HANDOFF.md` – `STAGE_5_FINAL_MASTER_HANDOFF.md`

## Core Capabilities & Formulas

* **Supported Buildings:** `library` (default), `lecture-hall-a`, and `lab-building`
* **Device Categories:** `Heating` (`1.4 kWh` base), `Servers` (`1.1 kWh` base), `Lighting` (`0.5 kWh` base), `Other` (`0.3 kWh` base)
* **Mathematical Engine (`ScoreCalculator`):**
  * **CO₂ Emissions:** `round(kWh × 0.38, 2)` kg
  * **Energy Cost:** `round(kWh × 0.35, 2)` EUR
  * **Comfort Index (`K`):** `round(max(0.0, min(1.0, 1.0 - (|room_temp - 21.0| / 10.0))), 2)`
  * **Sustainability Score:** `round(100 × (0.40 × E + 0.35 × C + 0.25 × K))` where `E = 1.0 - (hourly_kwh / 4.0)` and `C = 1.0 - ((hourly_kwh × 0.38) / 1.6)`
* **Deterministic Simulation & Seeding:** Uses an isolated `random.Random(42)` instance with occupancy multipliers (`1.4×` from `08:00–18:00`, `0.6×` off-peak) to seed 14 days of hourly history (`1,344` rows per building) in a single batch transaction (`< 0.05 s`). All returned timestamps are Python `datetime` objects.
* **What-If Scenario Projection (`simulate_scenario` & `estimate_scenario`):** Models heating setpoint changes (`6%` heating delta per `1.0 °C`) and lighting reductions (`0–50%`) without mutating database records.

## S1 Requirements Traceability Matrix

| ID | Requirement Summary | Implemented By | Automated Proof (`tests/test_s1_analytics.py`) |
| :--- | :--- | :--- | :--- |
| **FR1** | Generate realistic device energy readings | `EnergySimulator.generate_reading()`, `simulate_live_step()` | `test_single_calculation_performance_under_50ms`, `test_live_step_and_alert_fallback_safety` |
| **FR2** | Seed 14-day hourly historical dataset (1,344 rows) | `EnergySimulator.seed_history()`, `seed_if_empty()` | `test_seed_and_summary_with_temp_db`, `test_fixed_seed_determinism` |
| **FR3** | Calculate CO₂ emissions and EUR cost | `ScoreCalculator.calc_co2()`, `calc_cost()` | `test_co2_and_cost_calculation` |
| **FR4** | Calculate indoor thermal comfort index | `ScoreCalculator.calc_comfort()` | `test_comfort_score_at_ideal_temp` |
| **FR5** | Calculate weighted sustainability score (0–100) | `ScoreCalculator.calc_sustainability_score()` | `test_comfort_score_at_ideal_temp` |
| **FR6** | Produce unified dashboard KPIs & view model | `AnalyticsService.get_dashboard_summary()`, `get_score()` | `test_seed_and_summary_with_temp_db`, `test_score_alerts_and_scenario_api` |
| **FR7** | Detect threshold alerts & compute aggregations/WoW | `AlertMonitor.check_alerts()`, `get_alerts()`, `get_aggregates()`, `compute_week_over_week()` | `test_week_over_week_and_time_aggregations`, `test_alert_monitor_loads_building_limits`, `test_score_alerts_and_scenario_api` |
| **FR8** | Calculate financial & carbon savings vs. baseline | `AnalyticsService.get_dashboard_summary()` | `test_seed_and_summary_with_temp_db` |
| **FR9** | Project non-destructive What-If scenarios | `AnalyticsService.simulate_scenario()`, `estimate_scenario()` | `test_scenario_reduces_energy_when_heating_lowered`, `test_uml_method_signature_compatibility`, `test_score_alerts_and_scenario_api` |
| **FR10** | Validate and persist readings per building | `EnergyReading.validate()`, `save_reading()` | `test_reading_validation_rejects_negative_kwh`, `test_building_isolation` |
| **NFR1–10** | `< 50 ms` calc, determinism (`seed=42`), modular facade, type safety, safe fallbacks | `s1_analytics.py` & `config.py` | Full 14-test suite in `tests/test_s1_analytics.py`, including `test_returned_timestamps_are_datetime_objects` |

Run the Subsystem 1 test suite:

```bash
python -m pytest tests/test_s1_analytics.py -v
```
