"""Transparent Tactical Decision Support Engine.

Computes verifiable operational recommendations based strictly on:
- Incident severity and affected population
- Nearby hospital and shelter capacities (Haversine distance <= 50km)
- Available response fleet readiness
- Road blockage proximity
- Weather conditions (rainfall, wind)
- Live seismic intelligence

Outputs structured recommendations with explicit reasoning and evidence chains.
"""

import math
from typing import Any, Dict, List, Optional


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate the great-circle distance between two geographic coordinates in kilometers."""
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


def evaluate_tactical_decision(
    incident: Dict[str, Any],
    facilities: Optional[List[Dict[str, Any]]] = None,
    fleet: Optional[List[Dict[str, Any]]] = None,
    roadblocks: Optional[List[Dict[str, Any]]] = None,
    weather: Optional[Dict[str, Any]] = None,
    earthquakes: Optional[List[Dict[str, Any]]] = None,
    impact_assessment: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generate a structured, evidence-backed tactical recommendation for an incident."""
    if not incident or incident.get("latitude") is None or incident.get("longitude") is None:
        return {
            "classification": "CALCULATED DECISION SUPPORT",
            "priority_level": "INSUFFICIENT EVIDENCE",
            "recommended_resources": [],
            "suggested_hospital": "Location coordinates unavailable to evaluate nearby hospital capacity.",
            "suggested_shelter": "Location coordinates unavailable to evaluate nearby shelter capacity.",
            "evacuation_recommendation": "Awaiting geolocation coordinates for corridor planning.",
            "route_considerations": ["Routing suspended: missing target coordinates."],
            "operational_risks": ["Insufficient geolocation evidence."],
            "confidence_score": 0.0,
            "reasoning_and_evidence": ["Incident record lacks valid geographical coordinates."],
            "impact_assessment": None,
        }

    inc_lat = float(incident.get("latitude"))
    inc_lng = float(incident.get("longitude"))
    severity = str(incident.get("severity") or "low").lower()
    disaster_type = str(incident.get("disaster_type") or "incident").lower()
    affected = int(incident.get("people_affected") or 0)

    facilities = facilities or []
    fleet = fleet or []
    roadblocks = roadblocks or []
    weather = weather or {}
    earthquakes = earthquakes or []

    evidence: List[str] = []
    risks: List[str] = []

    # 1. Nearby Hospitals & Shelters
    nearby_hospitals = []
    nearby_shelters = []
    if inc_lat is not None and inc_lng is not None:
        for f in facilities:
            flat = f.get("latitude")
            flng = f.get("longitude")
            if flat is not None and flng is not None:
                dist = haversine_km(inc_lat, inc_lng, flat, flng)
                if f.get("facility_type") == "hospital" and dist <= 50.0:
                    nearby_hospitals.append({**f, "distance_km": round(dist, 1)})
                elif f.get("facility_type") == "shelter" and dist <= 50.0:
                    nearby_shelters.append({**f, "distance_km": round(dist, 1)})

    nearby_hospitals.sort(key=lambda x: x.get("distance_km", 999))
    nearby_shelters.sort(key=lambda x: x.get("distance_km", 999))

    suggested_hospital = None
    if nearby_hospitals:
        # Pick closest hospital with available beds
        avail_hosp = [h for h in nearby_hospitals if (h.get("available_capacity") or 0) > 0]
        chosen = avail_hosp[0] if avail_hosp else nearby_hospitals[0]
        suggested_hospital = f"{chosen.get('facility_name')} ({chosen.get('distance_km')} km, {chosen.get('available_capacity')}/{chosen.get('total_capacity')} beds available)"
        evidence.append(f"Selected hospital within {chosen.get('distance_km')} km with {chosen.get('available_capacity')} available beds.")
    else:
        suggested_hospital = "Deploy mobile trauma station (No hospitals within 50 km)."
        risks.append("No fixed hospital within 50km radius.")

    suggested_shelter = None
    if nearby_shelters:
        avail_sh = [s for s in nearby_shelters if (s.get("available_capacity") or 0) > 0]
        chosen_s = avail_sh[0] if avail_sh else nearby_shelters[0]
        suggested_shelter = f"{chosen_s.get('facility_name')} ({chosen_s.get('distance_km')} km, {chosen_s.get('available_capacity')}/{chosen_s.get('total_capacity')} capacity)"
        evidence.append(f"Selected relief shelter within {chosen_s.get('distance_km')} km.")
    else:
        suggested_shelter = "Establish temporary field camp (No shelters within 50 km)."

    # 2. Fleet Resource Recommendations
    avail_ambulances = len([r for r in fleet if r.get("resource_type") == "ambulance" and r.get("status") == "available"])
    avail_fire = len([r for r in fleet if r.get("resource_type") == "fire_truck" and r.get("status") == "available"])
    avail_boats = len([r for r in fleet if r.get("resource_type") == "rescue_boat" and r.get("status") == "available"])
    avail_drones = len([r for r in fleet if r.get("resource_type") == "drone" and r.get("status") == "available"])

    rec_resources = []
    if severity == "high":
        req_amb = min(avail_ambulances, max(2, affected // 10))
        rec_resources.append(f"{req_amb}x Ambulances")
        if "fire" in disaster_type or "explosion" in disaster_type or "hazmat" in disaster_type:
            rec_resources.append(f"{min(avail_fire, 2)}x Fire Engines")
        if "flood" in disaster_type or "cyclone" in disaster_type or "tsunami" in disaster_type:
            rec_resources.append(f"{min(avail_boats, 2)}x Rescue Boats")
        if avail_drones > 0:
            rec_resources.append("1x Recon Drone (Aerial Survey)")
        priority_level = "PRIORITY 1 - IMMEDIATE INTERVENTION"
        evacuation = f"Immediate mandatory evacuation of {affected} persons to {suggested_shelter.split('(')[0].strip()}."
    elif severity == "medium":
        rec_resources.append(f"{min(avail_ambulances, 2)}x Ambulances")
        priority_level = "PRIORITY 2 - RAPID RESPONSE"
        evacuation = "Stage evacuation corridor and issue citizen advisories."
    else:
        rec_resources.append("1x Rapid Assessment Unit")
        priority_level = "PRIORITY 3 - MONITOR & STABILIZE"
        evacuation = "Shelter-in-place recommended under local monitoring."

    evidence.append(f"Severity '{severity.upper()}' with {affected} affected population requires {', '.join(rec_resources)}.")

    # 3. Weather & Roadblock Considerations
    rainfall = weather.get("rainfall_mm")
    temp = weather.get("temperature")
    wind = weather.get("wind_speed")
    if rainfall is not None and rainfall > 20:
        risks.append(f"Heavy rainfall ({rainfall} mm/h) may increase transit delays.")
        evidence.append(f"Weather alert: {rainfall} mm/h rainfall recorded at coordinates.")
    elif weather.get("classification") == "UNAVAILABLE" or (rainfall is None and temp is None and wind is None):
        evidence.append("Meteorological data unavailable: Live weather impact not verified.")

    route_considerations = []
    if roadblocks:
        route_considerations.append(f"{len(roadblocks)} active road blockages identified; dynamic OSRM rerouting active.")
        evidence.append(f"{len(roadblocks)} blocked roads accounted for in navigation.")
    else:
        route_considerations.append("Primary arterial roads reported open and passable.")

    # 4. Live Seismic Proximity
    nearby_eqs = []
    if inc_lat is not None and inc_lng is not None:
        for eq in earthquakes:
            eq_lat = eq.get("latitude")
            eq_lng = eq.get("longitude")
            if eq_lat is not None and eq_lng is not None:
                dist = haversine_km(inc_lat, inc_lng, eq_lat, eq_lng)
                if dist <= 150.0:
                    nearby_eqs.append(f"M{eq.get('magnitude', 0):.1f} {dist:.0f}km away")

    if nearby_eqs:
        risks.append(f"Seismic activity nearby: {', '.join(nearby_eqs[:2])}. Assess structural stability.")
        evidence.append(f"USGS live earthquake spatial correlation: {', '.join(nearby_eqs[:2])}.")

    # 5. Calculated Impact Assessment Modeling (Phase P3.2)
    if impact_assessment:
        method = impact_assessment.get("methodology", "Empirical Hazard Modeling")
        conf = impact_assessment.get("confidence", "APPROXIMATE_ANALYTICAL")
        acc_status = impact_assessment.get("route_accessibility_status", "CLEAR")
        exposed_facs = impact_assessment.get("facilities_in_impact_zone", [])

        evidence.append(f"Impact Model: {method} (Confidence: {conf}) identified {len(exposed_facs)} exposed infrastructure facilities.")

        if acc_status == "DISRUPTED_SECONDARY_ROADS":
            route_considerations.append("Impact Model Alert: Secondary arterial network disrupted due to severe shaking/inundation threshold.")
            risks.append("Secondary access routes compromised; deploy high-clearance or aerial reconnaissance units.")
        elif acc_status == "CAUTION_URBAN_ARTERIALS":
            route_considerations.append("Impact Model Advisory: Heightened risk on urban arterial corridors.")

        # Check for critical facilities inside severe impact zone
        severe_facilities = [
            f for f in exposed_facs
            if "VII" in str(f.get("impact_tier", "")) or "CRITICAL" in str(f.get("impact_tier", "")).upper()
        ]
        if severe_facilities:
            crit_names = [f.get("name") for f in severe_facilities[:2]]
            risks.append(f"Severe shaking zone contains {len(severe_facilities)} critical facilities ({', '.join(crit_names)}). Verify structural integrity before dispatch.")

    confidence_score = round(min(0.98, max(0.40, len(evidence) * 0.20)), 2)

    return {
        "classification": "CALCULATED DECISION SUPPORT",
        "priority_level": priority_level,
        "recommended_resources": rec_resources,
        "suggested_hospital": suggested_hospital,
        "suggested_shelter": suggested_shelter,
        "evacuation_recommendation": evacuation,
        "route_considerations": route_considerations,
        "operational_risks": risks if risks else ["No abnormal hazard risks detected."],
        "confidence_score": confidence_score,
        "reasoning_and_evidence": evidence,
        "impact_assessment": impact_assessment,
    }
