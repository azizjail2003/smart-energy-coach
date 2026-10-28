"""Identifiers and choices that S2 accepts in URLs, forms and API requests."""
from zoneinfo import ZoneInfo

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
