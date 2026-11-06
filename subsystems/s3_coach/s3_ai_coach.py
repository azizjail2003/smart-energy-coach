"""
AI Coach logic for Subsystem 3.
Implements the Strategy pattern to seamlessly switch between NVIDIA, OpenAI, and Fallback.
"""
import json
import os
import hashlib
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from openai import OpenAI
from openai.types.chat import ChatCompletion
from subsystems.s3_coach.s3_repository import MySQLRepository

# --- Strategy Interface ---

class LLMClient(ABC):
    """Abstract base class defining the contract for recommendation engines."""
    
    @abstractmethod
    def generate_recommendation(self, anomaly_data: Dict[str, Any], tone: str) -> str:
        """Analyzes anomaly data and returns a JSON string with the recommendation."""
        pass

# --- Pure Python Fallback Engine ---

class FallbackCoach(LLMClient):
    """Rule-based engine built entirely in standard Python."""
    
    def __init__(self):
        # Constructor
        self._engine_name: Optional[str] = None
        # Initialization Method
        self._setup_engine()
        
    def _setup_engine(self):
        """Sets up default internal parameters for the fallback strategy."""
        self.engine_name = "FallbackEngine"
        
    # Encapsulation
    @property
    def engine_name(self) -> Optional[str]:
        return self._engine_name
        
    @engine_name.setter
    def engine_name(self, value: Optional[str]):
        if not value:
            raise ValueError("Engine name cannot be empty.")
        self._engine_name = value
        
    def generate_recommendation(self, anomaly_data: Dict[str, Any], tone: str) -> str:
        """Generates offline advice based on fixed rules."""
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

        if tone == "strict":
            message = f"URGENT ACTION REQUIRED: {tip}"
        elif tone == "encouraging":
            message = f"Here is a quick tip to improve your score: {tip}"
        else:
            message = f"System Analysis: {tip}"
            
        response_dict = {
            "tip": message,
            "generated_by": self.engine_name
        }
        
        return json.dumps(response_dict)

# --- OpenAI Client Integration ---

class OpenAIClient(LLMClient):
    """Connects to the OpenAI API with strict state encapsulation."""
    
    def __init__(self):
        self._api_key: Optional[str] = None
        self._client: Optional[OpenAI] = None
        self._setup_client()

    def _setup_client(self):
        """Initialization logic to securely configure the API client."""
        self.api_key = os.environ.get("OPENAI_API_KEY")

    @property
    def api_key(self) -> Optional[str]:
        return self._api_key

    @api_key.setter
    def api_key(self, value: Optional[str]):
        """Creates the OpenAI client only if a valid key is provided."""
        self._api_key = value
        if value:
            self._client = OpenAI(api_key=value)
        else:
            self._client = None

    def generate_recommendation(self, anomaly_data: Dict[str, Any], tone: str) -> str:
        if not self._client:
            raise ValueError("OpenAI API key not configured in environment.")

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
    """Connects to the NVIDIA API with strict state encapsulation."""
    
    def __init__(self):
        self._api_key: Optional[str] = None
        self._client: Optional[OpenAI] = None
        self._setup_client()

    def _setup_client(self):
        """Initialization logic to securely configure the NVIDIA client."""
        self.api_key = os.environ.get("NVIDIA_API_KEY")

    @property
    def api_key(self) -> Optional[str]:
        return self._api_key

    @api_key.setter
    def api_key(self, value: Optional[str]):
        """Creates the NVIDIA client with the specific base URL."""
        self._api_key = value
        if value:
            self._client = OpenAI(
                base_url="https://integrate.api.nvidia.com/v1",
                api_key=value
            )
        else:
            self._client = None

    def generate_recommendation(self, anomaly_data: Dict[str, Any], tone: str) -> str:
        if not self._client:
            raise ValueError("NVIDIA API key not configured in environment.")

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
    Orchestrates AI recommendations using the Strategy Pattern.
    Checks cache first, attempts live APIs, and falls back to the local engine.
    """
    
    def __init__(self, repository: MySQLRepository):
        self._repo: Optional[MySQLRepository] = None
        self._last_source: Optional[str] = None
        self._fallback_engine: Optional[FallbackCoach] = None
        self._nvidia_engine: Optional[NVIDIAClient] = None
        self._openai_engine: Optional[OpenAIClient] = None
        
        self.repo = repository
        self._initialize_strategies()

    def _initialize_strategies(self):
        """Instantiates all available recommendation strategies."""
        self.last_source = "Online"
        self._fallback_engine = FallbackCoach()
        self._nvidia_engine = NVIDIAClient()
        self._openai_engine = OpenAIClient()

    @property
    def repo(self) -> MySQLRepository:
        """Retrieves the injected repository."""
        return self._repo

    @repo.setter
    def repo(self, value: MySQLRepository):
        """Validates the repository injection."""
        if not value:
            raise ValueError("A valid MySQLRepository instance is required.")
        self._repo = value

    @property
    def last_source(self) -> str:
        """Retrieves the source of the last executed request."""
        return self._last_source

    @last_source.setter
    def last_source(self, value: str):
        """Validates the allowed source states for the UI badges."""
        valid_sources = ["Online", "Fallback", "Cached"]
        if value not in valid_sources:
            raise ValueError(f"Invalid status source. Must be one of {valid_sources}")
        self._last_source = value

    def _generate_hash(self, data: Any, tone: str) -> str:
        """Generates a unique SHA-256 hash for the given context payload."""
        if isinstance(data, dict):
            context_string = json.dumps(data, sort_keys=True) + tone
        else:
            context_string = str(data) + tone
        return hashlib.sha256(context_string.encode('utf-8')).hexdigest()

    def get_recommendation(self, building_id: str, anomaly_data: Dict[str, Any], tone: str = "analytical") -> str:
        """Maintains backward compatibility with S1 integration tests."""
        context_hash = self._generate_hash(anomaly_data, tone)
        cached_response = self.repo.get_cached_recommendation(building_id, context_hash)
        
        if cached_response:
            self.last_source = "Cached"
            return cached_response

        response_text = None
        source_label = "fallback"
        
        try:
            response_text = self._nvidia_engine.generate_recommendation(anomaly_data, tone)
            source_label = "nvidia"
            self.last_source = "Online"
        except (ValueError, RuntimeError):
            try:
                response_text = self._openai_engine.generate_recommendation(anomaly_data, tone)
                source_label = "openai"
                self.last_source = "Online"
            except (ValueError, RuntimeError):
                response_text = self._fallback_engine.generate_recommendation(anomaly_data, tone)
                source_label = "fallback"
                self.last_source = "Fallback"
            
        self.repo.save_ai_recommendation(
            building_id=building_id,
            context_hash=context_hash,
            tone=tone,
            response=response_text,
            source=source_label,
            tokens=0
        )
        
        return response_text

    def ask(self, question: str, tone: str, building_id: str) -> Dict[str, Any]:
        """Handles chat questions originating from the S2 Web Interface."""
        payload = {"question": question}
        context_hash = self._generate_hash(payload, tone)
        cached_response = self.repo.get_cached_recommendation(building_id, context_hash)
        
        if cached_response:
            self.last_source = "Cached"
            return {
                "answer": cached_response,
                "source": "cache"
            }

        response_text = None
        source_label = "fallback"
        
        try:
            response_text = self._nvidia_engine.generate_recommendation(payload, tone)
            source_label = "nvidia"
            self.last_source = "Online"
        except (ValueError, RuntimeError):
            try:
                response_text = self._openai_engine.generate_recommendation(payload, tone)
                source_label = "openai"
                self.last_source = "Online"
            except (ValueError, RuntimeError):
                response_text = self._fallback_engine.generate_recommendation(payload, tone)
                source_label = "fallback"
                self.last_source = "Fallback"
            
        self.repo.save_ai_recommendation(
            building_id=building_id,
            context_hash=context_hash,
            tone=tone,
            response=response_text,
            source=source_label,
            tokens=0
        )
        
        return {
            "answer": response_text,
            "source": source_label
        }

    def status(self) -> str:
        """Returns the current operational status for the S2 UI badges."""
        return self.last_source