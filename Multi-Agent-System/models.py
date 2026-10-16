"""Pydantic data models for the 14-Agent Evolving Disaster Management System."""

import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator



class DisasterInput(BaseModel):
    location: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    severity: str
    people_affected: int
    disaster_type: str  # flood, earthquake, cyclone, wildfire, chemical_leak, building_collapse, road_accident, landslide
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    wind_speed: Optional[float] = None
    rainfall_mm: Optional[float] = None
    population_density: Optional[int] = None
    infrastructure_score: Optional[int] = None
    hour_of_day: Optional[int] = None
    month: Optional[int] = None
    state: str = "INIT"


class IncidentReport(BaseModel):
    affected_area: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    priority: str
    estimated_risk: str
    people_affected: int = 0
    ml_predicted_severity: Optional[str] = None
    ml_confidence: Optional[float] = None
    ml_probabilities: Optional[Dict[str, float]] = None
    secondary_hazards: List[str] = []
    state: str = "INCIDENT_REPORTED"


class SituationAnalysis(BaseModel):
    threat_level: str
    risk_radius_km: float
    affected_population: int
    escalation_probability: float
    secondary_incidents_predicted: List[str] = []
    state: str = "SITUATION_ANALYZED"


class WeatherAnalysis(BaseModel):
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    wind_speed: Optional[float] = None
    rainfall_mm: Optional[float] = None
    weather_description: str = "UNAVAILABLE"
    people_affected: int = 0
    severity_multiplier: float = 1.0
    rescue_time_multiplier: float = 1.0
    victim_multiplier: float = 1.0
    fire_spread_speed_kmh: Optional[float] = None
    flood_rise_rate_cmh: Optional[float] = None
    special_resource_recommended: Optional[str] = None
    weather_warnings: List[str] = []
    classification: str = "UNAVAILABLE"
    state: str = "WEATHER_ANALYZED"


class VictimStatus(BaseModel):
    total_affected: int
    critically_injured: int
    moderately_injured: int
    trapped_count: int
    rescued_count: int
    triage_priority: str
    classification: str = "SIMULATED_HEURISTIC"
    methodology: Optional[str] = None
    state: str = "VICTIMS_TRIAGED"


class ResourceAllocation(BaseModel):
    teams_assigned: int
    resources: List[str]
    assigned_ambulances: int = 2
    assigned_fire_trucks: int = 1
    assigned_police: int = 1
    assigned_boats: int = 0
    assigned_drones: int = 1
    hazmat_teams: int = 0
    state: str = "RESOURCE_ALLOCATED"


class HospitalAssignment(BaseModel):
    assigned_hospital_id: str
    hospital_name: str
    beds_allocated: int
    trauma_units_ready: int = 2
    hospital_lat: Optional[float] = None
    hospital_lng: Optional[float] = None
    occupancy_pct: Optional[float] = None
    state: str = "HOSPITAL_ASSIGNED"


class ShelterAssignment(BaseModel):
    assigned_shelter_id: str
    shelter_name: str
    capacity_allocated: Optional[int] = None
    shelter_lat: Optional[float] = None
    shelter_lng: Optional[float] = None
    food_water_kits: Optional[int] = None
    occupancy_pct: Optional[float] = None
    classification: str = "SIMULATED"
    capacity_status: str = "SIMULATED"
    methodology: Optional[str] = None
    state: str = "SHELTER_ASSIGNED"


class TrafficStatus(BaseModel):
    blocked_roads_count: int
    detour_active: bool
    congestion_delay_mins: Optional[float] = None
    alternate_route_status: str
    blocked_segments: List[Dict[str, Any]] = []
    classification: str = "UNAVAILABLE"
    methodology: Optional[str] = None
    state: str = "TRAFFIC_MANAGED"


class PoliceDeployment(BaseModel):
    perimeter_secured: bool
    evacuation_corridor_active: bool
    patrol_units_deployed: int
    cell_broadcast_issued: bool
    classification: str = "SIMULATED_HEURISTIC"
    methodology: Optional[str] = None
    state: str = "POLICE_DEPLOYED"


class FireHazmatStatus(BaseModel):
    fire_contained: bool
    hazmat_containment_active: bool
    water_curtain_deployed: bool
    search_rescue_units: int
    classification: str = "SIMULATED_HEURISTIC"
    methodology: Optional[str] = None
    state: str = "FIRE_HAZMAT_MANAGED"


class DroneTelemetry(BaseModel):
    drones_airborne: int
    thermal_hotspots_detected: int
    survivors_located: int
    coverage_area_sqkm: float
    flight_vectors: List[List[float]] = []
    classification: str = "SIMULATED_HEURISTIC"
    methodology: Optional[str] = None
    state: str = "DRONE_RECON_ACTIVE"


class RoutePlan(BaseModel):
    route_path: List[str] = []
    route_coordinates: Optional[List[List[float]]] = None
    distance_km: Optional[float] = None
    eta_hours: Optional[float] = None
    has_blocked_road: bool = False
    detour_taken: bool = False
    route_provider: str = "UNAVAILABLE"
    route_type: str = "UNAVAILABLE"
    classification: str = "UNAVAILABLE"
    state: str = "ROUTE_PLANNED"


class RescueStatus(BaseModel):
    status: str = "IN_PROGRESS"
    rescued_people: int = 0
    rescued_count: int = 0
    remaining_victims: int = 0
    waiting_victims: int = 0
    rescues_in_progress: int = 0
    casualties_count: int = 0
    casualties: int = 0
    total_affected: Optional[int] = None
    classification: str = "SIMULATED_HEURISTIC"
    methodology: Optional[str] = None
    state: str = "RESCUE_IN_PROGRESS"

    @model_validator(mode="after")
    def sync_aliases(self) -> "RescueStatus":
        if self.rescued_count > 0 and self.rescued_people == 0:
            self.rescued_people = self.rescued_count
        elif self.rescued_people > 0 and self.rescued_count == 0:
            self.rescued_count = self.rescued_people
        if self.casualties_count > 0 and self.casualties == 0:
            self.casualties = self.casualties_count
        elif self.casualties > 0 and self.casualties_count == 0:
            self.casualties_count = self.casualties
        if self.waiting_victims > 0 and self.remaining_victims == 0:
            self.remaining_victims = self.waiting_victims
        elif self.remaining_victims > 0 and self.waiting_victims == 0:
            self.waiting_victims = self.remaining_victims
        return self


class CommunicationBroadcast(BaseModel):
    broadcast_id: str
    channels: List[str]
    alert_message: str
    recipients_reached: Optional[int] = None
    classification: str = "UNAVAILABLE"
    state: str = "COMMUNICATION_BROADCAST"


class AIRecommendation(BaseModel):
    predicted_threat: str
    recommended_actions: List[str]
    evacuation_instructions: str
    resource_adjustments: str
    summary: str
    provider: str = "LOCAL_HEURISTIC"
    model: str = "local-rule-engine"
    thinking_level: Optional[str] = None
    status: Optional[str] = "OPERATIONAL"
    generated_at: float = Field(default_factory=time.time)
    state: str = "AI_RECOMMENDATION"


class EvaluationReport(BaseModel):
    total_victims: int
    rescued_victims: int = 0
    rescued_count: int = 0
    waiting_victims: int = 0
    casualties: int = 0
    casualties_count: int = 0
    rescue_rate_pct: Optional[float] = None
    casualty_rate_pct: Optional[float] = None
    resource_assignment_rate_pct: Optional[float] = None
    active_resource_utilization_pct: Optional[float] = None
    resource_efficiency_pct: Optional[float] = None
    planned_route_eta_mins: Optional[float] = None
    actual_response_time_mins: Optional[float] = None
    avg_response_time_mins: Optional[float] = None
    simulation_performance_score: Optional[float] = None
    overall_score: Optional[float] = None
    metric_name: str = "Calculated Simulation Performance Score"
    evaluation_summary: str
    recommendations: List[str] = []
    classification: str = "CALCULATED"
    methodology: Optional[str] = None
    components: Optional[Dict[str, Any]] = None
    component_values: Optional[Dict[str, float]] = None
    weights: Optional[Dict[str, float]] = None
    state: str = "COMPLETED"
