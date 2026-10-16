import io
import json
import sys
import unittest
from fastapi.testclient import TestClient

sys.path.insert(0, r"d:\Disaster_OS_Phase2\multi_agent_disaster_management\Multi-Agent-System")

from app import app
from database import (
    init_db,
    get_connection,
    save_incident_timeline_entry,
    get_incident_timeline,
    update_incident_status,
    get_incident_analytics,
    get_resource_analytics,
    get_intelligence_analytics,
    get_data_quality_metrics,
    create_run,
)
from utils.report_generator import (
    generate_csv_report,
    generate_json_report,
    generate_pdf_report,
    get_run_details,
)
from utils.tactical_decision import evaluate_tactical_decision, haversine_km


class TestP23AnalyticsAndReports(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)
        # Obtain auth token
        res = cls.client.post(
            "/api/auth/login",
            json={"email": "operator@disaster.local", "password": "operator123"},
        )
        assert res.status_code == 200
        cls.token = res.json()["token"]
        cls.auth_headers = {"Authorization": f"Bearer {cls.token}"}

    def test_haversine_distance_calculation(self):
        # Mumbai (19.076, 72.878) to Pune (18.5204, 73.8567) is approx 118-125 km
        dist = haversine_km(19.076, 72.878, 18.5204, 73.8567)
        self.assertTrue(110.0 < dist < 135.0, f"Expected approx 120km, got {dist}")

    def test_incident_timeline_lifecycle(self):
        run_id = "test_run_p2_3"
        create_run(run_id, seed=42, strategy="smart")
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO incidents (run_id, location, latitude, longitude, severity, people_affected, disaster_type, status)
            VALUES ('test_run_p2_3', 'Colaba Coast', 18.9067, 72.8147, 'high', 45, 'flood', 'NEW')
            """
        )
        inc_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # 1. Update status to ASSESSED with reason
        res1 = self.client.put(
            f"/api/incidents/{inc_id}/status",
            headers=self.auth_headers,
            json={"status": "ASSESSED", "reason": "Initial drone reconnaissance verified flooding"},
        )
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertEqual(data1["incident"]["status"], "ASSESSED")

        # 2. Update status to RESPONDING
        res2 = self.client.put(
            f"/api/incidents/{inc_id}/status",
            headers=self.auth_headers,
            json={"status": "RESPONDING", "reason": "Ambulance and rescue boats dispatched"},
        )
        self.assertEqual(res2.status_code, 200)

        # 3. Retrieve timeline via API
        timeline_res = self.client.get(
            f"/api/incidents/{inc_id}/timeline",
            headers=self.auth_headers,
        )
        self.assertEqual(timeline_res.status_code, 200)
        tl_data = timeline_res.json()
        self.assertEqual(tl_data["status"], "success")
        self.assertTrue(len(tl_data["timeline"]) >= 2)

        # Verify timeline structure
        first_entry = tl_data["timeline"][0]
        self.assertEqual(first_entry["previous_status"], "NEW")
        self.assertEqual(first_entry["new_status"], "ASSESSED")
        self.assertIn("drone", first_entry["reason"])

    def test_invalid_status_transition_rejected(self):
        res = self.client.put(
            "/api/incidents/1/status",
            headers=self.auth_headers,
            json={"status": "INVALID_RANDOM_STATE"},
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("Invalid status", res.json()["message"])

    def test_analytics_overview_endpoint(self):
        res = self.client.get("/api/analytics/overview", headers=self.auth_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("incidents", data)
        self.assertIn("resources", data)
        self.assertIn("intelligence", data)
        self.assertIn("performance", data)

    def test_analytics_incidents_endpoint(self):
        res = self.client.get("/api/analytics/incidents", headers=self.auth_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()["analytics"]
        self.assertIn("total_incidents", data)
        self.assertIn("severity_breakdown", data)
        self.assertIn("status_breakdown", data)
        self.assertIn("time_series", data)

    def test_analytics_resources_endpoint(self):
        res = self.client.get("/api/analytics/resources", headers=self.auth_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()["analytics"]
        self.assertIn("fleet_utilization_pct", data)
        self.assertIn("hospitals", data)
        self.assertIn("shelters", data)

    def test_analytics_intelligence_endpoint(self):
        res = self.client.get("/api/analytics/intelligence", headers=self.auth_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()["analytics"]
        self.assertIn("total_external_events", data)
        self.assertIn("earthquake_magnitude_distribution", data)

    def test_data_quality_metrics_endpoint(self):
        res = self.client.get("/api/analytics/quality", headers=self.auth_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()["metrics"]
        self.assertEqual(data["db_integrity"], "ok")
        self.assertIn("coordinate_completeness_pct", data)
        self.assertIn("record_counts", data)

    def test_csv_report_generation_content(self):
        # Create a test run with incidents and resources
        run_id = "test_csv_run_101"
        create_run(run_id, seed=123, strategy="smart")
        conn = get_connection()
        conn.execute(
            "INSERT INTO incidents (run_id, location, latitude, longitude, severity, people_affected, disaster_type, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (run_id, "Marine Drive", 18.9438, 72.8233, "high", 50, "flood", "RESPONDING"),
        )
        conn.execute(
            "INSERT INTO simulation_resources (run_id, resource_id, resource_name, resource_type, latitude, longitude, status, capacity) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (run_id, "amb-01", "Ambulance Alpha", "ambulance", 18.94, 72.82, "dispatched", 4),
        )
        conn.commit()
        conn.close()

        csv_content = generate_csv_report(run_id)
        self.assertIn("DISASTER OS — EMERGENCY OPERATIONS CENTER AUDIT REPORT", csv_content)
        self.assertIn("Marine Drive", csv_content)
        self.assertIn("Ambulance Alpha", csv_content)
        self.assertIn("RESPONDING", csv_content)

    def test_json_report_generation_structure(self):
        run_id = "test_csv_run_101"
        json_content = generate_json_report(run_id)
        parsed = json.loads(json_content)
        self.assertEqual(parsed["status"], "success")
        self.assertEqual(parsed["run"]["run_id"], run_id)
        self.assertTrue(len(parsed["run"]["incidents"]) >= 1)

    def test_pdf_report_generation_bytes(self):
        run_id = "test_csv_run_101"
        buffer = io.BytesIO()
        generate_pdf_report(run_id, buffer)
        pdf_bytes = buffer.getvalue()
        self.assertTrue(len(pdf_bytes) > 500, f"PDF bytes should be non-empty, got {len(pdf_bytes)} bytes")
        self.assertTrue(pdf_bytes.startswith(b"%PDF"), "PDF must start with %PDF header")

    def test_export_endpoint_with_bearer_token(self):
        run_id = "test_csv_run_101"
        res = self.client.get(f"/api/run/{run_id}/export/csv", headers=self.auth_headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers["content-type"], "text/csv; charset=utf-8")
        self.assertIn("attachment; filename=", res.headers["content-disposition"])

    def test_export_endpoint_with_query_token_strictly_rejected(self):
        run_id = "test_csv_run_101"
        unauth_client = TestClient(app)
        # Attempting query-string authentication must be rejected with 401
        res = unauth_client.get(f"/api/run/{run_id}/export/pdf?token={self.token}")
        self.assertEqual(res.status_code, 401, "Query string authentication must NOT be supported.")

    def test_export_endpoint_unauthenticated_rejected(self):
        run_id = "test_csv_run_101"
        unauth_client = TestClient(app)
        res = unauth_client.get(f"/api/run/{run_id}/export/pdf")
        self.assertEqual(res.status_code, 401)

    def test_export_endpoints_invalid_run_returns_404(self):
        invalid_run_id = "non_existent_run_99999"
        res_csv = self.client.get(f"/api/run/{invalid_run_id}/export/csv", headers=self.auth_headers)
        self.assertEqual(res_csv.status_code, 404)
        
        res_json = self.client.get(f"/api/run/{invalid_run_id}/export/json", headers=self.auth_headers)
        self.assertEqual(res_json.status_code, 404)
        
        res_pdf = self.client.get(f"/api/run/{invalid_run_id}/export/pdf", headers=self.auth_headers)
        self.assertEqual(res_pdf.status_code, 404)

    def test_tactical_decision_support_engine(self):
        incident = {
            "latitude": 19.076,
            "longitude": 72.878,
            "severity": "high",
            "disaster_type": "flood",
            "people_affected": 80,
        }
        facilities = [
            {"facility_name": "Lilavati Hospital", "facility_type": "hospital", "latitude": 19.05, "longitude": 72.83, "total_capacity": 200, "available_capacity": 50},
            {"facility_name": "Bandra Relief Shelter", "facility_type": "shelter", "latitude": 19.06, "longitude": 72.84, "total_capacity": 500, "available_capacity": 150},
        ]
        fleet = [
            {"resource_type": "ambulance", "status": "available"},
            {"resource_type": "ambulance", "status": "available"},
            {"resource_type": "rescue_boat", "status": "available"},
            {"resource_type": "drone", "status": "available"},
        ]
        weather = {"rainfall_mm": 35.0, "temperature": 28.0}
        earthquakes = [{"magnitude": 5.2, "place": "West Coast", "latitude": 19.2, "longitude": 72.9}]

        eval_result = evaluate_tactical_decision(
            incident=incident,
            facilities=facilities,
            fleet=fleet,
            weather=weather,
            earthquakes=earthquakes,
        )

        self.assertEqual(eval_result["classification"], "CALCULATED DECISION SUPPORT")
        self.assertIn("PRIORITY 1", eval_result["priority_level"])
        self.assertTrue(len(eval_result["recommended_resources"]) >= 2)
        self.assertIn("Lilavati Hospital", eval_result["suggested_hospital"])
        self.assertIn("Bandra Relief Shelter", eval_result["suggested_shelter"])
        self.assertTrue(len(eval_result["reasoning_and_evidence"]) >= 3)
        self.assertTrue(eval_result["confidence_score"] >= 0.50)

    def test_tactical_decision_missing_coordinates_insufficient_evidence(self):
        incident = {
            "latitude": None,
            "longitude": None,
            "severity": "high",
            "disaster_type": "flood",
            "people_affected": 80,
        }
        eval_result = evaluate_tactical_decision(incident=incident)
        self.assertEqual(eval_result["priority_level"], "INSUFFICIENT EVIDENCE")
        self.assertEqual(eval_result["confidence_score"], 0.0)


if __name__ == "__main__":
    unittest.main()
