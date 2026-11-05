"""Turns service results into display values and Chart.js-ready data.

Templates and JSON routes both use these functions, so numbers are formatted
the same way everywhere and chart data is built in one place.
"""
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from subsystems.s2_web.catalog import BUILDINGS, CATEGORIES, METRIC_HELP, TIMEZONE

MINUS = "−"


def iso(moment):
    return moment.isoformat(timespec="seconds")


def number(value, decimals=1):
    text = f"{abs(value):.{decimals}f}"
    if value < 0 and float(text) != 0:
        return MINUS + text
    return text


def reading(value):
    """kWh reading with one decimal, or two when one would hide the difference (0.22 not 0.2)."""
    return number(value, 1 if round(value, 1) == round(value, 2) else 2)


def signed(value, decimals=1):
    if round(value, decimals) > 0:
        return "+" + number(value, decimals)
    return number(value, decimals)


def euro(value):
    return f"€{value:.2f}"


def money(value):
    """Euro amount that keeps its sign in front of the symbol, e.g. −€0.20."""
    return (MINUS if round(value, 2) < 0 else "") + euro(abs(value))


def trend(change):
    if change < 0:
        return "down"
    if change > 0:
        return "up"
    return "flat"


def percent_change(new, old):
    return round((new - old) / old * 100)


def building_info(building_id, source):
    return {"id": building_id, "name": BUILDINGS[building_id], "data": source}


def metric(value, unit, display, change_pct, compared_to):
    return {
        "value": value,
        "unit": unit,
        "display": display,
        "change_pct": change_pct,
        "change_display": f"{abs(change_pct)}%",
        "trend": trend(change_pct),
        "compared_to": compared_to,
    }


def week_savings(comparison):
    """€ and kg CO₂ saved this week against last week. Negative when this week used more."""
    last, this = comparison["last_week"], comparison["this_week"]
    eur = round(last["cost_eur"] - this["cost_eur"], 2)
    co2 = round(last["co2_kg"] - this["co2_kg"], 1)
    return {"eur": eur, "co2_kg": co2, "display": money(eur), "co2_display": number(co2), "negative": eur < 0}


def kpi_cards(kpis, category=None, trend=None, weeks=None):
    values = kpis["by_category"][category] if category else kpis
    change = values["change_pct"]
    savings = kpis["savings"]
    cards = {
        "energy": metric(values["energy_kwh"], "kWh", number(values["energy_kwh"]), change, "vs last week"),
        "co2": {**metric(values["co2_kg"], "kg", number(values["co2_kg"]), change, "vs last week"), "help": METRIC_HELP["co2"]},
        "cost": metric(values["cost_eur"], "EUR", euro(values["cost_eur"]), change, "vs last week"),
        "savings": {
            **metric(savings["eur"], "EUR", money(savings["eur"]), savings["change_pct"], "vs normal use"),
            "co2_kg": savings["co2_kg"],
            "co2_display": number(savings["co2_kg"]),
            "negative": savings["eur"] < 0,
            "scope": "building",
        },
    }
    if weeks:
        cards["savings"]["week"] = week_savings(weeks)
    if trend:
        days = [day_label(entry["date"]) for entry in trend]
        for name, key, show in (
            ("energy", "energy_kwh", lambda v: f"{number(v)} kWh"),
            ("co2", "co2_kg", lambda v: f"{number(v)} kg"),
            ("cost", "cost_eur", euro),
            ("savings", "savings_eur", euro),
        ):
            cards[name]["spark"] = sparkline([entry[key] for entry in trend], days, show)
    return cards


SPARK_WIDTH = 200
SPARK_HEIGHT = 44
SPARK_PADDING = 6


def sparkline(values, days, show):
    """SVG paths for a small smooth trend line and its filled area, plus a text description.

    Coordinates use a 200 × 44 viewBox that the page stretches to the card width. The line
    stops 8 units before the right edge so the dot marking today stays inside the card.
    """
    usable = SPARK_WIDTH - 8
    low, high = min(values), max(values)
    spread = (high - low) or 1
    step = usable / (len(values) - 1)
    points = [
        (index * step, SPARK_PADDING + (high - value) / spread * (SPARK_HEIGHT - 2 * SPARK_PADDING))
        for index, value in enumerate(values)
    ]
    # Catmull-Rom curve through every point, written as cubic Bézier segments.
    line = f"M{points[0][0]:.1f},{points[0][1]:.1f}"
    for index in range(len(points) - 1):
        before = points[max(index - 1, 0)]
        start, end = points[index], points[index + 1]
        after = points[min(index + 2, len(points) - 1)]
        first = (start[0] + (end[0] - before[0]) / 6, start[1] + (end[1] - before[1]) / 6)
        second = (end[0] - (after[0] - start[0]) / 6, end[1] - (after[1] - start[1]) / 6)
        line += f" C{first[0]:.1f},{first[1]:.1f} {second[0]:.1f},{second[1]:.1f} {end[0]:.1f},{end[1]:.1f}"
    last_x, last_y = points[-1]
    return {
        "line": line,
        "area": f"{line} L{last_x:.1f},{SPARK_HEIGHT} L0,{SPARK_HEIGHT} Z",
        "end_x": round(last_x / SPARK_WIDTH * 100, 2),
        "end_y": round(last_y / SPARK_HEIGHT * 100, 2),
        "label": f"Last {len(values)} days: " + ", ".join(f"{day} {show(value)}" for day, value in zip(days, values)),
    }


def score_band(value):
    """Colour band of the score gauge: below 60 red, 60 to 80 amber, above 80 green."""
    if value < 60:
        band, label = "red", "Needs attention"
    elif value <= 80:
        band, label = "amber", "Fair"
    else:
        band, label = "green", "Good"
    return {"band": band, "label": label, "needle_deg": round(max(0, min(value, 100)) * 1.8 - 90, 1)}


def score_payload(score):
    weights = score["weights"]
    measured_at = score["measured_at"].astimezone(TIMEZONE)
    return {
        "label": "Building score",
        "scope": "building",
        "score": score["live"],
        "display": number(score["live"], 1),
        "band": score_band(score["live"]),
        "reference_band": score_band(score["reference"]),
        "reference_score": score["reference"],
        "help": METRIC_HELP["score"],
        "target": score["target"],
        "components": {
            name: {"value": value, "display": f"{value:.2f}", "weight": weights[name], "help": METRIC_HELP[name]}
            for name, value in score["components"].items()
        },
        "formula": f"Score = 100 × ({weights['energy']:.2f}·E + {weights['carbon']:.2f}·C + {weights['comfort']:.2f}·K)",
        "measured_at": iso(measured_at),
        "time_display": measured_at.strftime("%H:%M:%S"),
    }


def hourly_chart(points, label, comparison=None, comparison_label=None, limit=None):
    labels = [moment.strftime("%H:%M") for moment, _ in points]
    values = [value for _, value in points]
    datasets = [{"key": "primary", "label": label, "data": values}]
    if comparison:
        datasets.append({"key": "comparison", "label": comparison_label, "data": [value for _, value in comparison]})

    above = []
    if limit is not None:
        above = [index for index, value in enumerate(values) if value is not None and value > limit]

    return {
        "type": "line",
        "labels": labels,
        "datasets": datasets,
        "unit": "kWh",
        "x_title": "Hour",
        "y_title": "kWh",
        "limit": None if limit is None else {"value": limit, "label": f"Limit: {number(limit)} kWh"},
        "above_limit": above,
        "summary": hourly_summary(labels, values, limit, above),
    }


def hourly_summary(labels, values, limit, above):
    readings = [(label, value) for label, value in zip(labels, values) if value is not None]
    if not readings:
        return "No readings for this day."
    peak_label, peak = max(readings, key=lambda reading: reading[1])
    text = f"Total {number(sum(value for _, value in readings))} kWh. Peak {number(peak, 2)} kWh at {peak_label}."
    if limit is not None:
        if above:
            hours = ", ".join(labels[index] for index in above)
            text += f" Above the {number(limit)} kWh limit at {hours}."
        else:
            text += f" No hour above the {number(limit)} kWh limit."
    missing = len(values) - len(readings)
    if missing:
        text += f" {missing} hours without data."
    return text


def day_label(day):
    return f"{day:%a} {day.day} {day:%b}"


def daily_chart(days):
    """Stacked bars of kWh per day, one segment per device type.

    `days` is a list of (date, {category: kWh}) pairs, oldest first.
    """
    categories = [name for name in CATEGORIES if any(name in parts for _, parts in days)]
    totals = [round(sum(parts.values()), 1) for _, parts in days]
    peak_index = max(range(len(days)), key=lambda index: totals[index])
    return {
        "type": "bar",
        "stacked": True,
        "labels": [day_label(day) for day, _ in days],
        "categories": categories,
        "datasets": [
            {"key": name, "label": CATEGORIES[name], "data": [round(parts.get(name, 0), 2) for _, parts in days]}
            for name in categories
        ],
        "totals": totals,
        "unit": "kWh",
        "x_title": "Day",
        "y_title": "kWh",
        "limit": None,
        "above_limit": [],
        "summary": f"Total {number(sum(totals))} kWh over {len(days)} days. "
        f"Highest: {number(totals[peak_index])} kWh on {day_label(days[peak_index][0])}.",
    }


def category_rows(totals):
    total = sum(totals.values())
    return [
        {
            "id": name,
            "label": CATEGORIES[name],
            "kwh": totals[name],
            "share_pct": round(totals[name] / total * 100) if total else 0,
        }
        for name in CATEGORIES
        if name in totals
    ]


def category_chart(rows):
    return {
        "type": "bar",
        "labels": [row["label"] for row in rows],
        "categories": [row["id"] for row in rows],
        "datasets": [{"key": "share", "label": "Share of total", "data": [row["share_pct"] for row in rows]}],
        "unit": "%",
        "x_title": "Device type",
        "y_title": "%",
        "limit": None,
        "above_limit": [],
        "summary": ", ".join(f"{row['label']} {row['share_pct']}% ({number(row['kwh'])} kWh)" for row in rows) + ".",
    }


def when_label(moment, today):
    days_ago = (today - moment.date()).days
    if days_ago == 0:
        return f"Today {moment:%H:%M}"
    if days_ago == 1:
        return f"Yesterday {moment:%H:%M}"
    return f"{day_label(moment)}, {moment:%H:%M}"


def alert_rows(alerts, today):
    rows = []
    for alert in alerts:
        name = CATEGORIES[alert["category"]]
        rows.append({
            "time": iso(alert["time"]),
            "time_label": when_label(alert["time"], today),
            "category": alert["category"],
            "category_label": name,
            "value_kwh": alert["value_kwh"],
            "limit_kwh": alert["limit_kwh"],
            "value_display": f"{reading(alert['value_kwh'])} kWh",
            "limit_display": f"{reading(alert['limit_kwh'])} kWh",
            "message": f"{name} above limit: {reading(alert['value_kwh'])} kWh",
        })
    return rows


BANNER_LINES = 3


def alert_banner(alerts):
    """Dashboard banner listing today's alerts (latest first), or None when there are none.

    `key` names the exact set of alerts, so the page can tell a new alert from one
    the user already dismissed.
    """
    if not alerts:
        return None
    first = alerts[0]
    name = CATEGORIES[first["category"]]
    if len(alerts) == 1:
        title = f"{name} is above the limit at {first['time']:%H:%M}."
        text = (f"The {name.lower()} load ({reading(first['value_kwh'])} kWh) exceeds "
                f"the defined limit of {reading(first['limit_kwh'])} kWh.")
    else:
        title = f"{len(alerts)} readings are above their limits today."
        text = "Latest first."
    lines = [
        f"{alert['time']:%H:%M} {CATEGORIES[alert['category']]}: {reading(alert['value_kwh'])} kWh, "
        f"limit {reading(alert['limit_kwh'])} kWh"
        for alert in alerts[:BANNER_LINES]
    ]
    if len(alerts) > BANNER_LINES:
        lines.append(f"and {len(alerts) - BANNER_LINES} more")
    key = ";".join(f"{iso(alert['time'])}/{alert['category']}" for alert in alerts)
    return {"key": key, "title": title, "text": text, "lines": lines if len(alerts) > 1 else []}


def week_rows(comparison):
    rows = []
    for label, key, decimals in (("Energy (kWh)", "energy_kwh", 1), ("CO₂ (kg)", "co2_kg", 1), ("Cost (€)", "cost_eur", 2)):
        last, this = comparison["last_week"][key], comparison["this_week"][key]
        change = percent_change(this, last)
        rows.append({
            "label": label,
            "last_week": number(last, decimals),
            "this_week": number(this, decimals),
            "change_display": f"{signed(change, 0)}%",
            "trend": trend(change),
        })
    return rows


def scenario_rows(result):
    rows = []
    for label, key, decimals in (("Energy (kWh)", "energy_kwh", 1), ("CO₂ (kg)", "co2_kg", 1), ("Cost (€)", "cost_eur", 2)):
        before, after = result["before"][key], result["after"][key]
        difference = round(after - before, decimals)
        change = percent_change(after, before)
        rows.append({
            "key": key,
            "label": label,
            "before": number(before, decimals),
            "after": number(after, decimals),
            "change_display": f"{signed(difference, decimals)} ({signed(change, 0)}%)",
            "trend": trend(difference),
            "good": difference <= 0,
        })
    points = result["after"]["score"] - result["before"]["score"]
    rows.append({
        "key": "score",
        "label": "Score",
        "before": str(result["before"]["score"]),
        "after": str(result["after"]["score"]),
        "change_display": signed(points, 0),
        "trend": trend(points),
        "good": points >= 0,
    })
    return rows


def scenario_summary(heating_change, lighting_pct, result):
    steps = []
    if heating_change < 0:
        steps.append(f"lowering the heating by {abs(heating_change):g} °C")
    elif heating_change > 0:
        steps.append(f"raising the heating by {heating_change:g} °C")
    if lighting_pct:
        steps.append(f"reducing lighting by {lighting_pct}%")
    if not steps:
        return "No changes entered, so the values stay as they are today."

    before, after = result["before"], result["after"]
    difference = round(after["energy_kwh"] - before["energy_kwh"], 1)
    change = percent_change(after["energy_kwh"], before["energy_kwh"])
    if difference < 0:
        effect = f"save about {number(-difference)} kWh per day ({signed(change, 0)}%)"
    elif difference > 0:
        effect = f"add about {number(difference)} kWh per day ({signed(change, 0)}%)"
    else:
        effect = "keep energy use about the same"

    if after["score"] > before["score"]:
        score = f"increase the score to {after['score']}"
    elif after["score"] < before["score"]:
        score = f"lower the score to {after['score']}"
    else:
        score = f"keep the score at {after['score']}"

    sentence = " and ".join(steps)
    return f"{sentence[0].upper()}{sentence[1:]} could {effect} and {score}."


def split_advice(answer):
    """Split a coach answer into its first sentence (headline) and the rest."""
    first, separator, rest = answer.partition(". ")
    if not separator:
        return answer, ""
    return first + ".", rest


class ChartPresenter:
    """Shapes service results for the templates and for Chart.js.

    The module functions above do the actual formatting. This class gives the
    pages one object to call and keeps the display timezone in one place.
    """

    def __init__(self, timezone="Europe/Berlin"):
        self._timezone = None
        self.timezone = timezone

    @property
    def timezone(self):
        """IANA name of the zone that chart labels and timestamps are shown in."""
        return self._timezone

    @timezone.setter
    def timezone(self, name):
        if not isinstance(name, str) or not name:
            raise ValueError("timezone must be a non-empty IANA zone name such as 'Europe/Berlin'.")
        try:
            self._zone = ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError(f"Unknown timezone '{name}'.") from None
        self._timezone = name

    def localize(self, moment):
        """Return the moment in the display timezone, leaving naive values unchanged."""
        return moment.astimezone(self._zone) if moment.tzinfo else moment

    def now(self):
        return datetime.now(self._zone)

    def to_line_chart(self, points, label, comparison=None, comparison_label=None, limit=None):
        points = [(self.localize(moment), value) for moment, value in points]
        return hourly_chart(points, label, comparison, comparison_label, limit)

    def to_bar_chart(self, totals):
        return category_chart(category_rows(totals))

    def to_daily_chart(self, days):
        return daily_chart(days)

    def sparkline(self, values, days, show):
        return sparkline(values, days, show)

    def kpi_cards(self, kpis, category=None, trend=None, weeks=None):
        return kpi_cards(kpis, category, trend, weeks)

    def score_payload(self, score):
        return score_payload(score)

    def alert_rows(self, alerts, today):
        return alert_rows(alerts, today)
