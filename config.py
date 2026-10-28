"""Shared configuration for the Smart Energy Coach application."""

import os

from dotenv import load_dotenv

load_dotenv()


DEVICES = ["Heating", "Lighting", "Servers", "Other"]

CO2_FACTOR_KG_PER_KWH = 0.38
COST_EUR_PER_KWH = 0.35
IDEAL_TEMP_C = 21.0

DB_PATH = os.getenv("DB_PATH", "data/energy.db")
DEFAULT_LIMITS = {
	"Heating": 2.0,
	"Lighting": 0.8,
	"Servers": 3.5,
	"Other": 1.0,
}
BASELINE_DAILY_KWH = 18.0

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
