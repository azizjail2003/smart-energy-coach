import unittest
import json
from unittest.mock import patch, MagicMock
from subsystems.s3_coach.s3_ai_coach import FallbackCoach, OpenAIClient, AICoach

class TestFallbackCoach(unittest.TestCase):
    def setUp(self):
        self.coach = FallbackCoach()
        self.anomaly = {"alert_type": "HIGH", "device_category": "HVAC", "value_kwh": 10, "threshold_kwh": 5}

    def test_fallback_strict_tone(self):
        response = self.coach.generate_recommendation(self.anomaly, tone="strict")
        data = json.loads(response)
        self.assertIn("URGENT ACTION REQUIRED", data["tip"])
        self.assertEqual(data["generated_by"], "fallback_engine")

class TestOpenAIClient(unittest.TestCase):
    def setUp(self):
        self.anomaly = {"alert_type": "HIGH", "device_category": "HVAC"}

    @patch.dict('os.environ', clear=True)
    def test_security_missing_key(self):
        # Validates that it raises an error if the environment variable is missing
        with self.assertRaises(ValueError):
            client = OpenAIClient()
            client.generate_recommendation(self.anomaly, "analytical")

class TestAICoachOrchestrator(unittest.TestCase):
    def test_cache_hit_logic(self):
        # Repository simulation (Mock)
        mock_repo = MagicMock()
        mock_repo.get_cached_recommendation.return_value = '{"tip": "Cached tip"}'

        # Orchestrator execution injecting the fake repository
        orchestrator = AICoach(repository=mock_repo)
        result = orchestrator.get_recommendation("campus-A", {}, tone="analytical")
        
        # Assertions
        self.assertEqual(result, '{"tip": "Cached tip"}')
        # Verifies that the save method is NEVER called if there was a cache hit
        mock_repo.save_ai_recommendation.assert_not_called()