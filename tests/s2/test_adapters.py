"""S2 connected to the real S1 and S3 code (USE_MOCK=false)."""
from datetime import timedelta

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("dotenv")

from subsystems.s2_web import create_app  # noqa: E402
from subsystems.s2_web.catalog import CATEGORIES  # noqa: E402
from subsystems.s2_web.services.s1_adapter import S1AnalyticsAdapter  # noqa: E402
from subsystems.s2_web.views.coach_view import CoachView  # noqa: E402
from subsystems.s2_web.views.page_view import PageView  # noqa: E402
from subsystems.s3_coach.s3_ai_coach import AICoach  # noqa: E402
from subsystems.s3_coach.s3_repository import MySQLRepository, get_session  # noqa: E402


@pytest.fixture(scope="module")
def folder(tmp_path_factory):
    return tmp_path_factory.mktemp("connected")


@pytest.fixture
def s1(folder):
    return S1AnalyticsAdapter(str(folder / "s1.db"))


@pytest.fixture
def s3(folder, monkeypatch):
    # S3 opens the database named by DATABASE_URL; no API keys, so it answers with backup tips.
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{folder / 's3.db'}")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    return AICoach(MySQLRepository(get_session()))


def test_real_subsystems_fit_the_views(s1, s3):
    # PageView and CoachView check the method names in their setters.
    PageView(s1, coach=CoachView(s3))


def test_kpis_come_from_s1_and_add_up(s1):
    kpis = s1.get_kpis("library")
    assert kpis["source"] == "live"
    assert set(kpis["by_category"]) == set(CATEGORIES)
    total = sum(part["energy_kwh"] for part in kpis["by_category"].values())
    assert total == pytest.approx(kpis["energy_kwh"], abs=0.3)


def test_hourly_has_24_hours_and_rejects_days_without_data(s1):
    day = s1.get_kpis("library")["date"]
    hours = s1.get_hourly("library", day, "heating")
    assert len(hours) == 24 and hours[0][0].tzinfo is not None
    with pytest.raises(ValueError):
        s1.get_hourly("library", day + timedelta(days=1))


def test_alerts_and_score_use_s1_methods(s1):
    score = s1.get_score("library")
    assert 0 <= score["reference"] <= 100
    assert set(score["components"]) == {"energy", "carbon", "comfort"}
    for alert in s1.get_alerts("library"):
        assert alert["category"] in CATEGORIES and alert["value_kwh"] > alert["limit_kwh"]


def test_saved_limits_are_stored_by_s1(folder, s1):
    s1.save_limits("lab-building", {"heating": 9.0})
    assert S1AnalyticsAdapter(str(folder / "s1.db")).get_limits("lab-building")["heating"] == 9.0


def test_s3_answers_with_backup_tips_then_from_its_cache(s3):
    view = CoachView(s3)
    assert view.status()["status"] == "fallback"
    first = view.ask("How can we save energy at night?", "strict", "lecture-hall-a")
    assert first["answer"].startswith("URGENT ACTION REQUIRED")
    assert first["source"] == "Backup tips" and first["response_time_s"] is None
    again = view.ask("How can we save energy at night?", "strict", "lecture-hall-a")
    assert again["source"] == "Cached answer"


@pytest.mark.parametrize("path", ["/", "/history?period=30d", "/scenarios", "/coach", "/settings",
                                  "/api/kpis?building=library", "/api/aggregates?building=library&period=30d"])
def test_every_page_works_when_connected(folder, monkeypatch, path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{folder / 's3.db'}")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    app = create_app({"TESTING": True, "SECRET_KEY": "test-secret", "USE_MOCK": False,
                      "S1_DB_PATH": str(folder / "s1.db")})
    response = app.test_client().get(path)
    assert response.status_code == 200
    if path == "/":
        assert b"Live data" in response.data
