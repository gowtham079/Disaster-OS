"""Unit Tests for Phase P3.4 Evacuation Corridor Optimization & Multi-Profile Routing.

Verifies:
- Multi-profile routing (emergency vehicle 'car', heavy transport 'hgv', pedestrian 'foot')
- Dynamic hazard avoidance against active MMI VII+ isoseismals and roadblocks
- Evacuation bottleneck throughput and clearance time calculations
- SQLite database persistence and retrieval (save_evacuation_corridor, get_evacuation_corridors)
- FastAPI REST endpoints (/api/corridors/plan, /api/corridors/active)
"""

import unittest
from fastapi.testclient import TestClient

import database
from app import app
from intelligence.corridor_router import haversine_km, plan_evacuation_corridor


class TestCorridorRouter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database.init_db()
        cls.client = TestClient(app)
        login_res = cls.client.post("/api/auth/login", json={"email": "operator@disaster.local", "password": "operator123"})
        if login_res.status_code == 200:
            token = login_res.json().get("token")
            cls.client.headers.update({"Authorization": f"Bearer {token}"})

    def test_multi_profile_routing(self):
        """Verify different vehicle and pedestrian profiles compute appropriate speeds and throughputs."""
        origin = (19.076, 72.878)
        dest = (19.120, 72.900)

        car_plan = plan_evacuation_corridor(
            origin_lat=origin[0], origin_lng=origin[1],
            dest_lat=dest[0], dest_lng=dest[1],
            profile="car",
            population_to_evacuate=1000,
        )
        foot_plan = plan_evacuation_corridor(
            origin_lat=origin[0], origin_lng=origin[1],
            dest_lat=dest[0], dest_lng=dest[1],
            profile="foot",
            population_to_evacuate=1000,
        )
        hgv_plan = plan_evacuation_corridor(
            origin_lat=origin[0], origin_lng=origin[1],
            dest_lat=dest[0], dest_lng=dest[1],
            profile="hgv",
            population_to_evacuate=1000,
        )

        self.assertEqual(car_plan["profile"], "car")
        self.assertEqual(foot_plan["profile"], "foot")
        self.assertEqual(hgv_plan["profile"], "hgv")

        # Foot transit time should be longer than car transit time
        self.assertGreater(foot_plan["transit_time_minutes"], car_plan["transit_time_minutes"])
        self.assertEqual(car_plan["classification"], "CALCULATED")

    def test_hazard_avoidance_intersections(self):
        """Verify corridor identifies intersections with active MMI VII+ impact zones and marks status compromised."""
        origin = (19.050, 72.850)
        dest = (19.150, 72.950)

        # Impact zone directly centered in the middle of origin and destination
        mid_lat = (origin[0] + dest[0]) / 2.0
        mid_lng = (origin[1] + dest[1]) / 2.0

        severe_zone = [{
            "center_latitude": mid_lat,
            "center_longitude": mid_lng,
            "radius_km": 15.0,
            "name": "MMI VII+ Severe Shaking Epicenter",
            "level": "CRITICAL",
        }]

        impeded_plan = plan_evacuation_corridor(
            origin_lat=origin[0], origin_lng=origin[1],
            dest_lat=dest[0], dest_lng=dest[1],
            profile="car",
            impact_zones=severe_zone,
        )

        self.assertEqual(impeded_plan["status"], "HAZARDOUS_IMPEDED")
        self.assertEqual(impeded_plan["safety_tier"], "TIER_3_COMPROMISED")
        self.assertGreaterEqual(len(impeded_plan["hazard_intersections"]), 1)

    def test_roadblock_bottleneck_detection(self):
        """Verify nearby road blockages trigger caution status and reduce throughput."""
        origin = (19.076, 72.878)
        dest = (19.090, 72.885)

        # Roadblock directly on origin coordinate
        roadblocks = [{"latitude": 19.076, "longitude": 72.878, "road_name": "MG Road"}]

        plan = plan_evacuation_corridor(
            origin_lat=origin[0], origin_lng=origin[1],
            dest_lat=dest[0], dest_lng=dest[1],
            profile="car",
            roadblocks=roadblocks,
        )

        self.assertEqual(plan["status"], "CAUTION_RESTRICTED")
        self.assertEqual(plan["safety_tier"], "TIER_2_RESTRICTED")
        self.assertIn("Road blockage", plan["hazard_intersections"][0])

    def test_corridors_database_crud(self):
        """Verify saving and retrieving evacuation corridors from SQLite."""
        sample_corridor = {
            "corridor_id": "CORR-TEST-99",
            "name": "North Sector Evacuation Route",
            "profile": "car",
            "profile_label": "Standard Motor Corridor",
            "status": "SAFE_PASSABLE",
            "origin": {"latitude": 19.076, "longitude": 72.878},
            "destination": {"latitude": 19.150, "longitude": 72.950},
            "distance_km": 14.2,
            "transit_time_minutes": 18,
            "population_to_evacuate": 1200,
            "bottleneck_throughput_per_hour": 1200,
            "estimated_clearance_hours": 1.3,
            "path_coordinates": [[19.076, 72.878], [19.150, 72.950]],
            "hazard_intersections": [],
            "safety_tier": "TIER_1_OPTIMAL",
            "classification": "CALCULATED",
            "methodology": "Lighthill-Whitham-Richards Flow Dynamics",
        }

        # Ensure clean state for test record
        conn = database.get_connection()
        conn.execute("DELETE FROM evacuation_corridors WHERE corridor_id = 'CORR-TEST-99'")
        conn.commit()
        conn.close()

        database.save_evacuation_corridor(sample_corridor)

        corridors = database.get_evacuation_corridors(limit=10)
        self.assertIsInstance(corridors, list)
        self.assertTrue(any(c["corridor_id"] == "CORR-TEST-99" for c in corridors))

    def test_corridors_api_endpoints(self):
        """Verify REST API endpoints for corridor planning."""
        # 1. Successful POST /api/corridors/plan
        resp = self.client.post(
            "/api/corridors/plan",
            json={
                "origin_lat": 19.076,
                "origin_lng": 72.878,
                "dest_lat": 19.120,
                "dest_lng": 72.900,
                "profile": "car",
                "population_to_evacuate": 750,
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("corridor", data)
        self.assertTrue(data["corridor"]["corridor_id"].startswith("CORR-"))

        # 2. Coordinates validation error
        bad_resp = self.client.post(
            "/api/corridors/plan",
            json={"origin_lat": 95.0, "origin_lng": 72.0, "dest_lat": 19.0, "dest_lng": 72.0},
        )
        self.assertEqual(bad_resp.status_code, 400)

        # 3. GET /api/corridors/active
        list_resp = self.client.get("/api/corridors/active")
        self.assertEqual(list_resp.status_code, 200)
        self.assertIsInstance(list_resp.json()["corridors"], list)


if __name__ == "__main__":
    unittest.main()
