"""Step 6: Comprehensive Routing and OSRM Truthfulness Audit Test Suite.

Verifies:
1. Successful OSRM response => provider OSRM, route_type ROAD_ROUTE, classification CALCULATED, with full live evidence.
2. OSRM HTTP failure => no OSRM route is recorded (falls back to LOCAL_ASTAR).
3. Invalid OSRM response => UNAVAILABLE or valid fallback (never labeled OSRM).
4. A* fallback is labeled LOCAL_ASTAR with route_type GRAPH_ESTIMATE and classification CALCULATED.
5. Missing start coordinates => status ROUTE_UNAVAILABLE, provider UNAVAILABLE, distance is None, eta is None, geometry is None.
6. Missing destination coordinates => status ROUTE_UNAVAILABLE, provider UNAVAILABLE, distance is None, eta is None, geometry is None.
7. Invalid coordinates (NaN, Inf, out-of-range, null island 0,0) => status ROUTE_UNAVAILABLE, provider UNAVAILABLE, distance is None, eta is None.
8. Route distance comes from provider result.
9. Route ETA comes from provider result.
10. Route geometry comes from provider result.
11. No hardcoded production route values in orchestrator / routing services.
12. Run A route data never appears in Run B queries.
13. Corridor router exposes truthful provenance (provider, classification, start/end coordinates, distance, planned ETA, methodology).
14. Planned ETA is not labeled actual response time.
"""

import json
import math
import time
import unittest
import uuid
from unittest.mock import MagicMock, patch
import urllib.error

from routing.service import RoutingService
from models import RoutePlan
from orchestrator import Orchestrator
from intelligence.corridor_router import plan_evacuation_corridor
import database


class TestRoutingTruthfulness(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        database.init_db()

    def test_01_successful_osrm_response_labels_osrm_provenance(self):
        """1. Successful OSRM response => provider OSRM, route_type ROAD_ROUTE, classification CALCULATED, with live evidence."""
        router = RoutingService()
        fake_osrm_payload = {
            "code": "Ok",
            "routes": [
                {
                    "distance": 14250.5,
                    "duration": 1820.0,
                    "geometry": {
                        "coordinates": [
                            [77.5946, 12.9716],
                            [77.6000, 12.9650],
                            [77.6245, 12.9352],
                        ]
                    },
                }
            ],
        }

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.read.return_value = json.dumps(fake_osrm_payload).encode("utf-8")
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            res = router._osrm(12.9716, 77.5946, 12.9352, 77.6245)

            self.assertIsNotNone(res)
            self.assertEqual(res["provider"], "OSRM")
            self.assertEqual(res["route_provider"], "OSRM")
            self.assertEqual(res["route_type"], "ROAD_ROUTE")
            self.assertEqual(res["classification"], "CALCULATED")
            self.assertEqual(res["distance_km"], 14.25)
            self.assertEqual(res["eta_hours"], 0.51)
            self.assertEqual(res["duration_minutes"], 30.3)
            self.assertIn("request_url", res)
            self.assertTrue(res["request_url"].startswith("https://router.project-osrm.org"))
            self.assertEqual(res["start_coordinates"], [12.9716, 77.5946])
            self.assertEqual(res["destination_coordinates"], [12.9352, 77.6245])
            self.assertIsNotNone(res["fetched_at"])
            self.assertEqual(len(res["coordinates"]), 3)
            self.assertEqual(res["coordinates"][0], [12.9716, 77.5946])

    def test_02_osrm_http_failure_records_no_osrm(self):
        """2. OSRM HTTP failure => no OSRM route is recorded; falls back to LOCAL_ASTAR or direct geometric."""
        router = RoutingService()
        with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError("url", 503, "Service Unavailable", {}, None)):
            res = router.route(12.9716, 77.5946, 13.0827, 80.2707)

            self.assertIsNotNone(res)
            self.assertNotEqual(res.get("provider"), "OSRM")
            self.assertNotEqual(res.get("route_provider"), "OSRM")
            self.assertIn(res.get("provider"), ["LOCAL_ASTAR", "DIRECT_GEOMETRIC"])
            self.assertIn(res.get("route_type"), ["GRAPH_ESTIMATE", "STRAIGHT_LINE_ESTIMATE"])
            self.assertEqual(res.get("classification"), "CALCULATED")

    def test_03_invalid_osrm_response_fallback(self):
        """3. Invalid OSRM response (non-Ok code, empty routes, missing geometry) => never saved as OSRM."""
        router = RoutingService()

        # Case A: Non-Ok code
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.read.return_value = b'{"code":"NoRoute","routes":[]}'
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            res_a = router._osrm(12.9716, 77.5946, 13.0827, 80.2707)
            self.assertIsNone(res_a)

        # Case B: Malformed geometry / empty coordinates
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.read.return_value = b'{"code":"Ok","routes":[{"distance":100,"duration":50,"geometry":{"coordinates":[]}}]}'
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            res_b = router._osrm(12.9716, 77.5946, 13.0827, 80.2707)
            self.assertIsNone(res_b)

        # Case C: Negative distance
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.read.return_value = b'{"code":"Ok","routes":[{"distance":-50,"duration":10,"geometry":{"coordinates":[[77.5,12.9]]}}]}'
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            res_c = router._osrm(12.9716, 77.5946, 13.0827, 80.2707)
            self.assertIsNone(res_c)

    def test_04_astar_fallback_labeled_local_astar(self):
        """4. A* fallback is explicitly labeled LOCAL_ASTAR, route_type GRAPH_ESTIMATE, classification CALCULATED."""
        router = RoutingService()
        res = router._astar(12.9716, 77.5946, 13.0827, 80.2707)

        self.assertIn(res["provider"], ["LOCAL_ASTAR", "DIRECT_GEOMETRIC"])
        self.assertIn(res["route_type"], ["GRAPH_ESTIMATE", "STRAIGHT_LINE_ESTIMATE"])
        self.assertEqual(res["classification"], "CALCULATED")
        self.assertNotIn("OSRM", res["provider"])
        self.assertNotIn("REAL_ROAD", res["route_type"])
        self.assertNotIn("REAL_ROUTE", res["route_type"])
        self.assertIn("not a verified road route", res["methodology"])

    def test_05_missing_start_coordinates_unavailable(self):
        """5. Missing start coordinates => ROUTE_UNAVAILABLE, provider UNAVAILABLE, distance/eta/geometry None."""
        router = RoutingService()
        res = router.route(None, None, 13.0827, 80.2707)

        self.assertEqual(res["status"], "ROUTE_UNAVAILABLE")
        self.assertEqual(res["provider"], "UNAVAILABLE")
        self.assertEqual(res["route_provider"], "UNAVAILABLE")
        self.assertEqual(res["route_type"], "UNAVAILABLE")
        self.assertEqual(res["classification"], "UNAVAILABLE")
        self.assertIsNone(res["distance_km"])
        self.assertIsNone(res["distance"])
        self.assertIsNone(res["eta_hours"])
        self.assertIsNone(res["eta"])
        self.assertIsNone(res["coordinates"])
        self.assertIsNone(res["geometry"])

    def test_06_missing_destination_coordinates_unavailable(self):
        """6. Missing destination coordinates => ROUTE_UNAVAILABLE, provider UNAVAILABLE, distance/eta None."""
        router = RoutingService()
        res = router.route(12.9716, 77.5946, None, None)

        self.assertEqual(res["status"], "ROUTE_UNAVAILABLE")
        self.assertEqual(res["provider"], "UNAVAILABLE")
        self.assertIsNone(res["distance_km"])
        self.assertIsNone(res["eta_hours"])
        self.assertIsNone(res["coordinates"])

    def test_07_invalid_coordinates_rejected(self):
        """7. Invalid coordinates (NaN, Inf, out-of-range, null island 0,0) => ROUTE_UNAVAILABLE."""
        router = RoutingService()

        # NaN
        res_nan = router.route(float("nan"), 77.59, 13.08, 80.27)
        self.assertEqual(res_nan["status"], "ROUTE_UNAVAILABLE")
        self.assertIsNone(res_nan["distance_km"])

        # Inf
        res_inf = router.route(12.97, float("inf"), 13.08, 80.27)
        self.assertEqual(res_inf["status"], "ROUTE_UNAVAILABLE")
        self.assertIsNone(res_inf["distance_km"])

        # Out of bounds latitude (> 90)
        res_oob = router.route(95.0, 77.59, 13.08, 80.27)
        self.assertEqual(res_oob["status"], "ROUTE_UNAVAILABLE")
        self.assertIsNone(res_oob["distance_km"])

        # Null Island (0.0, 0.0)
        res_null = router.route(0.0, 0.0, 13.08, 80.27)
        self.assertEqual(res_null["status"], "ROUTE_UNAVAILABLE")
        self.assertIsNone(res_null["distance_km"])

    def test_08_route_distance_comes_from_provider_result(self):
        """8. Route distance comes from provider result, not a synthetic hardcoded formula."""
        router = RoutingService()
        fake_osrm_payload = {
            "code": "Ok",
            "routes": [{"distance": 7890.0, "duration": 900.0, "geometry": {"coordinates": [[77.5, 12.9], [77.6, 13.0]]}}],
        }
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.read.return_value = json.dumps(fake_osrm_payload).encode("utf-8")
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            res = router.route(12.9, 77.5, 13.0, 77.6)
            self.assertEqual(res["distance_km"], 7.89)

    def test_09_route_eta_comes_from_provider_result(self):
        """9. Route ETA comes from provider duration, not a synthetic formula."""
        router = RoutingService()
        fake_osrm_payload = {
            "code": "Ok",
            "routes": [{"distance": 36000.0, "duration": 1800.0, "geometry": {"coordinates": [[77.5, 12.9], [77.6, 13.0]]}}],
        }
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.read.return_value = json.dumps(fake_osrm_payload).encode("utf-8")
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            res = router.route(12.9, 77.5, 13.0, 77.6)
            self.assertEqual(res["eta_hours"], 0.5)
            self.assertEqual(res["duration_minutes"], 30.0)

    def test_10_route_geometry_comes_from_provider_result(self):
        """10. Route geometry comes from provider GeoJSON points."""
        router = RoutingService()
        fake_coords = [[77.51, 12.91], [77.55, 12.95], [77.60, 13.00]]
        fake_osrm_payload = {
            "code": "Ok",
            "routes": [{"distance": 12000.0, "duration": 1200.0, "geometry": {"coordinates": fake_coords}}],
        }
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.read.return_value = json.dumps(fake_osrm_payload).encode("utf-8")
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            res = router.route(12.91, 77.51, 13.00, 77.60)
            self.assertEqual(res["coordinates"], [[12.91, 77.51], [12.95, 77.55], [13.00, 77.60]])

    def test_11_no_hardcoded_production_route_values(self):
        """11. Orchestrator and RouteAgent do not use fabricated formulas like 3.5 + i*1.8 or default OSRM stamps."""
        default_plan = RoutePlan()
        self.assertEqual(default_plan.route_provider, "UNAVAILABLE")
        self.assertIsNone(default_plan.distance_km)
        self.assertIsNone(default_plan.eta_hours)
        self.assertIsNone(default_plan.route_coordinates)

        orch = Orchestrator(seed=101)
        with patch.object(orch.router, "route") as mock_route, \
             patch.object(orch, "_stream_vehicle_updates"), \
             patch.object(orch.message_bus, "publish"):
            mock_route.return_value = {
                "status": "FALLBACK_ASTAR",
                "provider": "LOCAL_ASTAR",
                "route_provider": "LOCAL_ASTAR",
                "route_type": "GRAPH_ESTIMATE",
                "classification": "CALCULATED",
                "distance_km": 11.4,
                "eta_hours": 0.28,
                "coordinates": [[13.0, 80.0], [13.05, 80.05]],
                "path": ["Sector 1"],
            }
            orch.run()
            self.assertTrue(mock_route.called)

            conn = database.get_connection()
            incidents = [dict(r) for r in conn.execute("SELECT * FROM incidents WHERE run_id = ?", (orch.run_id,)).fetchall()]
            conn.close()

            self.assertGreater(len(incidents), 0)
            for inc in incidents:
                self.assertEqual(inc["route_provider"], "LOCAL_ASTAR")
                self.assertEqual(inc["route_distance_km"], 11.4)
                self.assertEqual(inc["route_eta_hours"], 0.28)

    def test_12_run_a_route_data_isolated_from_run_b(self):
        """12. Run A route data is strictly isolated from Run B."""
        run_a = f"run-a-{uuid.uuid4().hex[:8]}"
        run_b = f"run-b-{uuid.uuid4().hex[:8]}"

        database.create_run(run_a, 42, "smart", 1)
        database.create_run(run_b, 43, "smart", 1)

        database.save_incidents(run_a, [
            {
                "location": "Sector A-1",
                "latitude": 13.0,
                "longitude": 80.0,
                "severity": "high",
                "people_affected": 20,
                "disaster_type": "flood",
                "route_distance_km": 5.5,
                "route_eta_hours": 0.15,
                "route_source": "OSRM",
                "route_provider": "OSRM",
            }
        ])

        database.save_incidents(run_b, [
            {
                "location": "Sector B-1",
                "latitude": 28.0,
                "longitude": 77.0,
                "severity": "medium",
                "people_affected": 10,
                "disaster_type": "earthquake",
                "route_distance_km": 25.0,
                "route_eta_hours": 0.55,
                "route_source": "LOCAL_ASTAR",
                "route_provider": "LOCAL_ASTAR",
            }
        ])

        conn = database.get_connection()
        incs_a = [dict(r) for r in conn.execute("SELECT * FROM incidents WHERE run_id = ?", (run_a,)).fetchall()]
        incs_b = [dict(r) for r in conn.execute("SELECT * FROM incidents WHERE run_id = ?", (run_b,)).fetchall()]
        conn.close()

        self.assertEqual(len(incs_a), 1)
        self.assertEqual(incs_a[0]["route_provider"], "OSRM")
        self.assertEqual(incs_a[0]["route_distance_km"], 5.5)

        self.assertEqual(len(incs_b), 1)
        self.assertEqual(incs_b[0]["route_provider"], "LOCAL_ASTAR")
        self.assertEqual(incs_b[0]["route_distance_km"], 25.0)

    def test_13_corridor_router_exposes_truthful_provenance(self):
        """13. Corridor router exposes truthful provenance (provider, classification, start/end coordinates, distance, planned ETA)."""
        corr = plan_evacuation_corridor(
            origin_lat=13.0827,
            origin_lng=80.2707,
            dest_lat=12.9716,
            dest_lng=77.5946,
            corridor_name="Test Corridor",
            profile="car",
        )

        self.assertIn("provider", corr)
        self.assertIn(corr["provider"], ["OSRM", "LOCAL_ASTAR", "DIRECT_GEOMETRIC"])
        self.assertIn(corr["route_type"], ["ROAD_ROUTE", "GRAPH_ESTIMATE", "STRAIGHT_LINE_ESTIMATE"])
        self.assertEqual(corr["classification"], "CALCULATED")
        self.assertIsNotNone(corr["distance_km"])
        self.assertIsNotNone(corr["planned_eta"])
        self.assertEqual(corr["start_coordinates"], [13.0827, 80.2707])
        self.assertEqual(corr["end_coordinates"], [12.9716, 77.5946])
        self.assertIn("methodology", corr)

        # Missing / invalid coordinates
        corr_bad = plan_evacuation_corridor(
            origin_lat=None,
            origin_lng=None,
            dest_lat=12.9716,
            dest_lng=77.5946,
        )
        self.assertEqual(corr_bad["status"], "ROUTE_UNAVAILABLE")
        self.assertEqual(corr_bad["provider"], "UNAVAILABLE")
        self.assertIsNone(corr_bad["distance_km"])
        self.assertIsNone(corr_bad["planned_eta"])

    def test_14_planned_eta_is_not_labeled_actual_response_time(self):
        """14. Planned ETA is formatted with explicit 'planned ETA' label, never 'actual response time'."""
        orch = Orchestrator(seed=55)
        with patch.object(orch, "_stream_vehicle_updates"), patch.object(orch.message_bus, "publish"):
            orch.run()

        # Check run metrics summary in database
        metrics = database.get_run_metrics(orch.run_id)
        if metrics:
            avg_resp = metrics.get("avg_response_time", "")
            if avg_resp and avg_resp != "N/A":
                self.assertIn("planned ETA", avg_resp)
                self.assertNotIn("actual response time", avg_resp.lower())


if __name__ == "__main__":
    unittest.main()
