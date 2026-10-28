"""Turns service results into display values and Chart.js-ready data.

Templates and JSON routes both use these functions, so numbers are formatted
the same way everywhere and chart data is built in one place.
"""
from app.catalog import BUILDINGS, CATEGORIES, TIMEZONE

MINUS = "−"


def iso(moment):
    return moment.isoformat(timespec="seconds")


def number(value, decimals=1):
    text = f"{abs(value):.{decimals}f}"
    if value < 0 and float(text) != 0:
        return MINUS + text
    return text


def signed(value, decimals=1):
    if round(value, decimals) > 0:
        return "+" + number(value, decimals)
    return number(value, decimals)


def euro(value):
    return f"€{value:.2f}"


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


def kpi_cards(kpis, category=None):
    values = kpis["by_category"][category] if category else kpis
    change = values["change_pct"]
    savings = kpis["savings"]
    return {
        "energy": metric(values["energy_kwh"], "kWh", number(values["energy_kwh"]), change, "vs last week"),
        "co2": metric(values["co2_kg"], "kg", number(values["co2_kg"]), change, "vs last week"),
        "cost": metric(values["cost_eur"], "EUR", euro(values["cost_eur"]), change, "vs last week"),
        "savings": {
            **metric(savings["eur"], "EUR", euro(savings["eur"]), savings["change_pct"], "vs normal use"),
            "co2_kg": savings["co2_kg"],
            "co2_display": number(savings["co2_kg"]),
            "scope": "building",
        },
    }


def score_payload(score):
    weights = score["weights"]
    measured_at = score["measured_at"].astimezone(TIMEZONE)
    return {
        "label": "Building score",
        "scope": "building",
        "score": score["live"],
        "display": number(score["live"], 1),
        "reference_score": score["reference"],
        "target": score["target"],
        "components": {
            name: {"value": value, "display": f"{value:.2f}", "weight": weights[name]}
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
    labels = [day_label(day) for day, _ in days]
    values = [total for _, total in days]
    peak_day, peak = max(days, key=lambda item: item[1])
    return {
        "type": "bar",
        "labels": labels,
        "datasets": [{"key": "primary", "label": "Energy use", "data": values}],
        "unit": "kWh",
        "x_title": "Day",
        "y_title": "kWh",
        "limit": None,
        "above_limit": [],
        "summary": f"Total {number(sum(values))} kWh over {len(days)} days. "
        f"Highest: {number(peak)} kWh on {day_label(peak_day)}.",
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
            "value_display": f"{number(alert['value_kwh'])} kWh",
            "limit_display": f"{number(alert['limit_kwh'])} kWh",
            "message": f"{name} above limit: {number(alert['value_kwh'])} kWh",
        })
    return rows


def alert_banner(alert):
    name = CATEGORIES[alert["category"]]
    return {
        "title": f"{name} is above the limit at {alert['time']:%H:%M}.",
        "text": f"The {name.lower()} load ({number(alert['value_kwh'])} kWh) exceeds "
        f"the defined limit of {number(alert['limit_kwh'])} kWh.",
    }


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
