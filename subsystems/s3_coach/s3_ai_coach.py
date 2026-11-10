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
import time

def build_system_prompt(data: Dict[str, Any], tone: str) -> str:
    """Chat questions are answered directly; alerts still get one tip."""
    if data.get("question"):
        return (
            "You are the energy coach of a university building. "
            f"Your tone must be {tone}. "
            "Answer the user's question directly and briefly (at most 3 sentences), "
            "using the building data provided (date, energy, score, devices, alerts). "
            "If the question is not about energy or the building, say briefly what you can help with. "
            "You must return ONLY a raw JSON object with a single key 'tip' that holds your answer."
        )
    return (
        "You are an energy efficiency AI for a smart building. "
        f"Your tone must be {tone}. "
        "Analyze the input data and provide exactly one actionable tip. "
        "You must return ONLY a raw JSON object with a single key 'tip'."
    )


def building_context(building_id: str) -> Dict[str, Any]:
    """Today's figures from S1, so the AI can answer questions about the building."""
    db_path = os.environ.get("S1_DB_PATH")
    if not db_path:
        return {}
    try:
        from datetime import date
        from subsystems.s1_analytics import AnalyticsService
        service = AnalyticsService(db_path)
        summary = service.get_dashboard_summary(building_id)
        week = service.compute_week_over_week(building_id)
        alerts = service.get_alerts(building_id)[:3]
    except Exception:
        return {}
    return {
        "today": date.today().isoformat(),
        "score": summary["score"],
        "score_parts": {"energy": summary["E"], "carbon": summary["C"], "comfort": summary["K"]},
        "room_temp_c": summary["room_temp"],
        "kwh_by_device_last_hours": summary["by_device"],
        "this_week": week["this_week"],
        "change_vs_last_week_pct": week["change_pct"],
        "latest_alerts": [
            {"time": str(a["timestamp"]), "device": a["device_type"], "kwh": a["kwh"], "limit": a["limit"]}
            for a in alerts
        ],
    }

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
    Connects to the OpenAI / KI Connect NRW API to generate contextual recommendations.
    Requires OPENAI_API_KEY environment variable to be set.
    """
    
    def __init__(self):
        self._api_key: Optional[str] = None
        self._client: Optional[OpenAI] = None
        self._timeout_s: float = 10.0
        self._max_tokens: int = 500
        self._base_url: str = os.environ.get("OPENAI_BASE_URL", "https://chat.kiconnect.nrw/api/v1")
        self._model: str = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
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
            self._client = OpenAI(
                api_key=value,
                base_url=self._base_url,
                timeout=self._timeout_s,
                max_retries=2,
            )
        else:
            self._client = None

    def _resolve_model(self) -> str:
        """Uses configured model or queries KI Connect /models if needed."""
        try:
            models = self._client.models.list()
            available_ids = [m.id for m in models.data]
            if available_ids and self._model not in available_ids:
                self._model = available_ids[0]
        except Exception:
            pass
        return self._model

    def generate_recommendation(self, anomaly_data: Dict[str, Any], tone: str) -> str:
        if not self._client:
            raise S3ConfigurationError("OpenAI API key not configured in environment.")
            
        system_prompt = build_system_prompt(anomaly_data, tone)

        user_message = f"Input Data: {json.dumps(anomaly_data)}"

        try:
            response: ChatCompletion = self._client.chat.completions.create(
                model=self._resolve_model(),
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
        self._max_tokens: int = 300
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
            
        system_prompt = build_system_prompt(anomaly_data, tone)

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
        self._last_source: str = "online"
        self._fallback_engine: Optional[FallbackCoach] = None
        self._nvidia_engine: Optional[NVIDIAClient] = None
        self._openai_engine: Optional[OpenAIClient] = None

        self.repo = repository
        self._initialize_strategies()

    def _initialize_strategies(self) -> None:
        """Instantiates recommendation engine strategies and detects initial connectivity state."""
        self._fallback_engine = FallbackCoach()
        self._nvidia_engine = NVIDIAClient()
        self._openai_engine = OpenAIClient()
        
        # Check if at least one API key is present in the environment
        if self._nvidia_engine.api_key or self._openai_engine.api_key:
            self.last_source = "online"
        else:
            self.last_source = "fallback"

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
        valid_sources = ["online", "fallback", "cached"]
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
        valid_tones = ["strict", "analytical", "encouraging"]
        clean_tone = tone.strip().lower() if tone else "analytical"
        if clean_tone not in valid_tones:
            raise S3ConfigurationError(f"Unsupported tone '{tone}'. Allowed tones: {valid_tones}")

        context_hash = self._generate_hash(anomaly_data, clean_tone)
        cached_response = self.repo.get_cached_recommendation(building_id, context_hash)
        
        if cached_response:
            self.last_source = "cached" 
            return cached_response

        response_text = None
        source = "fallback"
        
        try:
            response_text = self._openai_engine.generate_recommendation(anomaly_data, clean_tone)
            source = "openai"
            self.last_source = "online"
        except (S3ConfigurationError, S3APIError, ValueError, RuntimeError):
            try:
                response_text = self._nvidia_engine.generate_recommendation(anomaly_data, clean_tone)
                source = "nvidia"
                self.last_source = "online"
            except (S3ConfigurationError, S3APIError, ValueError, RuntimeError):
                response_text = self._fallback_engine.generate_recommendation(anomaly_data, clean_tone)
                source = "fallback"
                self.last_source = "fallback"
            
        self.repo.save_ai_recommendation(
            building_id=building_id,
            context_hash=context_hash,
            tone=clean_tone,
            response=response_text,
            source=source,
            tokens=len(response_text.split()) if response_text else 0
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
            
        valid_tones = ["strict", "analytical", "encouraging"]
        clean_tone = tone.strip().lower() if tone else "analytical"
        if clean_tone not in valid_tones:
            raise S3ConfigurationError(f"Unsupported tone '{tone}'. Allowed tones: {valid_tones}")
        
        payload = {"question": question.strip(), "building_id": building_id, **building_context(building_id)}
        context_hash = self._generate_hash(payload, clean_tone)

        # Start timing
        start_time = time.time()

        cached_response = self.repo.get_cached_recommendation(building_id, context_hash)

        if cached_response:
            self.last_source = "cached"
            return {
                "answer": self._extract_clean_text(cached_response),
                "source": "cached",
                "response_time_s": None
            }

        response_text = None
        source = "fallback"
        
        try:
            response_text = self._openai_engine.generate_recommendation(payload, clean_tone)
            source = "openai"
            self._last_source = "online"
        except (S3ConfigurationError, S3APIError, ValueError, RuntimeError):
            try:
                response_text = self._nvidia_engine.generate_recommendation(payload, clean_tone)
                source = "nvidia"
                self._last_source = "online"
            except (S3ConfigurationError, S3APIError, ValueError, RuntimeError):
                response_text = self._fallback_engine.generate_recommendation(payload, clean_tone)
                source = "fallback"
                self._last_source = "fallback"

        clean_answer = self._extract_clean_text(response_text)

        self.repo.save_ai_recommendation(
            building_id=building_id,
            context_hash=context_hash,
            tone=clean_tone,
            response=clean_answer,
            source=source,
            tokens=len(clean_answer.split()) if clean_answer else 0
        )

        # Calculate final elapsed time
        elapsed_time = round(time.time() - start_time, 2)
        
        return {
            "answer": clean_answer,
            "source": source,
            "response_time_s": elapsed_time
        }

    def status(self) -> str:
        """
        Returns the current service status for S2 badges ('online', 'fallback', or 'cached').
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