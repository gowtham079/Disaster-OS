"""Tests for Step 4: Geographic Consistency & Mumbai Fallback Removal.

Verifies:
1. Missing incident coordinates never become Mumbai coordinates (remain None or UNAVAILABLE).
2. Chennai scenario does not receive Mumbai resource coordinates.
3. Bengaluru scenario does not receive Mumbai resource coordinates.
4. Real facility coordinates are preserved.
5. Missing real facility capacity remains None (capacity_status UNAVAILABLE).
6. Simulated facility capacity is labelled SIMULATED.
7. Missing route coordinates produce INSUFFICIENT_EVIDENCE or UNAVAILABLE.
8. Real OSRM / router uses actual coordinates.
9. No API payload silently injects Mumbai coordinates.
10. No backend geographic fallback uses 19.076 / 72.878.
"""

import unittest
from unittest.mock import patch, MagicMock
from models import DisasterInput, IncidentReport, HospitalAssignment, ShelterAssignment
from agents import HospitalAgent, ShelterAgent, RouteAgent, AIAgent
from message_bus import MessageBus, AgentMessage
from resource_generator import (
    generate_simulation_resources,
    generate_facilities,
    generate_blocked_roads,
    generate_disaster_zones,
)
from routing.service import RoutingService
from weather_service import get_weather


class TestGeographicConsistency(unittest.TestCase):
    def setUp(self):
        self.bus = MessageBus()

    def test_01_missing_incident_coordinates_never_become_mumbai(self):
        """1. Missing incident coordinates never become Mumbai coordinates."""
        inp = DisasterInput(
            location="Test Sector X",
            severity="high",
            people_affected=100,
            disaster_type="flood",
        )
        self.assertIsNone(inp.latitude)
        self.assertIsNone(inp.longitude)

        report = IncidentReport(
            affected_area=inp.location,
            latitude=inp.latitude,
            longitude=inp.longitude,
            priority="high",
            estimated_risk="high",
        )
        self.assertIsNone(report.latitude)
        self.assertIsNone(report.longitude)
        self.assertNotEqual(report.latitude, 19.076)
        self.assertNotEqual(report.longitude, 72.878)

    def test_02_chennai_scenario_receives_chennai_coordinates(self):
        """2. Chennai scenario does not receive Mumbai resource coordinates."""
        chennai_lat, chennai_lng = 13.0827, 80.2707
        res = generate_simulation_resources(seed=42, center_lat=chennai_lat, center_lng=chennai_lng, city_name="Chennai")
        self.assertTrue(len(res) > 0)
        for r in res:
            self.assertEqual(r.get("classification"), "SIMULATED")
            # All resources should be positioned near Chennai (~13.0, 80.2), NOT Mumbai (19.0, 72.8)
            self.assertAlmostEqual(r["latitude"], chennai_lat, delta=0.2)
            self.assertAlmostEqual(r["longitude"], chennai_lng, delta=0.2)
            self.assertNotAlmostEqual(r["latitude"], 19.076, delta=0.5)

    def test_03_bengaluru_scenario_receives_bengaluru_coordinates(self):
        """3. Bengaluru scenario does not receive Mumbai resource coordinates."""
        blr_lat, blr_lng = 12.9716, 77.5946
        facs = generate_facilities(seed=42, center_lat=blr_lat, center_lng=blr_lng, city_name="Bengaluru")
        self.assertTrue(len(facs) > 0)
        for f in facs:
            self.assertEqual(f.get("classification"), "SIMULATED")
            self.assertAlmostEqual(f["latitude"], blr_lat, delta=0.2)
            self.assertAlmostEqual(f["longitude"], blr_lng, delta=0.2)
            self.assertNotAlmostEqual(f["latitude"], 19.076, delta=0.5)

    def test_04_real_facility_coordinates_preserved(self):
        """4. Real facility coordinates are preserved without alteration."""
        real_lat, real_lng = 28.6139, 77.2090  # New Delhi
        from intelligence.models import FacilityRecord
        fac = FacilityRecord(
            facility_id="osm-node-12345",
            name="Safdarjung Hospital",
            facility_type="hospital",
            latitude=real_lat,
            longitude=real_lng,
            classification="LIVE",
        )
        self.assertEqual(fac.latitude, real_lat)
        self.assertEqual(fac.longitude, real_lng)

    def test_05_missing_real_facility_capacity_remains_none(self):
        """5. Missing real facility capacity remains None with UNAVAILABLE capacity_status."""
        from intelligence.models import FacilityRecord, CapacityStatus
        fac = FacilityRecord(
            facility_id="osm-node-99999",
            name="Local Health Center",
            facility_type="hospital",
            latitude=13.0827,
            longitude=80.2707,
            capacity=None,
            capacity_status=CapacityStatus.UNAVAILABLE,
            classification="LIVE",
        )
        self.assertIsNone(fac.capacity)
        self.assertEqual(fac.capacity_status, CapacityStatus.UNAVAILABLE)

    def test_06_simulated_facility_capacity_is_labelled_simulated(self):
        """6. Simulated facility capacity is labelled SIMULATED."""
        facs = generate_facilities(seed=99, center_lat=17.3850, center_lng=78.4867, city_name="Hyderabad")
        for f in facs:
            self.assertEqual(f.get("classification"), "SIMULATED")
            self.assertEqual(f.get("capacity_status"), "SIMULATED")
            self.assertIsNotNone(f.get("total_capacity"))

    def test_07_missing_route_coordinates_produce_unavailable(self):
        """7. Missing route coordinates produce UNAVAILABLE / Invalid coordinates."""
        router = RoutingService()
        res = router.route(None, None, 13.0, 80.0)
        self.assertEqual(res.get("classification"), "UNAVAILABLE")
        self.assertEqual(res.get("route_source").upper(), "UNAVAILABLE")

        res2 = router.route(13.0, 80.0, None, None)
        self.assertEqual(res2.get("classification"), "UNAVAILABLE")

    def test_08_osrm_routes_use_actual_coordinates(self):
        """8. Real OSRM routes use actual coordinates, not Mumbai coordinates."""
        router = RoutingService()
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.read.return_value = b'{"code":"Ok","routes":[{"distance":5000,"duration":600,"geometry":{"coordinates":[[77.59,12.97],[77.60,12.98]]}}]}'
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            result = router._osrm(start_lat=12.97, start_lng=77.59, end_lat=12.98, end_lng=77.60)
            self.assertIsNotNone(result)
            self.assertIn(result["classification"], ["REAL_ROUTE", "CALCULATED"])
            self.assertEqual(result["route_type"], "ROAD_ROUTE")
            self.assertEqual(result["coordinates"][0], [12.97, 77.59])

    def test_09_api_facilities_requires_coordinates_without_mumbai_default(self):
        """9. No API payload silently injects Mumbai coordinates when params are omitted."""
        from fastapi.testclient import TestClient
        from app import app
        client = TestClient(app)

        resp = client.get("/api/intelligence/facilities")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Valid latitude and longitude coordinates are required", resp.json()["message"])

    def test_10_no_weather_fallback_uses_mumbai(self):
        """10. No backend geographic fallback uses 19.076 / 72.878 when coordinates are missing."""
        w = get_weather(None, None)
        self.assertEqual(w["classification"], "UNAVAILABLE")
        self.assertIsNone(w["temperature"])
        self.assertIsNone(w["humidity"])
        self.assertIsNone(w["wind_speed"])


if __name__ == "__main__":
    unittest.main()
