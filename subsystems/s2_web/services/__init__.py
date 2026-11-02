"""Service access for the views.

Views get S1 (analytics) and S3 (AI coach) through these functions only.
When the real subsystems are ready, return adapters here instead of the mocks.
"""
from flask import current_app, session

from subsystems.s2_web.presenter import ChartPresenter
from subsystems.s2_web.views.coach_view import CoachView
from subsystems.s2_web.views.page_view import PageView

from .analytics import MockAnalyticsService
from .coach import MockAICoach


def get_analytics():
    return MockAnalyticsService(state=session)


def get_coach():
    return MockAICoach(status=current_app.config["COACH_STATUS"])


def get_coach_view():
    return CoachView(get_coach())


def get_page_view():
    return PageView(get_analytics(), ChartPresenter(), get_coach_view())
