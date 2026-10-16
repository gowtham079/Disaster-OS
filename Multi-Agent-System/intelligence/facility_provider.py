"""Real Geographic & Facility Intelligence Provider via OpenStreetMap / Overpass API.

Retrieves verified real-world emergency facilities (hospitals, shelters, fire stations, police stations)
grounded in actual OpenStreetMap nodes and ways.
Strictly adheres to Disaster OS Data Provenance rules: NEVER fabricates hospital bed counts or shelter capacities.
If capacity tags are absent in OSM, capacity is explicitly set to None and marked UNAVAILABLE.
"""

import json
import logging
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from intelligence.models import CapacityStatus, DataClassification, FacilityRecord
from intelligence.source_health import health_manager

logger = logging.getLogger(__name__)

OVERPASS_ENDPOINTS = [
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://z.overpass-api.de/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]

AMENITY_TYPE_MAP = {
    "hospital": "hospital",
    "clinic": "hospital",
    "fire_station": "fire_station",
    "police": "police_station",
    "shelter": "shelter",
    "community_centre": "shelter",
    "social_facility": "shelter",
    "helipad": "helipad",
}


def build_overpass_query(lat: float, lng: float, radius_meters: int = 20000, limit: int = 60, timeout_seconds: int = 6) -> str:
    """Construct an optimized Overpass QL query for emergency amenities and helipads around a point."""
    amenities = "hospital|clinic|fire_station|police|shelter|community_centre"
    return (
        f"[out:json][timeout:{timeout_seconds}];\n"
        f"(\n"
        f'  node["amenity"~"{amenities}"](around:{radius_meters},{lat},{lng});\n'
        f'  way["amenity"~"{amenities}"](around:{radius_meters},{lat},{lng});\n'
        f'  node["aeroway"="helipad"](around:{radius_meters},{lat},{lng});\n'
        f'  way["aeroway"="helipad"](around:{radius_meters},{lat},{lng});\n'
        f");\n"
        f"out center {limit};\n"
    )


def _http_post_overpass(query: str, timeout: float = 10.0) -> bytes:
    """Execute Overpass query with failover across public mirror endpoints."""
    headers = {
        "User-Agent": "DisasterOS/3.0 (Emergency Operations Center Geographic Foundation)",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    last_error = None

    for endpoint in OVERPASS_ENDPOINTS:
        try:
            req = urllib.request.Request(endpoint, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as exc:
            last_error = exc
            logger.debug(f"Overpass mirror {endpoint} failed: {exc}. Trying next mirror.")

    raise last_error or RuntimeError("All Overpass mirrors unreachable")


def probe_overpass_health(timeout: float = 8.0) -> bool:
    """Lightweight Overpass query to verify connectivity and record health status."""
    query = '[out:json][timeout:5];node(18.9,72.8,19.2,73.0)["amenity"="hospital"];out 1;'
    start = time.time()
    try:
        raw_bytes = _http_post_overpass(query, timeout=timeout)
        duration_ms = (time.time() - start) * 1000
        data = json.loads(raw_bytes.decode("utf-8"))
        elements = data.get("elements", [])
        health_manager.record_success("Overpass", duration_ms, record_count=max(1, len(elements)))
        return True
    except Exception as exc:
        health_manager.record_failure("Overpass", str(exc))
        return False


def parse_overpass_elements(elements: List[Dict[str, Any]]) -> List[FacilityRecord]:
    """Parse raw Overpass JSON elements into normalized FacilityRecord models.

    Strict Data Provenance Rule:
    - Never fabricates hospital beds or shelter capacities.
    - Capacity is ONLY populated if an authoritative integer tag ('beds' or 'capacity') is present.
    """
    facilities: List[FacilityRecord] = []
    seen_ids = set()

    for el in elements:
        osm_type = el.get("type", "node")
        osm_id = el.get("id")
        if not osm_id:
            continue

        facility_id = f"osm-{osm_type}-{osm_id}"
        if facility_id in seen_ids:
            continue
        seen_ids.add(facility_id)

        # Coordinate extraction (node has lat/lon; way center has center.lat/center.lon)
        lat = el.get("lat")
        lng = el.get("lon")
        if lat is None or lng is None:
            center = el.get("center") or {}
            lat = center.get("lat")
            lng = center.get("lon")

        if lat is None or lng is None:
            continue

        try:
            lat = float(lat)
            lng = float(lng)
        except (ValueError, TypeError):
            continue

        tags = el.get("tags") or {}
        amenity = tags.get("amenity") or tags.get("aeroway") or "emergency_facility"
        fac_type = AMENITY_TYPE_MAP.get(amenity, "shelter")

        # Name normalization
        name = (
            tags.get("name")
            or tags.get("name:en")
            or tags.get("official_name")
            or tags.get("operator")
        )
        if not name:
            type_label = fac_type.replace("_", " ").title()
            name = f"{type_label} (OSM #{osm_id})"

        # Address construction
        addr_parts = [
            tags.get("addr:housenumber"),
            tags.get("addr:street"),
            tags.get("addr:suburb"),
            tags.get("addr:district"),
            tags.get("addr:city"),
        ]
        address = ", ".join([p for p in addr_parts if p]) or tags.get("addr:full") or None
        city = tags.get("addr:city") or tags.get("addr:district") or None

        # Honest Capacity Parsing — NEVER FABRICATE
        raw_capacity = tags.get("beds") or tags.get("capacity")
        parsed_capacity: Optional[int] = None
        capacity_status = CapacityStatus.UNAVAILABLE

        if raw_capacity:
            try:
                val = int(str(raw_capacity).strip().split(";")[0].split()[0])
                if val > 0:
                    parsed_capacity = val
                    capacity_status = CapacityStatus.VERIFIED
            except (ValueError, TypeError):
                parsed_capacity = None
                capacity_status = CapacityStatus.UNAVAILABLE

        phone = tags.get("phone") or tags.get("contact:phone") or tags.get("emergency:phone") or None
        emergency = tags.get("emergency") != "no"

        metadata = {
            "osm_type": osm_type,
            "osm_id": osm_id,
            "amenity": amenity,
            "operator": tags.get("operator"),
            "wheelchair": tags.get("wheelchair"),
            "opening_hours": tags.get("opening_hours"),
            "website": tags.get("website") or tags.get("contact:website"),
        }

        rec = FacilityRecord(
            facility_id=facility_id,
            facility_type=fac_type,
            name=name,
            latitude=round(lat, 6),
            longitude=round(lng, 6),
            address=address,
            city=city,
            source="OpenStreetMap",
            source_id=f"{osm_type}/{osm_id}",
            classification=DataClassification.LIVE,
            fetched_at=time.time(),
            capacity=parsed_capacity,
            available_capacity=None,  # Live occupancy sensors currently unavailable
            capacity_status=capacity_status,
            phone=phone,
            emergency_service=emergency,
            metadata=metadata,
        )
        facilities.append(rec)

    return facilities


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2.0) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
    return R * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def fetch_real_facilities(
    lat: float,
    lng: float,
    radius_km: float = 20.0,
    facility_type: Optional[str] = None,
    use_cache: bool = True,
    timeout: float = 8.0,
) -> Tuple[List[FacilityRecord], str]:
    """Fetch real facilities from OpenStreetMap via Overpass API with local SQLite cache & health tracking.

    Returns:
    --------
    (facilities, provenance_classification)
    provenance_classification is 'LIVE' if freshly fetched, 'DATABASE' if from cache, 'UNAVAILABLE' if empty/error.
    """
    import database

    radius_meters = int(min(50.0, max(1.0, radius_km)) * 1000)
    grid_lat = round(lat, 2)
    grid_lng = round(lng, 2)
    cache_key = f"overpass_fac_{grid_lat}_{grid_lng}_{radius_meters}"

    # 1. Check local SQLite geographic cache and persisted facilities if requested
    if use_cache:
        cached_payload = database.get_geographic_cache(cache_key)
        if cached_payload and isinstance(cached_payload, list):
            try:
                valid_facs = []
                for item in cached_payload:
                    f = FacilityRecord(**item)
                    if f.latitude is not None and f.longitude is not None:
                        dist = _haversine_distance(lat, lng, float(f.latitude), float(f.longitude))
                        if dist <= radius_km:
                            f.classification = DataClassification.DATABASE
                            if not facility_type or f.facility_type == facility_type:
                                valid_facs.append(f)
                if valid_facs:
                    return valid_facs, DataClassification.DATABASE.value
            except Exception as e:
                logger.warning(f"Error decoding cached facility records: {e}")

        # Check geographically valid persisted facilities in database
        try:
            persisted = database.get_external_facilities(
                facility_type=facility_type, lat=lat, lng=lng, radius_km=radius_km
            )
            if persisted and len(persisted) >= 2:
                valid_recs = []
                for item in persisted:
                    f_lat = item.get("latitude")
                    f_lng = item.get("longitude")
                    if f_lat is not None and f_lng is not None:
                        dist = _haversine_distance(lat, lng, float(f_lat), float(f_lng))
                        if dist <= radius_km:
                            item["distance_km"] = round(dist, 2)
                            r = FacilityRecord(**item)
                            r.classification = DataClassification.DATABASE
                            valid_recs.append(r)
                if valid_recs:
                    return valid_recs, DataClassification.DATABASE.value
        except Exception as e:
            logger.debug(f"Persisted facilities check error: {e}")

    # 2. Query Overpass API
    start_time = time.time()
    query = build_overpass_query(lat=lat, lng=lng, radius_meters=radius_meters, limit=60)

    try:
        raw_bytes = _http_post_overpass(query, timeout=timeout)
        duration_ms = (time.time() - start_time) * 1000
        data = json.loads(raw_bytes.decode("utf-8"))
        elements = data.get("elements", [])

        facilities = parse_overpass_elements(elements)

        # Save to SQLite geographic_cache (24-hour TTL)
        serializable_facs = [f.model_dump() for f in facilities]
        database.set_geographic_cache(cache_key, "facilities", serializable_facs, ttl_seconds=86400)

        # Also persist individual facility records into external_facilities table
        database.save_external_facilities(serializable_facs)

        health_manager.record_success("Overpass", duration_ms, record_count=len(facilities))

        if facility_type:
            facilities = [f for f in facilities if f.facility_type == facility_type]

        return facilities, DataClassification.LIVE.value

    except Exception as e:
        health_manager.record_failure("Overpass", str(e))
        logger.warning(f"Overpass facility query failed: {e}. Checking persisted database records.")

        # Fallback to previously stored external facilities in database within radius
        try:
            persisted = database.get_external_facilities(
                facility_type=facility_type, lat=lat, lng=lng, radius_km=radius_km
            )
            valid_recs = []
            if persisted:
                for item in persisted:
                    f_lat = item.get("latitude")
                    f_lng = item.get("longitude")
                    if f_lat is not None and f_lng is not None:
                        dist = _haversine_distance(lat, lng, float(f_lat), float(f_lng))
                        if dist <= radius_km:
                            item["distance_km"] = round(dist, 2)
                            r = FacilityRecord(**item)
                            r.classification = DataClassification.DATABASE
                            valid_recs.append(r)
            if valid_recs:
                return valid_recs, DataClassification.DATABASE.value
        except Exception as db_err:
            logger.error(f"Failed querying persisted facilities: {db_err}")

        # Zero fake data / zero unrelated geographic data rule:
        return [], DataClassification.UNAVAILABLE.value
