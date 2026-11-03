# Stage 5 Final Master Handoff: Subsystem 1

**Owner:** Abdelhamid Ahbane  
**Subsystem:** Energy Simulation and Analytics Engine  
**Final implementation:** `subsystems/s1_analytics.py`  
**Automated tests:** `tests/test_s1_analytics.py`

## Final Scope

Subsystem 1 is complete. It contains five collaborating UML classes:

1. `EnergyReading`: validated dataclass and dictionary contract.
2. `ScoreCalculator`: deterministic CO2, cost, comfort, and sustainability math.
3. `EnergySimulator`: deterministic device readings and fourteen-day hourly historical generation.
4. `AlertMonitor`: autonomous per-building threshold loading and alert detection.
5. `AnalyticsService`: repository facade for persistence, dashboard summaries, aggregations, alerts, and what-if scenarios.

The final pytest file covers the original tests plus deterministic seeding, multi-building isolation, hourly/daily/weekly aggregation, week-over-week comparison, and autonomous alert-limit loading.

## Traceability Matrix

The following matrix covers every Subsystem 1 requirement from **FR1-FR10** and
**NFR1-NFR10**, with its implementation owner and executable proof.

### Functional Requirements

| Requirement | Implemented by | Proof in tests |
| --- | --- | --- |
| FR1: Generate an energy reading | `EnergySimulator.generate_reading()`; `AnalyticsService.simulate_live_step()` | `test_single_calculation_performance_under_50ms`; `test_live_step_and_alert_fallback_safety` |
| FR2: Seed historical energy data | `EnergySimulator.seed_history()`; `AnalyticsService.seed_if_empty()` | `test_seed_and_summary_with_temp_db`; `test_fixed_seed_determinism` |
| FR3: Calculate CO2 and cost | `ScoreCalculator.calc_co2()` and `calc_cost()` | `test_co2_and_cost_calculation` |
| FR4: Calculate comfort index | `ScoreCalculator.calc_comfort()` | `test_comfort_score_at_ideal_temp` |
| FR5: Calculate sustainability score | `ScoreCalculator.calc_sustainability_score()` | `test_comfort_score_at_ideal_temp` |
| FR6: Produce dashboard KPIs | `AnalyticsService.get_dashboard_summary()` | `test_seed_and_summary_with_temp_db` |
| FR7: Detect threshold alerts and aggregations | `AlertMonitor.check_alerts()`; `get_aggregates()`; `compute_week_over_week()` | `test_live_step_and_alert_fallback_safety`; `test_week_over_week_and_time_aggregations` |
| FR8: Calculate savings and dashboard metrics | `AnalyticsService.get_dashboard_summary()` using `BASELINE_DAILY_KWH` | `test_seed_and_summary_with_temp_db` |
| FR9: Project what-if scenarios | `AnalyticsService.simulate_scenario()` | `test_scenario_reduces_energy_when_heating_lowered`; `test_uml_method_signature_compatibility` |
| FR10: Validate and persist readings | `EnergyReading.validate()`; `AnalyticsService.save_reading()` and seeding | `test_reading_validation_rejects_negative_kwh`; `test_live_step_and_alert_fallback_safety` |

### Non-Functional Requirements

| Requirement | Implemented by | Proof in tests |
| --- | --- | --- |
| NFR1: Fast calculation | Pure `ScoreCalculator` methods and in-memory simulator calculations | `test_single_calculation_performance_under_50ms` |
| NFR2: Deterministic mathematical engine | `ScoreCalculator` uses only inputs and configured constants | `test_co2_and_cost_calculation`; `test_comfort_score_at_ideal_temp` |
| NFR3: Modular architecture | Five UML classes plus repository adapter with facade boundaries | Expanded pytest suite imports and exercises classes independently |
| NFR4: Data integrity and deterministic simulation | `EnergyReading.validate()` plus isolated `random.Random(42)` | `test_reading_validation_rejects_negative_kwh`; `test_fixed_seed_determinism` |
| NFR5: Configurability | `ScoreCalculator` loads factors from `config.py`; service loads DB, limits, and baseline constants | `test_co2_and_cost_calculation`; `test_seed_and_summary_with_temp_db` |
| NFR6: Standard data interchange | `EnergyReading.to_dict()` and service dictionary contracts | `test_live_step_and_alert_fallback_safety`; summary contract assertions |
| NFR7: Repository persistence | S3 MySQL repository interface with local offline fallback and batch `executemany` | `test_seed_and_summary_with_temp_db` asserts 1,344 rows under 10 seconds |
| NFR8: Type-hinted, readable Python API | Type hints and clear class/method contracts throughout `s1_analytics.py` | All tests execute the public API; diagnostics and compilation pass |
| NFR9: Human-readable documentation | Docstrings, comments, staged handoffs, and this guide | Review artifact: Stage 1–5 handoff documents |
| NFR10: Safe fallback behavior | Default limits, empty dashboard response, missing scenario values, and default threshold `2.0` | `test_live_step_and_alert_fallback_safety`; `test_uml_method_signature_compatibility` |

## Integration Guide: Subsystem 2 Web UI

Abdelaziz Jail can use the facade without issuing SQL or recreating S1 formulas. The exact import is:

```python
from subsystems.s1_analytics import AnalyticsService
```

Create the service with the configured or injected database path and seed at application startup:

```python
analytics_service = AnalyticsService(db_path)
analytics_service.seed_if_empty()
```

A dashboard route can request the complete view model:

```python
limits = threshold_settings_manager.get_limits()
summary = analytics_service.get_dashboard_summary(limits)
return render_template("dashboard.html", summary=summary)
```

The live simulation route can call:

```python
results = analytics_service.simulate_live_step()
return jsonify(results)
```

The scenarios route can call:

```python
result = analytics_service.simulate_scenario(
    summary,
    heating_delta_c,
    light_reduction_pct,
)
return render_template("scenarios.html", result=result)
```

`dashboard.html` can read `summary["energy_today"]`, `summary["co2_today"]`, `summary["cost_today"]`, `summary["score"]`, `summary["E"]`, `summary["C"]`, `summary["K"]`, `summary["room_temp"]`, `summary["by_device"]`, and `summary["alerts"]`. The normalized `E`, `C`, and `K` values range from `0.0` to `1.0`; multiply by `100` for progress-bar percentages.

## Integration Guide: Subsystem 3 AI Coach and Database

Nestor David Carrizo can use the same facade and consume the stable summary keys:

```python
from subsystems.s1_analytics import AnalyticsService

analytics = AnalyticsService(db_path)
summary = analytics.get_dashboard_summary()
energy_today = summary.get("energy_today")
co2_today = summary.get("co2_today")
score = summary.get("score")
building_id = summary.get("building_id", "library")
week_over_week = summary.get("week_over_week")
```

The S1-owned MySQL repository schema is:

```sql
CREATE TABLE IF NOT EXISTS energy_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    building_id VARCHAR(50) NOT NULL,
    device_type ENUM('Heating','Lighting','Servers','Other') NOT NULL,
    kwh DECIMAL(6,2) NOT NULL,
    room_temp DECIMAL(4,1) NOT NULL,
    co2_kg DECIMAL(6,2) NOT NULL,
    sustainability_score INT NOT NULL
);
```

Column meanings:

| Column | Type | Contract |
| --- | --- | --- |
| `id` | `INTEGER` | Database-generated primary key |
| `timestamp` | `DATETIME` | `%Y-%m-%d %H:%M` |
| `building_id` | `VARCHAR(50)` | `library` or `central_office` |
| `device_type` | `ENUM` | `Heating`, `Lighting`, `Servers`, or `Other` |
| `kwh` | `DECIMAL(6,2)` | Non-negative energy consumption |
| `room_temp` | `DECIMAL(4,1)` | Validated range `0` to `45` C |
| `co2_kg` | `DECIMAL(6,2)` | Calculated CO2 emissions |
| `sustainability_score` | `INT` | Calculated score from `0` to `100` |

The dashboard summary dictionary has these exact keys:

```python
{
    "energy_today": float,
    "building_id": str,
    "co2_today": float,
    "cost_today": float,
    "savings_eur": float,
    "savings_co2": float,
    "score": int,
    "E": float,
    "C": float,
    "K": float,
    "room_temp": float,
    "by_device": dict,
    "alerts": list,
    "recent_rows": list,
    "vs_last_week_pct": float,
    "this_week_by_device": dict,
    "hourly_series": list,
    "daily_totals": dict,
    "weekly_totals": dict,
    "week_over_week": dict,
}
```

For the AI coach, the primary required inputs are `summary.get("energy_today")`, `summary.get("co2_today")`, and `summary.get("score")`. The remaining values are available for richer coaching explanations.

## Personal Presentation and Screencast Script

### Seven-minute screencast

**0:00–0:45 — Introduce ownership and goal**

Say: “I am Abdelhamid Ahbane, owner of Subsystem 1. My subsystem turns campus energy measurements into validated readings, analytics, sustainability scores, alerts, savings, and scenario projections. It exposes a small facade so the web UI and AI subsystem do not need to know the internal SQL or formulas.”

**0:45–1:45 — Show the data model**

Open `EnergyReading` and point to the seven fields, including `building_id`. Explain that `validate()` rejects negative energy, unrealistic temperatures, unknown devices, and empty building identifiers before repository insertion. Mention the `score` property as the UML-compatible alias.

**1:45–2:45 — Show the mathematical engine**

Open `ScoreCalculator`. Explain the configured factors: `0.38 kg CO2/kWh`, `0.35 EUR/kWh`, and ideal temperature `21 C`. Walk through the comfort formula and the weighted score: 40% energy efficiency, 35% carbon efficiency, and 25% comfort. Emphasize that the methods are deterministic and have no database or web dependencies.

**2:45–3:45 — Show realistic simulation**

Open `EnergySimulator`. Explain the base loads for Heating, Lighting, Servers, and Other. Show the occupancy model: `1.4x` from 08:00 through 18:00 and `0.6x` outside that window, with bounded random noise. Explain that fourteen days at one-hour intervals produce 336 timestamps and 1,344 readings per building, using `RANDOM_SEED = 42`.

**3:45–4:45 — Show persistence and facade behavior**

Open `AlertMonitor` and `AnalyticsService`. Explain that limits and readings are scoped by building, and that S1 delegates persistence to S3's MySQL repository interface with a local fallback for tests. Point to `seed_if_empty()` and `save_reading()` and explain the single batch transaction.

**4:45–5:45 — Demonstrate the dashboard and alerts**

Show `get_dashboard_summary()`. Explain that it aggregates the latest 16 rows by device, calculates energy, CO2, cost, savings against `BASELINE_DAILY_KWH`, score components, and recent rows. Show that limits are merged with defaults, so missing or `None` settings do not crash alert detection.

**5:45–6:30 — Demonstrate the scenario projection**

Show `simulate_scenario()`. Explain that lowering temperature by one degree changes Heating usage by 6%, while lighting reduction scales Lighting usage directly. The method returns before/after kWh, CO2, cost, and score without changing the database.

**6:30–7:00 — Run the tests and close**

Run `pytest -q`. Say: “The test suite covers the mandatory formulas, validation, scenario reduction, fourteen-day hourly seeding, deterministic output, multi-building isolation, aggregation accuracy, alert fallback safety, and UML-compatible signatures.”

### Fifteen-to-twenty-minute defense

1. **Architecture, 2 minutes:** Draw the chain `EnergyReading -> ScoreCalculator -> EnergySimulator -> AlertMonitor -> AnalyticsService`. Explain the single-responsibility boundary of each class and the repository adapter boundary.
2. **Data integrity, 3 minutes:** Demonstrate the three `ValueError` guards and explain why invalid values must be rejected before persistence.
3. **Math, 4 minutes:** Whiteboard the CO2, cost, comfort, and weighted sustainability formulas. Use `10 kWh -> 3.8 kg CO2 and 3.5 EUR`, then use `2 kWh/hour at 21 C` for a score example.
4. **Simulation, 2 minutes:** Explain base loads, occupancy multiplier, noise bounds, fixed seed, and the 1,344-row fourteen-day dataset.
5. **Database facade, 3 minutes:** Show the MySQL schema, repository interface, parameterized batch insert, and building filters. Explain why on-demand generation avoids background-thread and database locking issues.
6. **Cross-subsystem integration, 2 minutes:** Show the exact `AnalyticsService` calls used by the web UI and the three summary values consumed by the AI coach.
7. **Testing and quality, 2 minutes:** Run pytest, point out the under-10-second 1,344-row seed requirement and under-50-ms single-reading requirement, then explain deterministic, aggregation, isolation, AlertMonitor, fallback, and UML tests.
8. **Likely questions, 1–2 minutes:** Be ready to answer why `sustainability_score` is stored instead of `score`, why only the latest 16 rows drive dashboard totals, and why scenario projections do not write to the database.

## Final Verification Command

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The expected result is the expanded suite passing. Syntax compilation can be checked with:

```powershell
.\.venv\Scripts\python.exe -m py_compile .\config.py .\subsystems\s1_analytics.py .\tests\test_s1_analytics.py
```
