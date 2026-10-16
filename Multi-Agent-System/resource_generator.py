"""Dynamic Resource, Facility, Fleet Lifecycle & Hazard Generator for Hybrid Disaster Management.

Generates realistic simulated entities grounded in real geospatial coordinates:
- 7 Response Fleet Vehicle Types:
  1. Ambulance        - Medical evacuation & hospital trauma transport
  2. Fire Truck       - Urban firefighting & HAZMAT suppression
  3. Police Car       - Road closures, traffic diversion & perimeter security
  4. Rescue Boat      - Waterborne flood rescue along inundated rivers
  5. Helicopter       - Airborne airlift & remote medical drops
  6. Drone            - Aerial thermal scanning & survivor locating
  7. Supply Truck     - Emergency relief delivery to shelters
- 7-Stage Vehicle Lifecycle States:
  BASE -> MISSION_RECEIVED -> TRAVEL_ON_ROAD -> PICK_VICTIMS -> DELIVER_TO_HOSPITAL -> REFUEL -> READY_FOR_NEXT_MISSION
"""

import random
from typing import Any, Dict, List, Optional, Tuple



def generate_simulation_resources(
    seed: int = 42,
    center_lat: Optional[float] = None,
    center_lng: Optional[float] = None,
    city_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Generate 7 response vehicle types with full fuel, capacity, and lifecycle tracking.
    Grounds resources around the scenario center_lat / center_lng and tags them as SIMULATED.
    """
    rng = random.Random(seed)
    resources = []

    # If coordinates are missing, fail loudly instead of silently falling back to Mumbai
    if center_lat is None or center_lng is None:
        raise ValueError(
            "generate_simulation_resources requires center_lat and center_lng. "
            "The orchestrator must provide real scenario coordinates."
        )
    c_lat = center_lat
    c_lng = center_lng
    c_name = city_name or "Operational Sector"

    base_coords = [
        (f"{c_name} Central Hub", c_lat, c_lng),
        (f"{c_name} Sector North", round(c_lat + 0.012, 5), round(c_lng + 0.008, 5)),
        (f"{c_name} Sector South", round(c_lat - 0.014, 5), round(c_lng - 0.011, 5)),
        (f"{c_name} Sector East", round(c_lat + 0.005, 5), round(c_lng + 0.015, 5)),
        (f"{c_name} Bypass Base", round(c_lat + 0.025, 5), round(c_lng + 0.020, 5)),
    ]

    fleet_configs = [
        ("AMB", "Ambulance", "ambulance", "Medical Evacuation", 4, 75.0, "#ef4444"),
        ("FIR", "Fire Engine", "fire_truck", "Fire & HAZMAT Containment", 6, 60.0, "#f97316"),
        ("POL", "Police Cruiser", "police_car", "Traffic Diversion & Perimeter", 4, 85.0, "#3b82f6"),
        ("BOT", "Rescue Boat", "rescue_boat", "Waterborne Flood Evacuation", 8, 40.0, "#06b6d4"),
        ("HELI", "Air Medical Helicopter", "helicopter", "Airborne Airlift & Drop", 2, 180.0, "#a855f7"),
        ("DRN", "Recon Drone Alpha", "drone", "Aerial Thermal Scanning", 0, 90.0, "#10b981"),
        ("SUP", "Relief Supply Truck", "supply_truck", "Emergency Food & Tent Logistics", 10, 50.0, "#eab308"),
    ]

    resource_id_counter = 101

    for base_name, base_lat, base_lng in base_coords:
        for prefix, label, vtype, spec, cap, speed, color in fleet_configs:
            lat_offset = rng.uniform(-0.008, 0.008)
            lng_offset = rng.uniform(-0.008, 0.008)
            rid = f"{prefix}-{resource_id_counter}"
            resource_id_counter += 1

            resources.append({
                "resource_id": rid,
                "resource_name": f"{label} {rid}",
                "resource_type": vtype,
                "city": base_name,
                "latitude": round(base_lat + lat_offset, 5),
                "longitude": round(base_lng + lng_offset, 5),
                "home_latitude": base_lat,
                "home_longitude": base_lng,
                "status": "available",
                "lifecycle_state": "BASE",
                "capacity": cap,
                "victims_onboard": 0,
                "fuel_pct": rng.randint(75, 100),
                "specialization": spec,
                "speed_kmh": speed,
                "marker_color": color,
                "heading": rng.uniform(0, 360),
                "assigned_incident": None,
                "current_eta_min": 0.0,
                "classification": "SIMULATED",
            })

    return resources


def generate_facilities(
    seed: int = 42,
    center_lat: Optional[float] = None,
    center_lng: Optional[float] = None,
    city_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Generate simulated Civil Hospitals, Relief Shelters, and Emergency HQ for a scenario.
    All facilities are classified as SIMULATED with simulated capacity metrics.
    """
    rng = random.Random(seed + 1)
    facilities = []

    if center_lat is None or center_lng is None:
        raise ValueError(
            "generate_facilities requires center_lat and center_lng. "
            "The orchestrator must provide real scenario coordinates."
        )
    c_lat = center_lat
    c_lng = center_lng
    c_name = city_name or "Emergency Sector"

    facility_specs = [
        ("FAC-HOSP-01", f"{c_name} Trauma Central Hospital", "hospital", round(c_lat + 0.008, 5), round(c_lng + 0.005, 5), 300, 210, f"{c_name} Central"),
        ("FAC-HOSP-02", f"{c_name} Emergency Specialty Care", "hospital", round(c_lat + 0.016, 5), round(c_lng - 0.007, 5), 200, 140, f"{c_name} North"),
        ("FAC-SHEL-01", f"{c_name} Community Relief Dome", "shelter", round(c_lat + 0.019, 5), round(c_lng + 0.013, 5), 800, 480, f"{c_name} Highland"),
        ("FAC-SHEL-02", f"{c_name} Stadium Evacuation Camp", "shelter", round(c_lat + 0.032, 5), round(c_lng + 0.021, 5), 1200, 920, f"{c_name} Bypass"),
        ("FAC-POL-01", f"{c_name} Police Division EOC", "police_station", round(c_lat - 0.004, 5), round(c_lng - 0.002, 5), 150, 150, f"{c_name} Central"),
        ("FAC-FIR-01", f"{c_name} Fire & Rescue Station #1", "fire_station", round(c_lat + 0.009, 5), round(c_lng + 0.001, 5), 100, 100, f"{c_name} Sector 1"),
    ]

    for fid, name, ftype, lat, lng, total_cap, avail_cap, city in facility_specs:
        facilities.append({
            "facility_id": fid,
            "facility_name": name,
            "facility_type": ftype,
            "latitude": lat,
            "longitude": lng,
            "total_capacity": total_cap,
            "available_capacity": avail_cap,
            "city": city,
            "status": "operational",
            "phone": "+91 112-EOC",
            "classification": "SIMULATED",
            "capacity_status": "SIMULATED",
        })

    return facilities


def generate_blocked_roads(
    seed: int = 42,
    city_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Generate highway closures and blocked road hazards within the scenario context."""
    rng = random.Random(seed + 2)
    c_name = city_name or "Sector"
    cities = [f"{c_name} Central", f"{c_name} North", f"{c_name} Highland", f"{c_name} Harbor", f"{c_name} Bypass"]
    blocked_records = []
    pairs = [(cities[i], cities[i+1]) for i in range(len(cities)-1)]

    for idx, (city1, city2) in enumerate(pairs[:2], 1):
        blocked_records.append({
            "blockage_id": f"BLK-{idx:03d}",
            "from_city": city1,
            "to_city": city2,
            "reason": rng.choice(["Landslide Blockage", "Flash Flood Inundation", "Bridge Damage", "Severe Gridlock"]),
            "status": "blocked",
            "detour_available": True,
            "classification": "SIMULATED",
        })
    return blocked_records


def generate_disaster_zones(
    incidents_or_seed: Any = 42,
    center_lat: Optional[float] = None,
    center_lng: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Generate polygon/circle geo-zones for flood impact, earthquake seismic ripples, and safe zones.
    If seed is passed, creates zones centered around the given center_lat/center_lng if provided.
    """
    if isinstance(incidents_or_seed, (int, float)):
        if center_lat is None or center_lng is None:
            raise ValueError(
                "generate_disaster_zones requires center_lat and center_lng when given a seed. "
                "The orchestrator must provide real scenario coordinates."
            )
        c_lat = center_lat
        c_lng = center_lng
        incidents = [
            {"latitude": c_lat, "longitude": c_lng, "disaster_type": "flood", "severity": "high"},
            {"latitude": round(c_lat + 0.009, 5), "longitude": round(c_lng + 0.013, 5), "disaster_type": "earthquake", "severity": "medium"},
        ]
    elif isinstance(incidents_or_seed, list):
        incidents = incidents_or_seed
    else:
        incidents = []

    zones = []
    for idx, inc in enumerate(incidents, 1):
        lat = inc.get("latitude")
        lng = inc.get("longitude")
        dtype = str(inc.get("disaster_type", "flood")).lower()
        sev = str(inc.get("severity", "medium")).lower()

        if lat is None or lng is None:
            continue

        radius_m = 45000 if sev == "high" else 25000 if sev == "medium" else 12000

        if dtype == "flood":
            zones.append({
                "zone_id": f"ZONE-FLD-{idx}",
                "zone_name": f"Flood Inundation Sector #{idx}",
                "zone_type": "flood_zone",
                "center_latitude": lat,
                "center_longitude": lng,
                "radius_meters": radius_m,
                "color": "#38bdf8",
                "opacity": 0.25,
                "classification": "SIMULATED",
            })
        elif dtype == "earthquake":
            zones.append({
                "zone_id": f"ZONE-EQ-{idx}",
                "zone_name": f"Seismic Epicenter Radius #{idx}",
                "zone_type": "earthquake_zone",
                "center_latitude": lat,
                "center_longitude": lng,
                "radius_meters": radius_m * 1.2,
                "color": "#f0a44b",
                "opacity": 0.2,
                "classification": "SIMULATED",
            })

    return zones
