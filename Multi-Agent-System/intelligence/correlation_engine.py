"""Compound Disaster Event Correlation & Cascading Hazard Modeling Engine.

Phase P3.3 Implementation:
- Spatio-temporal clustering of multi-source events (USGS seismic, GDACS alerts, Weather, EOC incidents)
- Physical causal cascade rule evaluation (Earthquake -> Power Failure -> Hospital Generator Strain; Heavy Rain -> Urban Inundation -> Route Submergence; Offshore Seismic -> Coastal Tsunami Surge)
- Directed cascade risk graph computation with conditional probabilities
- Honest data provenance: exposes mathematical methodology, correlation parameters, and confidence scores (CALCULATED classification).
"""

import logging
import math
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import database
from intelligence.models import DataClassification

logger = logging.getLogger(__name__)


def haversine_distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Compute great-circle distance between coordinates in kilometers."""
    try:
        r = 6371.0
        d_lat = math.radians(lat2 - lat1)
        d_lng = math.radians(lng2 - lng1)
        a = (
            math.sin(d_lat / 2.0) ** 2
            + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lng / 2.0) ** 2
        )
        return r * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    except Exception:
        return 999.0


# ── Physical Correlation Rule Definitions ──────────────────────────────────

def evaluate_seismic_infrastructure_cascade(
    earthquake: Dict[str, Any],
    facilities: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Evaluate earthquake-induced lifeline failure cascade (substations, hospital trauma facilities)."""
    mag = float(earthquake.get("magnitude") or 0.0)
    eq_lat = float(earthquake.get("latitude") or 0.0)
    eq_lng = float(earthquake.get("longitude") or 0.0)

    if mag < 5.2:
        return None

    # Check for facilities within empirical shaking zone
    radius_km = 10.0 ** (0.45 * mag - 1.55)
    exposed_hospitals = []

    for f in facilities:
        flat = f.get("latitude")
        flng = f.get("longitude")
        if flat is not None and flng is not None:
            dist = haversine_distance_km(eq_lat, eq_lng, flat, flng)
            if dist <= radius_km and f.get("facility_type") == "hospital":
                exposed_hospitals.append({
                    "facility_id": f.get("facility_id") or f.get("id"),
                    "name": f.get("name") or f.get("facility_name"),
                    "distance_km": round(dist, 1),
                })

    cascade_prob = min(0.95, round(0.35 + 0.12 * (mag - 5.0), 2))
    risk_level = "CRITICAL" if mag >= 6.2 or exposed_hospitals else "ELEVATED"

    chain = [
        f"Primary Seismic Shock (M{mag:.1f}) at focal depth {earthquake.get('depth_km', 10)}km (Observed Trigger)",
        "CALCULATED CASCADE RISK: Modelled ground motion peak acceleration indicates potential tripping of electrical distribution substations (Unverified physical occurrence)",
        f"CALCULATED CASCADE RISK: Potential grid power disruption risk across {len(exposed_hospitals)} regional trauma centers within isoseismal perimeter",
        "RECOMMENDED PRECAUTION: Verification of backup diesel generator fuel autonomy and emergency circuits",
    ]

    recommendations = [
        "Pre-stage emergency mobile power generators near high-density medical centers.",
        "Dispatch structural integrity reconnaissance teams to verify bridge overpasses within isoseismal perimeter.",
        "Verify generator fuel autonomy (>72 hours) at all tier-1 response facilities.",
    ]

    evidence_chain = [
        {
            "source": earthquake.get("source", "USGS"),
            "source_event_id": str(earthquake.get("event_id") or earthquake.get("id")),
            "timestamp": earthquake.get("observed_at") or time.time(),
            "classification": str(earthquake.get("classification", "LIVE")),
            "type": "OBSERVED_TRIGGER",
            "description": f"Seismic event M{mag:.1f} at {earthquake.get('place', 'epicenter')}",
        },
        {
            "source": "Disaster OS Empirical Attenuation Model",
            "source_event_id": f"ISOSEISMAL-R-{round(radius_km, 1)}KM",
            "timestamp": time.time(),
            "classification": "CALCULATED",
            "type": "MODELLED_PROJECTION",
            "description": f"Isoseismal severe shaking perimeter calculated at {round(radius_km, 1)}km with {len(exposed_hospitals)} hospitals exposed",
        },
    ]

    return {
        "correlation_type": "SEISMIC_INFRASTRUCTURE_FAILURE",
        "primary_event_id": earthquake.get("event_id") or str(earthquake.get("id")),
        "secondary_event_type": "LIFELINE_GRID_DISRUPTION",
        "confidence_score": cascade_prob,
        "confidence_score_label": "MODELLED_CONDITIONAL_PROBABILITY",
        "cascade_risk_level": risk_level,
        "classification": DataClassification.CALCULATED.value,
        "affected_facilities": exposed_hospitals,
        "cascade_chain": chain,
        "evidence_chain": evidence_chain,
        "recommendations": recommendations,
        "trigger_parameters": {
            "magnitude": mag,
            "shaking_radius_km": round(radius_km, 1),
            "hospitals_exposed_count": len(exposed_hospitals),
            "evidence_chain": evidence_chain,
        },
    }


def evaluate_coastal_tsunami_cascade(
    earthquake: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Evaluate offshore seismic triggering of coastal tsunami surges."""
    mag = float(earthquake.get("magnitude") or 0.0)
    depth = float(earthquake.get("depth_km") or 10.0)
    place = str(earthquake.get("place") or "").lower()

    coastal_keywords = ["sea", "ocean", "coast", "bay", "island", "gulf", "channel", "strait", "off"]
    is_marine_or_coastal = any(k in place for k in coastal_keywords)

    if mag < 6.5 or depth > 60.0 or not is_marine_or_coastal:
        return None

    tsunami_prob = min(0.92, round(0.40 + 0.18 * (mag - 6.5) - 0.003 * depth, 2))
    risk_level = "CRITICAL" if mag >= 7.0 else "ELEVATED"

    chain = [
        f"High-Magnitude Offshore Rupture (M{mag:.1f}, depth {depth:.0f}km) (Observed Trigger)",
        "CALCULATED CASCADE RISK: Modelled seafloor displacement indicates potential coastal tsunami wave propagation (Unverified wave arrival)",
        "CALCULATED CASCADE RISK: Modelled estuarine surge and low-lying coastal arterial inundation risk",
        "RECOMMENDED PRECAUTION: Activation of coastal early warning sirens and harbour departure halts",
    ]

    recommendations = [
        "Issue immediate coastal low-lying area evacuation advisories (elevation < 10m MSL).",
        "Halt all marine harbor departures and instruct vessels to proceed to deep water (>100 fathom).",
        "Activate coastal early warning siren networks and broadcast emergency SMS bursts.",
    ]

    evidence_chain = [
        {
            "source": earthquake.get("source", "USGS"),
            "source_event_id": str(earthquake.get("event_id") or earthquake.get("id")),
            "timestamp": earthquake.get("observed_at") or time.time(),
            "classification": str(earthquake.get("classification", "LIVE")),
            "type": "OBSERVED_TRIGGER",
            "description": f"Offshore seismic rupture M{mag:.1f} near {earthquake.get('place')}",
        },
        {
            "source": "Disaster OS Tsunami Propagation Model",
            "source_event_id": "TSUNAMI-SURGE-PROJECTION",
            "timestamp": time.time(),
            "classification": "CALCULATED",
            "type": "MODELLED_PROJECTION",
            "description": f"Marine rupture depth {depth}km triggers calculated coastal inundation warning",
        },
    ]

    return {
        "correlation_type": "COASTAL_TSUNAMI_SURGE",
        "primary_event_id": earthquake.get("event_id") or str(earthquake.get("id")),
        "secondary_event_type": "COASTAL_INUNDATION",
        "confidence_score": tsunami_prob,
        "confidence_score_label": "MODELLED_CONDITIONAL_PROBABILITY",
        "cascade_risk_level": risk_level,
        "classification": DataClassification.CALCULATED.value,
        "affected_facilities": [],
        "cascade_chain": chain,
        "evidence_chain": evidence_chain,
        "recommendations": recommendations,
        "trigger_parameters": {
            "magnitude": mag,
            "depth_km": depth,
            "location": earthquake.get("place"),
            "evidence_chain": evidence_chain,
        },
    }


def evaluate_hydrometeorological_cascade(
    weather: Dict[str, Any],
    incidents: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Evaluate precipitation deluge compounding into urban flash flooding and road blockages."""
    rainfall = float(weather.get("rainfall_mm") or weather.get("precipitation_mm") or 0.0)
    wind = float(weather.get("wind_speed_kmh") or 0.0)

    if rainfall < 30.0 and wind < 60.0:
        return None

    # Correlate with active flood/traffic incidents
    correlated_incidents = [
        inc for inc in incidents
        if any(k in str(inc.get("disaster_type", "")).lower() for k in ["flood", "water", "drainage", "traffic", "accident"])
    ]

    flood_prob = min(0.95, round(0.40 + 0.008 * rainfall + 0.004 * wind, 2))
    risk_level = "CRITICAL" if rainfall >= 60.0 or len(correlated_incidents) >= 2 else "ELEVATED"

    chain = [
        f"Hydrometeorological Deluge: {rainfall:.1f}mm/h rainfall, {wind:.1f}km/h gusts (Observed Weather)",
        "CALCULATED CASCADE RISK: Urban storm drainage capacity saturated (Runoff exceeding storm culvert design threshold)",
        f"CALCULATED CASCADE RISK: Surface water accumulation compromising {len(correlated_incidents)} local sectors",
        "RECOMMENDED PRECAUTION: Underpass submergence avoidance and secondary evacuation corridor impedance monitoring",
    ]

    recommendations = [
        "Deploy high-capacity dewatering pumps to documented arterial underpasses.",
        "Reroute emergency response fleet away from low-elevation riverine floodplains.",
        "Pre-position high-clearance rescue vehicles and inflatable zodiac craft.",
    ]

    evidence_chain = [
        {
            "source": weather.get("source", "Meteorological Feed"),
            "source_event_id": "WX-LIVE-OBS",
            "timestamp": weather.get("timestamp") or time.time(),
            "classification": str(weather.get("classification", "LIVE")),
            "type": "OBSERVED_WEATHER",
            "description": f"Precipitation {rainfall:.1f}mm/h with gusts of {wind:.1f}km/h",
        },
    ]
    for inc in correlated_incidents[:3]:
        evidence_chain.append({
            "source": "EOC Incident Log",
            "source_event_id": f"INC-{inc.get('incident_id')}",
            "timestamp": time.time(),
            "classification": str(inc.get("classification", "SIMULATED")),
            "type": "CO-LOCATED_INCIDENT",
            "description": f"{inc.get('disaster_type', 'Incident')} at {inc.get('location', 'Area')}",
        })

    return {
        "correlation_type": "METEOROLOGICAL_INUNDATION_CASCADE",
        "primary_event_id": f"WX-{int(time.time())}",
        "secondary_event_type": "URBAN_FLASH_FLOOD",
        "confidence_score": flood_prob,
        "confidence_score_label": "MODELLED_CONDITIONAL_PROBABILITY",
        "cascade_risk_level": risk_level,
        "classification": DataClassification.CALCULATED.value,
        "affected_facilities": [],
        "cascade_chain": chain,
        "evidence_chain": evidence_chain,
        "recommendations": recommendations,
        "trigger_parameters": {
            "rainfall_mm": rainfall,
            "wind_speed_kmh": wind,
            "correlated_incidents_count": len(correlated_incidents),
            "evidence_chain": evidence_chain,
        },
    }


# ── Master Compound Event Detection Orchestrator ──────────────────────────

def detect_compound_disaster_events(
    earthquakes: Optional[List[Dict[str, Any]]] = None,
    disasters: Optional[List[Dict[str, Any]]] = None,
    incidents: Optional[List[Dict[str, Any]]] = None,
    facilities: Optional[List[Dict[str, Any]]] = None,
    weather: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Execute multi-hazard correlation analysis and return detected compound events."""
    earthquakes = earthquakes or []
    disasters = disasters or []
    incidents = incidents or []
    facilities = facilities or []
    weather = weather or {}

    compound_events: List[Dict[str, Any]] = []

    # 1. Evaluate Seismic Lifeline Cascades
    for eq in earthquakes[:10]:
        cascade = evaluate_seismic_infrastructure_cascade(eq, facilities)
        if cascade:
            compound_id = f"COMP-SEIS-{uuid.uuid4().hex[:8].upper()}"
            cascade["compound_id"] = compound_id
            cascade["classification"] = DataClassification.CALCULATED.value
            cascade["detected_at"] = time.time()
            compound_events.append(cascade)

    # 2. Evaluate Coastal Tsunami Cascades
    for eq in earthquakes[:10]:
        tsunami = evaluate_coastal_tsunami_cascade(eq)
        if tsunami:
            compound_id = f"COMP-TSU-{uuid.uuid4().hex[:8].upper()}"
            tsunami["compound_id"] = compound_id
            tsunami["classification"] = DataClassification.CALCULATED.value
            tsunami["detected_at"] = time.time()
            compound_events.append(tsunami)

    # 3. Evaluate Hydrometeorological Deluge Cascades
    if weather and weather.get("classification") != "UNAVAILABLE":
        hydro = evaluate_hydrometeorological_cascade(weather, incidents)
        if hydro:
            compound_id = f"COMP-HYDRO-{uuid.uuid4().hex[:8].upper()}"
            hydro["compound_id"] = compound_id
            hydro["classification"] = DataClassification.CALCULATED.value
            hydro["detected_at"] = time.time()
            compound_events.append(hydro)

    # 4. Spatio-temporal Cross-Incident Correlator
    # If multiple severe incidents happen within 15km, flag multi-sector stress
    if len(incidents) >= 2:
        for i in range(len(incidents)):
            for j in range(i + 1, len(incidents)):
                inc1 = incidents[i]
                inc2 = incidents[j]
                lat1, lng1 = inc1.get("latitude"), inc1.get("longitude")
                lat2, lng2 = inc2.get("latitude"), inc2.get("longitude")
                if lat1 is not None and lng1 is not None and lat2 is not None and lng2 is not None:
                    dist = haversine_distance_km(float(lat1), float(lng1), float(lat2), float(lng2))
                    if dist <= 15.0:
                        compound_id = f"COMP-CLUSTER-{uuid.uuid4().hex[:8].upper()}"
                        cluster_evidence = [
                            {
                                "source": "EOC Incident Log",
                                "source_event_id": f"INC-{inc1.get('incident_id')}",
                                "timestamp": time.time(),
                                "classification": "SIMULATED" if inc1.get("simulated") else "DATABASE",
                                "type": "ACTIVE_INCIDENT",
                                "description": f"{inc1.get('disaster_type', 'Incident')} at {inc1.get('location', 'Sector')}",
                            },
                            {
                                "source": "EOC Incident Log",
                                "source_event_id": f"INC-{inc2.get('incident_id')}",
                                "timestamp": time.time(),
                                "classification": "SIMULATED" if inc2.get("simulated") else "DATABASE",
                                "type": "ACTIVE_INCIDENT",
                                "description": f"{inc2.get('disaster_type', 'Incident')} at {inc2.get('location', 'Sector')}",
                            },
                        ]
                        compound_events.append({
                            "compound_id": compound_id,
                            "correlation_type": "MULTI_SECTOR_URBAN_COMPLEX",
                            "primary_event_id": str(inc1.get("incident_id") or inc1.get("id")),
                            "secondary_event_id": str(inc2.get("incident_id") or inc2.get("id")),
                            "confidence_score": round(min(0.90, max(0.50, 1.0 - (dist / 20.0))), 2),
                            "confidence_score_label": "MODELLED_PROXIMITY_COEFFICIENT",
                            "cascade_risk_level": "ELEVATED",
                            "classification": DataClassification.CALCULATED.value,
                            "affected_facilities": [],
                            "cascade_chain": [
                                f"Incident INC-{inc1.get('incident_id')} ({inc1.get('disaster_type')})",
                                f"Concurrent Incident INC-{inc2.get('incident_id')} ({inc2.get('disaster_type')}) within {dist:.1f}km",
                                "CALCULATED CASCADE RISK: Simultaneous localized demand converging on first-responder emergency fleet",
                            ],
                            "evidence_chain": cluster_evidence,
                            "recommendations": [
                                "Coordinate dispatch routing to avoid fleet congestion at common arterial interchanges.",
                                "Establish unified field forward command post between incident sectors.",
                            ],
                            "trigger_parameters": {
                                "distance_km": round(dist, 1),
                                "incident_types": [inc1.get("disaster_type"), inc2.get("disaster_type")],
                                "evidence_chain": cluster_evidence,
                            },
                            "detected_at": time.time(),
                        })

    # Persist compound events in SQLite
    for ce in compound_events:
        try:
            database.save_compound_event(ce)
        except Exception as exc:
            logger.warning(f"Failed to persist compound event {ce.get('compound_id')}: {exc}")

    return compound_events
