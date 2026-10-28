# Stage 4 Handoff: AnalyticsService

## Facade Design

`AnalyticsService` is Subsystem 1's Facade. Subsystem 2 and Subsystem 3 call a small, stable API instead of knowing how SQLite connections, SQL statements, validation, simulation, and score calculations work internally.

For example, `seed_if_empty()` hides table checks, seven-day generation, validation, and one-transaction insertion. `get_dashboard_summary()` hides row retrieval, aggregation, savings math, and alert detection. This separation keeps web routes and AI/database consumers focused on their own responsibilities while keeping S1's persistence rules in one place.

## API Reference

| Public method | Parameters | Return value |
| --- | --- | --- |
| `save_reading` | `reading: EnergyReading` | `None`; validates and inserts one row |
| `seed_if_empty` | `days: int = 7` | `int`; inserted row count, or `0` if data exists |
| `simulate_live_step` | none | `list[dict]`; each dict has `timestamp`, `device_type`, `kwh`, `room_temp`, `co2_kg`, and `sustainability_score` |
| `check_alerts` | `limits: dict \| None = None`, `recent_rows: list \| None = None` | `list[dict]`; alert keys are `timestamp`, `device_type`, `kwh`, `limit`, and `message` |
| `get_dashboard_summary` | `limits: dict \| None = None` | `dict` with `energy_today`, `co2_today`, `cost_today`, `savings_eur`, `savings_co2`, `score`, `E`, `C`, `K`, `room_temp`, `by_device`, `alerts`, and `recent_rows` |
| `simulate_scenario` | `current_summary: dict \| float`, `heating_delta_c: float = 0.0`, `light_reduction_pct: float \| None = None` | `dict` with `before_kwh`, `after_kwh`, `before_co2`, `after_co2`, `before_cost`, `after_cost`, `before_score`, and `after_score` |

The service creates `energy_readings` on initialization, so isolated tests can use a temporary path without requiring Subsystem 3's database initializer.

## Dashboard Summary Walkthrough

`get_dashboard_summary()` reads the newest 32 database rows. The latest 16 rows represent four recent time steps across the four devices, so those 16 rows are used for device totals and alerts. Each device starts at `0.0` in `by_device`, and its kWh values are added and rounded to two decimals.

The daily dashboard totals are then derived from those latest readings:

1. `energy_today` is the sum of `by_device`.
2. `co2_today` and `cost_today` use `ScoreCalculator` with the configured factors.
3. The newest four rows provide the current average room temperature.
4. The score engine receives `energy_today / 8.0` and the average temperature to produce `score`, `E`, `C`, and `K`.
5. Savings compare usage with `config.BASELINE_DAILY_KWH`. The positive difference becomes `saved_kwh`, which is converted to `savings_eur` and `savings_co2`.
6. `recent_rows` converts all 32 SQLite rows to ordinary dictionaries for templates and consumers.

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

The projection does not write to SQLite. It is an isolated what-if calculation, so users can compare a possible intervention without changing the dashboard's stored readings.