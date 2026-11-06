"""Reference figures from the capstone report and deterministic demo fixtures.

Only the Library figures come from the report. Lecture Hall A and Lab Building
are small demonstration datasets made up for this prototype.
"""
from datetime import date

DEMO_DATE = date(2024, 5, 14)
FIRST_DATE = date(2024, 4, 15)  # daily fixtures cover 30 days up to DEMO_DATE

CO2_KG_PER_KWH = 0.38
EUR_PER_KWH = 0.35

SCORE_WEIGHTS = {"energy": 0.40, "carbon": 0.35, "comfort": 0.25}
SCORE_TARGET = 90

DEFAULT_LIMITS = {"heating": 2.0, "lighting": 0.8, "servers": 3.5, "other": 1.0}

# Scenario model: heating energy drops 6.4 % per degree, score gains 0.7 points per % saved.
HEATING_SAVING_PER_DEGREE = 0.064
SCORE_POINTS_PER_SAVED_PCT = 0.7

# Relative hourly weights used for days without explicit hourly fixtures.
HOURLY_PROFILES = {
    "heating": [1, 1, 1, 1, 1, 1, 2, 4, 6, 7, 7, 8, 9, 10, 9, 8, 6, 4, 2, 1, 1, 1, 1, 1],
    "lighting": [1, 1, 1, 1, 1, 1, 2, 5, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 6, 4, 1, 1, 1],
    "servers": [10, 10, 10, 10, 10, 10, 10, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 10, 10, 10, 10, 10],
    "other": [1, 1, 1, 1, 1, 1, 1, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 1, 1, 1, 1, 1],
}

BUILDINGS = {
    "library": {
        "source": "reference",
        "today": {"energy_kwh": 15.7, "co2_kg": 6.0, "cost_eur": 5.50, "change_pct": -6},
        "savings_today": {"eur": 0.35, "co2_kg": 1.0, "change_pct": -6},
        "today_by_category": {
            "heating": {"energy_kwh": 7.5, "co2_kg": 2.9, "cost_eur": 2.62},
            "lighting": {"energy_kwh": 3.1, "co2_kg": 1.2, "cost_eur": 1.09},
            "servers": {"energy_kwh": 3.5, "co2_kg": 1.3, "cost_eur": 1.23},
            "other": {"energy_kwh": 1.6, "co2_kg": 0.6, "cost_eur": 0.56},
        },
        "last_week_same_day_kwh": {"heating": 8.0, "lighting": 3.3, "servers": 3.7, "other": 1.7},
        "score": {"value": 82, "energy": 0.86, "carbon": 0.81, "comfort": 0.78},
        "this_week": {"energy_kwh": 103.3, "co2_kg": 39.3, "cost_eur": 36.15},
        "last_week": {"energy_kwh": 109.9, "co2_kg": 41.8, "cost_eur": 38.50},
        "week_by_category_kwh": {"heating": 49.6, "lighting": 20.7, "servers": 22.7, "other": 10.3},
        "daily_kwh": [
            17.9, 16.9, 16.4, 16.8, 15.6, 12.9, 12.3, 18.1, 17.0, 16.6, 16.2, 15.4, 12.7, 12.2, 17.7,
            16.5, 14.0, 17.9, 16.8, 13.2, 12.5, 18.8, 16.7, 15.9, 15.6, 14.8, 12.1, 11.6, 17.6, 15.7,
        ],
        "hourly_today": {
            "heating": [0.06] * 7 + [0.20, 0.30, 0.35, 0.40, 0.50, 1.00, 2.40, 1.00, 0.30, 0.15, 0.10, 0.08] + [0.06] * 5,
            "lighting": [0.03] * 7
            + [0.14, 0.20, 0.22, 0.22, 0.22, 0.22, 0.22, 0.22, 0.22, 0.22, 0.22, 0.20, 0.16, 0.12]
            + [0.03] * 3,
            "servers": [0.14] * 7 + [0.15] * 6 + [0.16, 0.16] + [0.15] * 4 + [0.14] * 5,
            "other": [0.04] * 7 + [0.06, 0.08, 0.10, 0.10, 0.10, 0.11, 0.11, 0.10, 0.10, 0.10, 0.08, 0.08] + [0.04] * 5,
        },
        # Peak readings from previous days; alerts are raised when a reading exceeds the limit.
        "peak_readings": [
            ("2024-05-13T02:10", "servers", 3.8),
            ("2024-05-12T09:30", "other", 0.9),
            ("2024-05-10T14:05", "heating", 1.9),
            ("2024-05-08T03:20", "servers", 3.3),
            ("2024-05-06T18:40", "lighting", 1.1),
        ],
    },
    "lecture-hall-a": {
        "source": "demo",
        "today": {"energy_kwh": 12.4, "co2_kg": 4.7, "cost_eur": 4.34, "change_pct": -5},
        "savings_today": {"eur": 0.25, "co2_kg": 0.3, "change_pct": -5},
        "today_by_category": {
            "heating": {"energy_kwh": 6.4, "co2_kg": 2.4, "cost_eur": 2.24},
            "lighting": {"energy_kwh": 3.7, "co2_kg": 1.4, "cost_eur": 1.30},
            "servers": {"energy_kwh": 0.8, "co2_kg": 0.3, "cost_eur": 0.28},
            "other": {"energy_kwh": 1.5, "co2_kg": 0.6, "cost_eur": 0.52},
        },
        "last_week_same_day_kwh": {"heating": 6.8, "lighting": 3.9, "servers": 0.8, "other": 1.6},
        "score": {"value": 80, "energy": 0.80, "carbon": 0.77, "comfort": 0.84},
        "this_week": {"energy_kwh": 72.9, "co2_kg": 27.7, "cost_eur": 25.52},
        "last_week": {"energy_kwh": 65.0, "co2_kg": 24.7, "cost_eur": 22.75},
        "week_by_category_kwh": {"heating": 37.9, "lighting": 21.9, "servers": 4.4, "other": 8.7},
        "daily_kwh": [
            13.8, 13.3, 13.0, 13.2, 11.5, 4.7, 4.3, 13.1, 12.6, 12.3, 12.5, 11.0, 4.5, 4.1, 13.5,
            13.0, 5.0, 12.9, 11.3, 4.6, 4.2, 13.9, 13.1, 13.1, 13.3, 11.6, 4.8, 4.4, 13.3, 12.4,
        ],
        "hourly_today": None,
        "peak_readings": [
            ("2024-05-13T08:00", "heating", 2.3),
            ("2024-05-10T19:30", "lighting", 0.9),
            ("2024-05-09T10:15", "other", 0.7),
        ],
    },
    "lab-building": {
        "source": "demo",
        "today": {"energy_kwh": 21.3, "co2_kg": 8.1, "cost_eur": 7.46, "change_pct": -5},
        "savings_today": {"eur": 0.39, "co2_kg": 0.4, "change_pct": -5},
        "today_by_category": {
            "heating": {"energy_kwh": 7.4, "co2_kg": 2.8, "cost_eur": 2.59},
            "lighting": {"energy_kwh": 3.2, "co2_kg": 1.2, "cost_eur": 1.12},
            "servers": {"energy_kwh": 8.1, "co2_kg": 3.1, "cost_eur": 2.84},
            "other": {"energy_kwh": 2.6, "co2_kg": 1.0, "cost_eur": 0.91},
        },
        "last_week_same_day_kwh": {"heating": 7.9, "lighting": 3.4, "servers": 8.3, "other": 2.8},
        "score": {"value": 73, "energy": 0.72, "carbon": 0.70, "comfort": 0.80},
        "this_week": {"energy_kwh": 139.2, "co2_kg": 52.9, "cost_eur": 48.72},
        "last_week": {"energy_kwh": 131.8, "co2_kg": 50.1, "cost_eur": 46.13},
        "week_by_category_kwh": {"heating": 48.7, "lighting": 20.9, "servers": 52.9, "other": 16.7},
        "daily_kwh": [
            23.3, 22.6, 22.1, 22.5, 21.0, 14.6, 14.2, 22.1, 21.5, 21.1, 21.4, 20.0, 13.9, 13.5, 22.8,
            22.1, 15.1, 22.0, 20.6, 14.3, 13.9, 23.5, 22.4, 22.4, 22.7, 21.2, 14.8, 14.4, 22.4, 21.3,
        ],
        "hourly_today": None,
        "peak_readings": [
            ("2024-05-13T03:15", "servers", 3.9),
            ("2024-05-11T22:40", "other", 1.2),
            ("2024-05-09T13:00", "heating", 1.8),
        ],
    },
}

COACH = {"source": "OpenAI", "response_time_s": 2.1}

COACH_ADVICE = {
    "library": {
        "heating": {
            "action": "Lower the heating by 1 °C between 13:00 and 17:00",
            "saving_kwh": 1.1,
            "saving_pct": 7,
            "benefit": "and keeps the rooms comfortable",
        },
        "lighting": {
            "action": "Turn off the lab lights after 20:00",
            "saving_kwh": 0.2,
            "saving_pct": 1,
            "benefit": "without changing opening hours",
        },
        "servers": {
            "action": "Check the server room at night, where usage reached 3.8 kWh at 02:10",
            "saving_kwh": 0.3,
            "saving_pct": 2,
            "benefit": "once the night peak is fixed",
        },
    },
    "lecture-hall-a": {
        "heating": {
            "action": "Start the heating 30 minutes later on lecture days",
            "saving_kwh": 0.6,
            "saving_pct": 5,
            "benefit": "and the hall is still warm for the first lecture",
        },
        "lighting": {
            "action": "Switch off the hall lights after the last lecture",
            "saving_kwh": 0.4,
            "saving_pct": 3,
            "benefit": "without affecting evening events",
        },
        "servers": {
            "action": "Put the lecture recording PCs into standby at night",
            "saving_kwh": 0.1,
            "saving_pct": 1,
            "benefit": "and they wake up before the first lecture",
        },
    },
    "lab-building": {
        "heating": {
            "action": "Lower the heating by 1 °C in labs that are empty after 16:00",
            "saving_kwh": 0.9,
            "saving_pct": 4,
            "benefit": "and keeps the occupied labs comfortable",
        },
        "lighting": {
            "action": "Turn off the corridor lights after 21:00",
            "saving_kwh": 0.3,
            "saving_pct": 1,
            "benefit": "while emergency lighting stays on",
        },
        "servers": {
            "action": "Shut down idle test benches after 18:00",
            "saving_kwh": 1.2,
            "saving_pct": 6,
            "benefit": "and frees capacity in the server room",
        },
    },
}

COACH_TIPS = {
    "library": [
        "Lower heating 1 °C, 13:00–17:00",
        "Turn off lab lights after 20:00",
        "Check server room at night",
    ],
    "lecture-hall-a": [
        "Start heating 30 min later on lecture days",
        "Switch off hall lights after the last lecture",
        "Put recording PCs into standby at night",
    ],
    "lab-building": [
        "Shut down idle test benches after 18:00",
        "Lower heating 1 °C in empty labs",
        "Turn off corridor lights after 21:00",
    ],
}
