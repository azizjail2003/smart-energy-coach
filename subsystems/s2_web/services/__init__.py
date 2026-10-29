"""Service access for the views.

Views get S1 (analytics) and S3 (AI coach) through these two functions only.
When the real subsystems are ready, return adapters here instead of the mocks.
"""
from flask import current_app, session

from .analytics import MockAnalyticsService
from .coach import MockAICoach


def get_analytics():
    return MockAnalyticsService(state=session)


def get_coach():
    return MockAICoach(status=current_app.config["COACH_STATUS"])
