# Stage 4 Handoff: AnalyticsService

## Facade Design

`AnalyticsService` is Subsystem 1's Facade. Subsystem 2 and Subsystem 3 call a small, stable API instead of knowing how MySQL repository calls, validation, simulation, and score calculations work internally. S1 delegates persistence and queries to S3's repository interface, with an isolated local repository fallback for offline pytest.

For example, `seed_if_empty()` hides building-scoped checks, fourteen-day hourly generation, validation, and one-transaction insertion. `get_dashboard_summary()` hides repository retrieval, aggregation, savings math, and `AlertMonitor` threshold detection. This separation keeps web routes and AI/database consumers focused on their own responsibilities while keeping S1's persistence rules in one place.

## API Reference

| Public method | Parameters | Return value |
| --- | --- | --- |
| `save_reading` | `reading: EnergyReading` | `None`; validates and inserts one row |
| `seed_if_empty` | `days: int = 14`, `building_id: str = "library"` | `int`; inserted row count, or `0` if that building already has data |
| `simulate_live_step` | `building_id: str = "library"` | `list[dict]`; each dict has `timestamp`, `building_id`, `device_type`, `kwh`, `room_temp`, `co2_kg`, and `sustainability_score` |
| `check_alerts` | `building_id`, `limits: dict \| None`, `recent_rows: list \| None` | `list[dict]`; alert keys are `building_id`, `timestamp`, `device_type`, `kwh`, `limit`, and `message` |
| `get_dashboard_summary` | `building_id: str = "library"`, `limits: dict \| None = None` | Existing KPI keys plus `building_id`, `vs_last_week_pct`, `this_week_by_device`, `hourly_series`, `daily_totals`, `weekly_totals`, and `week_over_week` |
| `get_aggregates` | `building_id: str = "library"` | Hourly series, prior-week hourly series, daily totals, weekly totals, and `by_device_week` |
| `compute_week_over_week` | `building_id: str = "library"` | `this_week`, `last_week`, and `change_pct` for energy, CO2, and cost |
| `simulate_scenario` | `current_summary: dict \| float \| str`, deltas, `building_id` | `dict` with the existing before/after kWh, CO2, cost, and score keys |

The service accepts an S3 `EnergyRepository`/MySQL adapter through dependency injection. A temporary path selects the local repository fallback, so isolated tests run without a live MySQL server. All reading and threshold operations are filtered by `building_id`, defaulting to `library`.

## Dashboard Summary Walkthrough

`get_dashboard_summary()` reads the newest 32 repository rows for one building. The latest 16 rows represent four recent hourly time steps across the four devices, so those 16 rows are used for device totals and alerts. Each device starts at `0.0` in `by_device`, and its kWh values are added and rounded to two decimals.

The daily dashboard totals are then derived from those latest readings:

1. `energy_today` is the sum of `by_device`.
2. `co2_today` and `cost_today` use `ScoreCalculator` with the configured factors.
3. The newest four rows provide the current average room temperature.
4. The score engine receives `energy_today / 8.0` and the average temperature to produce `score`, `E`, `C`, and `K`.
5. Savings compare usage with `config.BASELINE_DAILY_KWH`. The positive difference becomes `saved_kwh`, which is converted to `savings_eur` and `savings_co2`.
6. `recent_rows` exposes the latest 32 MySQL repository rows as ordinary dictionaries for templates and consumers.

`get_aggregates()` adds 24 hourly points, the same 24-hour window one week earlier, daily totals, weekly totals, and device totals for the latest 7-day weekly window. `compute_week_over_week()` compares the latest 672 readings with the previous 672 readings and returns percentage changes using the documented formula, or `0.0` when the prior value is zero.

Alerts use the same latest 16 rows. The effective threshold limits merge `config.DEFAULT_LIMITS` with caller-provided values, so `None`, an empty dictionary, or a partial dictionary cannot crash the check. A missing device-specific limit falls back to `2.0`. A row creates an alert only when its kWh value is strictly greater than its effective limit.

When the database is empty, the service returns a safe dashboard object with zero totals, neutral default score values, an empty device map, no alerts, and no recent rows.

## Scenario Projection

`simulate_scenario()` supports both the web-friendly form and the UML shorthand. The web form passes the current summary followed by a temperature delta and lighting reduction percentage. The shorthand passes the temperature delta and lighting reduction percentage as the first two arguments; the service fetches the current summary itself.

The calculation proceeds as follows:

1. Read current energy, Heating kWh, Lighting kWh, room temperature, and score from the summary. Missing values use the documented defaults: `15.7` kWh, `7.0` Heating kWh, `3.0` Lighting kWh, `21.0 C`, and score `80`.
2. Apply the heating adjustment. Each `-1 C` changes Heating usage by `-6%`, represented by `heating_kwh * (heating_delta_c * 0.06)`.
3. Apply the lighting reduction directly: `-lighting_kwh * (light_reduction_pct / 100.0)`.
4. Add both changes to current energy and clamp the result to at least `1.0` kWh.
5. Adjust room temperature by the requested temperature delta and recalculate the sustainability score using the projected energy.
6. Return before/after kWh, CO2, cost, and score values for `scenarios.html`.

The projection does not write to MySQL or call the repository. It is an isolated what-if calculation, so users can compare a possible intervention without changing the dashboard's stored readings.