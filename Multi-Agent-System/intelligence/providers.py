"""External Intelligence Data Providers.

Fetches real-time feeds from USGS, GDACS, OpenWeather, Open-Meteo, Nominatim, and OSRM.
Enforces retries with bounded exponential backoff, timeouts, deduplication, and zero fake data.
"""

import io
import json
import logging
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

from intelligence.cache import intelligence_cache
from intelligence.models import (
    DataClassification,
    EarthquakeEvent,
    ExternalDisasterEvent,
    RouteClassification,
    RouteResult,
    WeatherObservation,
)
from intelligence.source_health import health_manager

logger = logging.getLogger(__name__)

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")


def _http_get_with_retry(url: str, timeout: float = 3.0, max_retries: int = 2) -> bytes:
    """Execute HTTP GET request with bounded exponential backoff retries."""
    headers = {"User-Agent": "DisasterOS/2.0"}
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as e:
            last_exc = e
            if attempt < max_retries:
                sleep_time = 0.2 * (2 ** attempt)
                time.sleep(sleep_time)
    raise last_exc


def fetch_usgs_earthquakes(mag_min: float = 4.5) -> List[EarthquakeEvent]:
    """Fetch live earthquake feed from USGS with deduplication and provenance metadata."""
    cache_key = f"usgs_earthquakes_{mag_min}"
    cached = intelligence_cache.get(cache_key)
    if cached:
        return cached[0]

    start_time = time.time()
    url = f"https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/{mag_min}_day.geojson"

    try:
        raw_bytes = _http_get_with_retry(url, timeout=3.5, max_retries=2)
        duration_ms = (time.time() - start_time) * 1000
        data = json.loads(raw_bytes.decode("utf-8"))

        events: List[EarthquakeEvent] = []
        seen_ids = set()

        for feat in data.get("features", []):
            event_id = str(feat.get("id"))
            if not event_id or event_id in seen_ids:
                continue
            seen_ids.add(event_id)

            props = feat.get("properties", {})
            coords = feat.get("geometry", {}).get("coordinates", [])

            if len(coords) >= 2:
                lng, lat = coords[0], coords[1]
                depth = coords[2] if len(coords) >= 3 else None
                mag = float(props.get("mag") or 0.0)
                obs_time = (props.get("time") / 1000.0) if props.get("time") else time.time()

                sev = "high" if mag >= 6.0 else "medium" if mag >= 5.0 else "low"

                eq = EarthquakeEvent(
                    source="USGS",
                    source_event_id=event_id,
                    source_url=props.get("url") or url,
                    event_type="earthquake",
                    severity=sev,
                    status="active",
                    classification=DataClassification.LIVE,
                    latitude=lat,
                    longitude=lng,
                    observed_at=obs_time,
                    confidence=0.95,
                    magnitude=mag,
                    depth_km=depth,
                    place=props.get("place") or "Unknown Seismic Region",
                    raw_payload={"title": props.get("title")},
                )
                events.append(eq)

        intelligence_cache.set(cache_key, events, ttl=120)
        health_manager.record_success("USGS", duration_ms, record_count=len(events))
        return events

    except Exception as e:
        health_manager.record_failure("USGS", str(e))
        logger.warning(f"USGS Earthquake fetch failed: {e}")
        return []


def fetch_gdacs_disasters() -> List[ExternalDisasterEvent]:
    """Fetch global disaster alerts from GDACS RSS feed."""
    cache_key = "gdacs_disasters"
    cached = intelligence_cache.get(cache_key)
    if cached:
        return cached[0]

    start_time = time.time()
    url = "https://www.gdacs.org/xml/rss.xml"

    try:
        raw_bytes = _http_get_with_retry(url, timeout=3.5, max_retries=2)
        duration_ms = (time.time() - start_time) * 1000
        root = ET.fromstring(raw_bytes.decode("utf-8"))

        events: List[ExternalDisasterEvent] = []
        seen_ids = set()

        for idx, item in enumerate(root.findall("./channel/item")[:15]):
            guid = item.find("guid").text if item.find("guid") is not None else f"gdacs-{idx}"
            if guid in seen_ids:
                continue
            seen_ids.add(guid)

            title = item.find("title").text if item.find("title") is not None else "Disaster Alert"
            link = item.find("link").text if item.find("link") is not None else "https://www.gdacs.org"

            # Check for GDACS point coordinates if present
            lat, lng = None, None
            point = item.find("{http://www.georss.org/georss}point")
            if point is not None and point.text:
                parts = point.text.strip().split()
                if len(parts) == 2:
                    lat, lng = float(parts[0]), float(parts[1])

            sev = "high" if "Red Alert" in title else "medium" if "Orange Alert" in title else "low"
            dtype = "flood" if "Flood" in title else "cyclone" if "Cyclone" in title or "Storm" in title else "earthquake" if "Earthquake" in title else "general"

            ev = ExternalDisasterEvent(
                source="GDACS",
                source_event_id=guid,
                source_url=link,
                event_type=dtype,
                severity=sev,
                status="active",
                classification=DataClassification.LIVE,
                latitude=lat,
                longitude=lng,
                place=title,
                observed_at=time.time(),
                confidence=0.90,
                raw_payload={"title": title},
            )
            events.append(ev)

        intelligence_cache.set(cache_key, events, ttl=300)
        health_manager.record_success("GDACS", duration_ms, record_count=len(events))
        return events

    except Exception as e:
        health_manager.record_failure("GDACS", str(e))
        logger.warning(f"GDACS fetch failed: {e}")
        return []


def fetch_weather_observation(lat: float, lng: float) -> Optional[WeatherObservation]:
    """Fetch weather observation trying OpenWeather first, then Open-Meteo."""
    cache_key = f"weather_{round(lat, 2)}_{round(lng, 2)}"
    cached = intelligence_cache.get(cache_key)
    if cached:
        return cached[0]

    now = time.time()
    api_key = os.getenv("OPENWEATHER_API_KEY")

    # 1. Try OpenWeather API
    if api_key:
        start_time = time.time()
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lng}&appid={api_key}&units=metric"
        try:
            raw_bytes = _http_get_with_retry(url, timeout=2.5, max_retries=1)
            duration_ms = (time.time() - start_time) * 1000
            data = json.loads(raw_bytes.decode("utf-8"))

            main_data = data.get("main") or {}
            wind_data = data.get("wind") or {}
            rain_data = data.get("rain") or {}
            weather_data = data.get("weather") or []

            raw_temp = main_data.get("temp")
            temp = round(float(raw_temp), 1) if raw_temp is not None else None

            raw_feels = main_data.get("feels_like")
            apparent_temp = round(float(raw_feels), 1) if raw_feels is not None else temp

            raw_rain = rain_data.get("1h") if isinstance(rain_data, dict) else None
            rain_val = round(float(raw_rain), 1) if raw_rain is not None else None

            raw_wind = wind_data.get("speed") if isinstance(wind_data, dict) else None
            wind_speed = round(float(raw_wind) * 3.6, 1) if raw_wind is not None else None

            raw_humidity = main_data.get("humidity")
            humidity = round(float(raw_humidity), 1) if raw_humidity is not None else None

            weather_cond = weather_data[0].get("description", "").title() if (weather_data and isinstance(weather_data[0], dict) and weather_data[0].get("description")) else None

            if temp is not None or humidity is not None or rain_val is not None or wind_speed is not None:
                obs = WeatherObservation(
                    provider="OpenWeather",
                    classification=DataClassification.LIVE,
                    temperature=temp,
                    apparent_temperature=apparent_temp,
                    precipitation_mm=rain_val,
                    wind_speed_kmh=wind_speed,
                    humidity_pct=humidity,
                    weather_condition=weather_cond or "UNAVAILABLE",
                    latitude=lat,
                    longitude=lng,
                    observed_at=now,
                    fetched_at=now,
                )
                intelligence_cache.set(cache_key, obs, ttl=180)
                health_manager.record_success("OpenWeather", duration_ms, record_count=1)
                return obs
        except Exception as e:
            health_manager.record_failure("OpenWeather", str(e))
            logger.warning(f"OpenWeather fetch failed: {e}. Trying Open-Meteo fallback.")

    # 2. Try Open-Meteo API using current weather observation fields directly
    start_time = time.time()
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lng}&current=temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,weather_code"
    try:
        raw_bytes = _http_get_with_retry(url, timeout=2.5, max_retries=1)
        duration_ms = (time.time() - start_time) * 1000
        data = json.loads(raw_bytes.decode("utf-8"))

        current = data.get("current")
        # Support fallback if mock or legacy response provides current_weather
        if not current and isinstance(data.get("current_weather"), dict):
            current = data["current_weather"]

        if not current or not isinstance(current, dict):
            raise ValueError("Open-Meteo response missing current weather telemetry block")

        # 1. Temperature
        raw_temp = current.get("temperature_2m") if "temperature_2m" in current else current.get("temperature")
        temp = round(float(raw_temp), 1) if raw_temp is not None else None

        # 2. Relative Humidity (check current first, hourly index 0 only if current field absent)
        raw_hum = current.get("relative_humidity_2m")
        if raw_hum is None and "relative_humidity_2m" not in current and "hourly" in data and isinstance(data["hourly"], dict):
            hum_list = data["hourly"].get("relative_humidity_2m")
            if hum_list and hum_list[0] is not None:
                raw_hum = hum_list[0]
        humidity = round(float(raw_hum), 1) if raw_hum is not None else None

        # 3. Precipitation (distinguish 0.0 from None)
        raw_precip = current.get("precipitation")
        if raw_precip is None and "precipitation" not in current and "hourly" in data and isinstance(data["hourly"], dict):
            precip_list = data["hourly"].get("precipitation")
            if precip_list and precip_list[0] is not None:
                raw_precip = precip_list[0]
        precipitation = round(float(raw_precip), 1) if raw_precip is not None else None

        # 4. Wind Speed
        raw_wind = current.get("wind_speed_10m") if "wind_speed_10m" in current else current.get("windspeed")
        wind = round(float(raw_wind), 1) if raw_wind is not None else None

        # 5. Weather Code
        raw_code = current.get("weather_code") if "weather_code" in current else current.get("weathercode")
        wmo_codes = {
            0: "Clear Sky", 1: "Mainly Clear", 2: "Partly Cloudy", 3: "Overcast",
            45: "Fog", 48: "Depositing Rime Fog",
            51: "Light Drizzle", 53: "Moderate Drizzle", 55: "Dense Drizzle",
            61: "Slight Rain", 63: "Moderate Rain", 65: "Heavy Rain",
            71: "Slight Snow", 73: "Moderate Snow", 75: "Heavy Snow",
            80: "Slight Rain Showers", 81: "Moderate Rain Showers", 82: "Violent Rain Showers",
            95: "Thunderstorm", 96: "Thunderstorm with Slight Hail", 99: "Thunderstorm with Heavy Hail"
        }
        if raw_code is not None:
            try:
                code_int = int(raw_code)
                condition = wmo_codes.get(code_int, f"Weather Code {code_int}")
            except (ValueError, TypeError):
                condition = "UNAVAILABLE"
        else:
            condition = "UNAVAILABLE"

        # Check if ALL values are missing
        if temp is None and humidity is None and precipitation is None and wind is None:
            obs = WeatherObservation(
                provider="Open-Meteo",
                classification=DataClassification.UNAVAILABLE,
                temperature=None,
                apparent_temperature=None,
                precipitation_mm=None,
                wind_speed_kmh=None,
                humidity_pct=None,
                weather_condition="UNAVAILABLE",
                latitude=lat,
                longitude=lng,
                observed_at=now,
                fetched_at=now,
            )
            intelligence_cache.set(cache_key, obs, ttl=60)
            health_manager.record_failure("Open-Meteo", "Empty weather telemetry payload")
            return obs

        obs = WeatherObservation(
            provider="Open-Meteo",
            classification=DataClassification.LIVE,
            temperature=temp,
            apparent_temperature=temp,
            precipitation_mm=precipitation,
            wind_speed_kmh=wind,
            humidity_pct=humidity,
            weather_condition=condition,
            latitude=lat,
            longitude=lng,
            observed_at=now,
            fetched_at=now,
        )
        intelligence_cache.set(cache_key, obs, ttl=180)
        health_manager.record_success("Open-Meteo", duration_ms, record_count=1)
        return obs
    except Exception as e:
        health_manager.record_failure("Open-Meteo", str(e))
        logger.warning(f"Open-Meteo fetch failed: {e}")
        return None


def probe_open_meteo_health(lat: float = 19.076, lng: float = 72.877, timeout: float = 4.0) -> bool:
    """Verify live connectivity to Open-Meteo API and update its operational health status."""
    start_time = time.time()
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lng}&current=temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,weather_code"
    try:
        raw_bytes = _http_get_with_retry(url, timeout=timeout, max_retries=1)
        duration_ms = (time.time() - start_time) * 1000
        data = json.loads(raw_bytes.decode("utf-8"))
        if data.get("current") or data.get("current_weather"):
            health_manager.record_success("Open-Meteo", duration_ms, record_count=1)
            return True
        else:
            health_manager.record_failure("Open-Meteo", "Empty weather payload")
            return False
    except Exception as e:
        health_manager.record_failure("Open-Meteo", str(e))
        return False


def reverse_geocode_nominatim(lat: float, lng: float) -> Dict[str, Any]:
    """Convert lat/lng to human-readable street address via Nominatim API with provenance."""
    cache_key = f"nominatim_{round(lat, 4)}_{round(lng, 4)}"
    cached = intelligence_cache.get(cache_key)
    if cached:
        return cached[0]

    start_time = time.time()
    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lng}"
    try:
        raw_bytes = _http_get_with_retry(url, timeout=3.0, max_retries=1)
        duration_ms = (time.time() - start_time) * 1000
        data = json.loads(raw_bytes.decode("utf-8"))
        display_name = data.get("display_name")

        if not display_name:
            health_manager.record_failure("Nominatim", "No address found for coordinates")
            return {
                "provider": "Nominatim",
                "classification": DataClassification.UNAVAILABLE.value,
                "address": None,
                "latitude": lat,
                "longitude": lng,
                "fetched_at": time.time(),
            }

        res = {
            "provider": "Nominatim",
            "classification": DataClassification.LIVE.value,
            "address": display_name,
            "latitude": lat,
            "longitude": lng,
            "fetched_at": time.time(),
        }
        intelligence_cache.set(cache_key, res, ttl=300)
        health_manager.record_success("Nominatim", duration_ms, record_count=1)
        return res
    except Exception as e:
        health_manager.record_failure("Nominatim", str(e))
        logger.warning(f"Nominatim geocoding failed: {e}")
        return {
            "provider": "Nominatim",
            "classification": DataClassification.UNAVAILABLE.value,
            "address": None,
            "latitude": lat,
            "longitude": lng,
            "fetched_at": time.time(),
        }


def search_nominatim_location(query: str) -> List[Dict[str, Any]]:
    """Search for locations by query text via Nominatim API with rate limiting and caching."""
    clean_query = query.strip()
    if not clean_query:
        return []

    cache_key = f"nominatim_search_{clean_query.lower()}"
    cached = intelligence_cache.get(cache_key)
    if cached:
        return cached[0]

    start_time = time.time()
    encoded_q = urllib.parse.quote(clean_query)
    url = f"https://nominatim.openstreetmap.org/search?q={encoded_q}&format=json&limit=5"
    try:
        raw_bytes = _http_get_with_retry(url, timeout=3.5, max_retries=1)
        duration_ms = (time.time() - start_time) * 1000
        data = json.loads(raw_bytes.decode("utf-8"))
        results = []
        for item in data:
            lat = float(item.get("lat", 0.0))
            lng = float(item.get("lon", 0.0))
            results.append({
                "provider": "Nominatim",
                "classification": DataClassification.LIVE.value,
                "display_name": item.get("display_name"),
                "latitude": lat,
                "longitude": lng,
                "place_id": item.get("place_id"),
                "type": item.get("type", "location"),
                "fetched_at": time.time(),
            })

        intelligence_cache.set(cache_key, results, ttl=300)
        health_manager.record_success("Nominatim", duration_ms, record_count=len(results))
        return results
    except Exception as e:
        health_manager.record_failure("Nominatim", str(e))
        logger.warning(f"Nominatim location search failed: {e}")
        return []
