"""Identifiers and choices that S2 accepts in URLs, forms and API requests."""
from zoneinfo import ZoneInfo

APP_VERSION = "1.0.0"

TIMEZONE = ZoneInfo("Europe/Berlin")

BUILDINGS = {
    "library": "Library",
    "lecture-hall-a": "Lecture Hall A",
    "lab-building": "Lab Building",
}
DEFAULT_BUILDING = "library"

CATEGORIES = {
    "heating": "Heating",
    "lighting": "Lighting",
    "servers": "Servers",
    "other": "Other",
}

TONES = {
    "encouraging": "Encouraging",
    "analytical": "Analytical",
    "strict": "Strict",
}

COACH_STATUSES = {
    "online": "Online",
    "fallback": "Fallback",
    "cached": "Cached",
}

HISTORY_PERIODS = {
    "today": "Today",
    "7d": "Last 7 days",
    "30d": "Last 30 days",
}

# Number of days covered by each aggregate period, ending on the report date.
PERIOD_DAYS = {"today": 1, "week": 7, "7d": 7, "30d": 30}

MAX_QUESTION_LENGTH = 500

# Tooltip text for the metrics that need explaining (formulas from the S1 section of the report).
METRIC_HELP = {
    "score": "Weighted mix of energy, carbon and comfort, from 0 to 100. "
             "Red below 60, amber 60 to 80, green above 80.",
    "energy": "E, weight 0.40: target kWh per m² divided by actual kWh per m², at most 1. "
              "1.00 means the building is at or below its target.",
    "carbon": "C, weight 0.35: target CO₂ divided by actual CO₂, at most 1.",
    "comfort": "K, weight 0.25: average comfort index. 1.0 at 21 °C, falling to 0 at 16 °C or 26 °C.",
    "co2": "Energy use × 0.38 kg CO₂ per kWh, the approximate German grid average.",
}
