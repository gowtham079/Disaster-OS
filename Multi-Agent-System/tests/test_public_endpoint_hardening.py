import math
import sys
import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

sys.path.insert(0, r"d:\Disaster_OS_Phase2\multi_agent_disaster_management\Multi-Agent-System")

from app import app
import database
from intelligence.cache import intelligence_cache


class TestPublicEndpointHardening(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def get_auth_headers(self):
        res = self.client.post("/api/auth/login", json={
            "email": "operator@disaster.local",
            "password": "operator123",
        })
        token = res.json()["token"]
        return {"Authorization": f"Bearer {token}"}

    # ── FIX 1: Earthquakes & Disasters Cache-Hit DB Write Prevention ─────────

    def test_earthquakes_cached_requests_do_not_repeat_db_writes(self):
        """When earthquakes are cached, GET /api/intelligence/earthquakes must not perform DB writes."""
        # Prime the cache with test event
        intelligence_cache.clear()
        with patch("database.save_external_disaster_events") as mock_save:
            res1 = self.client.get("/api/intelligence/earthquakes?mag_min=4.5")
            self.assertEqual(res1.status_code, 200)
            data1 = res1.json()
            self.assertEqual(data1["status"], "success")
            self.assertIn("events", data1)
            first_call_count = mock_save.call_count

            # Second call (cache hit)
            res2 = self.client.get("/api/intelligence/earthquakes?mag_min=4.5")
            self.assertEqual(res2.status_code, 200)
            # save_external_disaster_events must NOT be called on cache hit
            self.assertEqual(mock_save.call_count, first_call_count, "DB write occurred on cache hit")

    def test_disasters_cached_requests_do_not_repeat_db_writes(self):
        """When disasters are cached, GET /api/intelligence/disasters must not perform DB writes."""
        intelligence_cache.clear()
        with patch("database.save_external_disaster_events") as mock_save:
            res1 = self.client.get("/api/intelligence/disasters")
            self.assertEqual(res1.status_code, 200)
            data1 = res1.json()
            self.assertEqual(data1["status"], "success")
            self.assertIn("events", data1)
            first_call_count = mock_save.call_count

            # Second call (cache hit)
            res2 = self.client.get("/api/intelligence/disasters")
            self.assertEqual(res2.status_code, 200)
            self.assertEqual(mock_save.call_count, first_call_count, "DB write occurred on cache hit")

    def test_earthquakes_invalid_magnitude_rejected(self):
        """mag_min outside [0.0, 10.0] or non-finite must receive HTTP 400."""
        res_neg = self.client.get("/api/intelligence/earthquakes?mag_min=-1.0")
        self.assertEqual(res_neg.status_code, 400)
        self.assertEqual(res_neg.json()["status"], "error")

        res_huge = self.client.get("/api/intelligence/earthquakes?mag_min=11.0")
        self.assertEqual(res_huge.status_code, 400)

        res_nan = self.client.get("/api/intelligence/earthquakes?mag_min=nan")
        self.assertEqual(res_nan.status_code, 400)

    # ── FIX 2: Facilities Radius Clamping & Cache Bypass Prevention ──────────

    def test_facilities_excessive_radius_clamped(self):
        """Excessive radius values must be safely clamped to 50.0 km."""
        with patch("app.fetch_real_facilities") as mock_fetch:
            mock_fetch.return_value = ([], "LIVE")
            res = self.client.get("/api/intelligence/facilities?lat=19.076&lng=72.877&radius_km=1000")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["radius_km"], 50.0)
            mock_fetch.assert_called_once()
            _, kwargs = mock_fetch.call_args
            self.assertEqual(kwargs["radius_km"], 50.0)

    def test_facilities_subminimum_radius_clamped(self):
        """Radius values below 1.0 km must be clamped to 1.0 km."""
        with patch("app.fetch_real_facilities") as mock_fetch:
            mock_fetch.return_value = ([], "LIVE")
            res = self.client.get("/api/intelligence/facilities?lat=19.076&lng=72.877&radius_km=0.05")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["radius_km"], 1.0)
            mock_fetch.assert_called_once()
            _, kwargs = mock_fetch.call_args
            self.assertEqual(kwargs["radius_km"], 1.0)

    def test_facilities_normal_dashboard_radius_preserved(self):
        """Radius values of 25 km and 30 km used by dashboard components must be preserved."""
        with patch("app.fetch_real_facilities") as mock_fetch:
            mock_fetch.return_value = ([], "LIVE")
            res25 = self.client.get("/api/intelligence/facilities?lat=19.076&lng=72.877&radius_km=25")
            self.assertEqual(res25.status_code, 200)
            self.assertEqual(res25.json()["radius_km"], 25.0)

            res30 = self.client.get("/api/intelligence/facilities?lat=19.076&lng=72.877&radius_km=30")
            self.assertEqual(res30.status_code, 200)
            self.assertEqual(res30.json()["radius_km"], 30.0)

    def test_facilities_public_cache_bypass_prevented(self):
        """Unauthenticated public requests cannot force use_cache=false."""
        with patch("app.fetch_real_facilities") as mock_fetch:
            mock_fetch.return_value = ([], "LIVE")
            res = self.client.get("/api/intelligence/facilities?lat=19.076&lng=72.877&radius_km=20&use_cache=false")
            self.assertEqual(res.status_code, 200)
            mock_fetch.assert_called_once()
            _, kwargs = mock_fetch.call_args
            # Public caller forced to use_cache=True
            self.assertTrue(kwargs["use_cache"], "Public caller was allowed to bypass cache")

    def test_facilities_authenticated_operator_can_bypass_cache(self):
        """Authenticated operator can legitimately request use_cache=false."""
        headers = self.get_auth_headers()
        with patch("app.fetch_real_facilities") as mock_fetch:
            mock_fetch.return_value = ([], "LIVE")
            res = self.client.get(
                "/api/intelligence/facilities?lat=19.076&lng=72.877&radius_km=20&use_cache=false",
                headers=headers,
            )
            self.assertEqual(res.status_code, 200)
            mock_fetch.assert_called_once()
            _, kwargs = mock_fetch.call_args
            self.assertFalse(kwargs["use_cache"])

    # ── FIX 3: Location Search Validation ───────────────────────────────────

    def test_search_excessive_length_rejected(self):
        """Queries exceeding 100 characters must receive HTTP 400."""
        long_q = "A" * 101
        res = self.client.get(f"/api/intelligence/search?q={long_q}")
        self.assertEqual(res.status_code, 400)
        data = res.json()
        self.assertEqual(data["status"], "error")
        self.assertIn("100 characters", data["message"])

    def test_search_control_characters_rejected(self):
        """Queries containing control characters (e.g. null bytes) must receive HTTP 400."""
        res = self.client.get("/api/intelligence/search?q=Mumbai%00Station")
        self.assertEqual(res.status_code, 400)
        data = res.json()
        self.assertEqual(data["status"], "error")
        self.assertIn("control characters", data["message"])

    def test_search_empty_and_short_queries_handled(self):
        """Empty or single-character queries return empty results without error."""
        res_empty = self.client.get("/api/intelligence/search?q=")
        self.assertEqual(res_empty.status_code, 200)
        self.assertEqual(res_empty.json()["count"], 0)

        res_short = self.client.get("/api/intelligence/search?q=A")
        self.assertEqual(res_short.status_code, 200)
        self.assertEqual(res_short.json()["count"], 0)

    def test_search_valid_query_preserved(self):
        """Valid queries return expected schema with provider provenance."""
        with patch("app.search_nominatim_location") as mock_search:
            mock_search.return_value = [{
                "provider": "Nominatim",
                "classification": "LIVE",
                "display_name": "Mumbai, Maharashtra, India",
                "latitude": 19.076,
                "longitude": 72.877,
                "place_id": 12345,
                "type": "city",
                "fetched_at": 1700000000.0,
            }]
            res = self.client.get("/api/intelligence/search?q=Mumbai")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["status"], "success")
            self.assertEqual(data["count"], 1)
            self.assertEqual(data["provider"], "Nominatim")

    # ── FIX 4: Reverse Geocoding Bounds Checking ────────────────────────────

    def test_geocode_invalid_latitude_rejected(self):
        """Latitude outside [-90, 90] must receive HTTP 400 before provider call."""
        with patch("weather_service.reverse_geocode") as mock_geo:
            res_high = self.client.get("/api/geocode/95.0/72.877")
            self.assertEqual(res_high.status_code, 400)
            mock_geo.assert_not_called()

            res_low = self.client.get("/api/geocode/-95.0/72.877")
            self.assertEqual(res_low.status_code, 400)
            mock_geo.assert_not_called()

    def test_geocode_invalid_longitude_rejected(self):
        """Longitude outside [-180, 180] must receive HTTP 400 before provider call."""
        with patch("weather_service.reverse_geocode") as mock_geo:
            res_high = self.client.get("/api/geocode/19.076/185.0")
            self.assertEqual(res_high.status_code, 400)
            mock_geo.assert_not_called()

            res_low = self.client.get("/api/geocode/19.076/-185.0")
            self.assertEqual(res_low.status_code, 400)
            mock_geo.assert_not_called()

    def test_geocode_non_finite_rejected(self):
        """NaN or Inf coordinates must receive HTTP 400."""
        with patch("weather_service.reverse_geocode") as mock_geo:
            res_nan = self.client.get("/api/geocode/nan/72.877")
            self.assertEqual(res_nan.status_code, 400)
            mock_geo.assert_not_called()

            res_inf = self.client.get("/api/geocode/19.076/inf")
            self.assertEqual(res_inf.status_code, 400)
            mock_geo.assert_not_called()

    def test_geocode_valid_coordinates_preserved(self):
        """Valid coordinates successfully call reverse geocoding and return address."""
        with patch("weather_service.reverse_geocode") as mock_geo:
            mock_geo.return_value = "Nariman Point, Mumbai"
            res = self.client.get("/api/geocode/18.926/72.823")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["status"], "success")
            self.assertEqual(data["address"], "Nariman Point, Mumbai")
            self.assertEqual(data["latitude"], 18.926)
            self.assertEqual(data["longitude"], 72.823)

    # ── FIX 5: Route Planning Coordinates Validation ────────────────────────

    def test_route_plan_invalid_lat_rejected(self):
        """Latitude outside [-90, 90] must receive HTTP 422."""
        headers = self.get_auth_headers()
        res = self.client.post(
            "/api/routes/plan",
            json={
                "start_lat": 95.0,
                "start_lng": 72.878,
                "end_lat": 19.120,
                "end_lng": 72.900,
            },
            headers=headers,
        )
        self.assertEqual(res.status_code, 422)

    def test_route_plan_invalid_lng_rejected(self):
        """Longitude outside [-180, 180] must receive HTTP 422."""
        headers = self.get_auth_headers()
        res = self.client.post(
            "/api/routes/plan",
            json={
                "start_lat": 19.076,
                "start_lng": -185.0,
                "end_lat": 19.120,
                "end_lng": 72.900,
            },
            headers=headers,
        )
        self.assertEqual(res.status_code, 422)

    def test_route_plan_valid_coordinates_accepted(self):
        """Valid coordinates within ranges are processed normally."""
        headers = self.get_auth_headers()
        with patch("routing.service.RoutingService.route") as mock_route:
            mock_route.return_value = {
                "distance_km": 5.2,
                "duration_min": 12.0,
                "provenance": "LOCAL_ASTAR",
                "coordinates": [[19.076, 72.878], [19.120, 72.900]],
            }
            res = self.client.post(
                "/api/routes/plan",
                json={
                    "start_lat": 19.076,
                    "start_lng": 72.878,
                    "end_lat": 19.120,
                    "end_lng": 72.900,
                },
                headers=headers,
            )
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["status"], "success")
            self.assertIn("route", data)
            self.assertEqual(data["route"]["provenance"], "LOCAL_ASTAR")


if __name__ == "__main__":
    unittest.main()
