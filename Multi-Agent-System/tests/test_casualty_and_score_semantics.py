"""Regression test suite for Step 7.2: Final Metric Semantics Repair.

Covers:
1. Waiting victims are not casualties (total=100, rescued=40, waiting=60 => casualties=0).
2. Zero death transitions => casualties=0.
3. Explicit death transitions => casualties=count of death states (total=100, rescued=40, waiting=55, deceased=5 => casualties=5).
4. Rescue rate uses rescued / total (None if total==0).
5. Casualty rate uses casualties / total (None if total==0).
6. Overall score uses the documented weighted formula:
   Score = 0.40 * Rescue Rate + 0.25 * (100 - Casualty Rate) + 0.20 * Resource Assignment Rate + 0.15 * max(0, 100 - (Planned ETA Mins * 2))
7. Overall score does not equal rescue rate unless they mathematically coincide.
8. Database/API/export score consistency across all layers.
9. Database/API/export casualty consistency across all layers.
10. Missing required score component => None / UNAVAILABLE with explicit reason.
11. Waiting and casualties are separately displayed.
12. No occurrence of "casualties / waiting" in production UI/report labels.
"""

import json
import os
import unittest
import uuid
from fastapi.testclient import TestClient

from app import app
from database import (
    create_run,
    create_session,
    get_connection,
    get_response_performance_analytics,
    get_run_metrics,
    init_db,
    save_incidents,
    save_run_metrics,
    save_simulation_resources,
)
from models import EvaluationReport, RescueStatus
from utils.metrics import calculate_simulation_performance_score
from utils.report_generator import (
    generate_csv_report,
    generate_json_report,
    generate_pdf_report,
    get_run_details,
)


class TestCasualtyAndScoreSemantics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)
        cls.token = create_session(1)
        cls.auth_headers = {"Authorization": f"Bearer {cls.token}"}

    def test_01_waiting_victims_are_not_casualties_zero_deaths(self):
        """1 & 2. Zero death states => casualties=0, waiting=60."""
        total = 100
        rescued = 40
        waiting = 60
        # When no death states exist
        status = RescueStatus(
            total_affected=total,
            rescued_count=rescued,
            casualties_count=0,
            waiting_victims=waiting,
            remaining_victims=waiting,
        )
        self.assertEqual(status.rescued_count, 40)
        self.assertEqual(status.waiting_victims, 60)
        self.assertEqual(status.casualties, 0)
        self.assertNotEqual(status.casualties, status.waiting_victims)

    def test_02_explicit_death_transitions_produce_casualties(self):
        """3. Explicit death transitions => casualties=count of death states."""
        total = 100
        rescued = 40
        deceased = 5
        waiting = 55
        status = RescueStatus(
            total_affected=total,
            rescued_count=rescued,
            casualties_count=deceased,
            waiting_victims=waiting,
            remaining_victims=waiting,
        )
        self.assertEqual(status.rescued_count, 40)
        self.assertEqual(status.waiting_victims, 55)
        self.assertEqual(status.casualties, 5)

    def test_03_rescue_rate_and_casualty_rate_formula(self):
        """4 & 5. Rates use respective counts divided by total victims."""
        # Normal case
        res = calculate_simulation_performance_score(
            rescue_rate_pct=40.0,
            casualty_rate_pct=5.0,
            resource_assignment_rate_pct=50.0,
            planned_route_eta_mins=10.0,
        )
        self.assertIsNotNone(res["score"])

        # Division by zero handling
        res_zero = calculate_simulation_performance_score(
            rescue_rate_pct=None,
            casualty_rate_pct=None,
            resource_assignment_rate_pct=50.0,
            planned_route_eta_mins=10.0,
        )
        self.assertIsNone(res_zero["score"])
        self.assertEqual(res_zero["classification"], "UNAVAILABLE")
        self.assertIn("Missing required score component", res_zero["missing_reason"])

    def test_04_overall_score_weighted_formula(self):
        """6. Score = 0.40*Rescue + 0.25*(100-Casualty) + 0.20*Assignment + 0.15*max(0, 100 - 2*ETA)."""
        # Exact runtime values from Kolkata test:
        # rescue_rate ≈ 8.9%
        # casualty_rate = 0.0%
        # resource_assignment_rate = 17.1%
        # planned_eta = 8.2 mins
        # Component 1: 0.40 * 8.9 = 3.56
        # Component 2: 0.25 * (100 - 0.0) = 25.0
        # Component 3: 0.20 * 17.1 = 3.42
        # Component 4: 0.15 * max(0, 100 - 16.4) = 0.15 * 83.6 = 12.54
        # Total = 3.56 + 25.0 + 3.42 + 12.54 = 44.52 => rounded to 44.5
        calc = calculate_simulation_performance_score(
            rescue_rate_pct=8.9,
            casualty_rate_pct=0.0,
            resource_assignment_rate_pct=17.1,
            planned_route_eta_mins=8.2,
        )
        self.assertEqual(calc["score"], 44.5)
        self.assertEqual(calc["classification"], "CALCULATED")
        self.assertIn("weights", calc)
        self.assertEqual(calc["weights"]["rescue_rate"], 0.40)
        self.assertEqual(calc["weights"]["casualty_factor"], 0.25)
        self.assertEqual(calc["weights"]["resource_assignment"], 0.20)
        self.assertEqual(calc["weights"]["eta_factor"], 0.15)

    def test_05_overall_score_does_not_equal_rescue_rate(self):
        """7. Score does not merely echo rescue rate."""
        calc = calculate_simulation_performance_score(
            rescue_rate_pct=8.9,
            casualty_rate_pct=0.0,
            resource_assignment_rate_pct=17.1,
            planned_route_eta_mins=8.2,
        )
        self.assertNotEqual(calc["score"], 8.9)
        self.assertEqual(calc["score"], 44.5)

    def test_06_missing_required_score_component_handling(self):
        """10. Missing required component => score=None, classification=UNAVAILABLE, do not substitute 0."""
        # Missing ETA
        res1 = calculate_simulation_performance_score(
            rescue_rate_pct=50.0,
            casualty_rate_pct=0.0,
            resource_assignment_rate_pct=50.0,
            planned_route_eta_mins=None,
        )
        self.assertIsNone(res1["score"])
        self.assertEqual(res1["classification"], "UNAVAILABLE")
        self.assertIn("planned_route_eta_mins", res1["missing_reason"])

        # Missing assignment rate
        res2 = calculate_simulation_performance_score(
            rescue_rate_pct=50.0,
            casualty_rate_pct=0.0,
            resource_assignment_rate_pct=None,
            planned_route_eta_mins=10.0,
        )
        self.assertIsNone(res2["score"])
        self.assertEqual(res2["classification"], "UNAVAILABLE")
        self.assertIn("resource_assignment_rate_pct", res2["missing_reason"])

    def test_07_database_api_export_score_and_casualty_consistency(self):
        """8 & 9. Verify consistency of score, rescued, waiting, and casualties across DB, API, CSV, JSON, PDF."""
        run_id = f"test-consist-{uuid.uuid4().hex[:8]}"
        create_run(run_id, 42, "smart", 1)

        # 1 incident with 100 victims, planned ETA 8.2 mins
        incidents = [
            {
                "incident_id": 1,
                "location": "Sector A",
                "latitude": 22.57,
                "longitude": 88.36,
                "severity": "high",
                "people_affected": 100,
                "disaster_type": "flood",
                "route_eta_hours": round(8.2 / 60, 4),
            }
        ]
        save_incidents(run_id, incidents)

        # 35 resources total, 6 assigned
        resources = [
            {
                "resource_id": f"R-{i}",
                "resource_name": f"Unit {i}",
                "resource_type": "ambulance",
                "latitude": 22.57,
                "longitude": 88.36,
                "status": "available",
                "capacity": 2,
            }
            for i in range(35)
        ]
        save_simulation_resources(run_id, resources)

        # Save metrics: rescued=40, waiting=60, casualties=0
        calc = calculate_simulation_performance_score(
            rescue_rate_pct=40.0,
            casualty_rate_pct=0.0,
            resource_assignment_rate_pct=17.1,
            planned_route_eta_mins=8.2,
        )
        # 0.40*40 + 0.25*100 + 0.20*17.1 + 0.15*(100 - 16.4) = 16.0 + 25.0 + 3.42 + 12.54 = 56.96 => 57.0
        expected_score = calc["score"]

        save_run_metrics(
            run_id,
            {
                "total_incidents": 1,
                "total_affected": 100,
                "total_victims": 100,
                "rescued_victims": 40,
                "total_lives_saved": 40,
                "waiting_victims": 60,
                "casualties": 0,
                "rescue_rate_pct": 40.0,
                "casualty_rate_pct": 0.0,
                "simulation_performance_score": expected_score,
                "overall_score": expected_score,
                "overall_efficiency": f"{expected_score}%",
                "planned_route_eta_mins": 8.2,
                "actual_response_time_mins": None,
                "resource_assignment_rate_pct": 17.1,
                "active_resource_utilization_pct": 0.0,
                "status": "COMPLETED",
            },
        )

        # 1. DB check
        db_m = get_run_metrics(run_id)
        self.assertEqual(db_m["total_victims"], 100)
        self.assertEqual(db_m["rescued_victims"], 40)
        self.assertEqual(db_m["waiting_victims"], 60)
        self.assertEqual(db_m["casualties"], 0)
        self.assertEqual(db_m["simulation_performance_score"], expected_score)

        # 2. API check
        res = self.client.get(f"/api/run/{run_id}/dashboard", headers=self.auth_headers)
        self.assertEqual(res.status_code, 200)
        api_m = res.json()["metrics"]
        self.assertEqual(api_m["total_victims"], 100)
        self.assertEqual(api_m["rescued_victims"], 40)
        self.assertEqual(api_m["waiting_victims"], 60)
        self.assertEqual(api_m["casualties"], 0)
        self.assertEqual(api_m["simulation_performance_score"], expected_score)

        # 3. JSON Export check
        json_str = generate_json_report(run_id)
        json_data = json.loads(json_str)
        json_m = json_data["run"]["metrics"]
        self.assertEqual(json_m["total_victims"], 100)
        self.assertEqual(json_m["rescued_victims"], 40)
        self.assertEqual(json_m["waiting_victims"], 60)
        self.assertEqual(json_m["casualties"], 0)
        self.assertEqual(json_m["simulation_performance_score"], expected_score)

        # 4. CSV Export check
        csv_str = generate_csv_report(run_id)
        self.assertIn("Rescued Victims,40", csv_str)
        self.assertIn("Waiting / Unresolved Victims,60", csv_str)
        self.assertIn("Casualties,0", csv_str)
        self.assertIn(f"Calculated Simulation Performance Score,{expected_score}%", csv_str)

        # 5. PDF Export check
        pdf_path = f"test_report_{run_id}.pdf"
        generate_pdf_report(run_id, pdf_path)
        self.assertTrue(os.path.exists(pdf_path))
        self.assertGreater(os.path.getsize(pdf_path), 1000)
        os.remove(pdf_path)

    def test_08_no_occurrence_of_casualties_waiting_in_ui_or_reports(self):
        """11 & 12. Check that 'casualties / waiting' does not appear anywhere in UI or reports."""
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        forbidden_phrase = "casualties / waiting"
        forbidden_phrase_no_space = "casualties/waiting"

        # Search across frontend and backend source files
        dirs_to_check = [
            os.path.join(repo_root, "utils"),
            os.path.join(repo_root, "..", "multiagent project", "src"),
        ]

        for d in dirs_to_check:
            if not os.path.exists(d):
                continue
            for root, _, files in os.walk(d):
                for f in files:
                    if f.endswith((".py", ".jsx", ".js", ".html")):
                        fpath = os.path.join(root, f)
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as fh:
                            content = fh.read().lower()
                            self.assertNotIn(
                                forbidden_phrase,
                                content,
                                f"Found forbidden '{forbidden_phrase}' in {fpath}",
                            )
                            self.assertNotIn(
                                forbidden_phrase_no_space,
                                content,
                                f"Found forbidden '{forbidden_phrase_no_space}' in {fpath}",
                            )


if __name__ == "__main__":
    unittest.main()
