"""
AI Coach logic for Subsystem 3.
Implements a Strategy pattern to seamlessly switch between NVIDIA, OpenAI, and a local Fallback engine.
"""
import json
from abc import ABC, abstractmethod
from typing import Dict, Any
import os
from openai import OpenAI
from openai.types.chat import ChatCompletion
import hashlib
from subsystems.s3_coach.s3_repository import MySQLRepository

# --- Strategy Interface ---

class LLMClient(ABC):
    """
    Abstract base class defining the contract for any recommendation engine.
    Any class inheriting from this must implement generate_recommendation.
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
    Used when OpenAI/NVIDIA are disabled, unavailable, or to save API costs.
    """
    
    def generate_recommendation(self, anomaly_data: Dict[str, Any], tone: str) -> str:
        # Check if it's a direct chat question from S2
        question = anomaly_data.get("question")
        if question:
            tip = f"Regarding your query ('{question}'): Focus on optimizing operational schedules and flattening peak loads."
        else:
            alert_type = anomaly_data.get("alert_type", "UNKNOWN_ALERT")
            device_cat = anomaly_data.get("device_category", "Unknown Device")
            value = anomaly_data.get("value_kwh", 0)
            limit = anomaly_data.get("threshold_kwh", 0)
            
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
            
        # Format as JSON to match expected output structure
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
        self.api_key = os.environ.get("OPENAI_API_KEY")
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)
        else:
            self.client = None

    def generate_recommendation(self, anomaly_data: Dict[str, Any], tone: str) -> str:
        if not self.client:
            raise ValueError("OpenAI API key not configured in environment.")

        system_prompt = (
            "You are an energy efficiency AI for a smart building. "
            f"Your tone must be {tone}. "
            "Analyze the input data and provide exactly one actionable tip. "
            "You must return ONLY a raw JSON object with a single key 'tip'."
        )

        user_message = f"Input Data: {json.dumps(anomaly_data)}"

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
            
            content = response.choices[0].message.content
            if content:
                return content.strip()
            return '{"tip": "Failed to generate AI tip."}'
            
        except Exception as e:
            raise RuntimeError(f"OpenAI API Error: {str(e)}")

# --- NVIDIA Client Integration ---

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
            "Analyze the input data and provide exactly one actionable tip. "
            "You must return ONLY a raw JSON object with a single key 'tip'."
        )

        user_message = f"Input Data: {json.dumps(anomaly_data)}"

        try:
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
            if content:
                return content.strip()
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
        self._last_source = "Online"
        
    def _generate_hash(self, data: Any, tone: str) -> str:
        """Generates a unique SHA-256 hash for the given context to use as a cache key."""
        if isinstance(data, dict):
            context_string = json.dumps(data, sort_keys=True) + tone
        else:
            context_string = str(data) + tone
        return hashlib.sha256(context_string.encode('utf-8')).hexdigest()
        
    def get_recommendation(self, building_id: str, anomaly_data: Dict[str, Any], tone: str = "analytical") -> str:
        """
        Retained for backward compatibility with existing unit tests.
        """
        context_hash = self._generate_hash(anomaly_data, tone)
        cached_response = self.repo.get_cached_recommendation(building_id, context_hash)
        
        if cached_response:
            self._last_source = "cache"
            return cached_response

        response_text = None
        source = "fallback"
        
        try:
            response_text = self.nvidia_engine.generate_recommendation(anomaly_data, tone)
            source = "nvidia"
            self._last_source = "Online"
        except (ValueError, RuntimeError):
            try:
                response_text = self.openai_engine.generate_recommendation(anomaly_data, tone)
                source = "openai"
                self._last_source = "Online"
            except (ValueError, RuntimeError):
                response_text = self.fallback_engine.generate_recommendation(anomaly_data, tone)
                source = "fallback"
                self._last_source = "Fallback"
            
        self.repo.save_ai_recommendation(
            building_id=building_id,
            context_hash=context_hash,
            tone=tone,
            response=response_text,
            source=source,
            tokens=0
        )
        
        return response_text

    def ask(self, question: str, tone: str, building_id: str) -> Dict[str, Any]:
        """
        Handles chat questions.
        Checks cache first, invokes LLM/Fallback, saves to cache, and returns a dict
        containing the answer and its source.
        """
        payload = {"question": question}
        context_hash = self._generate_hash(payload, tone)
        cached_response = self.repo.get_cached_recommendation(building_id, context_hash)
        
        if cached_response:
            self._last_source = "cache"
            return {
                "answer": cached_response,
                "source": "cache"
            }

        response_text = None
        source = "fallback"
        
        try:
            response_text = self.nvidia_engine.generate_recommendation(payload, tone)
            source = "nvidia"
            self._last_source = "Online"
        except (ValueError, RuntimeError):
            try:
                response_text = self.openai_engine.generate_recommendation(payload, tone)
                source = "openai"
                self._last_source = "Online"
            except (ValueError, RuntimeError):
                response_text = self.fallback_engine.generate_recommendation(payload, tone)
                source = "fallback"
                self._last_source = "Fallback"
            
        self.repo.save_ai_recommendation(
            building_id=building_id,
            context_hash=context_hash,
            tone=tone,
            response=response_text,
            source=source,
            tokens=0
        )
        
        return {
            "answer": response_text,
            "source": source
        }

    def status(self) -> str:
        """
        Returns the current service status for S2 badges ('Online', 'Fallback', or 'Cached').
        """
        if self._last_source == "cache":
            return "Cached"
        elif self._last_source == "fallback":
            return "Fallback"
        else:
            return "Online"