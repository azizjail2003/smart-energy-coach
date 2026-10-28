import random
from datetime import date, datetime, time, timedelta

from app.catalog import CATEGORIES, PERIOD_DAYS, TIMEZONE
from . import mock_data as data


def distribute(total, weights):
    """Split a total by weights, rounded to 0.01, so the parts still add up to the total."""
    scale = total / sum(weights)
    parts = [round(weight * scale, 2) for weight in weights]
    largest = parts.index(max(parts))
    parts[largest] = round(parts[largest] + total - sum(parts), 2)
    return parts


def percent_change(new, old):
    return round((new - old) / old * 100)


class MockAnalyticsService:
    """Provisional S1 (analytics) interface backed by mock_data.

    `state` is a dict-like store for the current browser session. The app passes
    the Flask session so that saved limits survive across requests and workers.
    """

    def __init__(self, state=None):
        self.state = state if state is not None else {}

    def get_kpis(self, building_id):
        building = self._building(building_id)
        by_category = {}
        for category, values in building["today_by_category"].items():
            last_week = building["last_week_same_day_kwh"][category]
            by_category[category] = {**values, "change_pct": percent_change(values["energy_kwh"], last_week)}
        return {
            "date": data.DEMO_DATE,
            "source": building["source"],
            **building["today"],
            "savings": dict(building["savings_today"]),
            "by_category": by_category,
        }

    def get_score(self, building_id):
        score = self._building(building_id)["score"]
        # Simulated live reading: the reference score plus a small fluctuation.
        live = round(score["value"] + random.uniform(-0.5, 0.5), 1)
        return {
            "reference": score["value"],
            "live": live,
            "target": data.SCORE_TARGET,
            "components": {name: score[name] for name in data.SCORE_WEIGHTS},
            "weights": dict(data.SCORE_WEIGHTS),
            "measured_at": datetime.now(TIMEZONE),
        }

    def get_hourly(self, building_id, day, category=None):
        building = self._building(building_id)
        if not data.FIRST_DATE <= day <= data.DEMO_DATE:
            raise ValueError(f"No data for {day}. Available days: {data.FIRST_DATE} to {data.DEMO_DATE}.")
        if category is not None and category not in CATEGORIES:
            raise ValueError(f"Unknown category '{category}'.")

        series = self._hourly_by_category(building, day)
        if category:
            values = series[category]
        else:
            values = [round(sum(hour), 2) for hour in zip(*series.values())]
        midnight = datetime.combine(day, time(), TIMEZONE)
        return [(midnight + timedelta(hours=hour), value) for hour, value in enumerate(values)]

    def get_aggregates(self, building_id, period="week", category=None):
        building = self._building(building_id)
        if period not in PERIOD_DAYS:
            raise ValueError(f"Unknown period '{period}'.")

        if period in ("week", "7d"):
            totals = dict(building["week_by_category_kwh"])
        else:
            totals = dict.fromkeys(CATEGORIES, 0.0)
            for day in self._days(PERIOD_DAYS[period]):
                for name, kwh in self._day_by_category(building, day).items():
                    totals[name] += kwh
            totals = {name: round(kwh, 1) for name, kwh in totals.items()}

        if category:
            return {category: totals[category]}
        return totals

    def get_week_comparison(self, building_id):
        building = self._building(building_id)
        return {
            "this_week": dict(building["this_week"]),
            "last_week": dict(building["last_week"]),
            "this_week_start": data.DEMO_DATE - timedelta(days=6),
            "last_week_start": data.DEMO_DATE - timedelta(days=13),
        }

    def get_alerts(self, building_id, limit=10):
        building = self._building(building_id)
        limits = self.get_limits(building_id)

        readings = []
        for category, values in self._hourly_by_category(building, data.DEMO_DATE).items():
            for hour, kwh in enumerate(values):
                readings.append((datetime.combine(data.DEMO_DATE, time(hour), TIMEZONE), category, kwh))
        for timestamp, category, kwh in building["peak_readings"]:
            readings.append((datetime.fromisoformat(timestamp).replace(tzinfo=TIMEZONE), category, kwh))

        alerts = [
            {"time": moment, "category": category, "value_kwh": kwh, "limit_kwh": limits[category]}
            for moment, category, kwh in readings
            if kwh > limits[category]
        ]
        alerts.sort(key=lambda alert: alert["time"], reverse=True)
        return alerts[:limit]

    def estimate_scenario(self, building_id, heating_change_c: float, lighting_reduction_pct: int):
        building = self._building(building_id)
        today = building["today"]
        heating_kwh = building["today_by_category"]["heating"]["energy_kwh"]
        lighting_kwh = building["today_by_category"]["lighting"]["energy_kwh"]

        saved_kwh = (
            heating_kwh * data.HEATING_SAVING_PER_DEGREE * -heating_change_c
            + lighting_kwh * lighting_reduction_pct / 100
        )
        energy_after = round(today["energy_kwh"] - saved_kwh, 1)
        ratio = energy_after / today["energy_kwh"]
        saved_pct = saved_kwh / today["energy_kwh"] * 100
        score_before = building["score"]["value"]
        score_after = round(score_before + data.SCORE_POINTS_PER_SAVED_PCT * saved_pct)

        return {
            "before": {
                "energy_kwh": today["energy_kwh"],
                "co2_kg": today["co2_kg"],
                "cost_eur": today["cost_eur"],
                "score": score_before,
            },
            "after": {
                "energy_kwh": energy_after,
                "co2_kg": round(today["co2_kg"] * ratio, 1),
                "cost_eur": round(today["cost_eur"] * ratio, 2),
                "score": max(0, min(100, score_after)),
            },
        }

    def get_limits(self, building_id):
        self._building(building_id)
        saved = self.state.get("limits", {}).get(building_id, {})
        return {**data.DEFAULT_LIMITS, **saved}

    def save_limits(self, building_id, limits):
        self._building(building_id)
        unknown = set(limits) - set(data.DEFAULT_LIMITS)
        if unknown:
            raise ValueError(f"Unknown categories: {', '.join(sorted(unknown))}.")
        all_limits = dict(self.state.get("limits", {}))
        all_limits[building_id] = {name: float(value) for name, value in limits.items()}
        # Assign a new dict so the Flask session notices the change.
        self.state["limits"] = all_limits

    def _building(self, building_id):
        if building_id not in data.BUILDINGS:
            raise ValueError(f"Unknown building '{building_id}'.")
        return data.BUILDINGS[building_id]

    def _days(self, count):
        return [data.DEMO_DATE - timedelta(days=offset) for offset in range(count - 1, -1, -1)]

    def _daily_total(self, building, day: date):
        return building["daily_kwh"][(day - data.FIRST_DATE).days]

    def _day_by_category(self, building, day):
        if day == data.DEMO_DATE:
            return {name: values["energy_kwh"] for name, values in building["today_by_category"].items()}
        if day == data.DEMO_DATE - timedelta(days=7):
            return dict(building["last_week_same_day_kwh"])
        week = building["week_by_category_kwh"]
        parts = distribute(self._daily_total(building, day), [week[name] for name in CATEGORIES])
        return dict(zip(CATEGORIES, parts))

    def _hourly_by_category(self, building, day):
        if day == data.DEMO_DATE and building["hourly_today"]:
            return building["hourly_today"]
        daily = self._day_by_category(building, day)
        return {name: distribute(daily[name], data.HOURLY_PROFILES[name]) for name in CATEGORIES}
