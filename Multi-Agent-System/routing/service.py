"""Resilient routing service utilizing real road OSRM APIs with local A* graph fallback.

Includes blocked road detour detection, OSRM route fetching, circuit breaker pattern,
and sub-second route interpolation for smooth 60 FPS vehicle animations over WebSockets.
"""

import json
import math
import os
import threading
import urllib.error
import urllib.request
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Set, Tuple

from routing.astar import AStarRouteSolver, haversine_distance
from intelligence.source_health import health_manager


class RouteCache:
    def __init__(self, max_size: int = 512):
        self.max_size = max_size
        self._items = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            value = self._items.get(key)
            if value is not None:
                self._items.move_to_end(key)
            return value

    def put(self, key, value):
        with self._lock:
            self._items[key] = value
            self._items.move_to_end(key)
            while len(self._items) > self.max_size:
                self._items.popitem(last=False)


def interpolate_route_points(coordinates: List[List[float]], num_steps: int = 10) -> List[List[float]]:
    """Interpolate route coordinates into smooth sub-step coordinates for animated vehicle movement.

    Parameters
    ----------
    coordinates : list of [lat, lng]
        Original path coordinates.
    num_steps : int
        Total frames/waypoints desired.

    Returns
    -------
    list of [lat, lng]
        Smoothly interpolated waypoint list.
    """
    if not coordinates or len(coordinates) < 2:
        return coordinates or []

    interpolated = []
    total_segments = len(coordinates) - 1
    steps_per_segment = max(1, num_steps // total_segments)

    for i in range(total_segments):
        p1 = coordinates[i]
        p2 = coordinates[i + 1]
        for step in range(steps_per_segment):
            t = step / float(steps_per_segment)
            lat = round(p1[0] + t * (p2[0] - p1[0]), 6)
            lng = round(p1[1] + t * (p2[1] - p1[1]), 6)
            interpolated.append([lat, lng])

    # Append destination point
    interpolated.append([coordinates[-1][0], coordinates[-1][1]])
    return interpolated


class RoutingService:
    """Try real road OSRM routing first and transparently use local A* city graph fallback."""

    def __init__(self):
        self.osrm_url = os.getenv("OSRM_BASE_URL", "https://router.project-osrm.org").rstrip("/")
        self.osrm_enabled = os.getenv("OSRM_ENABLED", "true").lower() in {"1", "true", "yes"}
        self.timeout = float(os.getenv("OSRM_TIMEOUT_SECONDS", "1.2"))
        self.fallback = AStarRouteSolver()
        self.cache = RouteCache()
        self._consecutive_failures = 0
        self._circuit_open_until = 0.0

    @staticmethod
    def _valid(lat, lng):
        try:
            if lat is None or lng is None:
                return False
            f_lat = float(lat)
            f_lng = float(lng)
            if math.isnan(f_lat) or math.isnan(f_lng) or math.isinf(f_lat) or math.isinf(f_lng):
                return False
            if not (-90.0 <= f_lat <= 90.0 and -180.0 <= f_lng <= 180.0):
                return False
            if f_lat == 0.0 and f_lng == 0.0:
                return False
            return True
        except (ValueError, TypeError):
            return False

    def _osrm(self, start_lat: float, start_lng: float, end_lat: float, end_lng: float) -> Optional[Dict]:
        import time as _time
        if not self.osrm_enabled:
            return None
        if self._consecutive_failures >= 3:
            if _time.monotonic() < self._circuit_open_until:
                return None
            else:
                self._consecutive_failures = 0

        start_time = _time.time()
        url = (
            f"{self.osrm_url}/route/v1/driving/{start_lng},{start_lat};{end_lng},{end_lat}"
            "?overview=full&geometries=geojson&steps=false"
        )
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "DisasterOS/2.0"})
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                status_code = getattr(response, "status", getattr(response, "code", 200))
                if isinstance(status_code, int) and status_code != 200:
                    self._consecutive_failures += 1
                    health_manager.record_failure("OSRM", f"OSRM returned HTTP {status_code}")
                    return None
                payload = json.loads(response.read().decode("utf-8"))

            if not isinstance(payload, dict) or payload.get("code") != "Ok" or not payload.get("routes"):
                self._consecutive_failures += 1
                health_manager.record_failure("OSRM", "OSRM returned non-Ok code or missing routes")
                return None

            route = payload["routes"][0]
            geom = route.get("geometry")
            if not geom or not isinstance(geom, dict) or not geom.get("coordinates"):
                self._consecutive_failures += 1
                health_manager.record_failure("OSRM", "OSRM missing geometry coordinates")
                return None

            raw_coords = geom["coordinates"]
            if not isinstance(raw_coords, list) or len(raw_coords) == 0:
                self._consecutive_failures += 1
                health_manager.record_failure("OSRM", "OSRM empty coordinates array")
                return None

            # Validate each coordinate pair is finite and within geographic range
            coordinates = []
            for pt in raw_coords:
                if not (isinstance(pt, (list, tuple)) and len(pt) >= 2):
                    self._consecutive_failures += 1
                    return None
                c_lng, c_lat = float(pt[0]), float(pt[1])
                if math.isnan(c_lat) or math.isnan(c_lng) or math.isinf(c_lat) or math.isinf(c_lng):
                    self._consecutive_failures += 1
                    return None
                if not (-90.0 <= c_lat <= 90.0 and -180.0 <= c_lng <= 180.0):
                    self._consecutive_failures += 1
                    return None
                coordinates.append([c_lat, c_lng])

            dist_m = route.get("distance")
            dur_s = route.get("duration")
            if dist_m is None or dur_s is None or dist_m < 0 or dur_s < 0:
                self._consecutive_failures += 1
                health_manager.record_failure("OSRM", "OSRM returned negative or invalid distance/duration")
                return None

            duration_ms = (_time.time() - start_time) * 1000
            self._consecutive_failures = 0
            health_manager.record_success("OSRM", duration_ms, record_count=1)

            fetched_ts = _time.time()
            return {
                "status": "SUCCESS",
                "path": [],
                "coordinates": coordinates,
                "geometry": geom,
                "distance_km": round(float(dist_m) / 1000.0, 2),
                "eta_hours": round(float(dur_s) / 3600.0, 2),
                "duration_minutes": round(float(dur_s) / 60.0, 1),
                "provider": "OSRM",
                "route_provider": "OSRM",
                "route_type": "ROAD_ROUTE",
                "route_source": "OSRM",
                "classification": "CALCULATED",
                "start_coordinates": [float(start_lat), float(start_lng)],
                "destination_coordinates": [float(end_lat), float(end_lng)],
                "request_url": url,
                "fetched_at": fetched_ts,
                "has_blocked_road": False,
                "detour_taken": False,
                "methodology": "OSRM OpenStreetMap Driving Network Engine",
            }
        except Exception as e:
            self._consecutive_failures += 1
            if self._consecutive_failures >= 3:
                self._circuit_open_until = _time.monotonic() + 45.0
            health_manager.record_failure("OSRM", str(e))
            return None

    def _astar(self, start_lat: float, start_lng: float, end_lat: float, end_lng: float, blocked_edges: Optional[Set[Tuple[str, str]]] = None) -> Dict:
        import time as _time

        def nearest(lat, lng):
            return min(
                self.fallback.cities,
                key=lambda name: haversine_distance(
                    lat, lng,
                    self.fallback.cities[name]["lat"],
                    self.fallback.cities[name]["lng"],
                ),
            )

        s_city = nearest(start_lat, start_lng)
        e_city = nearest(end_lat, end_lng)
        raw_route = self.fallback.solve(s_city, e_city, blocked_edges=blocked_edges)

        is_fallback = raw_route.get("fallback", False)
        provider = "DIRECT_GEOMETRIC" if is_fallback else "LOCAL_ASTAR"
        route_type = "STRAIGHT_LINE_ESTIMATE" if is_fallback else "GRAPH_ESTIMATE"
        methodology = (
            "Straight-line Euclidean estimate (calculated estimate, not a verified road route)"
            if is_fallback
            else "A* Search on Inter-City Graph Network (calculated estimate, not a verified road route)"
        )

        coords = raw_route.get("coordinates") or []
        if coords:
            full_coords = [[float(start_lat), float(start_lng)]] + coords + [[float(end_lat), float(end_lng)]]
        else:
            full_coords = [[float(start_lat), float(start_lng)], [float(end_lat), float(end_lng)]]

        dist_km = raw_route.get("distance_km")
        if dist_km is None:
            dist_km = round(haversine_distance(start_lat, start_lng, end_lat, end_lng), 2)

        eta_h = raw_route.get("eta_hours")
        if eta_h is None:
            eta_h = round(dist_km / 65.0, 2)

        return {
            "status": "FALLBACK_ASTAR" if not is_fallback else "FALLBACK_DIRECT",
            "path": raw_route.get("path", []),
            "coordinates": full_coords,
            "geometry": {"type": "LineString", "coordinates": [[pt[1], pt[0]] for pt in full_coords]},
            "distance_km": dist_km,
            "eta_hours": eta_h,
            "duration_minutes": round(eta_h * 60.0, 1),
            "provider": provider,
            "route_provider": provider,
            "route_type": route_type,
            "route_source": provider,
            "classification": "CALCULATED",
            "start_coordinates": [float(start_lat), float(start_lng)],
            "destination_coordinates": [float(end_lat), float(end_lng)],
            "request_url": None,
            "fetched_at": _time.time(),
            "has_blocked_road": bool(blocked_edges),
            "detour_taken": bool(blocked_edges),
            "methodology": methodology,
        }

    def get_route(self, *args, **kwargs) -> Dict:
        if len(args) == 4:
            start_lat, start_lng, end_lat, end_lng = args
            return self.route(start_lat, start_lng, end_lat, end_lng)
        elif len(args) >= 2 and isinstance(args[0], (tuple, list)) and isinstance(args[1], (tuple, list)):
            start_lat, start_lng = args[0]
            end_lat, end_lng = args[1]
            return self.route(start_lat, start_lng, end_lat, end_lng)
        elif "start" in kwargs and "end" in kwargs:
            start_lat, start_lng = kwargs["start"]
            end_lat, end_lng = kwargs["end"]
            return self.route(start_lat, start_lng, end_lat, end_lng)
        start_lat = kwargs.get("start_lat", 19.076)
        start_lng = kwargs.get("start_lng", 72.877)
        end_lat = kwargs.get("end_lat", 19.080)
        end_lng = kwargs.get("end_lng", 72.880)
        return self.route(start_lat, start_lng, end_lat, end_lng)

    def route(
        self,
        start_lat: float,
        start_lng: float,
        end_lat: float,
        end_lng: float,
        blocked_edges: Optional[Set[Tuple[str, str]]] = None,
    ) -> Dict:
        """Calculate optimal route considering real roads, A* solver, and blocked road detours."""
        if not all((self._valid(start_lat, start_lng), self._valid(end_lat, end_lng))):
            return {
                "status": "ROUTE_UNAVAILABLE",
                "path": [],
                "coordinates": None,
                "geometry": None,
                "distance_km": None,
                "distance": None,
                "eta_hours": None,
                "eta": None,
                "duration_minutes": None,
                "provider": "UNAVAILABLE",
                "route_provider": "UNAVAILABLE",
                "route_type": "UNAVAILABLE",
                "route_source": "UNAVAILABLE",
                "classification": "UNAVAILABLE",
                "has_blocked_road": False,
                "detour_taken": False,
                "start_coordinates": None,
                "destination_coordinates": None,
                "request_url": None,
                "fetched_at": None,
                "methodology": "None - Invalid or missing coordinates",
            }

        key = (round(float(start_lat), 4), round(float(start_lng), 4), round(float(end_lat), 4), round(float(end_lng), 4), bool(blocked_edges))
        cached = self.cache.get(key)
        if cached:
            return {**cached, "route_cached": True}

        # If blocked edges are present, use A* solver with blockage avoidance
        if blocked_edges:
            result = self._astar(start_lat, start_lng, end_lat, end_lng, blocked_edges=blocked_edges)
        else:
            result = self._osrm(start_lat, start_lng, end_lat, end_lng) or self._astar(start_lat, start_lng, end_lat, end_lng)

        # Generate interpolated sub-step waypoints for WebSocket smooth animation if coordinates exist
        coords = result.get("coordinates")
        if coords:
            result["interpolated_waypoints"] = interpolate_route_points(coords, num_steps=25)
        else:
            result["interpolated_waypoints"] = None
        result["route_cached"] = False

        self.cache.put(key, result)
        return result
