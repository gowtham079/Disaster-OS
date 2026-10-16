"""Modular AI Decision Support Service utilizing Google Gemini API.

Provides structured predictive warnings, tactical recommendations, evacuation protocols,
and resource adjustments. Integrates with the official Google GenAI Python SDK.
Falls back safely to local heuristic rule-based decision support when GEMINI_API_KEY
is not configured or when API queries fail, preventing simulation crashes.
"""

import json
import logging
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional

# Load environment configuration via python-dotenv
from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    load_dotenv(dotenv_path=_env_path)
else:
    load_dotenv()

logger = logging.getLogger(__name__)

# Try importing the official Google GenAI SDK
try:
    from google import genai
    from google.genai import types
    from google.genai.errors import APIError, ClientError
    GENAI_SDK_AVAILABLE = True
except ImportError:
    genai = None
    types = None
    APIError = Exception
    ClientError = Exception
    GENAI_SDK_AVAILABLE = False

# Default modern Flash model and thinking level (configured via environment)
DEFAULT_GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
DEFAULT_THINKING_LEVEL = os.environ.get("GEMINI_THINKING_LEVEL", "medium")

# Global in-memory cache to prevent redundant API queries during simulation runs
_cache: Dict[str, Dict[str, Any]] = {}


class LLMProvider:
    """Interface for modular LLM providers."""

    def generate(self, prompt: str) -> Dict[str, Any]:
        """Generate structured response dictionary containing text and provider metadata."""
        raise NotImplementedError("LLM providers must implement generate()")


class GeminiProvider(LLMProvider):
    """Google GenAI SDK provider for Google Gemini models."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        thinking_level: Optional[str] = None,
    ):
        self.api_key = (api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
        self.model = model or os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
        self.thinking_level = thinking_level or os.environ.get("GEMINI_THINKING_LEVEL", DEFAULT_THINKING_LEVEL)
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not configured.")
        if not GENAI_SDK_AVAILABLE:
            raise RuntimeError("google-genai SDK is not installed.")

        # Initialize the official Google GenAI Client (authentication handled securely via headers)
        self.client = genai.Client(api_key=self.api_key)

    def generate(self, prompt: str) -> Dict[str, Any]:
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not configured.")

        # Configure structured JSON output with thinking level — no obsolete temperature/budget parameters
        thinking_cfg = None
        if types and self.thinking_level:
            thinking_cfg = types.ThinkingConfig(thinking_level=self.thinking_level)

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            thinking_config=thinking_cfg,
        ) if types else None

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )
            raw_text = response.text or ""
            return {
                "text": raw_text,
                "provider": "GEMINI",
                "model": self.model,
                "thinking_level": self.thinking_level,
                "status": "OPERATIONAL",
                "generated_at": time.time(),
            }
        except (APIError, ClientError) as api_err:
            # Secure error logging: never expose key or credentials
            err_type = type(api_err).__name__
            logger.warning("Gemini API error during content generation: %s", err_type)
            raise RuntimeError(f"Gemini API request failed: {err_type}") from None
        except Exception as exc:
            err_type = type(exc).__name__
            logger.warning("Unexpected error during Gemini content generation: %s", err_type)
            raise RuntimeError(f"Gemini generation error: {err_type}") from None


class LocalHeuristicProvider(LLMProvider):
    """Local deterministic fallback provider generating structured rule-based decision support."""

    def __init__(self, reason: str = "GEMINI_UNAVAILABLE"):
        self.reason = reason
        self.model = "local-rule-engine"
        self.thinking_level = "heuristic"

    def generate(self, prompt: str) -> Dict[str, Any]:
        payload = {
            "predicted_threat": "Heavy rainfall detected. High risk of flash flooding within 2 hours.",
            "recommended_actions": [
                "Deploy 4 amphibious rescue boats to low-lying sectors.",
                "Activate local school shelters and mobilize supply trucks.",
                "Alert general hospital trauma centers to reserve ICU beds.",
            ],
            "evacuation_instructions": "HIGH PRIORITY: Evacuate residents along riverside districts immediately to secondary high-ground shelters.",
            "resource_adjustments": "Reallocate 2 ambulances from northern hub to central disaster perimeter.",
            "severity_analysis": "Disaster classified as high risk due to population density and rainfall index.",
            "allocation_analysis": "Allocated 8 teams with medical, fire, and water rescue capabilities.",
            "summary": "Tactical disaster operations initiated. All multi-agent modules communicating on active message bus.",
        }
        return {
            "text": json.dumps(payload),
            "provider": "LOCAL_HEURISTIC",
            "model": self.model,
            "thinking_level": self.thinking_level,
            "status": self.reason,
            "generated_at": time.time(),
        }


def get_llm_provider() -> LLMProvider:
    """Factory builder for LLM provider.
    
    Returns GeminiProvider if GEMINI_API_KEY is configured and SDK is installed;
    otherwise returns LocalHeuristicProvider with controlled GEMINI_UNAVAILABLE state.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    model = os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    thinking_level = os.environ.get("GEMINI_THINKING_LEVEL", DEFAULT_THINKING_LEVEL)
    if api_key and GENAI_SDK_AVAILABLE:
        try:
            return GeminiProvider(api_key=api_key, model=model, thinking_level=thinking_level)
        except Exception as exc:
            logger.warning("Failed to initialize GeminiProvider: %s. Using local fallback.", type(exc).__name__)
            return LocalHeuristicProvider(reason="GEMINI_UNAVAILABLE")

    if not api_key:
        logger.info("GEMINI_API_KEY environment variable is not configured; using local heuristic decision support (GEMINI_UNAVAILABLE).")
    elif not GENAI_SDK_AVAILABLE:
        logger.warning("google-genai SDK not available; using local heuristic decision support.")

    return LocalHeuristicProvider(reason="GEMINI_UNAVAILABLE")


class DecisionSupportAgent:
    """AI Decision Support Agent providing predictive recommendations and tactical summaries."""

    def __init__(self):
        self.provider = get_llm_provider()

    def get_explanation(
        self,
        incident: Dict[str, Any],
        allocation: Dict[str, Any],
        rescue: Dict[str, Any],
        weather: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate structured AI recommendations with caching and rule-based fallback."""
        location = incident.get("location", "Unknown")
        severity = incident.get("severity", "medium")
        teams = allocation.get("teams_assigned", 0)
        dtype = incident.get("disaster_type", "disaster")
        cache_key = f"{location}_{severity}_{teams}_{dtype}"

        if cache_key in _cache:
            return dict(_cache[cache_key])

        weather_str = ""
        if weather:
            weather_str = (
                f"Live Weather: Temp {weather.get('temperature')}°C, "
                f"Rainfall {weather.get('rainfall_mm')}mm, Wind {weather.get('wind_speed')}km/h, "
                f"Desc: {weather.get('description')}"
            )

        prompt = f"""
        You are an AI Disaster Management Operational Architect for an Emergency Operations Center (EOC).
        Provide tactical recommendations.

        Incident:
        - Location: {location}
        - Disaster Type: {dtype}
        - Severity: {severity}
        - Affected People: {incident.get("people_affected", 0)}
        {weather_str}

        Allocations:
        - Teams Assigned: {teams}
        - Resources: {", ".join(allocation.get("resources", []))}

        Generate a raw JSON object with these EXACT keys:
        - predicted_threat: 1-sentence forecast (e.g. Heavy rainfall detected. Flood likely within 2 hours).
        - recommended_actions: list of 3 concrete action steps (e.g. Deploy 4 rescue boats, Open temporary shelter, Increase ambulance availability).
        - evacuation_instructions: 1-sentence clear evacuation order.
        - resource_adjustments: 1-sentence fleet recommendation.
        - severity_analysis: 1-sentence analysis.
        - allocation_analysis: 1-sentence resource explanation.
        - summary: 2-sentence status summary.

        Respond ONLY with raw valid JSON without markdown wrapping.
        """

        try:
            gen_res = self.provider.generate(prompt)
            raw_text = gen_res.get("text", "")
            cleaned = raw_text.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
                if cleaned.endswith("```"):
                    cleaned = cleaned.rsplit("\n", 1)[0]
                cleaned = cleaned.strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()

            parsed = json.loads(cleaned)
            # Attach provider metadata
            parsed["provider"] = gen_res.get("provider", "GEMINI")
            parsed["model"] = gen_res.get("model", getattr(self.provider, "model", DEFAULT_GEMINI_MODEL))
            parsed["thinking_level"] = gen_res.get("thinking_level", getattr(self.provider, "thinking_level", DEFAULT_THINKING_LEVEL))
            parsed["status"] = gen_res.get("status", "OPERATIONAL")
            parsed["generated_at"] = gen_res.get("generated_at", time.time())

            _cache[cache_key] = parsed
            return parsed
        except Exception as exc:
            logger.warning("AI Decision support call failed: %s. Using local heuristic fallback.", type(exc).__name__)
            fallback = self._get_local_fallback(incident, allocation, rescue, weather)
            return fallback

    def _get_local_fallback(
        self,
        incident: Dict[str, Any],
        allocation: Dict[str, Any],
        rescue: Dict[str, Any],
        weather: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Rule-based local fallback response generator with explicit provenance."""
        dtype = str(incident.get("disaster_type", "disaster")).lower()
        severity = str(incident.get("severity", "medium")).lower()
        teams = allocation.get("teams_assigned", 2)
        people = incident.get("people_affected", 50)
        location = incident.get("location", "Target Sector")

        raw_rain = weather.get("rainfall_mm") if weather else None
        rain = float(raw_rain) if raw_rain is not None else None
        raw_wind = weather.get("wind_speed") if weather else None
        wind = float(raw_wind) if raw_wind is not None else None

        if dtype == "flood" or (rain is not None and rain > 40.0):
            rain_str = f" ({rain}mm)" if rain is not None else ""
            pred_threat = f"Heavy rainfall/inundation hazard detected{rain_str}. Flood likely within 2 hours in {location}."
            actions = [
                "Deploy 4 amphibious rescue boats to inundated low-lying sectors.",
                "Open temporary high-ground school shelters immediately.",
                "Increase ambulance readiness around casualty triage centers.",
            ]
        elif dtype == "fire" or (wind is not None and wind > 30.0):
            wind_str = f" ({wind} km/h)" if wind is not None else ""
            pred_threat = f"High wind/fire hazard detected{wind_str}. Fire propagation likely within 1 hour."
            actions = [
                "Deploy 4 heavy fire engines and establishes firebreaks.",
                "Reserve burn unit beds at nearest civil hospital.",
                "Issue immediate smoke hazard cell broadcast alerts.",
            ]
        else:
            pred_threat = f"Elevated seismic and structural risk detected in {location}."
            actions = [
                "Deploy search & rescue squads with heavy lifting gear.",
                "Establish field medical triage stations near safe assembly zones.",
                "Reserve trauma beds across regional hospital network.",
            ]

        has_key = bool(os.environ.get("GEMINI_API_KEY", "").strip())
        status = "FALLBACK_TRIGGERED" if has_key else "GEMINI_UNAVAILABLE"

        return {
            "predicted_threat": pred_threat,
            "recommended_actions": actions,
            "evacuation_instructions": f"HIGH PRIORITY: Evacuate residents along low-lying sectors near {location} immediately.",
            "resource_adjustments": f"Reallocate 2 ambulances and 1 fire unit to active incident zone in {location}.",
            "severity_analysis": f"Incident in {location} classified as {severity} severity affecting {people} citizens.",
            "allocation_analysis": f"Allocated {teams} specialized emergency response teams with medical and rescue equipment.",
            "summary": f"Emergency Operations Center actively managing {dtype} incident at {location}. {teams} response teams deployed.",
            "provider": "LOCAL_HEURISTIC",
            "model": "local-rule-engine",
            "thinking_level": "heuristic",
            "status": status,
            "generated_at": time.time(),
        }


def get_gemini_recommendation(
    disaster_type: str = "Flood",
    severity: str = "HIGH",
    victims: int = 350,
    location: str = "Incident Sector",
) -> Dict[str, Any]:
    """Convenience helper to retrieve AI decision support explanations."""
    agent = DecisionSupportAgent()
    inc = {"disaster_type": disaster_type, "severity": severity, "people_affected": victims, "location": location}
    alloc = {"teams_assigned": 8, "resources": ["Ambulances", "Fire Engines", "Police", "Boats", "Drones"]}
    return agent.get_explanation(inc, alloc, rescue={})


def smoke_test_gemini() -> Dict[str, Any]:
    """Execute ONE real Gemini API request to verify model, thinking level, and SDK functionality.
    
    Prompt:
    'Return JSON with:
    status=ok
    provider=GEMINI
    purpose=Disaster OS integration smoke test'
    """
    provider = get_llm_provider()
    if not isinstance(provider, GeminiProvider):
        return {
            "success": False,
            "error_category": "CONFIGURATION_ERROR",
            "error_message": "GEMINI_API_KEY is not configured or SDK is unavailable.",
            "provider": "LOCAL_HEURISTIC",
            "model": getattr(provider, "model", "local-rule-engine"),
            "thinking_level": getattr(provider, "thinking_level", "heuristic"),
        }

    test_prompt = (
        "Return JSON with:\n"
        "status=ok\n"
        "provider=GEMINI\n"
        "purpose=Disaster OS integration smoke test"
    )

    last_exc = None
    for attempt in range(1, 4):
        try:
            res = provider.generate(test_prompt)
            raw_text = res.get("text", "")
            cleaned = raw_text.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
                if cleaned.endswith("```"):
                    cleaned = cleaned.rsplit("\n", 1)[0]
                cleaned = cleaned.strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()

            parsed = json.loads(cleaned)
            return {
                "success": True,
                "raw_response": parsed,
                "provider": res.get("provider", "GEMINI"),
                "model": res.get("model", provider.model),
                "thinking_level": res.get("thinking_level", provider.thinking_level),
                "status": "OPERATIONAL",
                "generated_at": res.get("generated_at", time.time()),
                "attempt": attempt,
            }
        except json.JSONDecodeError as jde:
            return {
                "success": False,
                "error_category": "PARSE_ERROR",
                "error_message": "Failed to parse JSON response from Gemini",
                "provider": "GEMINI",
                "model": provider.model,
                "thinking_level": provider.thinking_level,
                "status": "PARSE_ERROR",
            }
        except Exception as exc:
            last_exc = exc
            if attempt < 3:
                time.sleep(1.5)

    err_cat = type(last_exc).__name__ if last_exc else "UnknownError"
    is_transient = "Server" in str(last_exc) or "503" in str(last_exc) or "ServerError" in str(last_exc)
    return {
        "success": False,
        "error_category": err_cat,
        "error_message": f"Gemini API request failed: {last_exc}",
        "provider": "GEMINI",
        "model": provider.model,
        "thinking_level": provider.thinking_level,
        "status": "TEMPORARILY_UNAVAILABLE" if is_transient else "ERROR",
    }
