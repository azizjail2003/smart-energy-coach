"""Service access for the views.

Views get S1 (analytics) and S3 (AI coach) through these functions only.
With USE_MOCK=true (the default) they return the demo services; with
USE_MOCK=false they return the real S1 and S3 code.
"""
from flask import current_app, session

from subsystems.s2_web.presenter import ChartPresenter
from subsystems.s2_web.views.coach_view import CoachView
from subsystems.s2_web.views.page_view import PageView

from .analytics import MockAnalyticsService
from .coach import MockAICoach


def get_analytics():
    if current_app.config["USE_MOCK"]:
        return MockAnalyticsService(state=session)
    from .s1_adapter import S1AnalyticsAdapter  # imported only when the real S1 is used
    return S1AnalyticsAdapter(current_app.config["S1_DB_PATH"])


def get_coach():
    if current_app.config["USE_MOCK"]:
        return MockAICoach(status=current_app.config["COACH_STATUS"])
    # S3's coach already has the methods S2 needs (ask, status, tips), so no adapter is needed.
    # get_session() opens the database named by DATABASE_URL.
    from subsystems.s3_coach.s3_ai_coach import AICoach
    from subsystems.s3_coach.s3_repository import MySQLRepository, get_session
    return AICoach(MySQLRepository(get_session()))


def get_coach_view():
    return CoachView(get_coach())


def get_page_view():
    return PageView(get_analytics(), ChartPresenter(), get_coach_view())
