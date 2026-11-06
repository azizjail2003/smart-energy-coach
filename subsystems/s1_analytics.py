"""Subsystem 1 (S1): Energy Simulation and Analytics Engine."""

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


def _parse_datetime(value: datetime | str) -> datetime:
    """Parse minute-format or standard DATETIME timestamp values."""
    if isinstance(value, datetime):
        return value
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M")
    except ValueError:
        return datetime.fromisoformat(str(value))


@dataclass
class EnergyReading:
    """Validated energy measurement shared by analytics and web templates."""

    timestamp: datetime
    device_type: str
    kwh: float
    room_temp: float
    co2_kg: float
    sustainability_score: int
    building_id: str = config.DEFAULT_BUILDING_ID

    def __post_init__(self) -> None:
        if isinstance(self.timestamp, str):
            self.timestamp = _parse_datetime(self.timestamp)

    @property
    def score(self) -> int:
        return self.sustainability_score

    def validate(self) -> bool:
        if not isinstance(self.timestamp, datetime):
            raise ValueError("Timestamp must be a valid datetime.")
        if self.kwh < 0:
            raise ValueError("Energy reading (kWh) cannot be negative.")
        if not (0.0 <= self.room_temp <= 45.0):
            raise ValueError("Room temperature out of realistic bounds (0-45 C).")
        if self.device_type not in config.DEVICES:
            raise ValueError(f"Unknown device type: {self.device_type}")
        if not isinstance(self.building_id, str) or not self.building_id.strip():
            raise ValueError("Building ID must be a non-empty string.")
        return True

    def to_dict(self) -> dict:
        return asdict(self)


class ScoreCalculator:
    """Calculate deterministic energy, carbon, cost, and comfort metrics."""

    def __init__(self) -> None:
        self.co2_factor: float = config.CO2_FACTOR_KG_PER_KWH
        self.cost_factor: float = config.COST_EUR_PER_KWH
        self.cost_per_kwh: float = config.COST_EUR_PER_KWH
        self.ideal_temp: float = config.IDEAL_TEMP_C

    def calc_co2(self, kwh: float) -> float:
        return round(kwh * self.co2_factor, 2)

    def calc_cost(self, kwh: float) -> float:
        return round(kwh * self.cost_factor, 2)

    def calc_comfort(self, room_temp: float) -> float:
        diff = abs(room_temp - self.ideal_temp)
        return round(max(0.0, min(1.0, 1.0 - (diff / 10.0))), 2)

    def calc_sustainability_score(self, total_hourly_kwh: float, room_temp: float) -> dict:
        e_sub = round(max(0.0, min(1.0, 1.0 - (total_hourly_kwh / 4.0))), 2)
        c_sub = round(max(0.0, min(1.0, 1.0 - ((total_hourly_kwh * self.co2_factor) / 1.6))), 2)
        k_sub = self.calc_comfort(room_temp)
        total_score = int(round(100 * (0.40 * e_sub + 0.35 * c_sub + 0.25 * k_sub)))
        return {"score": total_score, "E": e_sub, "C": c_sub, "K": k_sub}


class EnergySimulator:
    """Generate deterministic synthetic energy readings for campus devices."""

    def __init__(self, calculator: ScoreCalculator | None = None, seed: int = config.RANDOM_SEED) -> None:
        self.calculator: ScoreCalculator = calculator or ScoreCalculator()
        self.seed = seed
        self._rng = random.Random(seed)
        self.devices: list[str] = list(config.DEVICES)
        self.base_loads: dict[str, float] = {"Heating": 1.4, "Lighting": 0.5, "Servers": 1.1, "Other": 0.3}

    def set_seed(self, seed: int) -> None:
        self.seed = seed
        self._rng = random.Random(seed)

    def generate_reading(self, device: str, ts: datetime | int | str | None = None, building_id: str = config.DEFAULT_BUILDING_ID) -> EnergyReading:
        if ts is None:
            dt = datetime.now()
        elif isinstance(ts, int):
            dt = datetime.now().replace(hour=ts % 24, minute=0, second=0, microsecond=0)
        elif isinstance(ts, str):
            dt = _parse_datetime(ts)
        else:
            dt = ts
        daytime_multiplier = 1.4 if 8 <= dt.hour <= 18 else 0.6
        base = self.base_loads.get(device, 0.5)
        kwh = round(base * daytime_multiplier * self._rng.uniform(0.85, 1.25), 2)
        temp = round(21.0 + self._rng.uniform(-1.5, 2.0), 1)
        dt = dt.replace(second=0, microsecond=0)
        reading = EnergyReading(dt, device, kwh, temp, self.calculator.calc_co2(kwh), self.calculator.calc_sustainability_score(kwh, temp)["score"], building_id)
        reading.validate()
        return reading

    def seed_history(self, days: int = 14, building_id: str = config.DEFAULT_BUILDING_ID, reference_time: datetime | None = None) -> list[EnergyReading]:
        now = (reference_time or datetime.now()).replace(minute=0, second=0, microsecond=0)
        return [self.generate_reading(dev, now - timedelta(hours=hour), building_id) for hour in range(days * 24, 0, -1) for dev in self.devices]


class SQLiteRepository:
    """Offline repository adapter used when S3 does not inject MySQL."""

    def __init__(self, db_path: str) -> None:
        self.db_path = str(db_path)
        directory = os.path.dirname(self.db_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS energy_readings (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, building_id TEXT NOT NULL, device_type TEXT NOT NULL, kwh REAL NOT NULL, room_temp REAL NOT NULL, co2_kg REAL NOT NULL, sustainability_score INTEGER NOT NULL)")
            conn.execute("CREATE TABLE IF NOT EXISTS alert_thresholds (building_id TEXT NOT NULL, device_type TEXT NOT NULL, limit_kwh REAL NOT NULL, PRIMARY KEY (building_id, device_type))")

    def count_readings(self, building_id: str) -> int:
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM energy_readings WHERE building_id = ?", (building_id,)).fetchone()[0]

    def insert_readings(self, readings: list[EnergyReading]) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany("INSERT INTO energy_readings (timestamp, building_id, device_type, kwh, room_temp, co2_kg, sustainability_score) VALUES (?, ?, ?, ?, ?, ?, ?)", [(r.timestamp.strftime("%Y-%m-%d %H:%M"), r.building_id, r.device_type, r.kwh, r.room_temp, r.co2_kg, r.sustainability_score) for r in readings])

    def fetch_readings(self, building_id: str, limit: int | None = None) -> list[dict]:
        query = "SELECT * FROM energy_readings WHERE building_id = ? ORDER BY timestamp DESC, id DESC"
        params: tuple = (building_id,)
        if limit is not None:
            query += " LIMIT ?"
            params += (limit,)
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = [dict(row) for row in conn.execute(query, params).fetchall()]
        for row in rows:
            row["timestamp"] = _parse_datetime(row["timestamp"])
        return rows

    def get_limits_for_building(self, building_id: str) -> dict[str, float]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT device_type, limit_kwh FROM alert_thresholds WHERE building_id = ?", (building_id,)).fetchall()
        return {device: float(limit) for device, limit in rows}

    def save_limit(self, building_id: str, device_type: str, limit: float) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT OR REPLACE INTO alert_thresholds VALUES (?, ?, ?)", (building_id, device_type, limit))


class AlertMonitor:
    """Load and apply per-building alert thresholds."""

    def __init__(self, repository, default_limits: dict[str, float] | None = None):
        self.repository = repository
        self.default_limits = dict(default_limits or config.DEFAULT_LIMITS)

    def get_limits_for_building(self, building_id: str = config.DEFAULT_BUILDING_ID) -> dict[str, float]:
        stored = self.repository.get_limits_for_building(building_id)
        merged = {device: float(self.default_limits.get(device, 2.0)) for device in config.DEVICES}
        merged.update({device: float(value) for device, value in stored.items()})
        return merged

    def check_alerts(self, building_id: str = config.DEFAULT_BUILDING_ID, readings: list[dict | EnergyReading] | None = None, limits: dict[str, float] | None = None) -> list[dict]:
        if isinstance(building_id, dict):
            limits, building_id = building_id, config.DEFAULT_BUILDING_ID
        effective = {**self.get_limits_for_building(building_id), **(limits or {})}
        rows = readings if readings is not None else self.repository.fetch_readings(building_id, 16)
        alerts = []
        for row in rows[:16]:
            data = row.to_dict() if isinstance(row, EnergyReading) else row
            data["timestamp"] = _parse_datetime(data["timestamp"])
            device = data["device_type"]
            limit = float(effective.get(device, 2.0))
            if data["kwh"] > limit:
                alerts.append({"building_id": building_id, "timestamp": data["timestamp"], "device_type": device, "kwh": data["kwh"], "limit": limit, "message": f"{device} above limit: {data['kwh']} kWh (Limit: {limit} kWh)"})
        return alerts


class AnalyticsService:
    """Facade over an injected repository or the local SQLite adapter."""

    def __init__(self, db_or_repo=None, seed: int = config.RANDOM_SEED) -> None:
        self.db_path = str(db_or_repo) if isinstance(db_or_repo, (str, os.PathLike)) else config.DB_PATH
        self.repository = db_or_repo if db_or_repo is not None and not isinstance(db_or_repo, (str, os.PathLike)) else SQLiteRepository(self.db_path)
        self.calculator = ScoreCalculator()
        self.simulator = EnergySimulator(self.calculator, seed)
        self.alert_monitor = AlertMonitor(self.repository)

    def save_reading(self, reading: EnergyReading) -> None:
        reading.validate()
        self.repository.insert_readings([reading])

    def seed_if_empty(self, days: int = 14, building_id: str = config.DEFAULT_BUILDING_ID) -> int:
        if self.repository.count_readings(building_id) > 0:
            return 0
        readings = self.simulator.seed_history(days, building_id)
        for reading in readings:
            reading.validate()
        self.repository.insert_readings(readings)
        return len(readings)

    def simulate_live_step(self, building_id: str = config.DEFAULT_BUILDING_ID) -> list[dict]:
        now = datetime.now()
        results = []
        for device in config.DEVICES:
            reading = self.simulator.generate_reading(device, now, building_id)
            self.save_reading(reading)
            results.append(reading.to_dict())
        return results

    def check_alerts(self, building_id: str = config.DEFAULT_BUILDING_ID, limits: dict | None = None, recent_rows: list | None = None) -> list[dict]:
        if isinstance(building_id, dict):
            limits, building_id = building_id, config.DEFAULT_BUILDING_ID
        return self.alert_monitor.check_alerts(building_id, recent_rows, limits)

    @staticmethod
    def _dt(row: dict) -> datetime:
        return _parse_datetime(row["timestamp"])

    def _window(self, rows: list[dict], start: datetime, end: datetime) -> list[dict]:
        return [row for row in rows if start <= self._dt(row) < end]

    def _totals(self, rows: list[dict]) -> dict:
        energy = round(sum(row["kwh"] for row in rows), 2)
        return {"energy_kwh": energy, "co2_kg": self.calculator.calc_co2(energy), "cost_eur": self.calculator.calc_cost(energy)}

    def get_aggregates(self, period: str = "week", category: str | None = None, building_id: str = config.DEFAULT_BUILDING_ID) -> dict:
        if period in config.BUILDINGS and category is None:
            building_id, period = period, "week"
        period = (period or "week").lower()
        hours_by_period = {"day": 24, "week": 168, "month": 720}
        window_hours = hours_by_period.get(period, 168)
        rows = self.repository.fetch_readings(building_id)
        selected_category = None
        if category and category.lower() != "all":
            selected_category = next(
                (device for device in config.DEVICES if device.lower() == category.lower()),
                category,
            )
        if not rows:
            return {
                "hourly_series": [],
                "last_week_hourly_series": [],
                "daily_totals": {},
                "weekly_totals": {},
                "by_device_week": {},
                "period": period,
                "category": selected_category,
            }
        latest = max(self._dt(row) for row in rows)
        if selected_category is not None:
            rows = [row for row in rows if row["device_type"] == selected_category]
        def series(source: list[dict]) -> list[dict]:
            grouped = {}
            for row in source:
                stamp = self._dt(row).replace(minute=0, second=0, microsecond=0)
                item = grouped.setdefault(stamp, {"timestamp": stamp, "kwh": 0.0, "by_device": {device: 0.0 for device in config.DEVICES}})
                item["kwh"] += row["kwh"]
                item["by_device"][row["device_type"]] += row["kwh"]
            return [{**item, "kwh": round(item["kwh"], 2), "by_device": {key: round(value, 2) for key, value in item["by_device"].items()}} for item in sorted(grouped.values(), key=lambda item: item["timestamp"])]
        hourly = self._window(rows, latest - timedelta(hours=min(window_hours - 1, 23)), latest + timedelta(hours=1))
        last_hourly = self._window(rows, latest - timedelta(days=7, hours=min(window_hours - 1, 23)), latest - timedelta(days=7) + timedelta(hours=1))
        today = self._totals(hourly)
        previous = self._totals(last_hourly)
        versus = round(((today["energy_kwh"] - previous["energy_kwh"]) / previous["energy_kwh"]) * 100, 1) if previous["energy_kwh"] else 0.0
        week = self._window(rows, latest - timedelta(hours=window_hours - 1), latest + timedelta(hours=1))
        return {"hourly_series": series(hourly), "last_week_hourly_series": series(last_hourly), "daily_totals": {"today": today, "last_week": previous, "vs_last_week_pct": versus}, "weekly_totals": self._totals(week), "by_device_week": {device: round(sum(row["kwh"] for row in week if row["device_type"] == device), 2) for device in config.DEVICES}, "period": period, "category": selected_category or category}

    def compute_week_over_week(self, building_id: str = config.DEFAULT_BUILDING_ID) -> dict:
        rows = self.repository.fetch_readings(building_id)
        empty = {"energy_kwh": 0.0, "co2_kg": 0.0, "cost_eur": 0.0}
        if not rows:
            return {"this_week": empty.copy(), "last_week": empty.copy(), "change_pct": {key: 0.0 for key in empty}}
        latest = max(self._dt(row) for row in rows)
        this_week = self._totals(self._window(rows, latest - timedelta(hours=167), latest + timedelta(hours=1)))
        last_week = self._totals(self._window(rows, latest - timedelta(hours=335), latest - timedelta(hours=167)))
        return {"this_week": this_week, "last_week": last_week, "change_pct": {key: round(((this_week[key] - last_week[key]) / last_week[key]) * 100, 1) if last_week[key] else 0.0 for key in this_week}}

    def get_dashboard_summary(self, building_id: str = config.DEFAULT_BUILDING_ID, limits: dict | None = None) -> dict:
        if isinstance(building_id, dict):
            limits, building_id = building_id, config.DEFAULT_BUILDING_ID
        rows = self.repository.fetch_readings(building_id, 32)
        for row in rows:
            row["timestamp"] = _parse_datetime(row["timestamp"])
        aggregates = self.get_aggregates(building_id=building_id)
        week_over_week = self.compute_week_over_week(building_id)
        if not rows:
            return {"building_id": building_id, "energy_today": 0.0, "co2_today": 0.0, "cost_today": 0.0, "savings_eur": 0.0, "savings_co2": 0.0, "score": 80, "E": 0.8, "C": 0.8, "K": 0.8, "room_temp": 21.0, "by_device": {}, "alerts": [], "recent_rows": [], "vs_last_week_pct": 0.0, "this_week_by_device": {}, **aggregates, "week_over_week": week_over_week}
        latest = rows[:16]
        by_device = {device: round(sum(row["kwh"] for row in latest if row["device_type"] == device), 2) for device in config.DEVICES}
        energy = round(sum(by_device.values()), 2)
        avg_temp = round(sum(row["room_temp"] for row in rows[:4]) / len(rows[:4]), 1)
        parts = self.calculator.calc_sustainability_score(energy / 8.0, avg_temp)
        saved = max(0.0, config.BASELINE_DAILY_KWH - energy)
        return {"building_id": building_id, "energy_today": energy, "co2_today": self.calculator.calc_co2(energy), "cost_today": self.calculator.calc_cost(energy), "savings_eur": self.calculator.calc_cost(saved), "savings_co2": self.calculator.calc_co2(saved), "score": parts["score"], "E": parts["E"], "C": parts["C"], "K": parts["K"], "room_temp": avg_temp, "by_device": by_device, "alerts": self.check_alerts(building_id, limits, latest), "recent_rows": rows, "vs_last_week_pct": aggregates["daily_totals"].get("vs_last_week_pct", 0.0), "this_week_by_device": aggregates["by_device_week"], **aggregates, "week_over_week": week_over_week}

    def get_score(self, building_id: str = config.DEFAULT_BUILDING_ID) -> dict:
        rows = self.repository.fetch_readings(building_id, 16)
        if not rows:
            return {"score": 80, "E": 0.8, "C": 0.8, "K": 0.8, "room_temp": 21.0, "building_id": building_id}
        energy = round(sum(row["kwh"] for row in rows), 2)
        room_temp = round(sum(row["room_temp"] for row in rows[:4]) / len(rows[:4]), 1)
        score = self.calculator.calc_sustainability_score(energy / 8.0, room_temp)
        return {**score, "room_temp": room_temp, "building_id": building_id}

    def get_alerts(self, building_id: str = config.DEFAULT_BUILDING_ID, limits: dict | None = None, recent_rows: list | None = None) -> list[dict]:
        return self.check_alerts(building_id=building_id, limits=limits, recent_rows=recent_rows)

    def estimate_scenario(self, changes: dict, building_id: str = config.DEFAULT_BUILDING_ID) -> dict:
        scenario_building = changes.get("building_id", building_id)
        summary = changes.get("summary")
        if summary is None:
            summary = self.get_dashboard_summary(building_id=scenario_building)
        heating_delta = changes.get("heating_delta_c")
        if heating_delta is None:
            heating_delta = changes.get("heating_delta", 0.0)
        light_reduction = changes.get("light_reduction_pct")
        if light_reduction is None:
            light_reduction = changes.get("lighting_reduction", 0.0)
        return self.simulate_scenario(summary, heating_delta, light_reduction, scenario_building)

    def simulate_scenario(
            self,
            current_summary: dict | float | str | None = None,
            heating_delta_c: float = 0.0,
            light_reduction_pct: float | str | None = None,
            building_id: str = config.DEFAULT_BUILDING_ID,
        ) -> dict:
            if isinstance(current_summary, (int, float)):
                if isinstance(light_reduction_pct, str):
                    building_id = light_reduction_pct
                    light_reduction_pct = heating_delta_c
                elif light_reduction_pct is None:
                    light_reduction_pct = heating_delta_c
                heating_delta_c = float(current_summary)
                current_summary = self.get_dashboard_summary(building_id)
            elif isinstance(current_summary, str):
                building_id = current_summary
                current_summary = self.get_dashboard_summary(building_id)
            elif current_summary is None:
                current_summary = self.get_dashboard_summary(building_id)
            if not isinstance(current_summary, dict):
                raise TypeError("current_summary must be a dashboard summary dict, numeric delta, or building_id str.")

            light_pct = float(light_reduction_pct or 0.0)
            before = current_summary.get("energy_today") or 15.7
            devices = current_summary.get("by_device") or {}
            after = round(
                max(
                    1.0,
                    before
                    + devices.get("Heating", 7.0) * heating_delta_c * 0.06
                    - devices.get("Lighting", 3.0) * (light_pct / 100.0),
                ),
                2,
            )
            score = self.calculator.calc_sustainability_score(
                after / 8.0, current_summary.get("room_temp", 21.0) + heating_delta_c
            )["score"]
            return {
                "before_kwh": before,
                "after_kwh": after,
                "before_co2": self.calculator.calc_co2(before),
                "after_co2": self.calculator.calc_co2(after),
                "before_cost": self.calculator.calc_cost(before),
                "after_cost": self.calculator.calc_cost(after),
                "before_score": current_summary.get("score", 80),
                "after_score": score,
            }
