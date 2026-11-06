"""
AI Coach logic for Subsystem 3.
Implements a Strategy pattern to seamlessly switch between NVIDIA, OpenAI, and a local Fallback engine.
"""
import json
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import os
from openai import OpenAI
from openai.types.chat import ChatCompletion
import hashlib
from subsystems.s3_coach.s3_repository import MySQLRepository
from subsystems.s3_coach.s3_errors import S3ConfigurationError, S3APIError

# --- Strategy Interface ---

class LLMClient(ABC):
    """
    Abstract base class defining the contract for any recommendation engine.
    """
    
    @abstractmethod
    def generate_recommendation(self, anomaly_data: Dict[str, Any], tone: str) -> str:
        """
        Analyzes input data and returns a JSON string with the recommendation.
        """
        pass

# --- Pure Python Fallback Engine ---

class FallbackCoach(LLMClient):
    """
    Rule-based recommendation engine built entirely in standard Python.
    Used when OpenAI/NVIDIA are disabled, unavailable, or to save API costs.
    """
    def __init__(self):
        self._engine_name: Optional[str] = None
        self._setup_engine()

    def _setup_engine(self) -> None:
        """Initializes internal parameters for the fallback engine."""
        self.engine_name = "FallbackEngine"

    @property
    def engine_name(self) -> Optional[str]:
        return self._engine_name

    @engine_name.setter
    def engine_name(self, value: Optional[str]) -> None:
        if not value or not isinstance(value, str):
            raise S3ConfigurationError("Engine name must be a non-empty string.")
        self._engine_name = value

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
            
        # Expected output structure
        response_dict = {
            "tip": message,
            "generated_by": self.engine_name
        }
        
        return json.dumps(response_dict)

# --- OpenAI Client Integration ---

class OpenAIClient(LLMClient):
    """
    Connects to the OpenAI API to generate contextual recommendations.
    Requires OPENAI_API_KEY environment variable to be set.
    """
    
    def __init__(self):
        self._api_key: Optional[str] = None
        self._client: Optional[OpenAI] = None
        self._timeout_s: float = 10.0
        self._max_tokens: int = 500
        self._setup_client()

    def _setup_client(self) -> None:
        """Reads API key from environment and configures the client."""
        self.api_key = os.environ.get("OPENAI_API_KEY")

    @property
    def api_key(self) -> Optional[str]:
        return self._api_key

    @api_key.setter
    def api_key(self, value: Optional[str]) -> None:
        self._api_key = value
        if value:
            self._client = OpenAI(api_key=value, timeout=self._timeout_s, max_retries=2)
        else:
            self._client = None

    def generate_recommendation(self, anomaly_data: Dict[str, Any], tone: str) -> str:
        if not self._client:
            raise S3ConfigurationError("OpenAI API key not configured in environment.")
            
        system_prompt = (
            "You are an energy efficiency AI for a smart building. "
            f"Your tone must be {tone}. "
            "Analyze the input data and provide exactly one actionable tip. "
            "You must return ONLY a raw JSON object with a single key 'tip'."
        )

        user_message = f"Input Data: {json.dumps(anomaly_data)}"

        try:
            response: ChatCompletion = self._client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.7,
                max_tokens=self._max_tokens,
            )
            content = response.choices[0].message.content
            if content:
                return content.strip()
            return '{"tip": "Failed to generate AI tip."}'
        except Exception as exc:
            raise S3APIError(f"OpenAI API Error: {exc}") from exc

# --- NVIDIA Client Integration ---

class NVIDIAClient(LLMClient):
    """
    Connects to the NVIDIA API (using OpenAI's Python SDK) to generate recommendations.
    Requires NVIDIA_API_KEY environment variable to be set.
    """
    
    def __init__(self):
        self._api_key: Optional[str] = None
        self._client: Optional[OpenAI] = None
        self._timeout_s: float = 8.0
        self._max_tokens: int = 100
        self._setup_client()

    def _setup_client(self) -> None:
        """Reads NVIDIA API key from environment and initializes client."""
        self.api_key = os.environ.get("NVIDIA_API_KEY")

    @property
    def api_key(self) -> Optional[str]:
        return self._api_key

    @api_key.setter
    def api_key(self, value: Optional[str]) -> None:
        self._api_key = value
        if value:
            self._client = OpenAI(
                base_url="https://integrate.api.nvidia.com/v1",
                api_key=value,
            )
        else:
            self._client = None

    def generate_recommendation(self, anomaly_data: Dict[str, Any], tone: str) -> str:
        if not self._client:
            raise S3ConfigurationError("NVIDIA API key not configured in environment.")
            
        system_prompt = (
            "You are an energy efficiency AI for a smart building. "
            f"Your tone must be {tone}. "
            "Analyze the input data and provide exactly one actionable tip. "
            "You must return ONLY a raw JSON object with a single key 'tip'."
        )

        user_message = f"Input Data: {json.dumps(anomaly_data)}"

        try:
            response: ChatCompletion = self._client.chat.completions.create(
                model="nvidia/nemotron-3.5-bolt-e4b",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.7,
                max_tokens=self._max_tokens,
                timeout=self._timeout_s
            )
            
            content = response.choices[0].message.content
            if content:
                return content.strip()
            return '{"tip": "Failed to generate AI tip."}'
        except Exception as exc:
            raise S3APIError(f"NVIDIA API Error: {exc}") from exc

# --- Main AI Coach Orchestrator ---

class AICoach:
    """
    Orchestrates AI recommendations. Checks cache first, attempts NVIDIA/OpenAI, 
    and seamlessly falls back to the local engine if needed.
    """
    
    def __init__(self, repository: MySQLRepository):
        self._repo: Optional[MySQLRepository] = None
        self._last_source: str = "Online"
        self._fallback_engine: Optional[FallbackCoach] = None
        self._nvidia_engine: Optional[NVIDIAClient] = None
        self._openai_engine: Optional[OpenAIClient] = None

        self.repo = repository
        self._initialize_strategies()

    def _initialize_strategies(self) -> None:
        """Instantiates recommendation engine strategies."""
        self.last_source = "Online"
        self._fallback_engine = FallbackCoach()
        self._nvidia_engine = NVIDIAClient()
        self._openai_engine = OpenAIClient()

    @property
    def repo(self) -> MySQLRepository:
        return self._repo

    @repo.setter
    def repo(self, value: MySQLRepository) -> None:
        if value is None:
            raise S3ConfigurationError("A valid MySQLRepository instance is required.")
        self._repo = value

    @property
    def last_source(self) -> str:
        return self._last_source

    @last_source.setter
    def last_source(self, value: str) -> None:
        valid_sources = ["Online", "Fallback", "Cached"]
        if value not in valid_sources:
            raise S3ConfigurationError(f"Invalid status source. Must be one of {valid_sources}")
        self._last_source = value
        
    def _generate_hash(self, data: Any, tone: str) -> str:
        """Generates a unique SHA-256 hash for the given context to use as a cache key."""
        if isinstance(data, dict):
            context_string = json.dumps(data, sort_keys=True) + tone
        else:
            context_string = str(data) + tone
        return hashlib.sha256(context_string.encode('utf-8')).hexdigest()

    @staticmethod
    def _extract_clean_text(response_text: str) -> str:
        """Extracts the plain text tip from a JSON response string if formatted as JSON."""
        try:
            parsed = json.loads(response_text)
            if isinstance(parsed, dict) and "tip" in parsed:
                return str(parsed["tip"])
        except (json.JSONDecodeError, TypeError):
            pass
        return str(response_text)
        
    def get_recommendation(self, building_id: str, anomaly_data: Dict[str, Any], tone: str = "analytical") -> str:
        """
        Returns a JSON string recommendation for anomaly data (S1/S3 contract).
        """
        context_hash = self._generate_hash(anomaly_data, tone)
        cached_response = self.repo.get_cached_recommendation(building_id, context_hash)
        
        if cached_response:
            self.last_source = "Cached" 
            return cached_response

        response_text = None
        source = "Fallback"
        
        try:
            response_text = self._nvidia_engine.generate_recommendation(anomaly_data, tone)
            source = "nvidia"
            self.last_source = "Online"
        except (S3ConfigurationError, S3APIError, ValueError, RuntimeError):
            try:
                response_text = self._openai_engine.generate_recommendation(anomaly_data, tone)
                source = "openai"
                self.last_source = "Online"
            except (S3ConfigurationError, S3APIError, ValueError, RuntimeError):
                response_text = self._fallback_engine.generate_recommendation(anomaly_data, tone)
                source = "fallback"
                self.last_source = "Fallback"
            
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
        if not question or not question.strip():
            raise S3ConfigurationError("Question cannot be empty.")
        
        payload = {"question": question.strip(), "building_id": building_id}
        context_hash = self._generate_hash(payload, tone)
        cached_response = self.repo.get_cached_recommendation(building_id, context_hash)

        if cached_response:
            self.last_source = "Cached"
            return {
                "answer": self._extract_clean_text(cached_response),
                "source": "cache",
            }

        response_text = None
        source = "fallback"
        
        try:
            response_text = self._nvidia_engine.generate_recommendation(payload, tone)
            source = "nvidia"
            self._last_source = "Online"
        except (S3ConfigurationError, S3APIError, ValueError, RuntimeError):
            try:
                response_text = self._openai_engine.generate_recommendation(payload, tone)
                source = "openai"
                self._last_source = "Online"
            except (S3ConfigurationError, S3APIError, ValueError, RuntimeError):
                response_text = self._fallback_engine.generate_recommendation(payload, tone)
                source = "fallback"
                self._last_source = "Fallback"

        clean_answer = self._extract_clean_text(response_text)

        self.repo.save_ai_recommendation(
            building_id=building_id,
            context_hash=context_hash,
            tone=tone,
            response=clean_answer,
            source=source,
            tokens=0
        )
        
        return {
            "answer": clean_answer,
            "source": source
        }

    def status(self) -> str:
        """
        Returns the current service status for S2 badges ('Online', 'Fallback', or 'Cached').
        """
        return self.last_source

    def tips(self, building_id: str = "library") -> List[str]:
        """Returns actionable daily energy tips for the S2 dashboard."""
        default_tips = [
            f"Lower HVAC setpoint by 1 °C in {building_id} during peak afternoon hours (13:00–17:00).",
            "Enable automated daylight dimming in perimeter zones to cut lighting load by 15%.",
            "Consolidate underutilized server workloads outside core academic hours.",
        ]
        return default_tips