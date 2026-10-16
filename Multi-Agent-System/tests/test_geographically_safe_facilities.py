import unittest
from unittest.mock import patch

from intelligence.facility_provider import fetch_real_facilities
from intelligence.models import DataClassification
import database


class TestGeographicallySafeFacilities(unittest.TestCase):
    def setUp(self):
        database.init_db()
        # Seed test facilities in Mumbai and Kolkata
        conn = database.get_connection()
        conn.execute(
            """
            INSERT OR REPLACE INTO external_facilities
            (facility_id, facility_type, name, latitude, longitude, source, classification, capacity, capacity_status)
            VALUES
            ('test-hosp-mumbai', 'hospital', 'Lilavati Hospital Mumbai', 19.055, 72.835, 'OpenStreetMap', 'LIVE', 300, 'VERIFIED'),
            ('test-shelter-mumbai', 'shelter', 'Bandra Shelter Mumbai', 19.060, 72.840, 'OpenStreetMap', 'LIVE', 500, 'VERIFIED'),
            ('test-hosp-kolkata', 'hospital', 'Kolkata Medical College', 22.573, 88.364, 'OpenStreetMap', 'LIVE', 450, 'VERIFIED'),
            ('test-hosp-bengaluru', 'hospital', 'Manipal Hospital Bengaluru', 12.9716, 77.5946, 'OpenStreetMap', 'LIVE', 250, 'VERIFIED')
            """
        )
        conn.commit()
        conn.close()

    @patch("intelligence.facility_provider._http_post_overpass", side_effect=Exception("Overpass network timeout"))
    def test_01_kolkata_run_never_receives_mumbai_facility(self, mock_post):
        """1. Kolkata run must never receive a Mumbai fallback facility."""
        kolkata_lat, kolkata_lng = 22.573, 88.364
        facs, prov = fetch_real_facilities(lat=kolkata_lat, lng=kolkata_lng, radius_km=25.0, use_cache=False)
        self.assertEqual(prov, DataClassification.DATABASE.value)
        self.assertTrue(len(facs) > 0)
        for f in facs:
            self.assertNotEqual(f.facility_id, "test-hosp-mumbai")
            self.assertNotIn("Mumbai", f.name)
            # Distance must be within 25 km of Kolkata
            from intelligence.facility_provider import _haversine_distance
            dist = _haversine_distance(kolkata_lat, kolkata_lng, f.latitude, f.longitude)
            self.assertLessEqual(dist, 25.0)

    @patch("intelligence.facility_provider._http_post_overpass", side_effect=Exception("Overpass network timeout"))
    def test_02_chennai_run_never_receives_bengaluru_or_mumbai(self, mock_post):
        """2. Chennai run must never receive Bengaluru/Mumbai facilities."""
        chennai_lat, chennai_lng = 13.0827, 80.2707
        facs, prov = fetch_real_facilities(lat=chennai_lat, lng=chennai_lng, radius_km=25.0, use_cache=False)
        # Since no Chennai facilities are in DB, it must reject Mumbai and Bengaluru
        self.assertEqual(prov, DataClassification.UNAVAILABLE.value)
        self.assertEqual(len(facs), 0)

    @patch("intelligence.facility_provider._http_post_overpass", side_effect=Exception("Overpass network timeout"))
    def test_03_cached_facility_outside_search_radius_rejected(self, mock_post):
        """3. Cached facility outside search radius is rejected."""
        # Query at location 100 km away from Kolkata
        far_lat, far_lng = 23.573, 88.364  # ~111 km north of Kolkata
        facs, prov = fetch_real_facilities(lat=far_lat, lng=far_lng, radius_km=20.0, use_cache=False)
        self.assertEqual(prov, DataClassification.UNAVAILABLE.value)
        self.assertEqual(len(facs), 0)

    @patch("intelligence.facility_provider._http_post_overpass", side_effect=Exception("Overpass network timeout"))
    def test_04_cached_facility_inside_search_radius_may_be_used(self, mock_post):
        """4. Cached facility inside search radius may be used."""
        # Query 2 km from Kolkata Medical College
        near_lat, near_lng = 22.580, 88.370
        facs, prov = fetch_real_facilities(lat=near_lat, lng=near_lng, radius_km=10.0, use_cache=False)
        self.assertEqual(prov, DataClassification.DATABASE.value)
        self.assertTrue(len(facs) >= 1)
        self.assertEqual(facs[0].facility_id, "test-hosp-kolkata")

    @patch("intelligence.facility_provider._http_post_overpass", side_effect=Exception("Overpass network timeout"))
    def test_05_rejected_fallback_produces_unavailable(self, mock_post):
        """5. Rejected fallback produces UNAVAILABLE rather than unrelated data."""
        # Query in Shimla where no facilities exist in DB
        shimla_lat, shimla_lng = 31.1048, 77.1734
        facs, prov = fetch_real_facilities(lat=shimla_lat, lng=shimla_lng, radius_km=20.0, use_cache=False)
        self.assertEqual(prov, DataClassification.UNAVAILABLE.value)
        self.assertEqual(len(facs), 0)
        self.assertIsInstance(facs, list)
