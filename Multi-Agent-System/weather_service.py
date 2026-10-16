"""Meteorological, seismic, and geocoding integrations for Multi-Agent Disaster OS.

Delegates all external data calls directly to normalized intelligence providers (USGS, GDACS,
OpenWeather, Open-Meteo, Nominatim) to enforce strict data provenance and real-time source health tracking.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from intelligence.providers import (
    fetch_gdacs_disasters,
    fetch_usgs_earthquakes,
    fetch_weather_observation,
    reverse_geocode_nominatim,
)
from intelligence.models import DataClassification

logger = logging.getLogger(__name__)


def get_weather(lat: Optional[float] = None, lng: Optional[float] = None) -> Dict[str, Any]:
    """Fetch live meteorological data delegating to intelligence provider layer."""
    if lat is None or lng is None:
        return {
            "source": "UNAVAILABLE",
            "temperature": None,
            "humidity": None,
            "wind_speed": None,
            "rainfall_mm": None,
            "description": "Meteorological Feed Unavailable",
            "timestamp": time.time(),
            "classification": "UNAVAILABLE",
        }

    obs = fetch_weather_observation(lat, lng)
    if obs and obs.classification != DataClassification.UNAVAILABLE:
        # Check if at least one metric is present
        has_metric = any(v is not None for v in [obs.temperature, obs.humidity_pct, obs.wind_speed_kmh, obs.precipitation_mm])
        if has_metric:
            return {
                "source": f"{obs.provider} API",
                "temperature": obs.temperature,
                "humidity": obs.humidity_pct if hasattr(obs, "humidity_pct") else getattr(obs, "humidity", None),
                "wind_speed": obs.wind_speed_kmh,
                "rainfall_mm": obs.precipitation_mm,
                "description": obs.weather_condition or "UNAVAILABLE",
                "timestamp": obs.observed_at,
                "classification": obs.classification.value if hasattr(obs.classification, "value") else str(obs.classification),
            }

    return {
        "source": "UNAVAILABLE",
        "temperature": None,
        "humidity": None,
        "wind_speed": None,
        "rainfall_mm": None,
        "description": "Meteorological Feed Unavailable",
        "timestamp": time.time(),
        "classification": "UNAVAILABLE",
    }


def compute_weather_impact(
    weather_data: Optional[Dict[str, Any]], disaster_type: Optional[str] = "general"
) -> Dict[str, Any]:
    """Calculate severity adjustment multipliers based on weather conditions.
    
    If meteorological data is unavailable or missing required evidence, returns
    status='INSUFFICIENT_EVIDENCE', classification='UNAVAILABLE', and clearly notes
    that weather impact was NOT VERIFIED. Never fabricates fake temperatures or rainfall.
    """
    if not weather_data or weather_data.get("classification") == "UNAVAILABLE":
        return {
            "status": "INSUFFICIENT_EVIDENCE",
            "classification": "UNAVAILABLE",
            "verified": False,
            "severity_multiplier": 1.0,
            "rescue_time_multiplier": 1.0,
            "victim_multiplier": 1.0,
            "warnings": [
                "METEOROLOGICAL DATA UNAVAILABLE: Live weather impact cannot be verified. Operating with unadjusted baseline multipliers."
            ],
            "special_resource_recommended": None,
            "notes": "Weather impact NOT VERIFIED due to missing meteorological telemetry.",
        }

    temp = weather_data.get("temperature")
    rain = weather_data.get("rainfall_mm")
    wind = weather_data.get("wind_speed")

    # If all primary metrics are None, telemetry is insufficient
    if temp is None and rain is None and wind is None:
        return {
            "status": "INSUFFICIENT_EVIDENCE",
            "classification": "UNAVAILABLE",
            "verified": False,
            "severity_multiplier": 1.0,
            "rescue_time_multiplier": 1.0,
            "victim_multiplier": 1.0,
            "warnings": [
                "INSUFFICIENT METEOROLOGICAL TELEMETRY: Temperature, precipitation, and wind speeds unavailable. Weather impact NOT VERIFIED."
            ],
            "special_resource_recommended": None,
            "notes": "Weather impact NOT VERIFIED due to incomplete provider metrics.",
        }

    sev_mult = 1.0
    rescue_mult = 1.0
    victim_mult = 1.0
    warnings = []
    evaluated_metrics = []
    unverified_metrics = []
    special_res = None

    if rain is not None:
        evaluated_metrics.append(f"Rainfall: {rain} mm")
        if rain > 50:
            sev_mult += 0.4
            rescue_mult += 0.5
            victim_mult += 0.35
            warnings.append("FLASH FLOOD WARNING: Rainfall exceeds 50mm/hr.")
            special_res = "inflatable_boat"
        elif rain > 20:
            sev_mult += 0.2
            rescue_mult += 0.25
            warnings.append("MODERATE RAIN ALERT: Road visibility reduced.")
    else:
        unverified_metrics.append("Precipitation unavailable")

    if wind is not None:
        evaluated_metrics.append(f"Wind: {wind} km/h")
        if wind > 40:
            sev_mult += 0.3
            rescue_mult += 0.4
            warnings.append("HIGH WIND WARNING: Aerial drone & helicopter flights restricted.")
    else:
        unverified_metrics.append("Wind speed unavailable")

    if temp is not None:
        evaluated_metrics.append(f"Temperature: {temp}°C")
        if temp > 38:
            sev_mult += 0.25
            warnings.append("HEATWAVE ALERT: Increased fire risk.")
            if not special_res:
                special_res = "hazmat_unit"
    else:
        unverified_metrics.append("Temperature unavailable")

    if unverified_metrics:
        warnings.append(f"PARTIAL DATA NOTICE: Weather metrics not verified: {', '.join(unverified_metrics)}.")

    is_verified = len(unverified_metrics) == 0
    classification = "CALCULATED" if is_verified else "PARTIALLY_VERIFIED"
    status = "VERIFIED" if is_verified else "PARTIAL_EVIDENCE"

    return {
        "status": status,
        "classification": classification,
        "verified": is_verified,
        "severity_multiplier": round(sev_mult, 2),
        "rescue_time_multiplier": round(rescue_mult, 2),
        "victim_multiplier": round(victim_mult, 2),
        "warnings": warnings,
        "special_resource_recommended": special_res,
        "notes": f"Evaluated based on: {', '.join(evaluated_metrics)}." if evaluated_metrics else "No metrics verified.",
    }


def get_usgs_earthquakes() -> List[Dict[str, Any]]:
    """Fetch live USGS magnitude > 4.5 earthquake feed delegating to provider module."""
    eq_events = fetch_usgs_earthquakes(mag_min=4.5)
    results = []
    for eq in eq_events:
        results.append({
            "event_id": eq.source_event_id,
            "title": f"M {eq.magnitude} - {eq.place}",
            "place": eq.place,
            "magnitude": eq.magnitude,
            "latitude": eq.latitude,
            "longitude": eq.longitude,
            "source": eq.source,
            "classification": eq.classification,
        })
    return results


def get_gdacs_alerts() -> List[Dict[str, Any]]:
    """Fetch global disaster alerts delegating to provider module."""
    alerts = fetch_gdacs_disasters()
    results = []
    for a in alerts:
        results.append({
            "title": a.place or a.event_type,
            "link": a.source_url or "https://www.gdacs.org",
            "source": a.source,
            "classification": a.classification,
        })
    return results


def reverse_geocode(lat: float, lng: float) -> str:
    """Convert lat/lng to human-readable street address via Nominatim API delegating to provider module."""
    res = reverse_geocode_nominatim(lat, lng)
    if res and res.get("address"):
        return res["address"]
    return f"Sector ({lat:.3f}, {lng:.3f})"
