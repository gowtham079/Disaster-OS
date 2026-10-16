"""A* Route Optimization Solver for Disaster Response.

Models major highway connection graphs between Indian cities, executes A*
shortest path searches using Haversine heuristic distance estimation, supports
dynamic road blockages, and calculates path coordinates, distances, and ETAs.
"""

import heapq
import json
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ── Haversine Distance Helper ──────────────────────────────────────────────

def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate the great-circle distance between two points in kilometers."""
    R = 6371.0  # Earth's radius in km
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# ── Highway Graph Connections Map ──────────────────────────────────────────

HIGHWAY_GRAPH: Dict[str, List[str]] = {
    "Mumbai": ["Pune", "Surat", "Nashik"],
  "Delhi": ["Agra", "Jaipur", "Chandigarh", "Lucknow"],
  "Bangalore": ["Pune", "Chennai", "Kochi", "Coimbatore", "Hyderabad"],
  "Chennai": ["Bangalore", "Madurai", "Visakhapatnam"],
  "Kolkata": ["Patna", "Bhubaneswar", "Ranchi"],
  "Hyderabad": ["Bangalore", "Nagpur", "Visakhapatnam"],
  "Pune": ["Mumbai", "Nashik", "Bangalore"],
  "Ahmedabad": ["Vadodara", "Surat", "Rajkot", "Jaipur"],
  "Jaipur": ["Delhi", "Agra", "Ahmedabad", "Jodhpur"],
  "Lucknow": ["Delhi", "Kanpur", "Varanasi", "Patna"],
  "Surat": ["Mumbai", "Vadodara", "Ahmedabad"],
  "Kanpur": ["Lucknow", "Prayagraj", "Agra"],
  "Nagpur": ["Bhopal", "Hyderabad", "Vadodara"], # Connect central India
  "Indore": ["Bhopal", "Vadodara", "Nashik"],
  "Bhopal": ["Indore", "Gwalior", "Nagpur"],
  "Visakhapatnam": ["Chennai", "Bhubaneswar", "Hyderabad"],
  "Patna": ["Kolkata", "Ranchi", "Varanasi", "Lucknow"],
  "Vadodara": ["Ahmedabad", "Surat", "Indore"],
  "Ludhiana": ["Amritsar", "Chandigarh", "Shimla"],
  "Agra": ["Delhi", "Jaipur", "Kanpur", "Gwalior"],
  "Nashik": ["Mumbai", "Pune", "Indore"],
  "Varanasi": ["Lucknow", "Prayagraj", "Patna"],
  "Coimbatore": ["Bangalore", "Madurai", "Kochi"],
  "Madurai": ["Chennai", "Coimbatore", "Thiruvananthapuram"],
  "Kochi": ["Coimbatore", "Thiruvananthapuram", "Bangalore"],
  "Thiruvananthapuram": ["Kochi", "Madurai"],
  "Guwahati": ["Kolkata", "Patna"], # Northeast hook
  "Chandigarh": ["Delhi", "Ludhiana", "Dehradun", "Shimla"],
  "Dehradun": ["Chandigarh", "Shimla"],
  "Bhubaneswar": ["Kolkata", "Visakhapatnam"],
  "Ranchi": ["Patna", "Kolkata", "Prayagraj"],
  "Jodhpur": ["Jaipur", "Rajkot"],
  "Amritsar": ["Ludhiana", "Srinagar"],
  "Srinagar": ["Amritsar"],
  "Shimla": ["Chandigarh", "Dehradun", "Ludhiana"],
  "Gwalior": ["Agra", "Bhopal"],
  "Rajkot": ["Ahmedabad", "Jodhpur"],
  "Prayagraj": ["Kanpur", "Varanasi", "Ranchi"]
}


# ── A* Solver Class ────────────────────────────────────────────────────────

class AStarRouteSolver:
    """Computes shortest path routes across Indian cities using A* search."""

    def __init__(self):
        self.cities: Dict[str, Dict[str, Any]] = {}
        self._load_cities()

    def _load_cities(self) -> None:
        """Load city locations to map graph nodes to spatial coordinates."""
        try:
            cities_path = (
                Path(__file__).resolve().parent.parent / "data" / "indian_cities.json"
            )
            if cities_path.exists():
                with open(cities_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.cities = {c["name"]: c for c in data}
        except Exception as e:
            # Fallback if file load fails during compilation
            pass

    def solve(
        self,
        start_city: str,
        end_city: str,
        blocked_edges: Optional[Set[Tuple[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Compute the optimized route using A* search.

        Parameters
        ----------
        start_city : str
            Name of origin city (e.g. "Mumbai")
        end_city : str
            Name of destination city (e.g. "Delhi")
        blocked_edges : set of tuple, optional
            Edges that are temporarily blocked (e.g. {("Delhi", "Agra")})

        Returns
        -------
        dict
            Contains:
            - path: List of city name strings
            - coordinates: List of [lat, lng] lists
            - distance_km: Total path distance in km
            - eta_hours: Estimated response time at 65 km/h
        """
        # Parse city names from formatted strings (e.g. "Mumbai, Maharashtra" -> "Mumbai")
        s_name = start_city.split(",")[0].strip()
        e_name = end_city.split(",")[0].strip()

        # Sanity check
        if s_name not in self.cities or e_name not in self.cities:
            # Fallback to straight-line if nodes are not in graph
            return self._straight_line_fallback(start_city, end_city)

        if s_name == e_name:
            coords = [self.cities[s_name]["lat"], self.cities[s_name]["lng"]]
            return {
                "path": [s_name],
                "coordinates": [coords],
                "distance_km": 0.0,
                "eta_hours": 0.0,
            }

        # Initialize sets
        blocked = blocked_edges or set()
        open_set: List[Tuple[float, str]] = []
        # Priority queue stores tuples of (f_score, city_name)
        heapq.heappush(open_set, (0.0, s_name))

        came_from: Dict[str, str] = {}
        g_score: Dict[str, float] = {s_name: 0.0}

        # Heuristic: Haversine distance to target
        h = lambda name: haversine_distance(
            self.cities[name]["lat"],
            self.cities[name]["lng"],
            self.cities[e_name]["lat"],
            self.cities[e_name]["lng"],
        )

        f_score: Dict[str, float] = {s_name: h(s_name)}

        while open_set:
            _, current = heapq.heappop(open_set)

            if current == e_name:
                # Reconstruct path
                path = [e_name]
                while current in came_from:
                    current = came_from[current]
                    path.append(current)
                path.reverse()

                # Generate coordinate sets
                coordinates = [[self.cities[node]["lat"], self.cities[node]["lng"]] for node in path]
                dist = g_score[e_name]

                # Average response speed: 65 km/h
                return {
                    "path": path,
                    "coordinates": coordinates,
                    "distance_km": round(dist, 2),
                    "eta_hours": round(dist / 65.0, 2),
                }

            neighbors = HIGHWAY_GRAPH.get(current, [])
            for neighbor in neighbors:
                if neighbor not in self.cities:
                    continue

                # Check road blockage (both directions)
                if (current, neighbor) in blocked or (neighbor, current) in blocked:
                    continue

                # Edge weight is haversine distance
                weight = haversine_distance(
                    self.cities[current]["lat"],
                    self.cities[current]["lng"],
                    self.cities[neighbor]["lat"],
                    self.cities[neighbor]["lng"],
                )
                tentative_g_score = g_score[current] + weight

                if tentative_g_score < g_score.get(neighbor, float("inf")):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g_score
                    f_score[neighbor] = tentative_g_score + h(neighbor)
                    
                    # Push if not already in queue (heapq handles duplicates)
                    heapq.heappush(open_set, (f_score[neighbor], neighbor))

        # If A* fails due to disconnected graph, fall back to straight line
        return self._straight_line_fallback(start_city, end_city)

    def _straight_line_fallback(self, start: str, end: str) -> Dict[str, Any]:
        """Failsafe fallback estimating a straight line route between locations."""
        s_name = start.split(",")[0].strip()
        e_name = end.split(",")[0].strip()

        lat1, lng1 = 20.0, 78.0
        lat2, lng2 = 21.0, 79.0

        if s_name in self.cities:
            lat1 = self.cities[s_name]["lat"]
            lng1 = self.cities[s_name]["lng"]
        if e_name in self.cities:
            lat2 = self.cities[e_name]["lat"]
            lng2 = self.cities[e_name]["lng"]

        dist = haversine_distance(lat1, lng1, lat2, lng2)
        return {
            "path": [s_name, e_name],
            "coordinates": [[lat1, lng1], [lat2, lng2]],
            "distance_km": round(dist, 2),
            "eta_hours": round(dist / 65.0, 2),
            "fallback": True
        }
