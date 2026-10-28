# Stage 2 Handoff: ScoreCalculator

## Summary

Stage 2 adds `ScoreCalculator`, a deterministic mathematical engine for Subsystem 1. It converts energy use into carbon and cost estimates, measures room comfort, and combines energy efficiency, carbon efficiency, and comfort into a sustainability score from 0 to 100.

The calculator does not write to SQLite, read from the database, or render HTML. Its inputs and outputs are ordinary Python values and dictionaries, so the formulas can be tested independently and explained clearly during the presentation.

## Configurable Constants

`ScoreCalculator.__init__()` loads these values from `config.py`:

| Constant | Value | Meaning |
| --- | ---: | --- |
| `CO2_FACTOR_KG_PER_KWH` | `0.38` | Kilograms of CO2 produced per kWh |
| `COST_EUR_PER_KWH` | `0.35` | Euros per kWh |
| `IDEAL_TEMP_C` | `21.0` | Ideal room temperature in degrees C |

The class exposes `cost_factor` and the UML-compatible alias `cost_per_kwh`, both set from `COST_EUR_PER_KWH`.

## Formula 1: Carbon Emissions

```text
CO2 (kg) = kWh x CO2 factor
```

The configured factor is `0.38 kg/kWh`. For `10.0 kWh`:

```text
CO2 = 10.0 x 0.38
     = 3.8 kg
```

`calc_co2(10.0)` returns `3.8`.

## Formula 2: Energy Cost

```text
Cost (EUR) = kWh x cost factor
```

The configured price is `0.35 EUR/kWh`. For `10.0 kWh`:

```text
Cost = 10.0 x 0.35
     = 3.5 EUR
```

`calc_cost(10.0)` returns `3.5`.

## Formula 3: Comfort Index

Comfort is measured against the configured ideal temperature. The result is clamped between `0.0` and `1.0`:

```text
K = max(0.0, min(1.0, 1.0 - (abs(room_temp - ideal_temp) / 10.0)))
```

For a room at `26.0 C` and an ideal of `21.0 C`:

```text
difference = abs(26.0 - 21.0) = 5.0 C
K = 1.0 - (5.0 / 10.0)
  = 0.5
```

Therefore `calc_comfort(26.0)` returns `0.5`. At `21.0 C`, the difference is zero and `K = 1.0`. At `31.0 C` or `11.0 C`, the difference is `10.0 C` and `K = 0.0`. Larger differences remain `0.0` because of the clamp.

## Formula 4: Sustainability Score

The overall score combines three normalized subscores. Each subscore is clamped to the range `0.0` to `1.0` and rounded to two decimal places.

### Energy Efficiency: E

The maximum reference is `4.0 kWh/hour`:

```text
E = 1.0 - (total_hourly_kwh / 4.0)
```

For `2.0 kWh/hour`:

```text
E = 1.0 - (2.0 / 4.0)
  = 0.50
```

### Carbon Efficiency: C

The maximum reference is `1.6 kg CO2/hour`:

```text
C = 1.0 - ((total_hourly_kwh x 0.38) / 1.6)
```

For `2.0 kWh/hour`:

```text
CO2 = 2.0 x 0.38 = 0.76 kg/hour
C = 1.0 - (0.76 / 1.6)
  = 0.525
  = 0.53 after rounding
```

### Comfort: K

For `room_temp = 26.0 C`, the comfort calculation above gives `K = 0.50`.

### Weighted total

The weights are 40% for energy efficiency, 35% for carbon efficiency, and 25% for comfort:

```text
Score = round(100 x (0.40 x E + 0.35 x C + 0.25 x K))
```

Using `E = 0.50`, `C = 0.53`, and `K = 0.50`:

```text
Score = round(100 x ((0.40 x 0.50) + (0.35 x 0.53) + (0.25 x 0.50)))
      = round(100 x (0.20 + 0.1855 + 0.125))
      = round(51.05)
      = 51
```

## Purity and Determinism

The methods are pure mathematical functions in practice: the same inputs and the same configured constants always produce the same outputs. They do not mutate readings, access a database, depend on the clock, or perform I/O. This satisfies NFR2 and keeps the calculations easy to unit test, review, and reuse.

Configuration satisfies NFR5 by keeping factors and reference values outside the formulas. If the energy price or emissions factor changes, the application can update `config.py` without rewriting the calculation logic.

## Subsystem 2 Return Contract

`calc_sustainability_score(total_hourly_kwh, room_temp)` returns exactly:

```python
{
    "score": int,
    "E": float,
    "C": float,
    "K": float,
}
```

For example, the inputs `2.0` kWh/hour and `26.0 C` return:

```python
{"score": 51, "E": 0.5, "C": 0.53, "K": 0.5}
```

In `dashboard.html`, Subsystem 2 uses the three normalized values as progress-bar inputs:

- `E` renders the Energy Efficiency progress bar.
- `C` renders the Carbon Efficiency progress bar.
- `K` renders the Comfort progress bar.

Because all three values are normalized to `0.0` through `1.0`, the template can convert each value to a percentage by multiplying by `100` for the progress-bar width or display label. The overall `score` is shown separately as the combined sustainability result.