import sys
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

sys.path.insert(0, r"d:\Disaster_OS_Phase2\multi_agent_disaster_management\Multi-Agent-System")

from app import app
from database import init_db, get_connection


class TestCitizenReportSecurity(unittest.TestCase):
    def setUp(self):
        init_db()
        self._cleanup()

    def tearDown(self):
        self._cleanup()

    def _cleanup(self):
        conn = get_connection()
        conn.execute("DELETE FROM citizen_reports WHERE location LIKE 'TEST_%'")
        conn.commit()
        conn.close()

    def get_client(self):
        return TestClient(app)

    @patch("orchestrator.Orchestrator.run")
    def test_valid_citizen_report_submission_and_persistence(self, mock_orch_run):
        """Valid citizen report is accepted, persisted with pending_review status, and does NOT run simulation."""
        client = self.get_client()
        payload = {
            "location": "TEST_Marine Drive Junction",
            "latitude": 18.944,
            "longitude": 72.823,
            "disaster_type": "flood",
            "people_affected": 5,
            "severity": "high",
            "sos_type": "SOS",
            "media_url": "https://emergency.local/photos/flood_01.jpg",
            "description": "Rising seawater breaching promenade seawall.",
        }

        res = client.post("/api/incidents/citizen-report", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("report_id", data)
        report_id = data["report_id"]

        # Verify Orchestrator.run() was NEVER launched
        mock_orch_run.assert_not_called()

        # Verify record was persisted in database with status pending_review
        conn = get_connection()
        row = conn.execute("SELECT * FROM citizen_reports WHERE id = ?", (report_id,)).fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row["location"], "TEST_Marine Drive Junction")
        self.assertEqual(row["latitude"], 18.944)
        self.assertEqual(row["longitude"], 72.823)
        self.assertEqual(row["disaster_type"], "flood")
        self.assertEqual(row["people_affected"], 5)
        self.assertEqual(row["severity"], "high")
        self.assertEqual(row["sos_type"], "SOS")
        self.assertEqual(row["media_url"], "https://emergency.local/photos/flood_01.jpg")
        self.assertEqual(row["description"], "Rising seawater breaching promenade seawall.")
        self.assertEqual(row["status"], "pending_review")

    @patch("orchestrator.Orchestrator.run")
    def test_minimal_valid_citizen_report(self, mock_orch_run):
        """Valid citizen report with empty/omitted optional fields succeeds without running Orchestrator."""
        client = self.get_client()
        payload = {
            "location": "TEST_Andheri East Subway",
            "latitude": 19.115,
            "longitude": 72.856,
            "disaster_type": "waterlogging",
        }

        res = client.post("/api/incidents/citizen-report", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        report_id = data["report_id"]

        mock_orch_run.assert_not_called()

        conn = get_connection()
        row = conn.execute("SELECT * FROM citizen_reports WHERE id = ?", (report_id,)).fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row["media_url"], "")
        self.assertEqual(row["description"], "")
        self.assertEqual(row["status"], "pending_review")

    @patch("orchestrator.Orchestrator.run")
    def test_invalid_inputs_rejected(self, mock_orch_run):
        """Invalid fields are rejected by validation without triggering database inserts or simulations."""
        client = self.get_client()

        invalid_cases = [
            ("empty_location", {"location": "   ", "latitude": 19.0, "longitude": 72.0, "disaster_type": "fire"}),
            ("invalid_lat_high", {"location": "TEST_Loc", "latitude": 95.0, "longitude": 72.0, "disaster_type": "fire"}),
            ("invalid_lat_low", {"location": "TEST_Loc", "latitude": -95.0, "longitude": 72.0, "disaster_type": "fire"}),
            ("invalid_lng_high", {"location": "TEST_Loc", "latitude": 19.0, "longitude": 185.0, "disaster_type": "fire"}),
            ("invalid_lng_low", {"location": "TEST_Loc", "latitude": 19.0, "longitude": -185.0, "disaster_type": "fire"}),
            ("zero_people_affected", {"location": "TEST_Loc", "latitude": 19.0, "longitude": 72.0, "disaster_type": "fire", "people_affected": 0}),
            ("negative_people_affected", {"location": "TEST_Loc", "latitude": 19.0, "longitude": 72.0, "disaster_type": "fire", "people_affected": -3}),
            ("empty_disaster_type", {"location": "TEST_Loc", "latitude": 19.0, "longitude": 72.0, "disaster_type": ""}),
            ("javascript_media_url", {"location": "TEST_Loc", "latitude": 19.0, "longitude": 72.0, "disaster_type": "fire", "media_url": "javascript:alert(1)"}),
            ("ftp_media_url", {"location": "TEST_Loc", "latitude": 19.0, "longitude": 72.0, "disaster_type": "fire", "media_url": "ftp://files.com/exploit.sh"}),
            ("excessive_media_url", {"location": "TEST_Loc", "latitude": 19.0, "longitude": 72.0, "disaster_type": "fire", "media_url": "https://example.com/" + "a" * 501}),
            ("null_byte_description", {"location": "TEST_Loc", "latitude": 19.0, "longitude": 72.0, "disaster_type": "fire", "description": "malicious\x00data"}),
            ("excessive_description", {"location": "TEST_Loc", "latitude": 19.0, "longitude": 72.0, "disaster_type": "fire", "description": "a" * 2001}),
        ]

        for case_name, payload in invalid_cases:
            with self.subTest(case=case_name):
                res = client.post("/api/incidents/citizen-report", json=payload)
                self.assertIn(res.status_code, (400, 422), f"Case {case_name} should return 400 or 422")
                mock_orch_run.assert_not_called()

    def test_authorized_simulation_workflow_preserved(self):
        """Authorized operator can still launch simulations via POST /api/run."""
        client = self.get_client()
        login_res = client.post("/api/auth/login", json={"email": "operator@disaster.local", "password": "operator123"})
        self.assertEqual(login_res.status_code, 200)
        token = login_res.json()["token"]

        with patch("orchestrator.Orchestrator.run") as mock_orch_run:
            res = client.post(
                "/api/run",
                json={"seed": 99, "strategy": "smart"},
                headers={"Authorization": f"Bearer {token}"},
            )
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["message"], "Simulation run started")
            self.assertIn("run_id", data)
            mock_orch_run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
