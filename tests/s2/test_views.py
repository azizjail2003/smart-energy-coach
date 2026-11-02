"""The S2 classes: constructors, getters and setters, and the pages they build."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from subsystems.s2_web.forms import ScenarioForm, ThresholdForm
from subsystems.s2_web.presenter import ChartPresenter
from subsystems.s2_web.services.analytics import MockAnalyticsService
from subsystems.s2_web.services.coach import MockAICoach
from subsystems.s2_web.views.coach_view import CoachView
from subsystems.s2_web.views.page_view import PageView


@pytest.fixture
def analytics():
    return MockAnalyticsService(state={})


@pytest.fixture
def coach_view():
    return CoachView(MockAICoach())


@pytest.fixture
def page_view(analytics, coach_view):
    return PageView(analytics, ChartPresenter(), coach_view)


# -- ChartPresenter -------------------------------------------------------------------

def test_chart_presenter_defaults_to_berlin():
    assert ChartPresenter().timezone == "Europe/Berlin"


def test_chart_presenter_timezone_setter_accepts_known_zones():
    presenter = ChartPresenter()
    presenter.timezone = "UTC"
    assert presenter.timezone == "UTC"
    moment = datetime(2024, 5, 14, 12, 0, tzinfo=ZoneInfo("Europe/Berlin"))
    assert presenter.localize(moment).hour == 10


@pytest.mark.parametrize("bad", ["", None, 42, "Mars/Olympus"])
def test_chart_presenter_timezone_setter_rejects_bad_values(bad):
    presenter = ChartPresenter()
    with pytest.raises(ValueError):
        presenter.timezone = bad
    assert presenter.timezone == "Europe/Berlin"


def test_chart_presenter_builds_the_three_chart_types():
    presenter = ChartPresenter()
    points = [(datetime(2024, 5, 14, hour, tzinfo=ZoneInfo("Europe/Berlin")), 1.0 + hour) for hour in range(3)]
    line = presenter.to_line_chart(points, "Today", limit=2.5)
    assert line["type"] == "line" and line["labels"] == ["00:00", "01:00", "02:00"]
    assert line["above_limit"] == [2]
    bar = presenter.to_bar_chart({"heating": 6.0, "lighting": 2.0, "servers": 1.0, "other": 1.0})
    assert bar["type"] == "bar" and bar["datasets"][0]["data"] == [60, 20, 10, 10]
    daily = presenter.to_daily_chart([(datetime(2024, 5, 13).date(), 10.0), (datetime(2024, 5, 14).date(), 12.0)])
    assert daily["type"] == "bar" and "Highest: 12.0 kWh" in daily["summary"]


# -- Forms ---------------------------------------------------------------------------

def test_scenario_form_changes_property_round_trips(app):
    with app.test_request_context():
        form = ScenarioForm()
        assert form.changes == (-1.0, 20)
        form.changes = (1.5, 35)
        assert form.heating_change.data == 1.5 and form.lighting_reduction.data == 35
        assert form.changes == (1.5, 35)


def test_threshold_form_limits_property_round_trips(app):
    with app.test_request_context():
        form = ThresholdForm()
        limits = {"heating": 5.0, "lighting": 1.5, "servers": 2.0, "other": 1.0}
        form.limits = limits
        assert form.limits == limits
        assert form.servers.data == 2.0


def test_threshold_form_limits_setter_needs_every_category(app):
    with app.test_request_context():
        form = ThresholdForm()
        with pytest.raises(ValueError, match="other"):
            form.limits = {"heating": 5.0, "lighting": 1.5, "servers": 2.0}


# -- CoachView -----------------------------------------------------------------------

def test_coach_view_exposes_its_coach(coach_view):
    assert isinstance(coach_view.coach, MockAICoach)
    replacement = MockAICoach(status="fallback")
    coach_view.coach = replacement
    assert coach_view.coach is replacement
    assert coach_view.status() == {"status": "fallback", "label": "Fallback"}


def test_coach_view_rejects_objects_that_are_not_coaches(coach_view):
    with pytest.raises(TypeError, match="ask"):
        coach_view.coach = object()
    with pytest.raises(TypeError):
        CoachView(None)


def test_coach_view_page_has_everything_the_template_needs(coach_view):
    context = coach_view.page("library")
    assert context["page"] == "coach" and context["building"] == "library"
    assert set(context) >= {"tones", "status", "status_label", "tips", "max_length"}
    assert context["tips"]


def test_coach_view_ask_returns_a_complete_answer(coach_view):
    result = coach_view.ask("  How do we cut heating?  ", "strict", "library")
    assert result["question"] == "How do we cut heating?"
    assert set(result) == {"building", "question", "tone", "answer", "source", "response_time_s"}


@pytest.mark.parametrize("question, tone, building", [
    ("", "strict", "library"),
    ("x" * 501, "strict", "library"),
    (42, "strict", "library"),
    ("Hi", "friendly", "library"),
    ("Hi", "strict", "mensa"),
])
def test_coach_view_ask_rejects_invalid_input(coach_view, question, tone, building):
    with pytest.raises(ValueError):
        coach_view.ask(question, tone, building)


def test_coach_view_preview_splits_headline_and_detail(coach_view):
    headline, detail = coach_view.preview("library")
    assert headline.endswith(".")
    assert detail


# -- PageView ------------------------------------------------------------------------

def test_page_view_constructor_wires_its_parts(analytics, coach_view):
    view = PageView(analytics)
    assert view.analytics is analytics
    assert isinstance(view.presenter, ChartPresenter)
    assert view.coach is None
    view.coach = coach_view
    assert view.coach is coach_view


def test_page_view_setters_check_their_types(page_view, analytics):
    with pytest.raises(TypeError, match="get_kpis"):
        page_view.analytics = object()
    with pytest.raises(TypeError, match="ChartPresenter"):
        page_view.presenter = "Europe/Berlin"
    with pytest.raises(TypeError, match="CoachView"):
        page_view.coach = MockAICoach()
    assert page_view.analytics is analytics


def test_page_view_presenter_setter_changes_chart_timezone(page_view):
    utc = ChartPresenter("UTC")
    page_view.presenter = utc
    assert page_view.presenter.timezone == "UTC"
    chart = page_view.api_hourly("library")["chart"]
    assert chart["labels"][0] == "22:00"  # 00:00 Berlin summer time shown in UTC


def test_page_view_index_includes_the_coach_tip_only_when_a_coach_is_set(analytics, coach_view):
    without = PageView(analytics).index("library")
    assert "advice_headline" not in without
    assert without["kpis"]["energy"]["display"] == "15.7"
    with_coach = PageView(analytics, coach=coach_view).index("library")
    assert with_coach["advice_headline"] and with_coach["coach_status"] == "online"


def test_page_view_json_payloads(page_view):
    assert page_view.api_kpis("library")["kpis"]["energy"]["unit"] == "kWh"
    assert page_view.api_score("library")["score"] > 0
    assert page_view.api_aggregates("library", "week")["period"] == "week"
    assert page_view.api_alerts("library")["unit"] == "kWh"
    with pytest.raises(ValueError):
        page_view.api_hourly("library", datetime(1999, 1, 1).date())


def test_page_view_settings_fills_and_saves_the_form(app, page_view):
    with app.test_request_context():
        form = ThresholdForm()
        context = page_view.settings("library", form)
        assert context["form"].limits == page_view.analytics.get_limits("library")
        form.limits = {"heating": 9.9, "lighting": 1.0, "servers": 1.0, "other": 1.0}
        page_view.settings("library", form, save=True)
        assert page_view.analytics.get_limits("library")["heating"] == 9.9
