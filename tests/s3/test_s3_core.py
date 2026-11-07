"""
Test suite for Subsystem 3 (AI Coach & Data Persistence).
Covers custom error handling, in-memory SQLite persistence,
caching, and Strategy pattern fallbacks.
"""
import json
import unittest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from subsystems.s3_coach.s3_models import Base, AIRecommendation
from subsystems.s3_coach.s3_repository import MySQLRepository
from subsystems.s3_coach.s3_ai_coach import AICoach, FallbackCoach, OpenAIClient
from subsystems.s3_coach.s3_errors import (
    S3CoachError, S3ConfigurationError, S3APIError,
)
from flask import Flask
from subsystems.s2_web.views.api import bp as s2_api_bp

class TestS3Subsystem(unittest.TestCase):
    """Balanced unit and integration tests for Subsystem 3."""

    def setUp(self):
        """Creates an isolated in-memory SQLite database before each test."""
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        SessionLocal = sessionmaker(bind=self.engine)
        self.session = SessionLocal()
        self.repo = MySQLRepository(self.session)
        self.coach = AICoach(self.repo)
        # Flask test client conectado al API de S2
        self.app = Flask(__name__)
        self.app.register_blueprint(s2_api_bp)
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def tearDown(self):
        """Closes session and disposes in-memory engine after each test."""
        self.session.close()
        self.engine.dispose()

    # TEST 1: Custom Error Handling & Encapsulation in AICoach and Repository
    def test_01_encapsulation_raises_custom_configuration_error(self):
        """Verifies that invalid state assignments trigger S3ConfigurationError."""
        with self.assertRaises(S3ConfigurationError):
            self.coach.repo = None

        with self.assertRaises(S3ConfigurationError):
            self.coach.last_source = "InvalidStatus"

        with self.assertRaises(S3ConfigurationError):
            MySQLRepository(None)

    # TEST 2: Repository Persistence & Cache Lookup (In-Memory SQLite)
    def test_02_repository_saves_and_retrieves_recommendation(self):
        """Verifies that MySQLRepository persists and queries AIRecommendation models."""
        self.repo.save_ai_recommendation(
            building_id="library",
            context_hash="abc123hash",
            tone="analytical",
            response="Lower heating setpoint by 1 degree.",
            source="openai",
            tokens=42,
        )
        cached = self.repo.get_cached_recommendation("library", "abc123hash")
        self.assertEqual(cached, "Lower heating setpoint by 1 degree.")

        row_count = self.session.query(AIRecommendation).count()
        self.assertEqual(row_count, 1)

    # TEST 3: End-to-End Cache Hit Behavior in AICoach.ask()
    def test_03_ask_returns_cached_response_without_calling_apis(self):
        """Verifies that a second identical question hits the SQLite cache and sets status to Cached."""
        # Force fallback on first call to populate cache
        self.coach._nvidia_engine = MagicMock()
        self.coach._nvidia_engine.generate_recommendation.side_effect = S3APIError("Down")
        self.coach._openai_engine = MagicMock()
        self.coach._openai_engine.generate_recommendation.side_effect = S3APIError("Down")

        first_res = self.coach.ask("How to reduce HVAC load?", "encouraging", "library")
        self.assertEqual(first_res["source"], "fallback")
        self.assertEqual(self.coach.status(), "fallback")

        # Second identical call must return from cache
        second_res = self.coach.ask("How to reduce HVAC load?", "encouraging", "library")
        self.assertEqual(second_res["source"], "cached")
        self.assertEqual(second_res["answer"], first_res["answer"])
        self.assertEqual(self.coach.status(), "cached")

    # TEST 4: Live API Success Path (Mocked OpenAI Strategy)
    def test_04_ask_returns_openai_response_when_live_api_succeeds(self):
        """Verifies that AICoach parses JSON from OpenAI and returns a clean dict for S2."""
        self.coach._nvidia_engine = MagicMock()
        self.coach._nvidia_engine.generate_recommendation.side_effect = S3ConfigurationError("No key")
        self.coach._openai_engine = MagicMock()
        self.coach._openai_engine.generate_recommendation.return_value = json.dumps(
            {"tip": "Dim library lights by 20% in the afternoon."}
        )

        result = self.coach.ask("How can we save lighting energy?", "analytical", "library")

        self.assertEqual(result["source"], "openai")
        self.assertEqual(result["answer"], "Dim library lights by 20% in the afternoon.")
        self.assertEqual(self.coach.status(), "online")

    # TEST 5: FallbackCoach Rule Engine & Tone Formatting
    def test_05_fallback_coach_handles_anomalies_and_tones(self):
        """Verifies that FallbackCoach calculates kWh excess and applies strict tone."""
        fallback = FallbackCoach()
        anomaly = {
            "alert_type": "HIGH_CONSUMPTION",
            "device_category": "HVAC",
            "value_kwh": 15.5,
            "threshold_kwh": 10.0,
        }
        raw_json = fallback.generate_recommendation(anomaly, "strict")
        parsed = json.loads(raw_json)

        self.assertIn("URGENT ACTION REQUIRED", parsed["tip"])
        self.assertIn("5.50 kWh", parsed["tip"])
        self.assertEqual(parsed["generated_by"], "FallbackEngine")

    # TEST 6: LLM Client Missing Key & Empty Question Error Handling
    def test_06_missing_api_key_and_empty_question_raise_errors(self):
        """Verifies that missing credentials or blank questions raise S3ConfigurationError."""
        client = OpenAIClient()
        client.api_key = None

        with self.assertRaises(S3ConfigurationError):
            client.generate_recommendation({"value_kwh": 5}, "analytical")

        with self.assertRaises(S3ConfigurationError):
            self.coach.ask("   ", "analytical", "library")

    # TEST 7: Custom Error Hierarchy Formatting & Dashboard Tips
    def test_07_error_string_formatting_and_dashboard_tips(self):
        """Verifies standardized error codes and the S2 tips() contract."""
        err = S3CoachError("Connection failed", "E399_CUSTOM")
        self.assertEqual(str(err), "[E399_CUSTOM] Connection failed")

        tips = self.coach.tips("library")
        self.assertIsInstance(tips, list)
        self.assertEqual(len(tips), 3)

    # TEST 8: Serialization & S3 Exception structure
    def test_08_error_serialization(self):
        """Verifies that S3 exceptions store attributes correctly for JSON serialization."""
        err = S3ConfigurationError("Invalid configuration")
        self.assertEqual(err.error_code, "E301_CONFIG_ERROR")
        self.assertEqual(err.message, "Invalid configuration")

    # TEST 9: Repository Data Validation (Negative Consumption)
    def test_09_save_energy_log_rejects_negative_consumption(self):
        """Verifies negative kWh readings raise S3ConfigurationError directly."""
        from datetime import datetime, timezone
        with self.assertRaises(S3ConfigurationError) as context:
            self.repo.save_energy_log(
                building_id="library",
                device_id=1,
                timestamp=datetime.now(timezone.utc),
                consumption=-10.5,
                co2=400.0
            )
        self.assertEqual(context.exception.error_code, "E301_NEGATIVE_KWH")

    # TEST 10: Flask API - Missing JSON Payload (HTTP 400)
    def test_10_flask_api_ask_missing_payload_returns_400(self):
        """Verifies that hitting /api/coach/ask without JSON returns ApiError 400."""
        response = self.client.post("/api/coach/ask", data="plain text not json")
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertEqual(data["error"]["code"], "invalid_request")
        self.assertIn("JSON", data["error"]["message"])

    # TEST 11: Flask API - Invalid Tone/Parameter (HTTP 400)
    @patch('subsystems.s2_web.views.api.get_coach_view')
    def test_11_flask_api_ask_invalid_parameter_returns_400(self, mock_get_coach_view):
        """Verifies that ValueError raised by S3 is caught by S2 and returns HTTP 400."""
        mock_coach = MagicMock()
        mock_coach.ask.side_effect = ValueError("Unsupported tone")
        mock_get_coach_view.return_value = mock_coach

        response = self.client.post(
            "/api/coach/ask",
            json={"question": "Help", "tone": "sarcastic"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"]["code"], "invalid_parameter")
        self.assertIn("Unsupported tone", response.get_json()["error"]["message"])

    # TEST 12: Flask API - Successful Recommendation (HTTP 200)
    @patch('subsystems.s2_web.views.api.get_coach_view')
    def test_12_flask_api_ask_endpoint_returns_200(self, mock_get_coach_view):
        """Verifies a successful POST to /api/coach/ask returns HTTP 200 with answer."""
        mock_coach = MagicMock()
        mock_coach.ask.return_value = {"answer": "Reduce peak load.", "source": "fallback"}
        mock_get_coach_view.return_value = mock_coach

        response = self.client.post(
            "/api/coach/ask",
            json={"question": "How to reduce peak load?", "tone": "analytical"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["answer"], "Reduce peak load.")
        self.assertEqual(data["source"], "fallback")
        self.assertIn("answered_at", data)

    # TEST 13: Flask API - GET Status Endpoint Success (HTTP 200)
    @patch('subsystems.s2_web.views.api.get_coach_view')
    def test_13_flask_api_status_endpoint_returns_200(self, mock_get_coach_view):
        """Verifies the Flask status endpoint returns 200 OK and current system status."""
        mock_coach = MagicMock()
        mock_coach.status.return_value = {"status": "online"}
        mock_get_coach_view.return_value = mock_coach

        response = self.client.get("/api/coach/status")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "online")
        self.assertIn("checked_at", data)

    # TEST 14: Fallback Coach Formatting Rules
    def test_14_fallback_coach_tones_formatting(self):
        """Verifies FallbackCoach outputs the correct textual tone prefixes."""
        fallback = FallbackCoach()
        data = {"alert_type": "HIGH_CONSUMPTION", "value_kwh": 20, "threshold_kwh": 10}
        encouraging = fallback.generate_recommendation(data, "encouraging")
        self.assertIn("tip", encouraging)
        self.assertIn("Here is a quick tip", encouraging)

    # TEST 15: Flask API - Unknown Route (HTTP 404)
    def test_15_flask_api_unknown_route_returns_404(self):
        """Verifies that requesting an unregistered Flask route returns 404 Not Found."""
        response = self.client.get("/api/this-route-does-not-exist")
        self.assertEqual(response.status_code, 404)

if __name__ == "__main__":
    unittest.main()