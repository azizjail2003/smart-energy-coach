"""
AI Coach logic for Subsystem 3.
Implements a Strategy pattern to seamlessly switch between OpenAI and a local Fallback engine.
"""
import json
from abc import ABC, abstractmethod
from typing import Dict, Any
import os
from openai import OpenAI
from openai.types.chat import ChatCompletion
import hashlib
from subsystems.s3_repository import MySQLRepository

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

# --- OpenAI Client Integration ---

class OpenAIClient(LLMClient):
    """
    Connects to the OpenAI API to generate contextual recommendations.
    Requires OPENAI_API_KEY environment variable to be set.
    """
    
    def __init__(self):
        # To initialize the client. It will fail later if no key is found.
        self.api_key = os.environ.get("OPENAI_API_KEY")
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)
        else:
            self.client = None

    def generate_recommendation(self, anomaly_data: Dict[str, Any], tone: str) -> str:
        """
        Builds a prompt from the anomaly data and requests a JSON response from OpenAI.
        """
        if not self.client:
            raise ValueError("OpenAI API key not configured in environment.")

        # Construct a strict system prompt tailored to the tone
        system_prompt = (
            "You are an energy efficiency AI for a smart building. "
            f"Your tone must be {tone}. "
            "Analyze the anomaly data and provide exactly one actionable tip. "
            "You must return ONLY a raw JSON object with a single key 'tip'."
        )

        # Stringify the anomaly dictionary to feed the LLM
        user_message = f"Anomaly Data: {json.dumps(anomaly_data)}"

        try:
            response: ChatCompletion = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.7,
                max_tokens=100
            )
            
            # Extract the string content from the response object
            content = response.choices[0].message.content
            
            # Simple validation to ensure we got a string back
            if content:
                return content.strip()
            return '{"tip": "Failed to generate AI tip."}'
            
        except Exception as e:
            # Catch network errors, quota limits, or parsing errors
            raise RuntimeError(f"OpenAI API Error: {str(e)}")

class NVIDIAClient(LLMClient):
    """
    Connects to the NVIDIA API (using OpenAI's Python SDK) to generate recommendations.
    Requires NVIDIA_API_KEY environment variable to be set.
    """
    
    def __init__(self):
        self.api_key = os.environ.get("NVIDIA_API_KEY")
        if self.api_key:
            self.client = OpenAI(
                base_url="https://integrate.api.nvidia.com/v1",
                api_key=self.api_key
            )
        else:
            self.client = None

    def generate_recommendation(self, anomaly_data: Dict[str, Any], tone: str) -> str:
        if not self.client:
            raise ValueError("NVIDIA API key not configured in environment.")

        system_prompt = (
            "You are an energy efficiency AI for a smart building. "
            f"Your tone must be {tone}. "
            "Analyze the anomaly data and provide exactly one actionable tip. "
            "You must return ONLY a raw JSON object with a single key 'tip'."
        )

        user_message = f"Anomaly Data: {json.dumps(anomaly_data)}"

        try:
            # Using Meta's nemotron-3.5-bolt-e4b model hosted by NVIDIA
            response: ChatCompletion = self.client.chat.completions.create(
                model="nvidia/nemotron-3.5-bolt-e4b",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.7,
                max_tokens=100,
                timeout=8.0
            )
            
            content = response.choices[0].message.content
            print(f"\n[DEBUG] Raw AI Output: {content}\n") # <- DELETE
            if content:
                #return content.strip()
                clean_content = content.replace("```json", "").replace("```", "").strip()
                return clean_content
            return '{"tip": "Failed to generate AI tip."}'
            
        except Exception as e:
            raise RuntimeError(f"NVIDIA API Error: {str(e)}")

        
# --- Main AI Coach Orchestrator ---

class AICoach:
    """
    Orchestrates AI recommendations. Checks cache first, attempts NVIDIA/OpenAI, 
    and seamlessly falls back to the local engine if needed.
    """
    
    def __init__(self, repository: MySQLRepository):
        self.repo = repository
        self.fallback_engine = FallbackCoach()
        self.nvidia_engine = NVIDIAClient()
        self.openai_engine = OpenAIClient()
        
    def _generate_hash(self, anomaly_data: Dict[str, Any], tone: str) -> str:
        """Generates a unique SHA-256 hash for the given context to use as a cache key."""
        context_string = json.dumps(anomaly_data, sort_keys=True) + tone
        return hashlib.sha256(context_string.encode('utf-8')).hexdigest()
        
    def get_recommendation(self, building_id: str, anomaly_data: Dict[str, Any], tone: str = "analytical") -> str:
        # 1. Check Cache
        context_hash = self._generate_hash(anomaly_data, tone)
        cached_response = self.repo.get_cached_recommendation(building_id, context_hash)
        
        if cached_response:
            return cached_response

        # 2. Attempt Live APIs
        response_text = None
        source = "fallback"
        
        try:
            # Attempt NVIDIA first
            response_text = self.nvidia_engine.generate_recommendation(anomaly_data, tone)
            source = "nvidia"
        except (ValueError, RuntimeError):
            try:
                # Fallback to OpenAI if NVIDIA is missing/fails
                response_text = self.openai_engine.generate_recommendation(anomaly_data, tone)
                source = "openai"
            except (ValueError, RuntimeError):
                # 3. Graceful Fallback to pure Python local engine
                response_text = self.fallback_engine.generate_recommendation(anomaly_data, tone)
            
        # 4. Save to Cache for future use
        self.repo.save_ai_recommendation(
            building_id=building_id,
            context_hash=context_hash,
            tone=tone,
            response=response_text,
            source=source,
            tokens=0
        )
        
        return response_text