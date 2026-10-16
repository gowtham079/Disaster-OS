"""Normalized Data Models for Live Intelligence & Data Provenance.

Enforces strict provenance metadata, classification (LIVE, DATABASE, CALCULATED, SIMULATED, UNAVAILABLE),
and provider health tracking across USGS, GDACS, OpenWeather, Open-Meteo, Nominatim, and OSRM.
"""

from typing import Any, Dict, List, Optional, Union
from enum import Enum
import time
from pydantic import BaseModel, Field


class DataClassification(str, Enum):
    LIVE = "LIVE"
    DATABASE = "DATABASE"
    CALCULATED = "CALCULATED"
    SIMULATED = "SIMULATED"
    UNAVAILABLE = "UNAVAILABLE"


class SourceHealthStatus(str, Enum):
    OPERATIONAL = "OPERATIONAL"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    STALE = "STALE"


class CapacityStatus(str, Enum):
    UNAVAILABLE = "UNAVAILABLE"
    VERIFIED = "VERIFIED"
    SIMULATED = "SIMULATED"


class RouteClassification(str, Enum):
    REAL_ROUTE = "REAL_ROUTE"
    SIMULATED_ROUTE = "SIMULATED_ROUTE"


class FacilityRecord(BaseModel):
    facility_id: str
    facility_type: str  # "hospital" | "shelter" | "fire_station" | "police_station" | "helipad"
    name: str
    latitude: float
    longitude: float
    address: Optional[str] = None
    city: Optional[str] = None
    source: str = "OpenStreetMap"
    source_id: Optional[str] = None
    classification: DataClassification = DataClassification.LIVE
    fetched_at: Union[float, str] = Field(default_factory=time.time)
    capacity: Optional[int] = None
    available_capacity: Optional[int] = None
    capacity_status: CapacityStatus = CapacityStatus.UNAVAILABLE
    phone: Optional[str] = None
    emergency_service: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExternalDisasterEvent(BaseModel):
    source: str
    source_event_id: str
    source_url: Optional[str] = None
    event_type: str
    severity: str = "medium"
    status: str = "active"
    classification: DataClassification = DataClassification.LIVE
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    observed_at: Optional[float] = None
    fetched_at: float = Field(default_factory=time.time)
    expires_at: float = Field(default_factory=lambda: time.time() + 300)
    age_seconds: float = 0.0
    confidence: Optional[float] = None
    raw_payload: Optional[Dict[str, Any]] = None


class EarthquakeEvent(ExternalDisasterEvent):
    magnitude: float
    depth_km: Optional[float] = None
    place: str = "Unknown Seismic Region"


class WeatherObservation(BaseModel):
    provider: str
    classification: DataClassification = DataClassification.LIVE
    temperature: Optional[float] = None
    apparent_temperature: Optional[float] = None
    precipitation_mm: Optional[float] = None
    wind_speed_kmh: Optional[float] = None
    humidity_pct: Optional[float] = None
    weather_condition: Optional[str] = None
    latitude: float
    longitude: float
    observed_at: float = Field(default_factory=time.time)
    fetched_at: float = Field(default_factory=time.time)
    expires_at: float = Field(default_factory=lambda: time.time() + 180)
    freshness_seconds: float = 0.0


class WeatherAlert(BaseModel):
    provider: str
    alert_type: str
    severity: str
    headline: str
    description: Optional[str] = None
    issued_at: float = Field(default_factory=time.time)
    expires_at: float = Field(default_factory=lambda: time.time() + 3600)


class ExternalDataSourceStatus(BaseModel):
    name: str
    status: SourceHealthStatus = SourceHealthStatus.OPERATIONAL
    last_successful_fetch: Optional[float] = None
    last_failed_fetch: Optional[float] = None
    response_time_ms: float = 0.0
    error_message: Optional[str] = None
    freshness_seconds: Optional[float] = None
    record_count: int = 0


class RouteResult(BaseModel):
    provider: str
    classification: RouteClassification = RouteClassification.REAL_ROUTE
    source_coordinates: List[float]
    destination_coordinates: List[float]
    distance_km: float
    duration_minutes: float
    geometry: List[List[float]]
    fetched_at: float = Field(default_factory=time.time)
