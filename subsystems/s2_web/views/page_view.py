"""PageView: builds the data behind every page and JSON endpoint of the web interface."""
from datetime import timedelta

from subsystems.s2_web.catalog import CATEGORIES, HISTORY_PERIODS, PERIOD_DAYS
from subsystems.s2_web.errors import ServiceUnavailableError
from subsystems.s2_web.presenter import ChartPresenter, alert_banner, building_info, category_rows, day_label, iso
from subsystems.s2_web.presenter import scenario_rows, scenario_summary, week_rows
from subsystems.s2_web.views.coach_view import CoachView

ANALYTICS_METHODS = (
    "get_kpis", "get_score", "get_hourly", "get_aggregates", "get_week_comparison",
    "get_daily_trend", "get_alerts", "estimate_scenario", "get_limits", "save_limits",
)


class PageView:
    """One object the routes call for every page.

    It reads from the S1 analytics service, shapes the numbers with a
    ChartPresenter and, on the dashboard, asks a CoachView for the AI tip.
    Routes only parse the request and render what this class returns.
    """

    def __init__(self, analytics, presenter=None, coach=None):
        self._analytics = None
        self._presenter = None
        self._coach = None
        self.analytics = analytics
        self.presenter = presenter if presenter is not None else ChartPresenter()
        self.coach = coach

    @property
    def analytics(self):
        """The S1 analytics service that supplies every number on the pages."""
        return self._analytics

    @analytics.setter
    def analytics(self, service):
        missing = [name for name in ANALYTICS_METHODS if not callable(getattr(service, name, None))]
        if missing:
            raise TypeError(f"analytics service is missing: {', '.join(missing)}.")
        self._analytics = service

    @property
    def presenter(self):
        """The ChartPresenter that turns numbers into display values and chart data."""
        return self._presenter

    @presenter.setter
    def presenter(self, value):
        if not isinstance(value, ChartPresenter):
            raise TypeError("presenter must be a ChartPresenter.")
        self._presenter = value

    @property
    def coach(self):
        """Optional CoachView for the AI tip on the dashboard."""
        return self._coach

    @coach.setter
    def coach(self, value):
        if value is not None and not isinstance(value, CoachView):
            raise TypeError("coach must be a CoachView or None.")
        self._coach = value

    # -- helpers -----------------------------------------------------------------

    def kpis(self, building):
        """Today's figures from S1. Every page and endpoint starts here, so a lost
        connection to S1 is turned into a ServiceUnavailableError in this one place."""
        try:
            return self._analytics.get_kpis(building)
        except (ConnectionError, TimeoutError) as error:
            raise ServiceUnavailableError("The analytics service (S1) did not answer. Try again in a moment.") from error

    def report_date(self, building):
        return self.kpis(building)["date"]

    def todays_alerts(self, building, kpis):
        """Alerts from the report date, latest first."""
        return [alert for alert in self._analytics.get_alerts(building, limit=100)
                if alert["time"].date() == kpis["date"]]

    def building(self, building):
        """Building header used by every JSON response."""
        kpis = self.kpis(building)
        return kpis, building_info(building, kpis["source"])

    # -- pages --------------------------------------------------------------------

    def index(self, building, category=None):
        """Template context for the dashboard."""
        analytics, presenter = self._analytics, self._presenter
        kpis = self.kpis(building)
        context = {
            "page": "dashboard",
            "building": building,
            "category": category,
            "categories": CATEGORIES,
            "kpis": presenter.kpi_cards(
                kpis, category, analytics.get_daily_trend(building, category=category),
                analytics.get_week_comparison(building),
            ),
            "score": presenter.score_payload(analytics.get_score(building)),
            "banner": alert_banner(self.todays_alerts(building, kpis)),
            "report_day": kpis["date"].isoformat(),
        }
        if self._coach is not None:
            status = self._coach.status()
            try:
                headline, detail = self._coach.preview(building)
            except ServiceUnavailableError:
                # The dashboard still works without S3; only the tip is missing.
                headline, detail = "The AI coach is not available right now.", "Tips will appear here again once it answers."
            context.update(
                coach_status=status["status"],
                coach_status_label=status["label"],
                advice_headline=headline,
                advice_detail=detail,
            )
        return context

    def history(self, building, period="today", category=None):
        analytics = self._analytics
        report_date = self.report_date(building)
        return {
            "page": "history",
            "building": building,
            "period": period,
            "periods": HISTORY_PERIODS,
            "category": category,
            "categories": CATEGORIES,
            "alerts": self._presenter.alert_rows(analytics.get_alerts(building), report_date),
            "weeks": week_rows(analytics.get_week_comparison(building)),
            "report_day": report_date.isoformat(),
        }

    def scenarios(self, building, form):
        """Estimate the what-if result for the values currently in the form."""
        heating, lighting = form.changes
        result = self._analytics.estimate_scenario(building, heating, lighting)
        return {
            "page": "scenarios",
            "building": building,
            "form": form,
            "rows": scenario_rows(result),
            "summary": scenario_summary(heating, lighting, result),
        }

    def settings(self, building, form, save=False):
        """Fill the limits form from the service, or save the form's limits when asked."""
        if save:
            self._analytics.save_limits(building, form.limits)
        elif not form.is_submitted():
            form.limits = self._analytics.get_limits(building)
        return {"page": "settings", "building": building, "form": form}

    # -- JSON endpoints ---------------------------------------------------------------

    def api_kpis(self, building, category=None):
        kpis, info = self.building(building)
        trend = self._analytics.get_daily_trend(building, category=category)
        return {
            "building": info,
            "date": kpis["date"].isoformat(),
            "category": category or "all",
            "kpis": self._presenter.kpi_cards(kpis, category, trend, self._analytics.get_week_comparison(building)),
        }

    def api_score(self, building):
        _, info = self.building(building)
        return {"building": info, **self._presenter.score_payload(self._analytics.get_score(building))}

    def api_hourly(self, building, day=None, category=None, compare=False):
        """Hourly readings for one day as a line chart. Raises ValueError for a day without data."""
        analytics, presenter = self._analytics, self._presenter
        kpis, info = self.building(building)
        day = day or kpis["date"]
        points = analytics.get_hourly(building, day, category)

        comparison_day = day - timedelta(days=7)
        comparison = None
        if compare:
            try:
                comparison = analytics.get_hourly(building, comparison_day, category)
            except ValueError:
                comparison = None  # no fixture for that week; the chart shows only the selected day

        limit = analytics.get_limits(building)[category] if category else None
        label = "Today" if day == kpis["date"] else day_label(day)
        return {
            "building": info,
            "day": day.isoformat(),
            "category": category or "all",
            "unit": "kWh",
            "interval": "1h",
            "timestamps": [iso(moment) for moment, _ in points],
            "comparison_day": comparison_day.isoformat() if comparison else None,
            "limit_kwh": limit,
            "chart": presenter.to_line_chart(points, label, comparison, "Last week", limit),
        }

    def api_aggregates(self, building, period="week"):
        analytics, presenter = self._analytics, self._presenter
        kpis, info = self.building(building)
        end = kpis["date"]
        days = [end - timedelta(days=offset) for offset in range(PERIOD_DAYS[period] - 1, -1, -1)]
        totals = analytics.get_aggregates(building, period)
        rows = category_rows(totals)

        daily_chart = None
        if len(days) > 1:
            by_day = []
            for day in days:
                parts = {}
                for category in CATEGORIES:
                    readings = [kwh for _, kwh in analytics.get_hourly(building, day, category) if kwh is not None]
                    parts[category] = sum(readings)
                by_day.append((day, parts))
            daily_chart = presenter.to_daily_chart(by_day)

        return {
            "building": info,
            "period": period,
            "start": days[0].isoformat(),
            "end": end.isoformat(),
            "unit": "kWh",
            "total_kwh": round(sum(row["kwh"] for row in rows), 1),
            "categories": rows,
            "chart": presenter.to_bar_chart(totals),
            "daily_chart": daily_chart,
        }

    def api_alerts(self, building):
        kpis, info = self.building(building)
        return {
            "building": info,
            "unit": "kWh",
            "limits_kwh": self._analytics.get_limits(building),
            "alerts": self._presenter.alert_rows(self._analytics.get_alerts(building), kpis["date"]),
            "banner": alert_banner(self.todays_alerts(building, kpis)),
        }
