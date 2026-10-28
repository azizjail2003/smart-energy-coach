# Stage 3 Handoff: EnergySimulator

## Summary

Stage 3 adds `EnergySimulator`, which creates realistic synthetic campus energy readings for the four configured device categories: Heating, Lighting, Servers, and Other. It uses the Stage 2 `ScoreCalculator` to derive carbon emissions and sustainability scores, then returns validated `EnergyReading` objects.

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

An initial design considered a background thread that generated a new reading every five seconds. We replaced it with on-demand simulation and a historical seed operation at three-hour intervals for these reasons:

1. **Avoid Flask thread-locking problems:** Flask request handling and a background writer can compete for SQLite connections or transactions. Keeping generation inside an explicit request or startup operation makes database ownership clear.
2. **Avoid SQLite concurrency surprises:** The simulator itself has no database connection or worker thread. Stage 4 can persist the returned list through one controlled database workflow.
3. **Avoid database bloat:** A five-second loop would create 17,280 records per device during a day. Three-hour intervals create only 8 timestamps per device per day, which is enough for dashboard trends without overwhelming the database.
4. **Improve repeatability:** On-demand methods are easy to call in tests, startup scripts, or a controlled refresh action. There is no hidden process continuing after the caller has finished.

For the default seven-day history, `seed_history()` uses the requested range `range(days * 24, 0, -3)`. That produces `56` timestamps. With four devices at each timestamp, the result contains `56 x 4 = 224` readings.

## Method Behavior

### `generate_reading(device, ts)`

The timestamp parameter accepts all three supported forms:

- `None`: use the current date and time.
- An `int`: treat it as an hour of day, using `ts % 24` and zero minutes and seconds.
- A `datetime`: use that exact datetime.

The method applies the daytime or nighttime multiplier, generates bounded random energy and temperature values, delegates derived calculations to `ScoreCalculator`, and calls `EnergyReading.validate()` before returning.

### `seed_history(days=7)`

The method rounds the current time down to the hour, moves backward in three-hour steps, and generates one reading for every configured device at each timestamp. It returns a plain `list[EnergyReading]`, leaving persistence to the next subsystem.

## Stage 4 Persistence Preview

`AnalyticsService` will consume the readings returned by `generate_reading()` and `seed_history()`. It will be responsible for opening the SQLite database, inserting each reading's dictionary or field values into the `energy_readings` table, and querying records for Subsystem 2 dashboards and Subsystem 3 workflows. Keeping persistence out of `EnergySimulator` preserves the simulator's focused, testable generation responsibility.