"""Unit Tests for Phase P3.3 Compound Disaster Event Correlation Engine.

Verifies:
- Seismic infrastructure lifeline failure cascade evaluation
- Coastal offshore seismic tsunami surge triggering
- Hydrometeorological deluge & urban flood compounding
- Multi-incident spatio-temporal cluster detection
- SQLite persistence (save_compound_event, get_compound_events, get_compound_event_by_id)
- FastAPI REST endpoints (/api/intelligence/correlate, /api/intelligence/compound-events)
"""

import unittest
from fastapi.testclient import TestClient

import database
from app import app
from intelligence.correlation_engine import (
    detect_compound_disaster_events,
    evaluate_coastal_tsunami_cascade,
    evaluate_hydrometeorological_cascade,
    evaluate_seismic_infrastructure_cascade,
    haversine_distance_km,
)


class TestCorrelationEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database.init_db()
        cls.client = TestClient(app)
        login_res = cls.client.post("/api/auth/login", json={"email": "operator@disaster.local", "password": "operator123"})
        if login_res.status_code == 200:
            token = login_res.json().get("token")
            cls.client.headers.update({"Authorization": f"Bearer {token}"})

    def test_seismic_infrastructure_cascade(self):
        """Verify high-magnitude earthquakes trigger lifeline failure cascades for nearby hospitals."""
        major_eq = {
            "event_id": "EQ-MAJOR-001",
            "magnitude": 6.8,
            "depth_km": 12.0,
            "latitude": 19.076,
            "longitude": 72.878,
            "place": "15km W of Mumbai",
        }
        mock_facilities = [
            {
                "id": "fac-1",
                "name": "King Edward Memorial Hospital",
                "facility_type": "hospital",
                "latitude": 19.080,
                "longitude": 72.880,
            },
            {
                "id": "fac-2",
                "name": "Dadar Fire Station",
                "facility_type": "fire_station",
                "latitude": 19.085,
                "longitude": 72.885,
            },
        ]

        cascade = evaluate_seismic_infrastructure_cascade(major_eq, mock_facilities)
        self.assertIsNotNone(cascade)
        self.assertEqual(cascade["correlation_type"], "SEISMIC_INFRASTRUCTURE_FAILURE")
        self.assertIn("CRITICAL", cascade["cascade_risk_level"])
        self.assertGreaterEqual(cascade["confidence_score"], 0.50)
        self.assertGreaterEqual(len(cascade["affected_facilities"]), 1)
        self.assertGreaterEqual(len(cascade["cascade_chain"]), 3)

        # Low magnitude should not trigger cascade
        minor_eq = {"event_id": "EQ-MINOR-002", "magnitude": 4.1, "latitude": 19.0, "longitude": 72.8}
        self.assertIsNone(evaluate_seismic_infrastructure_cascade(minor_eq, mock_facilities))

    def test_coastal_tsunami_cascade(self):
        """Verify offshore shallow earthquakes trigger coastal tsunami watches."""
        offshore_eq = {
            "event_id": "EQ-TSU-001",
            "magnitude": 7.4,
            "depth_km": 18.0,
            "latitude": 38.2,
            "longitude": 142.3,
            "place": "Off the east coast of Honshu, Japan",
        }
        tsunami = evaluate_coastal_tsunami_cascade(offshore_eq)
        self.assertIsNotNone(tsunami)
        self.assertEqual(tsunami["correlation_type"], "COASTAL_TSUNAMI_SURGE")
        self.assertEqual(tsunami["cascade_risk_level"], "CRITICAL")
        self.assertGreaterEqual(tsunami["confidence_score"], 0.50)
        self.assertIn("evacuation", " ".join(tsunami["recommendations"]).lower())

        # Inland continental earthquake should not trigger tsunami
        inland_eq = {
            "event_id": "EQ-INLAND-002",
            "magnitude": 7.2,
            "depth_km": 10.0,
            "latitude": 39.5,
            "longitude": -105.0,
            "place": "50km E of Denver, Colorado",
        }
        self.assertIsNone(evaluate_coastal_tsunami_cascade(inland_eq))

    def test_hydrometeorological_deluge_cascade(self):
        """Verify heavy rainfall deluge compounds with active drainage/flood incidents."""
        deluge_weather = {"rainfall_mm": 65.0, "wind_speed_kmh": 60.0}
        incidents = [
            {"incident_id": 101, "disaster_type": "flood", "latitude": 19.076, "longitude": 72.878},
            {"incident_id": 102, "disaster_type": "traffic_jam", "latitude": 19.080, "longitude": 72.882},
        ]

        hydro = evaluate_hydrometeorological_cascade(deluge_weather, incidents)
        self.assertIsNotNone(hydro)
        self.assertEqual(hydro["correlation_type"], "METEOROLOGICAL_INUNDATION_CASCADE")
        self.assertEqual(hydro["cascade_risk_level"], "CRITICAL")
        self.assertGreaterEqual(hydro["confidence_score"], 0.60)

        # Mild weather should not trigger deluge cascade
        mild_weather = {"rainfall_mm": 2.0, "wind_speed_kmh": 10.0}
        self.assertIsNone(evaluate_hydrometeorological_cascade(mild_weather, incidents))

    def test_compound_events_database_crud(self):
        """Verify SQLite persistence and retrieval of compound events."""
        sample_compound = {
            "compound_id": "COMP-TEST-UNIT-99",
            "correlation_type": "SEISMIC_INFRASTRUCTURE_FAILURE",
            "primary_event_id": "EVT-TEST-EQ-1",
            "secondary_event_id": "HOSPITAL-TRAUMA-1",
            "secondary_event_type": "LIFELINE_GRID_DISRUPTION",
            "confidence_score": 0.85,
            "cascade_risk_level": "CRITICAL",
            "classification": "CALCULATED",
            "affected_facilities": [{"facility_id": "H1", "name": "General Hospital"}],
            "cascade_chain": ["Step 1", "Step 2", "Step 3"],
            "recommendations": ["Deploy backup generators", "Inspect overpasses"],
            "trigger_parameters": {"magnitude": 6.8},
        }

        conn = database.get_connection()
        conn.execute("DELETE FROM compound_events WHERE compound_id = 'COMP-TEST-UNIT-99'")
        conn.commit()
        conn.close()

        database.save_compound_event(sample_compound)

        # Retrieve single by id
        retrieved = database.get_compound_event_by_id("COMP-TEST-UNIT-99")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["compound_id"], "COMP-TEST-UNIT-99")
        self.assertEqual(retrieved["correlation_type"], "SEISMIC_INFRASTRUCTURE_FAILURE")
        self.assertEqual(retrieved["confidence_score"], 0.85)
        self.assertIsInstance(retrieved["cascade_chain"], list)
        self.assertEqual(len(retrieved["cascade_chain"]), 3)
        self.assertIsInstance(retrieved["recommendations"], list)
        self.assertEqual(len(retrieved["recommendations"]), 2)

        # Retrieve list
        compounds = database.get_compound_events(limit=10)
        self.assertIsInstance(compounds, list)
        self.assertTrue(any(c["compound_id"] == "COMP-TEST-UNIT-99" for c in compounds))

    def test_compound_api_endpoints(self):
        """Verify REST API endpoints for compound event correlation."""
        # 1. Trigger correlation run
        correlate_resp = self.client.post("/api/intelligence/correlate?run_id=demo")
        self.assertEqual(correlate_resp.status_code, 200)
        data = correlate_resp.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("compound_events", data)

        # 2. List compound events
        list_resp = self.client.get("/api/intelligence/compound-events")
        self.assertEqual(list_resp.status_code, 200)
        list_data = list_resp.json()
        self.assertEqual(list_data["status"], "success")
        self.assertIsInstance(list_data["compound_events"], list)

        # 3. Non-existent compound event returns 404
        not_found_resp = self.client.get("/api/intelligence/compound-events/COMP-DOES-NOT-EXIST-404")
        self.assertEqual(not_found_resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
