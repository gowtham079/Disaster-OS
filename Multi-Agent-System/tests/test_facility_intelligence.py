"""Unit and Integration Tests for Real Facility Intelligence & OpenStreetMap/Overpass Integration.

Tests Overpass QL query construction, element parsing, zero fake capacity rules,
SQLite geographic caching, spatial radius lookup, and FastAPI endpoints.
"""

import json
import time
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

import database
from app import app
from intelligence.facility_provider import (
    build_overpass_query,
    fetch_real_facilities,
    parse_overpass_elements,
)
from intelligence.models import CapacityStatus, DataClassification, FacilityRecord
from intelligence.source_health import health_manager


class TestFacilityIntelligence(unittest.TestCase):

    def setUp(self):
        database.init_db()
        self.client = TestClient(app)

    # 1. Test Query Construction
    def test_build_overpass_query_format(self):
        query = build_overpass_query(lat=19.076, lng=72.877, radius_meters=15000, limit=40)
        self.assertIn("[out:json][timeout:6];", query)
        self.assertIn("around:15000,19.076,72.877", query)
        self.assertIn("out center 40;", query)
        self.assertIn("hospital", query)
        self.assertIn("police", query)

    # 2. Test Element Parsing & Provenance Integrity
    def test_parse_overpass_elements_with_zero_fake_capacity(self):
        raw_elements = [
            {
                "type": "node",
                "id": 1001,
                "lat": 19.080,
                "lon": 72.885,
                "tags": {
                    "amenity": "hospital",
                    "name": "General Civil Hospital",
                    "addr:street": "MG Road",
                    "addr:city": "Mumbai",
                    # No 'beds' or 'capacity' tag
                },
            },
            {
                "type": "way",
                "id": 2002,
                "center": {"lat": 19.095, "lon": 72.890},
                "tags": {
                    "amenity": "community_centre",
                    "name": "East Relief Center",
                    "capacity": "450",  # Explicit real capacity tag present
                },
            },
            {
                "type": "node",
                "id": 3003,
                "lat": 19.070,
                "lon": 72.870,
                "tags": {
                    "amenity": "fire_station",
                    "name": "Central Fire Brigade",
                },
            },
        ]

        facilities = parse_overpass_elements(raw_elements)
        self.assertEqual(len(facilities), 3)

        # Hospital: Capacity MUST be None and UNAVAILABLE (Zero Fake Capacity Rule)
        hosp = next(f for f in facilities if f.facility_type == "hospital")
        self.assertEqual(hosp.facility_id, "osm-node-1001")
        self.assertEqual(hosp.name, "General Civil Hospital")
        self.assertIsNone(hosp.capacity, "Must NEVER fabricate beds or capacity when absent from OSM")
        self.assertEqual(hosp.capacity_status, CapacityStatus.UNAVAILABLE)
        self.assertEqual(hosp.classification, DataClassification.LIVE)
        self.assertIn("MG Road", hosp.address)

        # Shelter with real capacity tag:
        shelter = next(f for f in facilities if f.facility_type == "shelter")
        self.assertEqual(shelter.facility_id, "osm-way-2002")
        self.assertEqual(shelter.capacity, 450)
        self.assertEqual(shelter.capacity_status, CapacityStatus.VERIFIED)

        # Fire station:
        fire = next(f for f in facilities if f.facility_type == "fire_station")
        self.assertEqual(fire.facility_id, "osm-node-3003")
        self.assertIsNone(fire.capacity)
        self.assertEqual(fire.capacity_status, CapacityStatus.UNAVAILABLE)

    # 3. Test Provider Fetch with Mock Network Success
    @patch("intelligence.facility_provider._http_post_overpass")
    def test_fetch_real_facilities_network_success(self, mock_http):
        mock_payload = {
            "elements": [
                {
                    "type": "node",
                    "id": 5551,
                    "lat": 19.055,
                    "lon": 72.835,
                    "tags": {"amenity": "hospital", "name": "Lilavati Hospital & Research", "beds": "300"},
                },
                {
                    "type": "node",
                    "id": 5552,
                    "lat": 19.060,
                    "lon": 72.840,
                    "tags": {"amenity": "police", "name": "Bandra Police Station"},
                },
            ]
        }
        mock_http.return_value = json.dumps(mock_payload).encode("utf-8")

        facilities, provenance = fetch_real_facilities(lat=19.055, lng=72.835, radius_km=10.0, use_cache=False)
        self.assertEqual(len(facilities), 2)
        self.assertEqual(provenance, "LIVE")
        self.assertEqual(facilities[0].name, "Lilavati Hospital & Research")
        self.assertEqual(facilities[0].capacity, 300)
        self.assertEqual(facilities[0].capacity_status, CapacityStatus.VERIFIED)

        # Health status must be OPERATIONAL
        stat = health_manager.get_status("Overpass")
        self.assertIsNotNone(stat)
        self.assertEqual(stat.status.value, "OPERATIONAL")

    # 4. Test Overpass Failure Returns Zero Fake Data
    @patch("intelligence.facility_provider._http_post_overpass")
    def test_fetch_real_facilities_failure_returns_zero_fake_data(self, mock_http):
        mock_http.side_effect = TimeoutError("Overpass gateway timed out")

        # Clear any prior cache for these exact remote coordinates
        facs, provenance = fetch_real_facilities(lat=-45.123, lng=120.456, radius_km=5.0, use_cache=False)
        self.assertEqual(facs, [], "Must NEVER return fake facilities when provider is unreachable")
        self.assertEqual(provenance, "UNAVAILABLE")

    # 5. Test SQLite Geographic Cache Caching & Retrieval
    def test_sqlite_geographic_cache_lifecycle(self):
        cache_key = "test_geo_key_999"
        test_data = [{"facility_id": "osm-node-77", "name": "Cached Clinic", "facility_type": "hospital", "latitude": 19.0, "longitude": 72.0}]

        database.set_geographic_cache(cache_key, "facilities", test_data, ttl_seconds=3600)
        cached = database.get_geographic_cache(cache_key)
        self.assertIsNotNone(cached)
        self.assertEqual(len(cached), 1)
        self.assertEqual(cached[0]["name"], "Cached Clinic")

    # 6. Test Spatial Distance Filtering in Database
    def test_database_spatial_facility_lookup(self):
        sample_facs = [
            {
                "facility_id": "test-fac-near",
                "facility_type": "hospital",
                "name": "Nearby Hospital",
                "latitude": 19.076,
                "longitude": 72.877,
                "classification": "LIVE",
                "capacity": None,
                "capacity_status": "UNAVAILABLE",
            },
            {
                "facility_id": "test-fac-far",
                "facility_type": "hospital",
                "name": "Distant Hospital in Delhi",
                "latitude": 28.613,
                "longitude": 77.209,
                "classification": "LIVE",
                "capacity": None,
                "capacity_status": "UNAVAILABLE",
            },
        ]
        database.save_external_facilities(sample_facs)

        # Query around Mumbai (19.076, 72.877) with 30km radius: only Nearby Hospital should match
        nearby = database.get_external_facilities(lat=19.076, lng=72.877, radius_km=30.0)
        ids = [f["facility_id"] for f in nearby]
        self.assertIn("test-fac-near", ids)
        self.assertNotIn("test-fac-far", ids)

    # 7. Test FastAPI Endpoint /api/intelligence/facilities
    @patch("intelligence.facility_provider._http_post_overpass")
    def test_api_intelligence_facilities_endpoint(self, mock_http):
        mock_payload = {
            "elements": [
                {
                    "type": "node",
                    "id": 9999,
                    "lat": 19.076,
                    "lon": 72.878,
                    "tags": {"amenity": "shelter", "name": "St. Xavier Community Shelter"},
                }
            ]
        }
        mock_http.return_value = json.dumps(mock_payload).encode("utf-8")

        res = self.client.get("/api/intelligence/facilities?lat=19.076&lng=72.878&radius_km=15.0&use_cache=false")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["source"], "OpenStreetMap / Overpass")
        self.assertEqual(data["count"], 1)
        facility = data["facilities"][0]
        self.assertEqual(facility["name"], "St. Xavier Community Shelter")
        self.assertEqual(facility["capacity_status"], "UNAVAILABLE")
        self.assertIsNone(facility["capacity"])


if __name__ == "__main__":
    unittest.main()
