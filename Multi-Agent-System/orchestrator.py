"""Orchestrator Engine for the 14-Agent Evolving Disaster Simulation.

Manages state machine transitions across all 14 autonomous agents, initializes dynamic
geospatial entities (vehicles, facilities, blocked roads, disaster zones), persists
run logs & metrics, and streams live vehicle waypoint position steps over WebSockets.
"""

import json
import logging
import time
import traceback
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from agents import (
    AIAgent,
    CommunicationAgent,
    DroneAgent,
    EvaluationAgent,
    FireAgent,
    HospitalAgent,
    IncidentAgent,
    PoliceAgent,
    RescueAgent,
    ResourceAgent,
    RouteAgent,
    ShelterAgent,
    TrafficAgent,
    VictimAgent,
    WeatherAgent,
)
from database import (
    complete_run,
    create_run,
    save_agent_log,
    save_blocked_roads,
    save_disaster_zones,
    save_facilities,
    save_incidents,
    save_run_metrics,
    save_simulation_resources,
)
from routing.service import RoutingService
from logger import init_db, log_transition
from message_bus import AgentMessage, MessageBus
from resource_generator import (
    generate_blocked_roads,
    generate_disaster_zones,
    generate_facilities,
    generate_simulation_resources,
)


class SystemState(Enum):
    INIT = "INIT"
    INCIDENT_REPORTED = "INCIDENT_REPORTED"
    SITUATION_ANALYZED = "SITUATION_ANALYZED"
    WEATHER_ANALYZED = "WEATHER_ANALYZED"
    VICTIMS_TRIAGED = "VICTIMS_TRIAGED"
    RESOURCE_ALLOCATED = "RESOURCE_ALLOCATED"
    HOSPITAL_ASSIGNED = "HOSPITAL_ASSIGNED"
    SHELTER_ASSIGNED = "SHELTER_ASSIGNED"
    TRAFFIC_MANAGED = "TRAFFIC_MANAGED"
    POLICE_DEPLOYED = "POLICE_DEPLOYED"
    FIRE_HAZMAT_MANAGED = "FIRE_HAZMAT_MANAGED"
    DRONE_RECON_ACTIVE = "DRONE_RECON_ACTIVE"
    ROUTE_PLANNED = "ROUTE_PLANNED"
    RESCUE_IN_PROGRESS = "RESCUE_IN_PROGRESS"
    COMMUNICATION_BROADCAST = "COMMUNICATION_BROADCAST"
    AI_RECOMMENDATION = "AI_RECOMMENDATION"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


class Orchestrator:
    def __init__(self, seed: int = 42, strategy: str = "smart", user_id: int = 1):
        self.run_id = str(uuid.uuid4())
        self.seed = seed
        self.strategy = strategy
        self.user_id = user_id
        self.current_state = SystemState.INIT
        self.data_store = {}
        self._completed = False

        init_db()
        create_run(self.run_id, self.seed, self.strategy, self.user_id)
        self.router = RoutingService()

        # Initialize Centralized Message Bus and register 14 Operational Response Agents + 1 Evaluation Service (15 total registered entities)
        self.message_bus = MessageBus(self.run_id)
        self.incident_agent = IncidentAgent(self.message_bus)
        self.weather_agent = WeatherAgent(self.message_bus)
        self.victim_agent = VictimAgent(self.message_bus)
        self.resource_agent = ResourceAgent(self.message_bus)
        self.hospital_agent = HospitalAgent(self.message_bus)
        self.shelter_agent = ShelterAgent(self.message_bus)
        self.traffic_agent = TrafficAgent(self.message_bus)
        self.police_agent = PoliceAgent(self.message_bus)
        self.fire_agent = FireAgent(self.message_bus)
        self.drone_agent = DroneAgent(self.message_bus)
        self.route_agent = RouteAgent(self.message_bus)
        self.rescue_agent = RescueAgent(self.message_bus)
        self.comm_agent = CommunicationAgent(self.message_bus)
        self.ai_agent = AIAgent(self.message_bus)
        self.evaluation_agent = EvaluationAgent(self.message_bus)

        # Expose message bus to FastAPI app for agent health tracking
        try:
            from app import set_last_message_bus
            set_last_message_bus(self.message_bus)
        except Exception:
            pass

    def run(self) -> str:
        """Execute full 14 Operational Response Agents + 1 Evaluation Service Pipeline."""
        try:
            # 1. Select Scenario City & Geography (Grounds all resources/facilities/incidents in one consistent context)
            from generate_data import _load_cities
            cities = _load_cities("india")
            city = cities[self.seed % len(cities)]
            base_lat, base_lng = city["lat"], city["lng"]
            city_name = city["name"]

            # 2. Initialize Dynamic Geospatial Entities within the scenario context
            resources = generate_simulation_resources(self.seed, center_lat=base_lat, center_lng=base_lng, city_name=city_name)
            facilities = generate_facilities(self.seed, center_lat=base_lat, center_lng=base_lng, city_name=city_name)
            zones = generate_disaster_zones(self.seed, center_lat=base_lat, center_lng=base_lng)
            blocked = generate_blocked_roads(self.seed, city_name=city_name)

            save_simulation_resources(self.run_id, resources)
            save_facilities(self.run_id, facilities)
            save_disaster_zones(self.run_id, zones)
            save_blocked_roads(self.run_id, blocked)

            disaster_types = ["flood", "earthquake", "cyclone", "wildfire", "chemical_leak", "building_collapse", "road_accident", "landslide"]
            dtype = disaster_types[self.seed % len(disaster_types)]
            base_affected = max(50, int((city["population_density"] / 10) * ((self.seed % 5) + 1)))

            init_input = {
                "location": f"{city_name} Emergency Sector 1",
                "latitude": base_lat,
                "longitude": base_lng,
                "severity": "high" if (self.seed % 2 == 0) else "medium",
                "people_affected": base_affected,
                "disaster_type": dtype,
                "temperature": round(24.0 + (self.seed % 14), 1),
                "humidity": round(55.0 + (self.seed % 40), 1),
                "wind_speed": round(10.0 + (self.seed % 35), 1),
                "rainfall_mm": round(15.0 + (self.seed % 80), 1),
                "population_density": city.get("population_density", 10000),
                "infrastructure_score": city.get("infrastructure_score", 6),
                "weather_classification": "SEED_INITIAL",
                "weather_note": "Initial weather values are seed-derived scenario parameters, not live meteorological data. Live weather is fetched by WeatherAgent.",
            }

            self._log_and_broadcast(SystemState.INIT.value, init_input)

            # 3. Publish initial trigger message to IncidentAgent
            trigger_msg = AgentMessage(
                sender="Orchestrator",
                receiver="IncidentAgent",
                message_type="DISASTER_TRIGGER",
                payload={"disaster_input": init_input},
                priority=1,
            )
            self.message_bus.publish(trigger_msg)

            # 4. Stream vehicle movement animation updates via WebSockets
            self._stream_vehicle_updates(resources)

            # Generate dynamic incident sectors for the run
            num_incidents = 4 + (self.seed % 4)
            incidents_to_save = []
            for i in range(num_incidents):
                inc_lat = round(base_lat + ((i - 1) * 0.015) + ((self.seed % 5) * 0.003), 4)
                inc_lng = round(base_lng + ((i - 1) * 0.015) - ((self.seed % 7) * 0.003), 4)
                assigned_res = resources[i % len(resources)] if resources else None
                assigned_name = assigned_res["resource_name"] if assigned_res else "Fleet Unit 1"
                res_lat = assigned_res.get("latitude") if assigned_res else None
                res_lng = assigned_res.get("longitude") if assigned_res else None

                if res_lat is not None and res_lng is not None:
                    route_info = self.router.route(res_lat, res_lng, inc_lat, inc_lng)
                else:
                    route_info = {
                        "status": "ROUTE_UNAVAILABLE",
                        "path": [],
                        "coordinates": None,
                        "distance_km": None,
                        "eta_hours": None,
                        "route_source": "UNAVAILABLE",
                        "route_provider": "UNAVAILABLE",
                    }

                coords = route_info.get("coordinates")
                route_coords_json = json.dumps(coords) if coords is not None else None
                path = route_info.get("path")
                route_path_str = json.dumps(path) if path else f"{city_name} Sector Route {i + 1}"

                incidents_to_save.append({
                    "location": f"{city_name} Sector {i + 1} - {dtype.title()}",
                    "latitude": inc_lat,
                    "longitude": inc_lng,
                    "severity": "high" if (i + self.seed) % 2 == 0 else "medium",
                    "people_affected": int(base_affected * (0.5 + (i * 0.2))),
                    "disaster_type": dtype,
                    "priority": "high" if (i + self.seed) % 2 == 0 else "medium",
                    "estimated_risk": "high" if (i + self.seed) % 2 == 0 else "medium",
                    "ml_predicted_severity": "high" if (i + self.seed) % 2 == 0 else "medium",
                    "ml_confidence": 0.92,
                    "assigned_team_id": assigned_name,
                    "route_path": route_path_str,
                    "route_coordinates": route_coords_json,
                    "route_distance_km": route_info.get("distance_km"),
                    "route_eta_hours": route_info.get("eta_hours"),
                    "route_source": route_info.get("route_source", "UNAVAILABLE"),
                    "route_provider": route_info.get("route_provider", "UNAVAILABLE"),
                })

            save_incidents(self.run_id, incidents_to_save)

            # Compute and save run metrics to database from actual run entities
            total_affected = sum(x["people_affected"] for x in incidents_to_save)

            rescued_count = 0
            casualties_count = 0
            eval_score = None
            for msg in reversed(self.message_bus.history):
                if msg.run_id == self.run_id:
                    if msg.message_type == "COMPLETED" and eval_score is None:
                        eval_score = msg.payload.get("overall_score")
                    elif msg.message_type == "RESCUE_IN_PROGRESS" and rescued_count == 0:
                        rescued_count = msg.payload.get("rescued_people", 0)
                        casualties_count = msg.payload.get("casualties_count", 0)

            # Strict separation: remaining/waiting victims are NOT casualties
            waiting_count = max(0, total_affected - rescued_count - casualties_count)
            rescue_rate = round((rescued_count / total_affected) * 100, 1) if total_affected > 0 else None
            casualty_rate = round((casualties_count / total_affected) * 100, 1) if total_affected > 0 else None

            etas = [x["route_eta_hours"] * 60 for x in incidents_to_save if x.get("route_eta_hours") is not None]
            mean_eta = round(sum(etas) / len(etas), 1) if etas else None

            assigned_team_count = len(set(x.get("assigned_team_id") for x in incidents_to_save if x.get("assigned_team_id")))
            total_res_count = len(resources)
            util_pct = round((assigned_team_count / total_res_count) * 100, 1) if total_res_count > 0 else 0.0

            from utils.metrics import calculate_simulation_performance_score
            score_data = calculate_simulation_performance_score(
                rescue_rate_pct=rescue_rate,
                casualty_rate_pct=casualty_rate,
                resource_assignment_rate_pct=util_pct,
                planned_route_eta_mins=mean_eta,
            )
            sim_score = score_data.get("score")
            overall_eff = f"{sim_score}%" if sim_score is not None else "N/A"
            avg_resp_str = f"{mean_eta} mins (planned ETA)" if mean_eta is not None else "N/A"
            res_util_str = f"{util_pct}%" if util_pct is not None else "N/A"

            save_run_metrics(self.run_id, {
                "total_incidents": len(incidents_to_save),
                "total_affected": total_affected,
                "total_victims": total_affected,
                "total_lives_saved": rescued_count,
                "rescued_victims": rescued_count,
                "waiting_victims": waiting_count,
                "casualties": casualties_count,
                "rescue_rate_pct": rescue_rate,
                "casualty_rate_pct": casualty_rate,
                "overall_efficiency": overall_eff,
                "simulation_performance_score": sim_score,
                "overall_score": sim_score,
                "avg_response_time": avg_resp_str,
                "resource_utilization": res_util_str,
                "planned_route_eta_mins": mean_eta,
                "actual_response_time_mins": None,
                "resource_assignment_rate_pct": util_pct,
                "active_resource_utilization_pct": 0.0,
                "status": "COMPLETED"
            })

            complete_run(self.run_id, status="COMPLETED")
            self._completed = True

            try:
                from app import broadcast_sync
                broadcast_sync({
                    "type": "RUN_COMPLETED",
                    "run_id": self.run_id,
                    "status": "COMPLETED",
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                })
            except Exception:
                pass

            logger.info(f"Simulation completed successfully. Run ID: {self.run_id}")
            return self.run_id

        except Exception as e:
            logger.error(f"Error executing orchestrator: {e}\n{traceback.format_exc()}")
            complete_run(self.run_id, status="ERROR")
            self._log_and_broadcast(SystemState.ERROR.value, {"error": str(e)})
            return self.run_id

    def _stream_vehicle_updates(self, resources: List[Dict[str, Any]]) -> None:
        """Stream vehicle positions over WebSockets for live map animations."""
        try:
            from app import broadcast_sync
            for v in resources[:6]:
                start_lat = v.get("latitude")
                start_lng = v.get("longitude")
                if start_lat is None or start_lng is None:
                    continue
                # Simulate sub-second vehicle movement towards incident
                for step in range(3):
                    v_lat = start_lat + (step * 0.002)
                    v_lng = start_lng + (step * 0.002)
                    broadcast_sync({
                        "type": "VEHICLE_POSITION_UPDATE",
                        "run_id": self.run_id,
                        "vehicle": {
                            "resource_id": v.get("resource_id"),
                            "resource_name": v.get("resource_name"),
                            "resource_type": v.get("resource_type"),
                            "latitude": v_lat,
                            "longitude": v_lng,
                            "status": "en_route",
                        }
                    })
                    time.sleep(0.15)
        except Exception:
            pass

    def _log_and_broadcast(self, state: str, payload: Dict[str, Any]) -> None:
        try:
            log_transition(self.run_id, state, payload)
            save_agent_log(self.run_id, agent_name="Orchestrator", state=state, output_json=json.dumps(payload))
            
            from app import broadcast_sync
            broadcast_sync({
                "type": "STATE_TRANSITION",
                "run_id": self.run_id,
                "state": state,
                "payload": payload,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })
        except Exception as e:
            logger.warning(f"Failed log/broadcast: {e}")
