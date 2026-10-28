"""Stage 1 energy data model for the Energy Simulation and Analytics Engine."""

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
import os
from pathlib import Path
import random
import sqlite3
import sys

try:
    import config
except ModuleNotFoundError as error:
    if error.name != "config":
        raise
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import config


@dataclass
class EnergyReading:
    """Validated energy measurement shared by analytics and web templates."""

    timestamp: str
    device_type: str
    kwh: float
    room_temp: float
    co2_kg: float
    sustainability_score: int

    @property
    def score(self) -> int:
        """Return the sustainability score using the UML-compatible name."""
        return self.sustainability_score

    def validate(self) -> bool:
        """Validate the reading before it is written to SQLite.

        Raises:
            ValueError: If energy, temperature, or device data is invalid.
        """
        # FR10 and NFR4: reject measurements that would compromise data integrity.
        if self.kwh < 0:
            raise ValueError("Energy reading (kWh) cannot be negative.")
        if not (0.0 <= self.room_temp <= 45.0):
            raise ValueError("Room temperature out of realistic bounds (0-45 C).")
        if self.device_type not in config.DEVICES:
            raise ValueError(f"Unknown device type: {self.device_type}")
        return True

    def to_dict(self) -> dict:
        """Return the reading as a standard dictionary for template use."""
        # NFR6: use the standard dictionary contract shared with other subsystems.
        # NFR8 and NFR9: typed fields and clear documentation keep the contract readable.
        return asdict(self)


class ScoreCalculator:
    """Calculate deterministic energy, carbon, cost, and comfort metrics."""

    def __init__(self) -> None:
        """Load scoring constants from the shared configuration module."""
        # NFR5: keep business constants configurable without changing the engine.
        self.co2_factor: float = config.CO2_FACTOR_KG_PER_KWH
        self.cost_factor: float = config.COST_EUR_PER_KWH
        self.cost_per_kwh: float = config.COST_EUR_PER_KWH
        self.ideal_temp: float = config.IDEAL_TEMP_C

    def calc_co2(self, kwh: float) -> float:
        """Return carbon emissions in kilograms for the supplied energy use."""
        # FR3 and NFR2: this pure calculation has no side effects or external state.
        return round(kwh * self.co2_factor, 2)

    def calc_cost(self, kwh: float) -> float:
        """Return energy cost in EUR for the supplied energy use."""
        # FR3 and NFR2: use the configured price and return a stable rounded value.
        return round(kwh * self.cost_factor, 2)

    def calc_comfort(self, room_temp: float) -> float:
        """Return a comfort index from 0.0 to 1.0 around the ideal temperature."""
        # FR4 and NFR2: clamp the deterministic comfort score to its valid range.
        diff = abs(room_temp - self.ideal_temp)
        return round(max(0.0, min(1.0, 1.0 - (diff / 10.0))), 2)

    def calc_sustainability_score(
        self, total_hourly_kwh: float, room_temp: float
    ) -> dict:
        """Return weighted sustainability subscores and the overall score."""
        # FR5, NFR1, and NFR2: combine normalized efficiency and comfort metrics.
        e_sub = round(max(0.0, min(1.0, 1.0 - (total_hourly_kwh / 4.0))), 2)
        c_sub = round(
            max(
                0.0,
                min(1.0, 1.0 - ((total_hourly_kwh * self.co2_factor) / 1.6)),
            ),
            2,
        )
        k_sub = self.calc_comfort(room_temp)
        total_score = int(round(100 * (0.40 * e_sub + 0.35 * c_sub + 0.25 * k_sub)))
        return {"score": total_score, "E": e_sub, "C": c_sub, "K": k_sub}


class EnergySimulator:
    """Generate realistic synthetic energy readings for campus devices."""

    def __init__(self, calculator: ScoreCalculator | None = None) -> None:
        """Configure the simulator with a calculator and device load profiles."""
        self.calculator: ScoreCalculator = calculator or ScoreCalculator()
        self.devices: list[str] = list(config.DEVICES)
        self.base_loads: dict[str, float] = {
            "Heating": 1.4,
            "Lighting": 0.5,
            "Servers": 1.1,
            "Other": 0.3,
        }

    def generate_reading(
        self, device: str, ts: datetime | int | None = None
    ) -> EnergyReading:
        """Generate and validate one synthetic reading for a device."""
        if ts is None:
            dt = datetime.now()
        elif isinstance(ts, int):
            dt = datetime.now().replace(
                hour=ts % 24, minute=0, second=0, microsecond=0
            )
        else:
            dt = ts

        hour = dt.hour
        daytime_multiplier = 1.4 if 8 <= hour <= 18 else 0.6
        base = self.base_loads.get(device, 0.5)
        kwh = round(base * daytime_multiplier * random.uniform(0.85, 1.25), 2)
        temp = round(21.0 + random.uniform(-1.5, 2.0), 1)
        co2 = self.calculator.calc_co2(kwh)
        score_info = self.calculator.calc_sustainability_score(kwh, temp)

        reading = EnergyReading(
            timestamp=dt.strftime("%Y-%m-%d %H:%M"),
            device_type=device,
            kwh=kwh,
            room_temp=temp,
            co2_kg=co2,
            sustainability_score=score_info["score"],
        )
        reading.validate()
        return reading

    def seed_history(self, days: int = 7) -> list[EnergyReading]:
        """Generate readings for each device every three hours in past days."""
        now = datetime.now().replace(minute=0, second=0, microsecond=0)
        readings: list[EnergyReading] = []
        for h in range(days * 24, 0, -3):
            ts = now - timedelta(hours=h)
            for dev in self.devices:
                readings.append(self.generate_reading(dev, ts))
        return readings


class AnalyticsService:
    """Facade for energy persistence, dashboard analytics, and scenarios."""

    def __init__(self, db_path: str = config.DB_PATH) -> None:
        """Initialize calculators and ensure the service database is ready."""
        self.db_path: str = db_path
        self.calculator: ScoreCalculator = ScoreCalculator()
        self.simulator: EnergySimulator = EnergySimulator(self.calculator)
        self._ensure_table()

    def _ensure_table(self) -> None:
        """Create the energy table and its parent directory when necessary."""
        directory = os.path.dirname(self.db_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS energy_readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    device_type TEXT NOT NULL,
                    kwh REAL NOT NULL,
                    room_temp REAL NOT NULL,
                    co2_kg REAL NOT NULL,
                    sustainability_score INTEGER NOT NULL
                )
                """
            )
        conn.close()

    def save_reading(self, reading: EnergyReading) -> None:
        """Validate and persist one energy reading."""
        reading.validate()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO energy_readings
                    (timestamp, device_type, kwh, room_temp, co2_kg,
                     sustainability_score)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    reading.timestamp,
                    reading.device_type,
                    reading.kwh,
                    reading.room_temp,
                    reading.co2_kg,
                    reading.sustainability_score,
                ),
            )
        conn.close()

    def seed_if_empty(self, days: int = 7) -> int:
        """Seed historical readings only when the table has no rows."""
        with sqlite3.connect(self.db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM energy_readings").fetchone()[0]
        conn.close()
        if count > 0:
            return 0

        readings = self.simulator.seed_history(days)
        for reading in readings:
            reading.validate()
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                """
                INSERT INTO energy_readings
                    (timestamp, device_type, kwh, room_temp, co2_kg,
                     sustainability_score)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        reading.timestamp,
                        reading.device_type,
                        reading.kwh,
                        reading.room_temp,
                        reading.co2_kg,
                        reading.sustainability_score,
                    )
                    for reading in readings
                ],
            )
        conn.close()
        return len(readings)

    def simulate_live_step(self) -> list[dict]:
        """Generate, save, and return one current reading per device."""
        now = datetime.now()
        results: list[dict] = []
        for dev in config.DEVICES:
            reading = self.simulator.generate_reading(dev, now)
            self.save_reading(reading)
            results.append(reading.to_dict())
        return results

    def check_alerts(
        self, limits: dict | None = None, recent_rows: list | None = None
    ) -> list[dict]:
        """Return threshold alerts for the latest readings."""
        effective_limits = {**config.DEFAULT_LIMITS, **(limits or {})}
        if recent_rows is None:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                recent_rows = conn.execute(
                    "SELECT * FROM energy_readings ORDER BY id DESC LIMIT 16"
                ).fetchall()
            conn.close()

        alerts: list[dict] = []
        for row in recent_rows[:16]:
            device = row["device_type"]
            limit = effective_limits.get(device, 2.0)
            if row["kwh"] > limit:
                alerts.append(
                    {
                        "timestamp": row["timestamp"],
                        "device_type": device,
                        "kwh": row["kwh"],
                        "limit": limit,
                        "message": (
                            f"{device} above limit: {row['kwh']} kWh "
                            f"(Limit: {limit} kWh)"
                        ),
                    }
                )
        return alerts

    def get_dashboard_summary(self, limits: dict | None = None) -> dict:
        """Return dashboard KPIs, device totals, alerts, and recent rows."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM energy_readings ORDER BY id DESC LIMIT 32"
            ).fetchall()
        conn.close()

        if not rows:
            return {
                "energy_today": 0,
                "co2_today": 0,
                "cost_today": 0,
                "savings_eur": 0,
                "savings_co2": 0,
                "score": 80,
                "E": 0.8,
                "C": 0.8,
                "K": 0.8,
                "room_temp": 21.0,
                "by_device": {},
                "alerts": [],
                "recent_rows": [],
            }

        latest_rows = rows[:16]
        by_device = {device: 0.0 for device in config.DEVICES}
        for row in latest_rows:
            device = row["device_type"]
            by_device[device] = round(by_device.get(device, 0.0) + row["kwh"], 2)

        energy_today = round(sum(by_device.values()), 2)
        co2_today = self.calculator.calc_co2(energy_today)
        cost_today = self.calculator.calc_cost(energy_today)
        newest_rows = rows[:4]
        avg_temp = round(
            sum(row["room_temp"] for row in newest_rows) / len(newest_rows), 1
        )
        score_parts = self.calculator.calc_sustainability_score(
            energy_today / 8.0, avg_temp
        )
        saved_kwh = max(0.0, config.BASELINE_DAILY_KWH - energy_today)
        alerts = self.check_alerts(limits=limits, recent_rows=latest_rows)
        return {
            "energy_today": energy_today,
            "co2_today": co2_today,
            "cost_today": cost_today,
            "savings_eur": self.calculator.calc_cost(saved_kwh),
            "savings_co2": self.calculator.calc_co2(saved_kwh),
            "score": score_parts["score"],
            "E": score_parts["E"],
            "C": score_parts["C"],
            "K": score_parts["K"],
            "room_temp": avg_temp,
            "by_device": by_device,
            "alerts": alerts,
            "recent_rows": [dict(row) for row in rows],
        }

    def simulate_scenario(
        self,
        current_summary: dict | float,
        heating_delta_c: float = 0.0,
        light_reduction_pct: float | None = None,
    ) -> dict:
        """Project energy, cost, carbon, and score for a what-if scenario."""
        if isinstance(current_summary, (int, float)) and light_reduction_pct is None:
            light_reduction_pct = heating_delta_c
            heating_delta_c = current_summary
            current_summary = self.get_dashboard_summary()

        assert isinstance(current_summary, dict)
        light_reduction_pct = light_reduction_pct or 0.0
        before_kwh = current_summary.get("energy_today") or 15.7
        by_dev = current_summary.get("by_device") or {}
        heating_kwh = by_dev.get("Heating", 7.0)
        lighting_kwh = by_dev.get("Lighting", 3.0)
        heating_change = heating_kwh * (heating_delta_c * 0.06)
        lighting_change = -lighting_kwh * (light_reduction_pct / 100.0)
        after_kwh = round(max(1.0, before_kwh + heating_change + lighting_change), 2)
        new_temp = current_summary.get("room_temp", 21.0) + heating_delta_c
        after_score = self.calculator.calc_sustainability_score(
            after_kwh / 8.0, new_temp
        )["score"]
        return {
            "before_kwh": before_kwh,
            "after_kwh": after_kwh,
            "before_co2": self.calculator.calc_co2(before_kwh),
            "after_co2": self.calculator.calc_co2(after_kwh),
            "before_cost": self.calculator.calc_cost(before_kwh),
            "after_cost": self.calculator.calc_cost(after_kwh),
            "before_score": current_summary.get("score", 80),
            "after_score": after_score,
        }
