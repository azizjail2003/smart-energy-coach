"""
AI Coach logic for Subsystem 3.
Implements a Strategy pattern to seamlessly switch between OpenAI and a local Fallback engine.
"""
import json
from abc import ABC, abstractmethod
from typing import Dict, Any

# --- Strategy Interface ---

class LLMClient(ABC):
    """
    Abstract base class defining the contract for any recommendation engine.
    Any class inheriting from this MUST implement generate_recommendation.
    """
    
    @abstractmethod
    def generate_recommendation(self, anomaly_data: Dict[str, Any], tone: str) -> str:
        """
        Analyzes anomaly data and returns a JSON string with the recommendation.
        """
        pass

# --- Pure Python Fallback Engine ---

class FallbackCoach(LLMClient):
    """
    Rule-based recommendation engine built entirely in standard Python.
    Used when OpenAI is disabled, unavailable, or to save API costs.
    """
    
    def generate_recommendation(self, anomaly_data: Dict[str, Any], tone: str) -> str:
        alert_type = anomaly_data.get("alert_type", "UNKNOWN_ALERT")
        device_cat = anomaly_data.get("device_category", "Unknown Device")
        value = anomaly_data.get("value_kwh", 0)
        limit = anomaly_data.get("threshold_kwh", 0)
        
        # Base logic
        if alert_type == "HIGH_CONSUMPTION":
            excess = value - limit
            tip = f"Reduce usage. The {device_cat} exceeded its limit by {excess:.2f} kWh."
        elif alert_type == "EFFICIENCY_DROP":
            tip = f"Schedule maintenance for {device_cat}. Efficiency is dropping rapidly."
        else:
            tip = f"Monitor the {device_cat} closely. An anomaly was detected."

        # Tone adjustment
        if tone == "strict":
            message = f"URGENT ACTION REQUIRED: {tip}"
        elif tone == "encouraging":
            message = f"Here is a quick tip to improve your score: {tip}"
        else:  # analytical
            message = f"System Analysis: {tip}"
            
        # Format as JSON to match the expected OpenAI output structure
        response_dict = {
            "tip": message,
            "generated_by": "fallback_engine"
        }
        
        return json.dumps(response_dict)