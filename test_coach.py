import json
from subsystems.s3_ai_coach import FallbackCoach

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