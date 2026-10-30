import json
from subsystems.s3_models import Base
from subsystems.s3_repository import MySQLRepository
from subsystems.s3_ai_coach import FallbackCoach, OpenAIClient, AICoach
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Instantiate our pure Python fallback engine
coach = FallbackCoach()

# Simulate anomaly data coming from Subsystem 1
dummy_anomaly = {
    "alert_type": "HIGH_CONSUMPTION",
    "device_category": "HVAC",
    "value_kwh": 22.5,
    "threshold_kwh": 15.0
}

print("--- Testing Fallback Engine Tones ---")

# Test 1: Analytical Tone (Default)
response_analytical = coach.generate_recommendation(dummy_anomaly, tone="analytical")
print(f"Analytical:\n{json.dumps(json.loads(response_analytical), indent=2)}\n")

# Test 2: Strict Tone
response_strict = coach.generate_recommendation(dummy_anomaly, tone="strict")
print(f"Strict:\n{json.dumps(json.loads(response_strict), indent=2)}\n")

# Test 3: Encouraging Tone
response_encouraging = coach.generate_recommendation(dummy_anomaly, tone="encouraging")
print(f"Encouraging:\n{json.dumps(json.loads(response_encouraging), indent=2)}\n")


print("\n--- Testing OpenAI Client ---")

# Test 1: Verify security system (No API Key)
# If there is no environment variable, the client should fail
client_no_key = OpenAIClient()
try:
    client_no_key.generate_recommendation(dummy_anomaly, "analytical")
except ValueError as e:
    print(f"Security validated. Error caught successfully: {e}")

# Test 2: Simulate a successful OpenAI response
print("\n--- Simulating OpenAI API Call (Mocking) ---")

# Inject a fake key temporarily
with patch.dict('os.environ', {'OPENAI_API_KEY': 'fake-test-key'}):
    mocked_client = OpenAIClient()
    
    # Create a mock object that mimics the OpenAI response structure
    mock_response = MagicMock()
    mock_response.choices[0].message.content = '{"tip": "Simulated AI tip: Upgrade the HVAC system."}'
    
    # Intercept the 'create' method to return our mocked object
    with patch.object(mocked_client.client.chat.completions, 'create', return_value=mock_response):
        result = mocked_client.generate_recommendation(dummy_anomaly, "strict")
        print(f"Mocked Response:\n{result}")

print("\n--- Testing Main AICoach Orchestrator ---")

# Setup in-memory database
engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)
test_session = SessionLocal()
test_repo = MySQLRepository(test_session)

# Instantiate the orchestrator
orchestrator = AICoach(repository=test_repo)

building_id = "campus-A"
test_anomaly = {
    "alert_type": "HIGH_CONSUMPTION",
    "device_category": "Lighting",
    "value_kwh": 35.0,
    "threshold_kwh": 20.0
}

# First run: Cache is empty, no OpenAI key -> Uses Fallback and saves to Cache
print("\n[Run 1] Requesting recommendation (Cache empty, expecting Fallback)...")
response_1 = orchestrator.get_recommendation(building_id, test_anomaly, tone="encouraging")
print(f"Result 1:\n{response_1}")

# Second run: Exact same request -> Should hit the Cache directly
print("\n[Run 2] Requesting exact same recommendation (Expecting Cache hit)...")
response_2 = orchestrator.get_recommendation(building_id, test_anomaly, tone="encouraging")
print(f"Result 2:\n{response_2}")

# Validation
if response_1 == response_2:
    print("\nSUCCESS: Orchestrator logic is flawless. Cache hit confirmed!")
else:
    print("\nERROR: Cache mismatch.")

print("\n--- Testing Live NVIDIA Connection ---")
from subsystems.s3_ai_coach import NVIDIAClient

try:
    live_client = NVIDIAClient()
    # Llamada directa para evitar el salto automático al fallback
    result = live_client.generate_recommendation(test_anomaly, "analytical")
    print(f"NVIDIA API Success:\n{result}")
except Exception as e:
    print(f"NVIDIA API Failed: {e}")