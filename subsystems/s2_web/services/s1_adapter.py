"""Adapter that gives S2 its numbers from the real S1 analytics engine.

S1 stores one reading per device and hour, with device names like "Heating"
and timestamps without a timezone. S2's pages expect the same contract as
MockAnalyticsService, with names like "heating" and aware datetimes. This
class translates between the two and uses S1's own methods where one exists.
"""
from datetime import datetime, time, timedelta

from subsystems.s1_analytics import AnalyticsService
from subsystems.s2_web.catalog import BUILDINGS, CATEGORIES, PERIOD_DAYS, TIMEZONE

# S2 category key -> S1 device name
DEVICES = {"heating": "Heating", "lighting": "Lighting", "servers": "Servers", "other": "Other"}
CATEGORY_OF = {device: category for category, device in DEVICES.items()}
SCORE_WEIGHTS = {"energy": 0.40, "carbon": 0.35, "comfort": 0.25}
SCORE_TARGET = 90
HISTORY_DAYS = 31  # enough for the 30-day History view


def percent_change(new, old):
    return round((new - old) / old * 100) if old else 0


class S1AnalyticsAdapter:
    """S2's analytics contract on top of S1's AnalyticsService."""

    def __init__(self, db_path):
        self._services = {}
        self._cache = {}  # readings per building, read once per request
        for index, building in enumerate(BUILDINGS):
            # A different seed per building so the three buildings do not show identical data.
            service = AnalyticsService(db_path, seed=42 + index)
            service.seed_if_empty(HISTORY_DAYS, building)
            self._services[building] = service

    # -- readings ----------------------------------------------------------------------

    def _service(self, building_id):
        if building_id not in self._services:
            raise ValueError(f"Unknown building '{building_id}'.")
        return self._services[building_id]

    def _rows(self, building_id):
        """All readings of a building as (aware datetime, category, kWh, room temperature)."""
        if building_id in self._cache:
            return self._cache[building_id]
        rows = []
        for row in self._service(building_id).repository.fetch_readings(building_id):
            moment = self._aware(row["timestamp"])
            rows.append((moment, CATEGORY_OF[row["device_type"]], row["kwh"], row["room_temp"]))
        self._cache[building_id] = rows
        return rows

    @staticmethod
    def _aware(moment):
        """S1 timestamps are local time without a zone; S2 works with Europe/Berlin times."""
        if isinstance(moment, str):
            moment = datetime.fromisoformat(moment)
        return moment.replace(tzinfo=TIMEZONE)

    def _report_date(self, building_id):
        return max(moment for moment, *_ in self._rows(building_id)).date()

    def _day_totals(self, building_id, day, until_hour=None):
        """kWh per category on one day, optionally only up to a given hour."""
        totals = dict.fromkeys(CATEGORIES, 0.0)
        for moment, category, kwh, _ in self._rows(building_id):
            if moment.date() == day and (until_hour is None or moment.hour <= until_hour):
                totals[category] += kwh
        return {name: round(kwh, 2) for name, kwh in totals.items()}

    def _figures(self, building_id, kwh):
        calculator = self._service(building_id).calculator
        return {"energy_kwh": round(kwh, 1), "co2_kg": round(calculator.calc_co2(kwh), 1),
                "cost_eur": calculator.calc_cost(kwh)}

    # -- S2 contract ---------------------------------------------------------------------

    def get_kpis(self, building_id):
        day = self._report_date(building_id)
        last_hour = max(moment for moment, *_ in self._rows(building_id)).hour
        # Today is still running, so compare with the same hours one week earlier.
        today = self._day_totals(building_id, day, last_hour)
        before = self._day_totals(building_id, day - timedelta(days=7), last_hour)
        by_category = {
            name: {**self._figures(building_id, today[name]), "change_pct": percent_change(today[name], before[name])}
            for name in CATEGORIES
        }
        total, total_before = sum(today.values()), sum(before.values())
        saved = total_before - total
        calculator = self._service(building_id).calculator
        return {
            "date": day,
            "source": "s1",
            **self._figures(building_id, total),
            "change_pct": percent_change(total, total_before),
            "savings": {"eur": calculator.calc_cost(saved), "co2_kg": round(calculator.calc_co2(saved), 1),
                        "change_pct": percent_change(total, total_before)},
            "by_category": by_category,
        }

    def get_daily_trend(self, building_id, days=7, category=None):
        end = self._report_date(building_id)
        calculator = self._service(building_id).calculator
        trend = []
        for offset in range(days - 1, -1, -1):
            day = end - timedelta(days=offset)
            totals = self._day_totals(building_id, day)
            energy = totals[category] if category else sum(totals.values())
            baseline = sum(self._day_totals(building_id, day - timedelta(days=7)).values())
            trend.append({"date": day, **self._figures(building_id, energy),
                          "savings_eur": calculator.calc_cost(baseline - sum(totals.values()))})
        return trend

    def get_score(self, building_id):
        score = self._service(building_id).get_score(building_id)  # S1's own score method
        return {
            "reference": score["score"],
            "live": float(score["score"]),
            "target": SCORE_TARGET,
            "components": {"energy": score["E"], "carbon": score["C"], "comfort": score["K"]},
            "weights": dict(SCORE_WEIGHTS),
            "measured_at": datetime.now(TIMEZONE),
        }

    def get_hourly(self, building_id, day, category=None):
        if category is not None and category not in CATEGORIES:
            raise ValueError(f"Unknown category '{category}'.")
        rows = self._rows(building_id)
        first, last = min(m for m, *_ in rows).date(), max(m for m, *_ in rows).date()
        if not first <= day <= last:
            raise ValueError(f"No data for {day}. Available days: {first} to {last}.")
        hours = [None] * 24  # hours without a reading stay empty in the chart
        for moment, name, kwh, _ in rows:
            if moment.date() == day and (category is None or name == category):
                hours[moment.hour] = round((hours[moment.hour] or 0) + kwh, 2)
        midnight = datetime.combine(day, time(), TIMEZONE)
        return [(midnight + timedelta(hours=hour), value) for hour, value in enumerate(hours)]

    def get_aggregates(self, building_id, period="week", category=None):
        if period not in PERIOD_DAYS:
            raise ValueError(f"Unknown period '{period}'.")
        end = self._report_date(building_id)
        totals = dict.fromkeys(CATEGORIES, 0.0)
        for offset in range(PERIOD_DAYS[period]):
            for name, kwh in self._day_totals(building_id, end - timedelta(days=offset)).items():
                totals[name] += kwh
        totals = {name: round(kwh, 1) for name, kwh in totals.items()}
        return {category: totals[category]} if category else totals

    def get_week_comparison(self, building_id):
        # S1's own week-over-week method (rolling 7 × 24 hours).
        weeks = self._service(building_id).compute_week_over_week(building_id)
        end = self._report_date(building_id)
        pick = lambda part: {key: weeks[part][key] for key in ("energy_kwh", "co2_kg", "cost_eur")}
        return {"this_week": pick("this_week"), "last_week": pick("last_week"),
                "this_week_start": end - timedelta(days=6), "last_week_start": end - timedelta(days=13)}

    def get_alerts(self, building_id, limit=10):
        # S1's own alert check over all readings, with the limits saved in S1.
        alerts = [
            {"time": self._aware(alert["timestamp"]), "category": CATEGORY_OF[alert["device_type"]],
             "value_kwh": alert["kwh"], "limit_kwh": alert["limit"]}
            for alert in self._service(building_id).get_alerts(building_id)
        ]
        alerts.sort(key=lambda alert: alert["time"], reverse=True)
        return alerts[:limit]

    def estimate_scenario(self, building_id, heating_change_c, lighting_reduction_pct):
        kpis = self.get_kpis(building_id)
        score = self.get_score(building_id)
        temps = [temp for moment, _, _, temp in self._rows(building_id) if moment.date() == kpis["date"]]
        # Give S1's scenario method today's full-day figures so before/after match the dashboard.
        summary = {
            "energy_today": kpis["energy_kwh"],
            "by_device": {DEVICES[name]: values["energy_kwh"] for name, values in kpis["by_category"].items()},
            "room_temp": round(sum(temps) / len(temps), 1),
            "score": score["reference"],
        }
        changes = {"summary": summary, "heating_delta_c": heating_change_c, "light_reduction_pct": lighting_reduction_pct}
        result = self._service(building_id).estimate_scenario(changes, building_id)  # S1's report method
        return {
            "before": {"energy_kwh": round(result["before_kwh"], 1), "co2_kg": round(result["before_co2"], 1),
                       "cost_eur": result["before_cost"], "score": result["before_score"]},
            "after": {"energy_kwh": round(result["after_kwh"], 1), "co2_kg": round(result["after_co2"], 1),
                      "cost_eur": result["after_cost"], "score": result["after_score"]},
        }

    def get_limits(self, building_id):
        limits = self._service(building_id).alert_monitor.get_limits_for_building(building_id)
        return {CATEGORY_OF[device]: value for device, value in limits.items()}

    def save_limits(self, building_id, limits):
        unknown = set(limits) - set(DEVICES)
        if unknown:
            raise ValueError(f"Unknown categories: {', '.join(sorted(unknown))}.")
        repository = self._service(building_id).repository
        for name, value in limits.items():
            repository.save_limit(building_id, DEVICES[name], float(value))
