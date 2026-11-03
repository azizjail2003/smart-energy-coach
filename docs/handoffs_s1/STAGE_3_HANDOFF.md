# Stage 3 Handoff: EnergySimulator

## Summary

Stage 3 adds `EnergySimulator`, which creates realistic synthetic campus energy readings for the four configured device categories: Heating, Lighting, Servers, and Other. It uses the Stage 2 `ScoreCalculator` to derive carbon emissions and sustainability scores, then returns validated, building-scoped `EnergyReading` objects. Together with `EnergyReading`, `ScoreCalculator`, `AlertMonitor`, and `AnalyticsService`, it is one of five collaborating UML classes.

## Deterministic Seed and History

The simulator uses `RANDOM_SEED = 42` by default and owns an isolated `random.Random(seed)` instance. This keeps S1-NFR4 deterministic without mutating Python's global random state. `set_seed()` resets that private stream when a repeatable alternate scenario is required.

Each reading carries a `building_id`, defaulting to `library`. The same generation logic can therefore produce independent histories for `library` and `central_office` without mixing persistence, limits, alerts, or aggregates.

## Campus Behavior Model

Each device category has a representative base load:

| Device | Base load (kWh/hour) | Reasoning |
| --- | ---: | --- |
| Heating | `1.4` | Heating systems are a major building load. |
| Lighting | `0.5` | Lighting is distributed across rooms and corridors. |
| Servers | `1.1` | Server equipment has a steady, substantial demand. |
| Other | `0.3` | Small appliances and miscellaneous equipment. |

The simulator models university occupancy with a daytime multiplier:

- From `08:00` through `18:00`, the multiplier is `1.4`, representing peak occupancy and activity.
- At other hours, the multiplier is `0.6`, representing lower nighttime activity.

The generated energy value is:

```text
kWh = base load x daytime multiplier x random factor
```

The random factor is uniformly selected between `0.85` and `1.25`. This adds bounded sensor and usage variation without producing implausible values. Room temperature is generated around `21.0 C` with a random offset between `-1.5 C` and `+2.0 C`, then rounded to one decimal place.

For example, a Lighting reading during the day with random factor `1.10` is:

```text
kWh = 0.5 x 1.4 x 1.10
     = 0.77 kWh
```

The simulator then calculates CO2 and sustainability score through `ScoreCalculator`, creates the timestamp in `%Y-%m-%d %H:%M` format, validates the record, and returns it.

## Why On-Demand Seeding

An initial design considered a background thread that generated a new reading every five seconds. We replaced it with on-demand simulation and a historical seed operation at one-hour intervals for these reasons:

1. **Avoid Flask thread-locking problems:** Flask request handling and a background writer can compete for connections or transactions. Keeping generation inside an explicit request or startup operation makes repository ownership clear.
2. **Avoid concurrency surprises:** The simulator itself has no database connection or worker thread. `AnalyticsService` persists the returned list through Subsystem 3's MySQL repository interface, or the isolated local fallback in tests.
3. **Keep useful granularity without uncontrolled growth:** Fourteen days of hourly history creates `336` timestamps per building and `1,344` readings, enough for hourly, daily, weekly, and week-over-week dashboards while remaining bounded and batchable.
4. **Improve repeatability:** On-demand methods are easy to call in tests, startup scripts, or a controlled refresh action. There is no hidden process continuing after the caller has finished.

For the default fourteen-day history, `seed_history()` uses `range(days * 24, 0, -1)`. That produces `336` hourly timestamps. With four devices at each timestamp, the result contains `336 x 4 = 1,344` readings per building. `AnalyticsService.seed_if_empty()` inserts them in one batch transaction in under ten seconds.

## Method Behavior

### `generate_reading(device, ts, building_id)`

The timestamp parameter accepts all three supported forms:

- `None`: use the current date and time.
- An `int`: treat it as an hour of day, using `ts % 24` and zero minutes and seconds.
- A `datetime`: use that exact datetime.
- `building_id`: attach the reading to the requested building, defaulting to `library`.

The method applies the daytime or nighttime multiplier, generates bounded random energy and temperature values, delegates derived calculations to `ScoreCalculator`, and calls `EnergyReading.validate()` before returning.

### `seed_history(days=14, building_id="library")`

The method rounds the current time down to the hour, moves backward in one-hour steps, and generates one reading for every configured device at each timestamp. It returns a plain `list[EnergyReading]`, leaving persistence to `AnalyticsService` and S3's repository layer.

## Stage 4 Persistence Preview

`AnalyticsService` consumes the readings returned by `generate_reading()` and `seed_history()`. It delegates batch insertion and scoped queries to S3's MySQL repository interface, with a local repository fallback for offline pytest. `AlertMonitor` loads building-specific thresholds, while `AnalyticsService` provides hourly, daily, weekly, and week-over-week aggregates for Subsystem 2 and Subsystem 3. Keeping persistence out of `EnergySimulator` preserves the simulator's focused, deterministic generation responsibility.