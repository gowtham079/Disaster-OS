"""Unit Tests for Phase P3.2 Disaster Impact Analysis Engine.

Verifies:
- Joyner-Boore empirical seismic attenuation modeling
- Weather / inundation hazard buffer calculations
- Rigorous data provenance and mathematical metadata exposure (CALCULATED classification)
- Real OSM facility spatial intersection
- Database persistence and retrieval (save_impact_assessment, get_impact_assessment)
- FastAPI endpoints (/api/impact/assess, /api/impact/assessments, /api/impact/{id})
- Tactical decision support integration with empirical impact models
"""

import json
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

import database
from app import app
from intelligence.impact_engine import (
    calculate_disaster_impact,
    calculate_seismic_attenuation_radii,
    calculate_weather_impact_radii,
)
from intelligence.models import CapacityStatus, DataClassification, FacilityRecord
from utils.tactical_decision import evaluate_tactical_decision


def _mock_facilities(*args, **kwargs):
    """Return mock OSM facilities near Mumbai coordinates for fast offline testing."""
    return [
        FacilityRecord(
            facility_id="fac-mumbai-hosp-1",
            facility_type="hospital",
            name="Mumbai Central Hospital",
            latitude=19.080,
            longitude=72.880,
            address="Dr. Nair Road",
            city="Mumbai",
            classification=DataClassification.LIVE,
            capacity=None,
            capacity_status=CapacityStatus.UNAVAILABLE,
        ),
        FacilityRecord(
            facility_id="fac-mumbai-fire-1",
            facility_type="fire_station",
            name="Byculla Fire Station",
            latitude=19.085,
            longitude=72.885,
            classification=DataClassification.LIVE,
            capacity=None,
            capacity_status=CapacityStatus.UNAVAILABLE,
        ),
    ], "DATABASE"


class TestDisasterImpactEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database.init_db()
        cls.client = TestClient(app)
        login_res = cls.client.post("/api/auth/login", json={"email": "operator@disaster.local", "password": "operator123"})
        if login_res.status_code == 200:
            token = login_res.json().get("token")
            cls.client.headers.update({"Authorization": f"Bearer {token}"})

    def test_seismic_attenuation_radii_scaling(self):
        """Verify empirical attenuation isoseismals scale monotonically with magnitude and depth."""
        # Test 1: Radii ordering for standard M6.0 shallow earthquake
        radii_m6 = calculate_seismic_attenuation_radii(magnitude=6.0, depth_km=10.0)
        self.assertIn("mmi_vii_severe_km", radii_m6)
        self.assertIn("mmi_v_moderate_km", radii_m6)
        self.assertIn("mmi_iii_light_km", radii_m6)

        # MMI VII (severe) < MMI V (moderate) < MMI III (light shaking)
        self.assertLess(radii_m6["mmi_vii_severe_km"], radii_m6["mmi_v_moderate_km"])
        self.assertLess(radii_m6["mmi_v_moderate_km"], radii_m6["mmi_iii_light_km"])

        # Test 2: Monotonic magnitude scaling (M5.0 < M6.5 < M8.0)
        radii_m5 = calculate_seismic_attenuation_radii(magnitude=5.0, depth_km=10.0)
        radii_m65 = calculate_seismic_attenuation_radii(magnitude=6.5, depth_km=10.0)
        radii_m8 = calculate_seismic_attenuation_radii(magnitude=8.0, depth_km=10.0)

        self.assertLess(radii_m5["mmi_vii_severe_km"], radii_m65["mmi_vii_severe_km"])
        self.assertLess(radii_m65["mmi_vii_severe_km"], radii_m8["mmi_vii_severe_km"])
        self.assertLess(radii_m5["mmi_iii_light_km"], radii_m8["mmi_iii_light_km"])

        # Test 3: Hypocentral focal depth dampening (shallow vs deep)
        shallow = calculate_seismic_attenuation_radii(magnitude=7.0, depth_km=10.0)
        deep = calculate_seismic_attenuation_radii(magnitude=7.0, depth_km=120.0)
        self.assertGreater(shallow["mmi_vii_severe_km"], deep["mmi_vii_severe_km"])

    def test_weather_impact_radii(self):
        """Verify weather hazard buffers expand with heavy rainfall and severe wind."""
        light_weather = calculate_weather_impact_radii(rainfall_mm=5.0, wind_speed_kmh=15.0)
        severe_weather = calculate_weather_impact_radii(rainfall_mm=85.0, wind_speed_kmh=75.0)

        self.assertLess(light_weather["severe_zone_km"], severe_weather["severe_zone_km"])
        self.assertLess(light_weather["moderate_zone_km"], severe_weather["moderate_zone_km"])
        self.assertLess(light_weather["light_zone_km"], severe_weather["light_zone_km"])

    @patch("intelligence.facility_provider.fetch_real_facilities", side_effect=_mock_facilities)
    def test_calculate_disaster_impact_provenance_and_metadata(self, mock_fetch):
        """Verify calculation output exposes honest provenance and transparent mathematical methods."""
        assessment = calculate_disaster_impact(
            latitude=19.076,
            longitude=72.878,
            disaster_type="earthquake",
            magnitude=6.4,
            depth_km=12.0,
            event_id="TEST-EQ-001",
        )

        self.assertEqual(assessment["classification"], "CALCULATED")
        self.assertEqual(assessment["confidence"], "APPROXIMATE_ANALYTICAL")
        self.assertIn("Joyner-Boore", assessment["methodology"])
        self.assertTrue(len(assessment["assumptions"]) >= 2)
        self.assertTrue(len(assessment["limitations"]) >= 1)
        self.assertEqual(assessment["event_id"], "TEST-EQ-001")
        self.assertGreaterEqual(len(assessment["impact_zones"]), 3)

        # Ensure zones have radius and level attributes
        z_critical = assessment["impact_zones"][0]
        self.assertEqual(z_critical["level"], "CRITICAL")
        self.assertIn("radius_km", z_critical)
        self.assertIn("radius_meters", z_critical)

        # Check facilities in impact zone
        exposed = assessment["facilities_in_impact_zone"]
        self.assertGreaterEqual(len(exposed), 1)
        self.assertEqual(exposed[0]["capacity_status"], "UNAVAILABLE")

    def test_impact_database_crud(self):
        """Verify persistence and retrieval of calculated impact assessments in SQLite."""
        sample_assessment = {
            "assessment_id": "IMPACT-TEST-9999",
            "event_id": "EVT-UNIT-TEST",
            "disaster_type": "earthquake",
            "epicenter_latitude": 28.6139,
            "epicenter_longitude": 77.2090,
            "magnitude": 6.8,
            "depth_km": 15.0,
            "max_radius_km": 120.5,
            "impact_zones": [
                {"zone_id": "ZONE-VII", "name": "Severe", "radius_km": 25.0, "color": "#ef4444"}
            ],
            "facilities_in_impact_zone": [
                {
                    "facility_id": "fac-osm-1",
                    "name": "Central District Hospital",
                    "facility_type": "hospital",
                    "distance_km": 8.4,
                    "impact_tier": "Severe",
                    "capacity": None,
                    "capacity_status": "UNAVAILABLE",
                }
            ],
            "summary": {"total_facilities_exposed": 1, "hospitals_count": 1},
            "route_accessibility_status": "DISRUPTED_SECONDARY_ROADS",
            "methodology": "Joyner-Boore Attenuation",
            "assumptions": ["Uniform crustal attenuation."],
            "limitations": ["Point source approximation."],
            "confidence": "APPROXIMATE_ANALYTICAL",
        }

        # Ensure clean state for test record
        conn = database.get_connection()
        conn.execute("DELETE FROM impact_assessments WHERE assessment_id = 'IMPACT-TEST-9999'")
        conn.commit()
        conn.close()

        # Save to DB
        database.save_impact_assessment(sample_assessment)

        # Retrieve by assessment_id
        retrieved = database.get_impact_assessment(assessment_id="IMPACT-TEST-9999")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["assessment_id"], "IMPACT-TEST-9999")
        self.assertEqual(retrieved["source_event_id"], "EVT-UNIT-TEST")
        self.assertEqual(retrieved["route_accessibility_status"], "DISRUPTED_SECONDARY_ROADS")
        self.assertIsInstance(retrieved["impact_zones"], list)
        self.assertEqual(len(retrieved["impact_zones"]), 1)
        self.assertIsInstance(retrieved["facilities"], list)
        self.assertEqual(len(retrieved["facilities"]), 1)
        self.assertEqual(retrieved["facilities"][0]["capacity_status"], "UNAVAILABLE")

        # Retrieve by event_id
        by_evt = database.get_impact_assessment(event_id="EVT-UNIT-TEST")
        self.assertIsNotNone(by_evt)
        self.assertEqual(by_evt["assessment_id"], "IMPACT-TEST-9999")

        # Retrieve list
        latest = database.get_latest_impact_assessments(limit=10)
        self.assertIsInstance(latest, list)
        self.assertTrue(any(a["assessment_id"] == "IMPACT-TEST-9999" for a in latest))

    @patch("intelligence.facility_provider.fetch_real_facilities", side_effect=_mock_facilities)
    def test_impact_api_endpoints(self, mock_fetch):
        """Verify REST API endpoints for impact assessment."""
        # 1. Successful POST /api/impact/assess
        resp = self.client.post(
            "/api/impact/assess",
            json={
                "latitude": 13.0827,
                "longitude": 80.2707,
                "disaster_type": "cyclone",
                "rainfall_mm": 65.0,
                "wind_speed_kmh": 80.0,
                "event_id": "CYCLONE-CHN-01",
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("assessment", data)
        assessment_id = data["assessment"]["assessment_id"]
        self.assertTrue(assessment_id.startswith("IMPACT-"))
        self.assertEqual(data["assessment"]["classification"], "CALCULATED")

        # 2. Validation error on invalid coordinates
        bad_resp = self.client.post(
            "/api/impact/assess",
            json={"latitude": 120.0, "longitude": 80.0, "disaster_type": "earthquake"},
        )
        self.assertEqual(bad_resp.status_code, 400)

        # 3. List recent assessments
        list_resp = self.client.get("/api/impact/assessments")
        self.assertEqual(list_resp.status_code, 200)
        list_data = list_resp.json()
        self.assertEqual(list_data["status"], "success")
        self.assertIsInstance(list_data["assessments"], list)

        # 4. Get specific assessment
        single_resp = self.client.get(f"/api/impact/{assessment_id}")
        self.assertEqual(single_resp.status_code, 200)
        self.assertEqual(single_resp.json()["assessment"]["assessment_id"], assessment_id)

        # 5. Non-existent assessment returns 404
        not_found_resp = self.client.get("/api/impact/IMPACT-DOES-NOT-EXIST-404")
        self.assertEqual(not_found_resp.status_code, 404)

    def test_tactical_decision_impact_integration(self):
        """Verify tactical decision engine incorporates impact assessment modeling and warnings."""
        incident = {
            "incident_id": 999,
            "disaster_type": "earthquake",
            "severity": "high",
            "people_affected": 250,
            "latitude": 19.076,
            "longitude": 72.878,
            "location": "Central Mumbai Epicenter",
        }

        mock_impact = {
            "assessment_id": "IMPACT-TACTICAL-TEST",
            "disaster_type": "earthquake",
            "methodology": "Joyner-Boore Empirical Attenuation",
            "confidence": "APPROXIMATE_ANALYTICAL",
            "route_accessibility_status": "DISRUPTED_SECONDARY_ROADS",
            "facilities_in_impact_zone": [
                {
                    "facility_id": "fac-crit-1",
                    "name": "St. George Trauma Hospital",
                    "facility_type": "hospital",
                    "distance_km": 3.2,
                    "impact_tier": "Severe Shaking (MMI VII+)",
                    "capacity": None,
                    "capacity_status": "UNAVAILABLE",
                }
            ],
        }

        decision = evaluate_tactical_decision(
            incident=incident,
            facilities=[{
                "facility_name": "St. George Trauma Hospital",
                "facility_type": "hospital",
                "latitude": 19.080,
                "longitude": 72.880,
                "available_capacity": 40,
                "total_capacity": 100,
            }],
            impact_assessment=mock_impact,
        )

        # Verify impact assessment attached
        self.assertIsNotNone(decision.get("impact_assessment"))
        self.assertEqual(decision["impact_assessment"]["assessment_id"], "IMPACT-TACTICAL-TEST")

        # Verify evidence includes physical attenuation modeling note
        evidence_str = " ".join(decision["reasoning_and_evidence"])
        self.assertIn("Joyner-Boore", evidence_str)
        self.assertIn("exposed infrastructure facilities", evidence_str)

        # Verify route considerations flagged secondary arterial disruption
        route_str = " ".join(decision["route_considerations"])
        self.assertIn("Secondary arterial network disrupted", route_str)

        # Verify operational risks flagged structural risk for critical hospital in MMI VII+ zone
        risks_str = " ".join(decision["operational_risks"])
        self.assertIn("St. George Trauma Hospital", risks_str)


if __name__ == "__main__":
    unittest.main()
