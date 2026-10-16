"""Automated test suite for Disaster OS Step 5: Real Simulation Metrics + Telemetry.

Validates:
1. Rescued count comes from actual victim states.
2. Casualty count comes from actual victim states.
3. Rescue rate is mathematically derived.
4. Casualty rate is mathematically derived.
5. Response time comes from actual timestamps vs planned OSRM route ETA.
6. Absence of hardcoded final KPI numbers.
7. Absence of random telemetry generation.
8. Zero processed messages => latency None/UNAVAILABLE.
9. Run isolation (Run A metrics cannot include Run B records).
10. Reports use calculated run metrics.
11. Unavailable metric remains None / N/A.
12. Overall score is a documented Calculated Simulation Performance Score or None.
13. Communication recipients reached is None/UNAVAILABLE without arbitrary multipliers.
"""

import json
import os
import unittest
import uuid

from agents import (
    BaseAgent,
    CommunicationAgent,
    EvaluationAgent,
    RescueAgent,
    VictimAgent,
)
from database import (
    create_run,
    create_session,
    get_connection,
    get_db_agent_telemetry,
    get_response_performance_analytics,
    get_run_metrics,
    init_db,
    save_agent_log,
    save_incidents,
    save_run_metrics,
    save_simulation_resources,
)
from message_bus import AgentHealth, AgentMessage, MessageBus
from models import EvaluationReport, RescueStatus
from utils.report_generator import (
    generate_csv_report,
    generate_json_report,
)


class TestSimulationMetricsAndTelemetry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.bus = MessageBus(run_id=f"test-run-{uuid.uuid4().hex[:8]}")

    def test_01_rescued_count_from_actual_victim_states(self):
        """Rescued count comes from actual simulation victim entities and unit capacities."""
        rescue_agent = RescueAgent(self.bus)
        
        # Scenario: 150 victims triaged, 2 ambulances, 1 fire engine, 1 police
        # Deployed capacity = (2 * 25) + (1 * 30) + (1 * 15) = 95
        self.bus.history.append(AgentMessage(
            run_id=self.bus.run_id,
            sender="VictimAgent",
            message_type="VICTIMS_TRIAGED",
            payload={"total_affected": 150, "critically_injured": 30, "casualties_count": 0}
        ))
        self.bus.history.append(AgentMessage(
            run_id=self.bus.run_id,
            sender="ResourceAgent",
            message_type="RESOURCE_ALLOCATED",
            payload={"assigned_ambulances": 2, "assigned_fire_trucks": 1, "assigned_police": 1, "assigned_boats": 0}
        ))

        # Process ROUTE_PLANNED
        trigger_msg = AgentMessage(
            run_id=self.bus.run_id,
            sender="RouteAgent",
            message_type="ROUTE_PLANNED",
            payload={"distance_km": 5.0}
        )
        rescue_agent.process_message(trigger_msg)

        # Inspect published RESCUE_IN_PROGRESS message
        published = [m for m in self.bus.history if m.message_type == "RESCUE_IN_PROGRESS"]
        self.assertTrue(len(published) > 0)
        status = published[-1].payload
        self.assertEqual(status["rescued_people"], 95)
        self.assertEqual(status["remaining_victims"], 55)

    def test_02_casualty_count_from_actual_states(self):
        """Casualty count is derived strictly from recorded victim state transitions."""
        rescue_agent = RescueAgent(self.bus)
        
        # When casualty transition is 4
        self.bus.history.append(AgentMessage(
            run_id=self.bus.run_id,
            sender="VictimAgent",
            message_type="VICTIMS_TRIAGED",
            payload={"total_affected": 80, "critically_injured": 10, "casualties_count": 4}
        ))

        trigger_msg = AgentMessage(
            run_id=self.bus.run_id,
            sender="RouteAgent",
            message_type="ROUTE_PLANNED",
            payload={"distance_km": 3.0}
        )
        rescue_agent.process_message(trigger_msg)

        published = [m for m in self.bus.history if m.message_type == "RESCUE_IN_PROGRESS"]
        self.assertEqual(published[-1].payload["casualties_count"], 4)

    def test_03_04_rescue_and_casualty_rates_mathematically_derived(self):
        """Rescue and casualty rates are derived mathematically: count / total * 100."""
        eval_agent = EvaluationAgent(self.bus)
        
        total_victims = 200
        rescued = 160
        casualties = 10

        self.bus.history.append(AgentMessage(
            run_id=self.bus.run_id,
            sender="VictimAgent",
            message_type="VICTIMS_TRIAGED",
            payload={"total_affected": total_victims}
        ))
        self.bus.history.append(AgentMessage(
            run_id=self.bus.run_id,
            sender="RescueAgent",
            message_type="RESCUE_IN_PROGRESS",
            payload={"rescued_people": rescued, "casualties_count": casualties}
        ))

        eval_agent.process_message(AgentMessage(
            run_id=self.bus.run_id,
            sender="AIAgent",
            message_type="AI_RECOMMENDATION",
            payload={"predicted_threat": "Flood threat"}
        ))

        completed = [m for m in self.bus.history if m.message_type == "COMPLETED"]
        self.assertTrue(len(completed) > 0)
        report = completed[-1].payload

        # Expected: 160 / 200 * 100 = 80.0%, 10 / 200 * 100 = 5.0%
        self.assertEqual(report["rescue_rate_pct"], 80.0)
        self.assertEqual(report["casualty_rate_pct"], 5.0)

    def test_05_planned_eta_vs_actual_response_time(self):
        """Planned route ETA is distinct from actual response time; actual response time is None when arrival timestamps absent."""
        run_id = f"test-eta-{uuid.uuid4().hex[:8]}"
        create_run(run_id, 42, "smart", 1)

        # Save incidents with route ETA 0.2 hours (12.0 mins) and 0.3 hours (18.0 mins) -> avg 15.0 mins
        incidents = [
            {"location": "Sector A", "latitude": 20.0, "longitude": 80.0, "severity": "high", "people_affected": 50, "disaster_type": "flood", "route_eta_hours": 0.2},
            {"location": "Sector B", "latitude": 20.01, "longitude": 80.01, "severity": "medium", "people_affected": 30, "disaster_type": "flood", "route_eta_hours": 0.3},
        ]
        save_incidents(run_id, incidents)

        perf = get_response_performance_analytics(run_id)
        # Planned route ETA is 15.0 mins
        self.assertEqual(perf["planned_route_eta_mins"], 15.0)
        # Actual response time must be None because no arrival timestamps exist in incident_timeline
        self.assertIsNone(perf["actual_response_time_mins"])

    def test_06_no_hardcoded_final_kpi_in_evaluator(self):
        """Evaluator never returns the obsolete hardcoded numbers 95.8, 94.2, 332, 12.4, 5.1."""
        eval_agent = EvaluationAgent(self.bus)
        
        # Run with 100 victims, 50 rescued, 2 casualties
        self.bus.history.append(AgentMessage(
            run_id=self.bus.run_id,
            sender="VictimAgent",
            message_type="VICTIMS_TRIAGED",
            payload={"total_affected": 100}
        ))
        self.bus.history.append(AgentMessage(
            run_id=self.bus.run_id,
            sender="RescueAgent",
            message_type="RESCUE_IN_PROGRESS",
            payload={"rescued_people": 50, "casualties_count": 2}
        ))

        eval_agent.process_message(AgentMessage(
            run_id=self.bus.run_id,
            sender="AIAgent",
            message_type="AI_RECOMMENDATION",
            payload={"predicted_threat": "Storm"}
        ))

        completed = [m for m in self.bus.history if m.message_type == "COMPLETED"]
        report = completed[-1].payload

        self.assertNotEqual(report["total_victims"], 350)
        self.assertNotEqual(report["rescued_count"], 332)
        self.assertNotEqual(report["overall_score"], 95.8)
        self.assertNotEqual(report["casualty_rate_pct"], 5.1)

    def test_07_no_random_telemetry_generation(self):
        """get_db_agent_telemetry does not use random generation."""
        run_id = f"test-telemetry-{uuid.uuid4().hex[:8]}"
        create_run(run_id, 42, "smart", 1)

        # Log two agent actions with known execution timings: 12.5ms and 17.5ms -> avg 15.0ms
        save_agent_log(run_id, "ResourceAllocationAgent", "ALLOCATED", execution_time_ms=12.5)
        save_agent_log(run_id, "ResourceAllocationAgent", "ALLOCATED", execution_time_ms=17.5)

        telemetry = get_db_agent_telemetry(run_id=run_id)
        res_agent = next((a for a in telemetry if a["agent_name"] == "ResourceAllocationAgent"), None)
        self.assertIsNotNone(res_agent)
        self.assertEqual(res_agent["messages_processed"], 2)
        self.assertEqual(res_agent["avg_latency_ms"], 15.0)

    def test_08_zero_processed_messages_latency_is_none(self):
        """When an agent has processed zero messages, avg_latency_ms is None (not 0.0 or random)."""
        health = AgentHealth("TestAgent")
        self.assertEqual(health.messages_processed, 0)
        self.assertIsNone(health.to_dict()["avg_latency_ms"])

        base_agent = BaseAgent("TestBaseAgent", self.bus)
        self.assertEqual(base_agent.messages_processed, 0)
        self.assertIsNone(base_agent.get_health()["avg_latency_ms"])

        # Also test via get_db_agent_telemetry for empty run
        empty_run_id = f"test-empty-{uuid.uuid4().hex[:8]}"
        create_run(empty_run_id, 42, "smart", 1)
        telem = get_db_agent_telemetry(run_id=empty_run_id)
        for a in telem:
            self.assertEqual(a["messages_processed"], 0)
            self.assertIsNone(a["avg_latency_ms"])

    def test_09_run_isolation(self):
        """Run A metrics cannot include Run B records."""
        run_a = f"run-a-{uuid.uuid4().hex[:8]}"
        run_b = f"run-b-{uuid.uuid4().hex[:8]}"
        create_run(run_a, 42, "smart", 1)
        create_run(run_b, 43, "smart", 1)

        # Run A: 1 incident with 100 affected
        save_incidents(run_a, [{"location": "City A", "latitude": 10.0, "longitude": 70.0, "severity": "high", "people_affected": 100, "disaster_type": "flood", "route_eta_hours": 0.5}])
        save_run_metrics(run_a, {"total_incidents": 1, "total_affected": 100, "total_lives_saved": 85, "overall_efficiency": "85.0%"})

        # Run B: 1 incident with 50 affected
        save_incidents(run_b, [{"location": "City B", "latitude": 11.0, "longitude": 71.0, "severity": "medium", "people_affected": 50, "disaster_type": "fire", "route_eta_hours": 0.2}])
        save_run_metrics(run_b, {"total_incidents": 1, "total_affected": 50, "total_lives_saved": 40, "overall_efficiency": "80.0%"})

        perf_a = get_response_performance_analytics(run_a)
        perf_b = get_response_performance_analytics(run_b)

        # Run A success rate = 85 / 100 = 85.0%
        self.assertEqual(perf_a["mission_success_rate"], 85.0)
        self.assertEqual(perf_a["planned_route_eta_mins"], 30.0)

        # Run B success rate = 40 / 50 = 80.0%
        self.assertEqual(perf_b["mission_success_rate"], 80.0)
        self.assertEqual(perf_b["planned_route_eta_mins"], 12.0)

    def test_10_reports_use_calculated_run_metrics(self):
        """Reports use actual run metrics from the database without fake numbers."""
        run_id = f"test-report-{uuid.uuid4().hex[:8]}"
        create_run(run_id, 42, "smart", 1)
        save_incidents(run_id, [{"location": "Sector 9", "latitude": 18.5, "longitude": 73.8, "severity": "high", "people_affected": 77, "disaster_type": "earthquake", "route_eta_hours": 0.25}])
        save_run_metrics(run_id, {
            "total_incidents": 1,
            "total_affected": 77,
            "total_lives_saved": 68,
            "overall_efficiency": "88.3%",
            "planned_route_eta_mins": 15.0,
            "actual_response_time_mins": None,
        })

        csv_text = generate_csv_report(run_id)
        self.assertIn("77", csv_text)
        self.assertIn("68", csv_text)
        self.assertIn("88.3%", csv_text)
        self.assertIn("15.0 mins", csv_text)
        self.assertNotIn("95.8", csv_text)
        self.assertNotIn("94.2%", csv_text)

        json_text = generate_json_report(run_id)
        data = json.loads(json_text)
        self.assertEqual(data["run"]["metrics"]["total_affected"], 77)
        self.assertEqual(data["run"]["metrics"]["total_lives_saved"], 68)

    def test_11_unavailable_metric_remains_na(self):
        """When data is missing, metric is None / N/A with classification UNAVAILABLE."""
        run_id = f"test-unavail-{uuid.uuid4().hex[:8]}"
        create_run(run_id, 42, "smart", 1)

        perf = get_response_performance_analytics(run_id)
        self.assertTrue(perf["insufficient_data"])
        self.assertIsNone(perf["mission_success_rate"])
        self.assertIsNone(perf["planned_route_eta_mins"])
        self.assertIsNone(perf["actual_response_time_mins"])

    def test_12_overall_score_is_simulation_heuristic_or_none(self):
        """Overall score exposes formula and components, labeled as Calculated Simulation Performance Score."""
        eval_agent = EvaluationAgent(self.bus)
        
        # When victims are 0, overall score must be None
        eval_agent.process_message(AgentMessage(
            run_id=self.bus.run_id,
            sender="AIAgent",
            message_type="AI_RECOMMENDATION",
            payload={"predicted_threat": "None"}
        ))
        completed = [m for m in self.bus.history if m.message_type == "COMPLETED"]
        report = completed[-1].payload
        self.assertIsNone(report["overall_score"])
        self.assertEqual(report["metric_name"], "Calculated Simulation Performance Score")
        self.assertEqual(report["classification"], "CALCULATED")

    def test_13_communication_recipients_reached_is_none_without_multipliers(self):
        """Communication broadcast recipients_reached evaluates to None / UNAVAILABLE without arbitrary multipliers."""
        comm_agent = CommunicationAgent(self.bus)
        
        comm_agent.process_message(AgentMessage(
            run_id=self.bus.run_id,
            sender="RescueAgent",
            message_type="RESCUE_IN_PROGRESS",
            payload={"rescued_people": 50, "remaining_victims": 10}
        ))

        broadcasts = [m for m in self.bus.history if m.message_type == "COMMUNICATION_BROADCAST"]
        self.assertTrue(len(broadcasts) > 0)
        payload = broadcasts[-1].payload
        self.assertIsNone(payload["recipients_reached"])
        self.assertEqual(payload["classification"], "UNAVAILABLE")

    def test_14_osrm_eta_8_2_mins_with_no_arrival_timestamps_yields_actual_response_none(self):
        """Regression test: OSRM ETA 8.2 minutes + no arrival timestamps => actual_response_time_mins = None."""
        run_id = f"test-eta-truth-{uuid.uuid4().hex[:8]}"
        create_run(run_id, 42, "smart", 1)

        # Incident with route_eta_hours = 8.2 / 60
        incidents = [
            {
                "location": "Kolkata Sector 1",
                "latitude": 22.573,
                "longitude": 88.364,
                "severity": "high",
                "people_affected": 100,
                "disaster_type": "cyclone",
                "route_eta_hours": round(8.2 / 60, 6),
            }
        ]
        save_incidents(run_id, incidents)

        perf = get_response_performance_analytics(run_id)
        self.assertEqual(perf["planned_route_eta_mins"], 8.2)
        self.assertIsNone(perf["actual_response_time_mins"])

        from fastapi.testclient import TestClient
        from app import app
        client = TestClient(app)
        token = create_session(1)
        res = client.get(f"/api/run/{run_id}/dashboard", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res.status_code, 200)
        data = res.json()["metrics"]
        self.assertEqual(data["planned_route_eta_mins"], 8.2)
        self.assertIsNone(data["actual_response_time_mins"])
        self.assertIsNone(data["avg_response_time"])

    def test_15_resource_assignment_rate_and_active_utilization_cross_layer(self):
        """Regression test: resource_assignment_rate_pct is consistent across DB, API, and Reports."""
        run_id = f"test-util-{uuid.uuid4().hex[:8]}"
        create_run(run_id, 42, "smart", 1)

        # 35 resources total
        resources = [{"resource_id": f"R-{i}", "resource_name": f"Unit {i}", "resource_type": "ambulance", "latitude": 22.57, "longitude": 88.36, "status": "available", "capacity": 2} for i in range(35)]
        save_simulation_resources(run_id, resources)

        # 6 assigned teams
        incidents = [{"location": f"Sec {i}", "latitude": 22.57, "longitude": 88.36, "severity": "high", "people_affected": 50, "disaster_type": "cyclone", "assigned_team_id": f"Unit {i}"} for i in range(6)]
        save_incidents(run_id, incidents)

        # Assignment rate: 6 / 35 = 17.1%
        save_run_metrics(run_id, {
            "total_incidents": 6,
            "total_affected": 300,
            "total_lives_saved": 50,
            "overall_efficiency": "16.7%",
            "avg_response_time": "8.2 mins (planned ETA)",
            "resource_utilization": "17.1%",
            "planned_route_eta_mins": 8.2,
            "actual_response_time_mins": None,
            "status": "COMPLETED"
        })

        # 1. Check get_run_metrics
        db_m = get_run_metrics(run_id)
        self.assertEqual(db_m["resource_assignment_rate_pct"], 17.1)
        self.assertEqual(db_m["active_resource_utilization_pct"], 0.0)

        # 2. Check API Dashboard
        from fastapi.testclient import TestClient
        from app import app
        client = TestClient(app)
        token = create_session(1)
        res = client.get(f"/api/run/{run_id}/dashboard", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res.status_code, 200)
        api_m = res.json()["metrics"]
        self.assertEqual(api_m["resource_assignment_rate_pct"], 17.1)
        self.assertEqual(api_m["active_resource_utilization_pct"], 0.0)

        # 3. Check CSV Export
        from utils.report_generator import generate_csv_report
        csv_str = generate_csv_report(run_id)
        self.assertIn("17.1%", csv_str)


if __name__ == "__main__":
    unittest.main()
