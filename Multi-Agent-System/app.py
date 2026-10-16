import asyncio
from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional
import math
from urllib.parse import urlparse

from dotenv import load_dotenv

# Load environment variables from .env
_env_path = Path(__file__).resolve().parent / ".env"
if _env_path.exists():
    load_dotenv(dotenv_path=_env_path)
else:
    load_dotenv()

from fastapi import (
    BackgroundTasks,
    Cookie,
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Request,
    Response,
    status,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

import database
from database import (
    authenticate_user,
    clear_custom_incidents,
    complete_run,
    create_session,
    create_user_in_db,
    delete_user,
    get_active_ml_model,
    get_agent_messages,
    get_all_runs_with_metadata,
    get_analytics_summary,
    get_blocked_roads,
    get_custom_incidents,
    get_db_agent_telemetry,
    get_disaster_zones,
    get_facilities,
    get_incident_analytics,
    get_incident_timeline,
    get_incidents_by_run,
    get_intelligence_analytics,
    get_resource_analytics,
    get_response_performance_analytics,
    get_data_quality_metrics,
    get_rescue_teams,
    get_run_db_status,
    get_run_summary,
    get_simulation_resources,
    get_system_config,
    get_user_by_session,
    get_users,
    hash_password,
    init_db,
    revoke_session,
    save_custom_incident,
    save_incident_timeline_entry,
    save_ml_model_meta,
    update_incident_status,
    update_system_config,
    update_user_role,
    upsert_rescue_team,
    VALID_INCIDENT_STATUSES,
)
from logger import get_all_runs, get_run_history
from orchestrator import Orchestrator
from smart_suggestions import get_smart_suggestions
from weather_service import compute_weather_impact, get_weather
from intelligence.cache import intelligence_cache
from intelligence.source_health import health_manager
from intelligence.providers import fetch_usgs_earthquakes, fetch_gdacs_disasters, fetch_weather_observation, search_nominatim_location, probe_open_meteo_health
from intelligence.facility_provider import fetch_real_facilities, probe_overpass_health
from intelligence.impact_engine import calculate_disaster_impact
from intelligence.models import DataClassification, SourceHealthStatus

app = FastAPI(title="Multi-Agent Disaster Management API", version="2.0")


def _warmup_providers():
    """Background startup task to prime and verify all external intelligence providers."""
    time.sleep(1.0)
    try:
        eqs = fetch_usgs_earthquakes()
        if eqs:
            database.save_external_disaster_events([e.model_dump() for e in eqs])
    except Exception:
        pass
    try:
        dis = fetch_gdacs_disasters()
        if dis:
            database.save_external_disaster_events([e.model_dump() for e in dis])
    except Exception:
        pass
    try:
        fetch_weather_observation(19.076, 72.877)
    except Exception:
        pass
    try:
        probe_open_meteo_health()
    except Exception:
        pass
    try:
        search_nominatim_location("India")
    except Exception:
        pass
    try:
        probe_overpass_health()
    except Exception:
        pass
    try:
        from routing.service import RoutingService
        RoutingService().get_route(19.076, 72.877, 19.080, 72.880)
    except Exception:
        pass


@app.on_event("startup")
def startup_event():
    import threading
    threading.Thread(target=_warmup_providers, daemon=True).start()

# Configurable trusted CORS origins for local development and production
_raw_cors = os.getenv("DISASTER_OS_CORS_ORIGINS", "")
if _raw_cors.strip():
    TRUSTED_ORIGINS = [orig.strip() for orig in _raw_cors.split(",") if orig.strip()]
else:
    TRUSTED_ORIGINS = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=TRUSTED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


_allow_missing_origin_raw = os.getenv("DISASTER_OS_ALLOW_MISSING_ORIGIN", "true").lower()
ALLOW_MISSING_ORIGIN = _allow_missing_origin_raw in ("true", "1", "yes")


def is_trusted_origin(origin: Optional[str]) -> bool:
    """Validate WebSocket handshake Origin header against trusted frontend origins.
    Legitimate non-browser clients (missing Origin) require deliberate policy check
    and cannot bypass authentication.
    """
    if not origin:
        return ALLOW_MISSING_ORIGIN
    origin_clean = origin.strip().rstrip("/").lower()
    trusted_set = {t.strip().rstrip("/").lower() for t in TRUSTED_ORIGINS}
    return origin_clean in trusted_set


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass


main_loop = None
ws_manager = ConnectionManager()
_ws_logger = logging.getLogger("ws_broadcast")


def broadcast_sync(message: dict):
    """Thread-safe synchronous helper to broadcast WebSockets messages using main loop."""
    global main_loop
    if main_loop is None or main_loop.is_closed():
        try:
            main_loop = asyncio.get_running_loop()
        except RuntimeError:
            # Outside of an active running asyncio loop, WS broadcast cannot be scheduled
            return

    if main_loop and main_loop.is_running():
        try:
            future = asyncio.run_coroutine_threadsafe(ws_manager.broadcast(message), main_loop)
            future.add_done_callback(
                lambda f: _ws_logger.error("WS broadcast error: %s", f.exception()) if f.exception() else None
            )
        except Exception as e:
            _ws_logger.error("Failed to schedule WS broadcast: %s", e)


@app.websocket("/ws/simulation")
async def websocket_endpoint(websocket: WebSocket):
    # 1. Validate Origin header against trusted origins to prevent Cross-Site WebSocket Hijacking (CSWSH)
    origin = websocket.headers.get("origin")
    if not is_trusted_origin(origin):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Untrusted origin")
        return

    # 2. Extract session token ONLY from HttpOnly cookie or Authorization header
    token = websocket.cookies.get("disaster_os_session")
    if not token and "authorization" in websocket.headers:
        auth_header = websocket.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()

    # Reject if no token was provided
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication required")
        return

    # 3. Validate session against database (checks existence and expiration)
    user = get_user_by_session(token)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Session invalid or expired")
        return

    # 4. Connection accepted and registered ONLY after successful origin and auth validation
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


@app.on_event("startup")
async def startup_event() -> None:
    global main_loop
    try:
        main_loop = asyncio.get_running_loop()
    except RuntimeError:
        main_loop = None
    init_db()

    # Async provider health warmup (non-blocking)
    async def _warmup_providers():
        try:
            await asyncio.to_thread(fetch_weather_observation, 20.5937, 78.9629)
        except Exception:
            pass
        try:
            await asyncio.to_thread(fetch_usgs_earthquakes)
        except Exception:
            pass
        try:
            await asyncio.to_thread(fetch_gdacs_disasters)
        except Exception:
            pass

    asyncio.create_task(_warmup_providers())


# ── Authentication Security Dependency ─────────────────────────────────────

def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(None),
    disaster_os_session: Optional[str] = Cookie(None),
) -> Dict[str, Any]:
    """Validate active session token ONLY from Bearer header or HttpOnly cookie.
    Query-string token authentication is strictly prohibited.
    """
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
    elif disaster_os_session:
        token = disaster_os_session

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in to access EOC operations.",
        )

    user = get_user_by_session(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session invalid or expired. Please sign in again.",
        )
    return user


def require_admin(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Validate that the authenticated user possesses administrator privileges.
    Returns HTTP 403 for authenticated non-admin users.
    Preserves HTTP 401 behavior for unauthenticated requests via get_current_user.
    """
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Administrative privileges required.",
        )
    return current_user


class LoginRequest(BaseModel):
    email: str
    password: str


@app.post("/api/auth/login")
def auth_login(req: LoginRequest, response: Response):
    """Authenticate operator credentials and issue a persistent session token."""
    user = authenticate_user(req.email, req.password)
    if not user:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"status": "error", "message": "Invalid email or password."},
        )

    token = create_session(user["user_id"], duration_hours=24)
    cookie_secure = os.getenv("DISASTER_OS_COOKIE_SECURE", "false").lower() in ("true", "1", "yes")
    response.set_cookie(
        key="disaster_os_session",
        value=token,
        httponly=True,
        max_age=86400,
        samesite="lax",
        secure=cookie_secure,
    )
    return {
        "status": "success",
        "message": "Authenticated successfully.",
        "token": token,
        "user": user,
    }


@app.post("/api/auth/logout")
def auth_logout(
    response: Response,
    authorization: Optional[str] = Header(None),
    disaster_os_session: Optional[str] = Cookie(None),
):
    """Revoke active session token and clear authentication cookie."""
    token = disaster_os_session or (
        authorization[7:].strip() if authorization and authorization.startswith("Bearer ") else None
    )
    if token:
        revoke_session(token)
    response.delete_cookie(key="disaster_os_session")
    return {"status": "success", "message": "Session terminated."}


@app.get("/api/auth/me")
def auth_me(
    authorization: Optional[str] = Header(None),
    disaster_os_session: Optional[str] = Cookie(None),
):
    """Check active session validity and return current operator profile."""
    token = disaster_os_session or (
        authorization[7:].strip() if authorization and authorization.startswith("Bearer ") else None
    )
    if not token:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"status": "error", "message": "Not authenticated."},
        )
    user = get_user_by_session(token)
    if not user:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"status": "error", "message": "Session expired or invalid."},
        )
    return {"status": "success", "user": user}


class RunRequest(BaseModel):
    seed: int = 42
    strategy: str = "smart"
    user_id: int = 1


@app.post("/api/run")
def trigger_run(
    request: RunRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    orchestrator = Orchestrator(
        seed=request.seed, strategy=request.strategy, user_id=current_user.get("user_id", 1)
    )
    run_id = orchestrator.run_id
    background_tasks.add_task(orchestrator.run)
    return {
        "message": "Simulation run started",
        "run_id": run_id,
        "strategy": request.strategy,
    }


@app.get("/api/runs")
def list_runs(current_user: Dict[str, Any] = Depends(get_current_user)):
    return {"runs": get_all_runs_with_metadata()}


@app.get("/api/run/{run_id}/history")
def run_history(run_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    history = get_run_history(run_id)
    return {"run_id": run_id, "history": history}


@app.get("/api/run/{run_id}/status")
def run_status(run_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    db_status = get_run_db_status(run_id)
    if not db_status:
        return {"run_id": run_id, "status": "NOT_FOUND", "latest_state": None}

    status = db_status["status"] or "RUNNING"
    history = get_run_history(run_id)
    latest_state = history[-1].get("state") if history else None

    return {
        "run_id": run_id,
        "status": status,
        "latest_state": latest_state,
        "steps": len(history),
        "strategy": db_status.get("strategy"),
        "started_at": db_status.get("started_at"),
        "completed_at": db_status.get("completed_at"),
    }


@app.get("/api/run/{run_id}/incidents")
def run_incidents(run_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    return {"run_id": run_id, "incidents": get_incidents_by_run(run_id)}


# ── Live Intelligence & Provenance API Endpoints ───────────────────────────

@app.get("/api/intelligence/status")
def get_intelligence_status():
    """Return real-time health and freshness status for all 7 external data providers."""
    # 1. Open-Meteo probe
    om_stat = health_manager.get_status("Open-Meteo")
    if om_stat and (om_stat.status == SourceHealthStatus.UNAVAILABLE or (om_stat.freshness_seconds and om_stat.freshness_seconds > 300)):
        try:
            probe_open_meteo_health()
        except Exception:
            pass

    # 2. Nominatim probe
    nom_stat = health_manager.get_status("Nominatim")
    if nom_stat and (nom_stat.status == SourceHealthStatus.UNAVAILABLE or (nom_stat.freshness_seconds and nom_stat.freshness_seconds > 600)):
        try:
            search_nominatim_location("India")
        except Exception:
            pass

    # 3. Overpass probe
    op_stat = health_manager.get_status("Overpass")
    if op_stat and (op_stat.status in (SourceHealthStatus.UNAVAILABLE, SourceHealthStatus.DEGRADED) or (op_stat.freshness_seconds and op_stat.freshness_seconds > 300)):
        try:
            probe_overpass_health()
        except Exception:
            pass

    # 4. OSRM probe
    osrm_stat = health_manager.get_status("OSRM")
    if osrm_stat and (osrm_stat.status == SourceHealthStatus.UNAVAILABLE or (osrm_stat.freshness_seconds and osrm_stat.freshness_seconds > 600)):
        try:
            from routing.service import RoutingService
            RoutingService().get_route(19.076, 72.877, 19.080, 72.880)
        except Exception:
            pass

    # 5. OpenWeather probe
    ow_stat = health_manager.get_status("OpenWeather")
    if ow_stat and (ow_stat.status == SourceHealthStatus.UNAVAILABLE or (ow_stat.freshness_seconds and ow_stat.freshness_seconds > 600)):
        try:
            fetch_weather_observation(19.076, 72.877)
        except Exception:
            pass

    # 6. USGS probe
    usgs_stat = health_manager.get_status("USGS")
    if usgs_stat and (usgs_stat.status == SourceHealthStatus.UNAVAILABLE or (usgs_stat.freshness_seconds and usgs_stat.freshness_seconds > 600)):
        try:
            fetch_usgs_earthquakes()
        except Exception:
            pass

    # 7. GDACS probe
    gdacs_stat = health_manager.get_status("GDACS")
    if gdacs_stat and (gdacs_stat.status == SourceHealthStatus.UNAVAILABLE or (gdacs_stat.freshness_seconds and gdacs_stat.freshness_seconds > 600)):
        try:
            fetch_gdacs_disasters()
        except Exception:
            pass

    statuses = health_manager.get_all_statuses()
    return {
        "status": "success",
        "timestamp": time.time(),
        "sources": [s.model_dump() for s in statuses]
    }


@app.post("/api/intelligence/status/refresh")
def refresh_all_intelligence_providers(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Force an active health probe across all 7 external providers."""
    _warmup_providers()
    statuses = health_manager.get_all_statuses()
    return {
        "status": "success",
        "timestamp": time.time(),
        "sources": [s.model_dump() for s in statuses]
    }


@app.get("/api/intelligence/earthquakes")
def get_intelligence_earthquakes(mag_min: float = 4.5):
    """Retrieve normalized live USGS earthquake feed with deduplication and provenance."""
    if not (0.0 <= mag_min <= 10.0) or math.isnan(mag_min) or math.isinf(mag_min):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": "error", "message": "mag_min must be a finite number between 0.0 and 10.0."},
        )
    cache_key = f"usgs_earthquakes_{mag_min}"
    was_cached = intelligence_cache.get(cache_key) is not None
    eq_events = fetch_usgs_earthquakes(mag_min=mag_min)
    if not was_cached and eq_events:
        database.save_external_disaster_events([e.model_dump() for e in eq_events])
    return {
        "status": "success",
        "source": "USGS",
        "classification": DataClassification.LIVE.value if eq_events else DataClassification.UNAVAILABLE.value,
        "count": len(eq_events),
        "events": [e.model_dump() for e in eq_events]
    }


@app.get("/api/intelligence/disasters")
def get_intelligence_disasters():
    """Retrieve normalized live GDACS global disaster alert feed."""
    cache_key = "gdacs_disasters"
    was_cached = intelligence_cache.get(cache_key) is not None
    gdacs_events = fetch_gdacs_disasters()
    if not was_cached and gdacs_events:
        database.save_external_disaster_events([e.model_dump() for e in gdacs_events])
    return {
        "status": "success",
        "source": "GDACS",
        "classification": DataClassification.LIVE.value if gdacs_events else DataClassification.UNAVAILABLE.value,
        "count": len(gdacs_events),
        "events": [e.model_dump() for e in gdacs_events]
    }


@app.get("/api/intelligence/weather/{lat}/{lng}")
def get_intelligence_weather(lat: float, lng: float):
    """Retrieve normalized live weather observations with freshness metadata."""
    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lng <= 180.0):
        return JSONResponse(status_code=400, content={"status": "error", "message": "Invalid latitude/longitude bounds."})

    obs = fetch_weather_observation(lat, lng)
    if not obs:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unavailable",
                "classification": DataClassification.UNAVAILABLE.value,
                "message": "Live weather services currently unreachable."
            }
        )

    return {
        "status": "success",
        "observation": obs.model_dump()
    }


@app.get("/api/intelligence/overview")
def get_intelligence_overview():
    """Aggregated view of active external disaster events and provider health status."""
    earthquakes = fetch_usgs_earthquakes()
    disasters = fetch_gdacs_disasters()

    nom_stat = health_manager.get_status("Nominatim")
    if nom_stat and nom_stat.status == SourceHealthStatus.UNAVAILABLE:
        try:
            search_nominatim_location("India")
        except Exception:
            pass

    op_stat = health_manager.get_status("Overpass")
    if op_stat and op_stat.status == SourceHealthStatus.UNAVAILABLE:
        try:
            probe_overpass_health()
        except Exception:
            pass

    statuses = health_manager.get_all_statuses()

    return {
        "status": "success",
        "timestamp": time.time(),
        "sources_health": [s.model_dump() for s in statuses],
        "summary": {
            "total_earthquakes": len(earthquakes),
            "total_global_disasters": len(disasters),
            "operational_sources_count": len([s for s in statuses if s.status == SourceHealthStatus.OPERATIONAL])
        },
        "earthquakes": [e.model_dump() for e in earthquakes],
        "global_disasters": [d.model_dump() for d in disasters]
    }


@app.get("/api/intelligence/search")
def get_intelligence_search(q: str):
    """Geocode search query using Nominatim API returning normalized results with provenance."""
    if not q or not q.strip():
        return {"status": "success", "count": 0, "results": []}

    # Reject control characters (e.g. null bytes, terminal escapes)
    if any(ord(c) < 32 for c in q if c not in (" ", "\t")):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": "error", "message": "Search query contains invalid control characters."},
        )

    # Enforce maximum query length of 100 characters
    if len(q.strip()) > 100:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": "error", "message": "Search query exceeds maximum length of 100 characters."},
        )

    clean_q = q.strip()
    if len(clean_q) < 2:
        return {"status": "success", "count": 0, "results": []}

    results = search_nominatim_location(clean_q)
    return {
        "status": "success",
        "provider": "Nominatim",
        "classification": DataClassification.LIVE.value if results else DataClassification.UNAVAILABLE.value,
        "count": len(results),
        "results": results
    }


@app.get("/api/intelligence/facilities")
def get_intelligence_facilities(
    request: Request,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    radius_km: float = 20.0,
    facility_type: Optional[str] = None,
    use_cache: bool = True,
):
    """Retrieve real-world emergency facilities from OpenStreetMap via Overpass API.
    Enforces strict zero fake capacity rules (unprovided capacity is labeled UNAVAILABLE).
    """
    if lat is None or lng is None or math.isnan(lat) or math.isnan(lng) or math.isinf(lat) or math.isinf(lng):
        return JSONResponse(status_code=400, content={"status": "error", "message": "Valid latitude and longitude coordinates are required."})
    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lng <= 180.0):
        return JSONResponse(status_code=400, content={"status": "error", "message": "Valid latitude and longitude coordinates are required."})

    if math.isnan(radius_km) or math.isinf(radius_km) or radius_km <= 0:
        return JSONResponse(status_code=400, content={"status": "error", "message": "radius_km must be a positive finite number."})

    # Enforce safe radius bounds between 1.0 km and 50.0 km
    safe_radius_km = min(max(float(radius_km), 1.0), 50.0)

    # Ensure public unauthenticated requests cannot bypass caching
    session_token = request.cookies.get("disaster_os_session")
    if not session_token:
        auth_h = request.headers.get("authorization", "")
        if auth_h.startswith("Bearer "):
            session_token = auth_h[7:].strip()
    is_operator = bool(session_token and get_user_by_session(session_token))
    effective_use_cache = use_cache if is_operator else True

    facilities, provenance = fetch_real_facilities(
        lat=lat, lng=lng, radius_km=safe_radius_km, facility_type=facility_type, use_cache=effective_use_cache
    )

    return {
        "status": "success",
        "source": "OpenStreetMap / Overpass",
        "classification": provenance,
        "center": {"latitude": lat, "longitude": lng},
        "radius_km": safe_radius_km,
        "count": len(facilities),
        "facilities": [f.model_dump() for f in facilities],
    }


@app.get("/api/facilities/real")
def get_persisted_real_facilities(
    facility_type: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    radius_km: float = 25.0,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Retrieve verified real-world facilities persisted in SQLite external_facilities table."""
    facilities = database.get_external_facilities(
        facility_type=facility_type, lat=lat, lng=lng, radius_km=radius_km
    )
    return {
        "status": "success",
        "source": "DATABASE",
        "classification": DataClassification.DATABASE.value if facilities else DataClassification.UNAVAILABLE.value,
        "count": len(facilities),
        "facilities": facilities,
    }


# ── Phase P3.2 Disaster Impact Analysis Engine Endpoints ───────────────────

class ImpactAssessmentRequest(BaseModel):
    latitude: float
    longitude: float
    disaster_type: str = "earthquake"
    magnitude: Optional[float] = None
    depth_km: Optional[float] = 10.0
    rainfall_mm: Optional[float] = None
    wind_speed_kmh: Optional[float] = None
    event_id: Optional[str] = None


@app.post("/api/impact/assess")
def assess_disaster_impact(req: ImpactAssessmentRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Execute mathematical disaster impact assessment.
    Calculates empirical seismic attenuation zones (MMI VII/V/III) and physical hazard radii.
    Exposes real OSM facility exposure and explainable calculation methodology.
    """
    if not (-90.0 <= req.latitude <= 90.0) or not (-180.0 <= req.longitude <= 180.0):
        return JSONResponse(status_code=400, content={"status": "error", "message": "Invalid latitude/longitude coordinates."})

    result = calculate_disaster_impact(
        latitude=req.latitude,
        longitude=req.longitude,
        disaster_type=req.disaster_type,
        magnitude=req.magnitude,
        depth_km=req.depth_km,
        rainfall_mm=req.rainfall_mm,
        wind_speed_kmh=req.wind_speed_kmh,
        event_id=req.event_id,
    )
    return {"status": "success", "assessment": result}


@app.get("/api/impact/assessments")
def list_impact_assessments(limit: int = 20):
    """List recent calculated impact assessments."""
    return {"status": "success", "assessments": database.get_latest_impact_assessments(limit=limit)}


@app.get("/api/impact/{assessment_id}")
def get_single_impact_assessment(assessment_id: str):
    """Retrieve full details of a specific calculated impact assessment."""
    assessment = database.get_impact_assessment(assessment_id=assessment_id)
    if not assessment:
        return JSONResponse(status_code=404, content={"status": "error", "message": f"Assessment {assessment_id} not found."})
    return {"status": "success", "assessment": assessment}


# ── Phase P3.3 Compound Disaster Event Correlation Endpoints ───────────────

@app.post("/api/intelligence/correlate")
def run_compound_correlation(run_id: Optional[str] = "demo", current_user: Dict[str, Any] = Depends(get_current_user)):
    """Execute spatio-temporal multi-hazard compound event correlation analysis."""
    from intelligence.correlation_engine import detect_compound_disaster_events
    from weather_service import get_weather

    earthquakes = database.get_external_disaster_events(source="USGS", limit=25)
    disasters = database.get_external_disaster_events(source="GDACS", limit=25)
    incidents = get_incidents_by_run(run_id or "demo")
    facilities = get_facilities(run_id or "demo")
    weather_lat = incidents[0].get("latitude") if incidents else None
    weather_lng = incidents[0].get("longitude") if incidents else None
    w_data = get_weather(weather_lat, weather_lng)

    events = detect_compound_disaster_events(
        earthquakes=earthquakes,
        disasters=disasters,
        incidents=incidents,
        facilities=facilities,
        weather=w_data,
    )
    return {"status": "success", "count": len(events), "compound_events": events}


@app.get("/api/intelligence/compound-events")
def list_compound_events(limit: int = 30):
    """List detected compound disaster events and cascading hazard chains."""
    events = database.get_compound_events(limit=limit)
    return {"status": "success", "count": len(events), "compound_events": events}


@app.get("/api/intelligence/compound-events/{compound_id}")
def get_single_compound_event(compound_id: str):
    """Retrieve details of a single compound disaster event."""
    event = database.get_compound_event_by_id(compound_id)
    if not event:
        return JSONResponse(status_code=404, content={"status": "error", "message": f"Compound event {compound_id} not found."})
    return {"status": "success", "compound_event": event}


# ── Phase P3.4 Evacuation Corridor Optimization Endpoints ──────────────────

class CorridorPlanRequest(BaseModel):
    origin_lat: float
    origin_lng: float
    dest_lat: float
    dest_lng: float
    corridor_name: str = "Evacuation Sector Corridor"
    profile: str = "car"
    population_to_evacuate: int = 500
    run_id: Optional[str] = "demo"


@app.post("/api/corridors/plan")
def plan_corridor_endpoint(req: CorridorPlanRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Calculate optimized evacuation corridor with hazard avoidance & flow throughput."""
    from intelligence.corridor_router import plan_evacuation_corridor

    import math
    for lat, lng, name in [(req.origin_lat, req.origin_lng, "origin"), (req.dest_lat, req.dest_lng, "destination")]:
        if lat is None or lng is None or math.isnan(lat) or math.isnan(lng) or math.isinf(lat) or math.isinf(lng):
            return JSONResponse(status_code=400, content={"status": "error", "message": f"Invalid {name} coordinates."})
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
            return JSONResponse(status_code=400, content={"status": "error", "message": f"Invalid {name} coordinates range."})
        if lat == 0.0 and lng == 0.0:
            return JSONResponse(status_code=400, content={"status": "error", "message": f"Invalid {name} coordinates."})

    run_id = req.run_id or "demo"
    roadblocks = get_blocked_roads(run_id)
    recent_assessments = database.get_latest_impact_assessments(limit=5)
    impact_zones = []
    for a in recent_assessments:
        for z in a.get("impact_zones", []):
            if z.get("level") in ["CRITICAL", "ELEVATED"]:
                impact_zones.append({
                    "center_latitude": a.get("epicenter_latitude") or a.get("epicenter_lat"),
                    "center_longitude": a.get("epicenter_longitude") or a.get("epicenter_lng"),
                    "radius_km": z.get("radius_km"),
                    "name": z.get("name"),
                })

    corridor = plan_evacuation_corridor(
        origin_lat=req.origin_lat,
        origin_lng=req.origin_lng,
        dest_lat=req.dest_lat,
        dest_lng=req.dest_lng,
        corridor_name=req.corridor_name,
        profile=req.profile,
        population_to_evacuate=req.population_to_evacuate,
        impact_zones=impact_zones,
        roadblocks=roadblocks,
    )
    return {"status": "success", "corridor": corridor}


class RoutePlanApiRequest(BaseModel):
    start_lat: float
    start_lng: float
    end_lat: float
    end_lng: float
    avoid_blocked: bool = True

    @field_validator("start_lat", "end_lat")
    @classmethod
    def validate_lat(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v):
            raise ValueError("Latitude must be a finite number.")
        if not (-90.0 <= v <= 90.0):
            raise ValueError("Latitude must be between -90.0 and 90.0.")
        return v

    @field_validator("start_lng", "end_lng")
    @classmethod
    def validate_lng(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v):
            raise ValueError("Longitude must be a finite number.")
        if not (-180.0 <= v <= 180.0):
            raise ValueError("Longitude must be between -180.0 and 180.0.")
        return v


@app.post("/api/routes/plan")
def plan_route_endpoint(req: RoutePlanApiRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Query live route from RoutingService with truthful OSRM, LOCAL_ASTAR, or DIRECT_GEOMETRIC provenance."""
    from routing.service import RoutingService
    router = RoutingService()
    result = router.route(req.start_lat, req.start_lng, req.end_lat, req.end_lng)
    return {"status": "success", "route": result}


@app.get("/api/corridors/active")
def list_active_corridors(limit: int = 20):
    """List recently evaluated evacuation corridors and bottleneck statuses."""
    corridors = database.get_evacuation_corridors(limit=limit)
    return {"status": "success", "count": len(corridors), "corridors": corridors}


# ── Phase 4-9 Real-Time EOC Dashboard & Entities Endpoints ─────────────────

@app.get("/api/run/{run_id}/dashboard")
def get_eoc_dashboard(run_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Return 16 real-time auto-updating EOC dashboard metric counters calculated dynamically from DB."""
    try:
        incidents = get_incidents_by_run(run_id)
        resources = get_simulation_resources(run_id)
        facilities = get_facilities(run_id)
        blocked = get_blocked_roads(run_id)
        db_status = get_run_db_status(run_id)

        # Query persisted run metrics if available
        conn = database.get_connection()
        rm_row = conn.execute("SELECT * FROM run_metrics WHERE run_id = ?", (run_id,)).fetchone()
        conn.close()

        # 1. Victims calculation based on database records and strict casualty semantics
        total_victims = sum(inc.get("people_affected", 0) for inc in incidents)
        status_name = (db_status.get("status") if db_status else "RUNNING").upper()
        
        if rm_row and rm_row["total_lives_saved"] is not None:
            victims_rescued = rm_row["total_lives_saved"]
        elif status_name == "COMPLETED":
            victims_rescued = total_victims
        else:
            victims_rescued = 0

        # Casualties: ONLY victims whose lifecycle explicitly transitioned to a fatal state
        casualties_count = 0
        if rm_row and "casualties" in rm_row.keys() and rm_row["casualties"] is not None:
            casualties_count = rm_row["casualties"]

        # Remaining / Waiting: victims still unresolved at the end of the run
        victims_waiting = max(0, total_victims - victims_rescued - casualties_count)

        rescue_rate_pct = round((victims_rescued / max(1, total_victims)) * 100, 1) if total_victims > 0 else None
        casualty_rate_pct = round((casualties_count / max(1, total_victims)) * 100, 1) if total_victims > 0 else None

        # Calculate progress from pipeline stage history
        history = get_run_history(run_id) if run_id != 'demo' else []
        completed_stages = len(set(h.get('state') for h in history)) if history else 0
        total_stages = 14
        progress_pct = 100 if status_name == "COMPLETED" else round((completed_stages / total_stages) * 100) if completed_stages > 0 else 0
        eta_str = "Completed" if status_name == "COMPLETED" else "Calculating..." if status_name == "RUNNING" else "Idle"

        # 2. Fleet breakdown
        ambulances = [r for r in resources if r.get("resource_type") == "ambulance"]
        fire_trucks = [r for r in resources if r.get("resource_type") == "fire_truck"]
        police = [r for r in resources if r.get("resource_type") == "police_car"]

        avail_amb = len([r for r in ambulances if r.get("status") == "available"])
        avail_fire = len([r for r in fire_trucks if r.get("status") == "available"])
        avail_pol = len([r for r in police if r.get("status") == "available"])

        # 3. Facilities zero-division safe calculations
        hospitals = [f for f in facilities if f.get("facility_type") == "hospital"]
        shelters = [f for f in facilities if f.get("facility_type") == "shelter"]

        # Hospital capacity: use actual values; None means unknown (not 0)
        total_beds = 0
        avail_beds = 0
        has_hosp_capacity = False
        for h in hospitals:
            tc = h.get("total_capacity")
            ac = h.get("available_capacity")
            if tc is not None:
                total_beds += tc
                has_hosp_capacity = True
            if ac is not None:
                avail_beds += ac
        hosp_cap_pct = round(((total_beds - avail_beds) / max(1, total_beds)) * 100, 1) if has_hosp_capacity and total_beds > 0 else None

        # Shelter capacity: use actual values; None means unknown (not 0)
        total_shelter = 0
        avail_shelter = 0
        has_shelter_capacity = False
        for s in shelters:
            tc = s.get("total_capacity")
            ac = s.get("available_capacity")
            if tc is not None:
                total_shelter += tc
                has_shelter_capacity = True
            if ac is not None:
                avail_shelter += ac
        shelter_cap_pct = round(((total_shelter - avail_shelter) / max(1, total_shelter)) * 100, 1) if has_shelter_capacity and total_shelter > 0 else None

        # 4. Resource utilization calculation
        tot_res_count = len(resources)
        busy_res_count = len([r for r in resources if r.get("status") in ["dispatched", "busy", "en_route", "active"]])
        active_util_pct = round((busy_res_count / max(1, tot_res_count)) * 100, 1) if tot_res_count > 0 else 0.0

        # Assigned resources: derived from incidents assigned teams or persisted run_metrics
        assigned_team_count = len(set(inc.get("assigned_team_id") for inc in incidents if inc.get("assigned_team_id")))
        assignment_rate_pct = None
        if rm_row and "resource_assignment_rate_pct" in rm_row.keys() and rm_row["resource_assignment_rate_pct"] is not None:
            assignment_rate_pct = rm_row["resource_assignment_rate_pct"]
        elif rm_row and rm_row["resource_utilization"] is not None:
            try:
                assignment_rate_pct = float(str(rm_row["resource_utilization"]).replace("%", "").strip())
            except Exception:
                pass
        if assignment_rate_pct is None:
            assignment_rate_pct = round((assigned_team_count / max(1, tot_res_count)) * 100, 1) if tot_res_count > 0 else 0.0

        # 5. Planned route ETA vs actual response time (strictly separated)
        planned_eta_mins = None
        if rm_row and "planned_route_eta_mins" in rm_row.keys() and rm_row["planned_route_eta_mins"] is not None:
            planned_eta_mins = rm_row["planned_route_eta_mins"]
        else:
            etas = [inc.get("route_eta_hours") for inc in incidents if inc.get("route_eta_hours") is not None]
            planned_eta_mins = round((sum(etas) / len(etas)) * 60, 1) if etas else None

        # Check for actual dispatch-to-arrival timestamps in incident_timeline
        conn = database.get_connection()
        resp_row = conn.execute(
            """
            SELECT AVG((julianday(t2.timestamp) - julianday(t1.timestamp)) * 86400) as avg_sec
            FROM incident_timeline t1
            JOIN incident_timeline t2 ON t1.incident_id = t2.incident_id
            JOIN incidents i ON i.incident_id = t1.incident_id
            WHERE i.run_id = ? AND t1.new_status = 'DISPATCHED' AND t2.new_status = 'ARRIVED'
            """,
            (run_id,)
        ).fetchone()
        conn.close()
        actual_resp_mins = None
        if rm_row and "actual_response_time_mins" in rm_row.keys() and rm_row["actual_response_time_mins"] is not None:
            actual_resp_mins = rm_row["actual_response_time_mins"]
        elif resp_row and resp_row["avg_sec"] is not None:
            actual_resp_mins = round(float(resp_row["avg_sec"]) / 60, 1)

        # 6. Severe incident severity
        sev_counts = {"high": 0, "medium": 0, "low": 0}
        for inc in incidents:
            s = str(inc.get("severity", "low")).lower()
            if s in sev_counts:
                sev_counts[s] += 1
        curr_severity = "HIGH" if sev_counts["high"] > 0 else "MEDIUM" if sev_counts["medium"] > 0 else "LOW"

        # 7. Weather sample
        sample_lat = incidents[0].get("latitude") if incidents else None
        sample_lng = incidents[0].get("longitude") if incidents else None
        w_data = get_weather(sample_lat, sample_lng)

        # 8. Calculate Simulation Performance Score heuristic
        from utils.metrics import calculate_simulation_performance_score
        score_data = calculate_simulation_performance_score(
            rescue_rate_pct=rescue_rate_pct,
            casualty_rate_pct=casualty_rate_pct,
            resource_assignment_rate_pct=assignment_rate_pct,
            planned_route_eta_mins=planned_eta_mins,
        )
        sim_score = None
        if rm_row and "simulation_performance_score" in rm_row.keys() and rm_row["simulation_performance_score"] is not None:
            sim_score = rm_row["simulation_performance_score"]
        else:
            sim_score = score_data.get("score")

        return {
            "status": "success",
            "run_id": run_id,
            "metrics": {
                "total_victims": total_victims,
                "victims_rescued": victims_rescued,
                "rescued_victims": victims_rescued,
                "victims_waiting": victims_waiting,
                "waiting_victims": victims_waiting,
                "casualties": casualties_count,
                "casualties_count": casualties_count,
                "rescue_rate_pct": rescue_rate_pct,
                "casualty_rate_pct": casualty_rate_pct,
                "available_ambulances": avail_amb,
                "total_ambulances": len(ambulances),
                "available_fire_trucks": avail_fire,
                "total_fire_trucks": len(fire_trucks),
                "available_police": avail_pol,
                "total_police": len(police),
                "hospital_capacity_pct": hosp_cap_pct,
                "shelter_capacity_pct": shelter_cap_pct,
                "blocked_roads_count": len(blocked),
                "road_status": f"{len(blocked)} Highways Blocked" if blocked else "Normal Traffic Flow",
                "weather_temp": w_data.get('temperature'),
                "weather_desc": w_data.get("description"),
                "rainfall_mm": w_data.get('rainfall_mm'),
                "current_severity": curr_severity,
                "mission_progress_pct": progress_pct,
                "estimated_completion": eta_str,
                "resource_assignment_rate_pct": assignment_rate_pct,
                "active_resource_utilization_pct": active_util_pct,
                "resource_utilization": assignment_rate_pct,
                "mission_success_rate": sim_score if sim_score is not None else rescue_rate_pct,
                "simulation_performance_score": sim_score,
                "overall_score": sim_score,
                "score_details": score_data,
                "planned_route_eta_mins": planned_eta_mins,
                "actual_response_time_mins": actual_resp_mins,
                "avg_response_time": actual_resp_mins,
                "total_resources": tot_res_count,
                "busy_resources": busy_res_count,
                "total_incidents": len(incidents),
                "critical_incidents": sev_counts["high"],
                "hospitals": [{"name": h.get("facility_name"), "total": h.get("total_capacity"), "available": h.get("available_capacity"), "capacity_status": "VERIFIED" if h.get("total_capacity") is not None else "UNAVAILABLE"} for h in hospitals],
                "shelters": [{"name": s.get("facility_name"), "total": s.get("total_capacity"), "available": s.get("available_capacity"), "capacity_status": "VERIFIED" if s.get("total_capacity") is not None else "UNAVAILABLE"} for s in shelters],
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/run/{run_id}/resources")
def get_run_resources(run_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    resources = get_simulation_resources(run_id)
    return {"status": "success", "run_id": run_id, "resources": resources}


class IncidentStatusUpdate(BaseModel):
    status: str
    reason: Optional[str] = None


@app.put("/api/incidents/{incident_id}/status")
def update_status(
    incident_id: int,
    request: IncidentStatusUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Update incident status with validation and record timeline audit. Broadcasts change via WebSocket."""
    new_status = request.status.upper().strip()
    if new_status not in VALID_INCIDENT_STATUSES:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": f"Invalid status. Must be one of: {', '.join(sorted(VALID_INCIDENT_STATUSES))}"}
        )
    operator_name = current_user.get("name", "System Operator")
    operator_id = current_user.get("user_id")
    updated = update_incident_status(
        incident_id,
        new_status,
        operator_name=operator_name,
        operator_id=operator_id,
        reason=request.reason,
    )
    if not updated:
        return JSONResponse(status_code=404, content={"status": "error", "message": f"Incident {incident_id} not found."})

    timeline = get_incident_timeline(incident_id)

    # Broadcast via WebSocket
    broadcast_sync({
        "type": "INCIDENT_STATUS_CHANGED",
        "incident_id": incident_id,
        "new_status": new_status,
        "incident": updated,
        "timeline": timeline,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })
    return {"status": "success", "incident": updated, "timeline": timeline}


@app.get("/api/incidents/{incident_id}/timeline")
def incident_timeline_endpoint(
    incident_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Return chronological audit timeline for an incident."""
    return {"status": "success", "incident_id": incident_id, "timeline": get_incident_timeline(incident_id)}


@app.get("/api/analytics/overview")
def analytics_overview(
    run_id: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """High-level operational metrics overview."""
    return {
        "status": "success",
        "incidents": get_incident_analytics(run_id),
        "resources": get_resource_analytics(run_id),
        "intelligence": get_intelligence_analytics(),
        "performance": get_response_performance_analytics(run_id),
    }


@app.get("/api/analytics/incidents")
def analytics_incidents(
    run_id: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Incident breakdown and time series analytics."""
    return {"status": "success", "analytics": get_incident_analytics(run_id)}


@app.get("/api/analytics/resources")
def analytics_resources(
    run_id: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Resource allocation and facility occupancy analytics."""
    return {"status": "success", "analytics": get_resource_analytics(run_id)}


@app.get("/api/analytics/intelligence")
def analytics_intelligence(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """External intelligence feeds and source health analytics."""
    return {"status": "success", "analytics": get_intelligence_analytics()}


@app.get("/api/analytics/performance")
def analytics_performance(
    run_id: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Response time and mission success performance analytics."""
    return {"status": "success", "analytics": get_response_performance_analytics(run_id)}


@app.get("/api/analytics/quality")
def analytics_quality(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Data quality and SQLite database integrity metrics."""
    return {"status": "success", "metrics": get_data_quality_metrics()}


class TacticalEvaluationRequest(BaseModel):
    incident_id: Optional[int] = None
    incident: Optional[Dict[str, Any]] = None
    run_id: Optional[str] = None


@app.post("/api/tactical/evaluate")
def evaluate_tactical(
    request: TacticalEvaluationRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Compute transparent tactical recommendations based on incident, fleet, and facilities."""
    from utils.tactical_decision import evaluate_tactical_decision
    from weather_service import get_weather

    inc_data = request.incident
    if not inc_data and request.incident_id:
        from database import get_incident_by_id
        inc_data = get_incident_by_id(request.incident_id)

    if not inc_data:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Incident data or valid incident_id required."})

    run_id = request.run_id or inc_data.get("run_id") or "demo"
    facilities = get_facilities(run_id)
    fleet = get_simulation_resources(run_id)
    roadblocks = get_blocked_roads(run_id)
    earthquakes = database.get_external_disaster_events(source="USGS", limit=20)
    w_data = get_weather(inc_data.get("latitude"), inc_data.get("longitude"))

    # Phase P3.2 Impact Assessment Integration
    impact_assessment = None
    event_id = str(inc_data.get("incident_id") or "")
    if event_id:
        impact_assessment = database.get_impact_assessment(event_id=event_id)
    if not impact_assessment and inc_data.get("latitude") is not None and inc_data.get("longitude") is not None:
        try:
            from intelligence.impact_engine import calculate_disaster_impact
            impact_assessment = calculate_disaster_impact(
                latitude=float(inc_data["latitude"]),
                longitude=float(inc_data["longitude"]),
                disaster_type=inc_data.get("disaster_type", "incident"),
                event_id=event_id or f"INC-{inc_data.get('incident_id', 'EOC')}",
            )
        except Exception as e:
            logger.warning(f"Tactical impact calculation fallback skipped: {e}")

    eval_result = evaluate_tactical_decision(
        incident=inc_data,
        facilities=facilities,
        fleet=fleet,
        roadblocks=roadblocks,
        weather=w_data,
        earthquakes=earthquakes,
        impact_assessment=impact_assessment,
    )
    return {"status": "success", "evaluation": eval_result}


@app.get("/api/run/{run_id}/summary")
def run_summary(run_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Aggregated dashboard data in a single request for the EOC Command Overview."""
    try:
        summary = get_run_summary(run_id)
        return {"status": "success", **summary}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/run/{run_id}/facilities")
def get_run_facilities(run_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    facilities = get_facilities(run_id)
    return {"status": "success", "run_id": run_id, "facilities": facilities}


@app.get("/api/run/{run_id}/zones")
def get_run_zones(run_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    zones = get_disaster_zones(run_id)
    return {"status": "success", "run_id": run_id, "zones": zones}


@app.get("/api/run/{run_id}/blocked-roads")
def get_run_blocked_roads(run_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    blocked = get_blocked_roads(run_id)
    return {"status": "success", "run_id": run_id, "blocked_roads": blocked}


@app.get("/api/weather/{lat}/{lng}")
def get_weather_endpoint(lat: float, lng: float):
    w_data = get_weather(lat, lng)
    impact = compute_weather_impact(w_data, "general")
    return {"status": "success", "weather": w_data, "impact": impact}


@app.get("/api/analytics/summary")
def analytics_summary(current_user: Dict[str, Any] = Depends(get_current_user)):
    return get_analytics_summary()


@app.get("/api/suggestions")
def suggestions(seed: int | None = None, current_user: Dict[str, Any] = Depends(get_current_user)):
    return get_smart_suggestions(current_seed=seed)


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "2.0"}


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    role: str = "operator"


@app.post("/api/auth/register")
def register(request: RegisterRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    requested_role = (request.role or "operator").strip().lower()
    if requested_role in ("admin", "administrator"):
        if current_user.get("role") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Administrative privileges required to create admin accounts.",
            )
        assigned_role = "admin"
    else:
        assigned_role = "operator"

    try:
        user_id = create_user_in_db(request.name, request.email, request.password, assigned_role)
        return {"status": "success", "user_id": user_id}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/admin/users")
def list_users(current_user: Dict[str, Any] = Depends(require_admin)):
    return {"users": get_users()}


@app.delete("/api/admin/users/{user_id}")
def remove_user(user_id: int, current_user: Dict[str, Any] = Depends(require_admin)):
    delete_user(user_id)
    return {"status": "success"}


class RoleUpdateRequest(BaseModel):
    role: str


@app.put("/api/admin/users/{user_id}/role")
def change_role(user_id: int, request: RoleUpdateRequest, current_user: Dict[str, Any] = Depends(require_admin)):
    update_user_role(user_id, request.role)
    return {"status": "success"}


@app.get("/api/admin/config")
def get_config(current_user: Dict[str, Any] = Depends(require_admin)):
    return get_system_config()


@app.post("/api/admin/config")
def set_config(configs: Dict[str, str], current_user: Dict[str, Any] = Depends(require_admin)):
    update_system_config(configs)
    return {"status": "success"}


class CustomIncidentRequest(BaseModel):
    location: str
    severity: str
    people_affected: int
    disaster_type: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    @field_validator("people_affected")
    @classmethod
    def validate_affected(cls, v):
        if type(v) is not int or v < 1:
            raise ValueError("people_affected must be a positive integer >= 1.")
        return v

    @field_validator("latitude")
    @classmethod
    def validate_lat(cls, v):
        if v is not None:
            if type(v) not in (int, float) or math.isnan(v) or math.isinf(v) or not (-90.0 <= float(v) <= 90.0):
                raise ValueError("latitude must be a finite number between -90 and 90.")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_lng(cls, v):
        if v is not None:
            if type(v) not in (int, float) or math.isnan(v) or math.isinf(v) or not (-180.0 <= float(v) <= 180.0):
                raise ValueError("longitude must be a finite number between -180 and 180.")
        return v


@app.post("/api/incidents/custom")
def report_custom(request: CustomIncidentRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    if request.latitude is not None and not (-90.0 <= request.latitude <= 90.0):
        return {"status": "error", "message": "Latitude must be between -90 and 90 degrees."}
    if request.longitude is not None and not (-180.0 <= request.longitude <= 180.0):
        return {"status": "error", "message": "Longitude must be between -180 and 180 degrees."}
    if request.people_affected < 0:
        return {"status": "error", "message": "People affected cannot be negative."}

    save_custom_incident(
        location=request.location,
        severity=request.severity,
        people_affected=max(0, request.people_affected),
        disaster_type=request.disaster_type,
        latitude=request.latitude,
        longitude=request.longitude,
    )
    return {"status": "success"}


@app.get("/api/incidents/custom")
def list_custom(current_user: Dict[str, Any] = Depends(get_current_user)):
    return {"incidents": get_custom_incidents()}


@app.post("/api/incidents/custom/clear")
def clear_custom(current_user: Dict[str, Any] = Depends(get_current_user)):
    clear_custom_incidents()
    return {"status": "success"}


@app.post("/api/ml/train")
def trigger_ml_training(background_tasks: BackgroundTasks, current_user: Dict[str, Any] = Depends(get_current_user)):
    def _train():
        try:
            from ml.train_severity_model import train_model
            report = train_model()
            save_ml_model_meta(
                model_name=report["model_name"],
                model_path="ml/models/severity_model.joblib",
                accuracy=report["accuracy"],
                f1=report["f1_weighted"],
                training_samples=report["training_samples"],
            )
            from ml.predictor import get_predictor
            import ml.predictor as pred_mod
            pred_mod._singleton = None
        except Exception as e:
            import traceback
            traceback.print_exc()

    background_tasks.add_task(_train)
    return {"status": "training_started", "message": "Model training initiated in background."}


@app.get("/api/ml/status")
def ml_status(current_user: Dict[str, Any] = Depends(get_current_user)):
    model_info = get_active_ml_model()
    if model_info:
        return {"status": "active", "model": model_info}
    return {"status": "no_model", "message": "No trained model found."}


@app.get("/api/teams")
def list_teams(current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        teams = get_rescue_teams()
        if teams:
            return {"status": "success", "teams": teams}
    except Exception:
        pass
    return {"status": "success", "teams": []}


@app.get("/api/incidents/geo/{run_id}")
def incidents_geo(run_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        incidents = get_incidents_by_run(run_id)
        return {"status": "success", "incidents": incidents}
    except Exception as e:
        return {"status": "error", "message": str(e), "incidents": []}


@app.get("/api/run/{run_id}/messages")
def run_messages(run_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    return {"run_id": run_id, "messages": get_agent_messages(run_id)}


@app.get("/api/run/{run_id}/export/csv")
def export_csv(run_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        from utils.report_generator import generate_csv_report
        csv_data = generate_csv_report(run_id)
        if csv_data.startswith("error"):
            return JSONResponse(status_code=404, content={"status": "error", "message": f"Run ID {run_id} not found."})
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=run_{run_id}_report.csv"}
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


class CitizenReportRequest(BaseModel):
    location: str
    latitude: float
    longitude: float
    disaster_type: str
    people_affected: int = 1
    severity: str = "high"
    sos_type: str = "SOS"
    media_url: Optional[str] = ""
    description: Optional[str] = ""

    @field_validator("location")
    @classmethod
    def validate_location(cls, v):
        if not v or not v.strip():
            raise ValueError("location must not be empty.")
        if len(v.strip()) > 200:
            raise ValueError("location must not exceed 200 characters.")
        return v.strip()

    @field_validator("disaster_type")
    @classmethod
    def validate_disaster_type(cls, v):
        if not v or not v.strip():
            raise ValueError("disaster_type must not be empty.")
        if len(v.strip()) > 50:
            raise ValueError("disaster_type must not exceed 50 characters.")
        return v.strip()

    @field_validator("people_affected")
    @classmethod
    def validate_affected(cls, v):
        if type(v) is not int or v < 1:
            raise ValueError("people_affected must be a positive integer >= 1.")
        return v

    @field_validator("latitude")
    @classmethod
    def validate_lat(cls, v):
        if type(v) not in (int, float) or math.isnan(v) or math.isinf(v) or not (-90.0 <= float(v) <= 90.0):
            raise ValueError("latitude must be a finite number between -90 and 90.")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_lng(cls, v):
        if type(v) not in (int, float) or math.isnan(v) or math.isinf(v) or not (-180.0 <= float(v) <= 180.0):
            raise ValueError("longitude must be a finite number between -180 and 180.")
        return v

    @field_validator("media_url")
    @classmethod
    def validate_media_url(cls, v):
        if v is None:
            return ""
        v = v.strip()
        if not v:
            return ""
        if len(v) > 500:
            raise ValueError("media_url must not exceed 500 characters.")
        parsed = urlparse(v)
        if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
            raise ValueError("media_url must be a valid http or https URL.")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v):
        if v is None:
            return ""
        v = v.strip()
        if len(v) > 2000:
            raise ValueError("description must not exceed 2000 characters.")
        if "\x00" in v:
            raise ValueError("description must not contain null bytes.")
        return v


@app.post("/api/incidents/citizen-report")
def submit_citizen_report(request: CitizenReportRequest):
    if not (-90.0 <= request.latitude <= 90.0):
        return {"status": "error", "message": "Latitude must be between -90 and 90 degrees."}
    if not (-180.0 <= request.longitude <= 180.0):
        return {"status": "error", "message": "Longitude must be between -180 and 180 degrees."}
    if request.people_affected < 0:
        return {"status": "error", "message": "People affected cannot be negative."}

    try:
        from database import save_citizen_report
        report_id = save_citizen_report(
            location=request.location,
            latitude=request.latitude,
            longitude=request.longitude,
            disaster_type=request.disaster_type,
            people_affected=request.people_affected,
            severity=request.severity,
            sos_type=request.sos_type,
            media_url=request.media_url or "",
            description=request.description or "",
            status="pending_review",
        )

        return {
            "status": "success",
            "report_id": report_id,
            "message": "SOS Citizen Report recorded. Stored for operator review.",
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/incidents/citizen-reports")
def list_citizen_reports(current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        from database import get_citizen_reports
        return {"status": "success", "reports": get_citizen_reports()}
    except Exception as e:
        return {"status": "error", "message": str(e), "reports": []}


@app.get("/api/run/{run_id}/export/json")
def export_json(run_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        from utils.report_generator import generate_json_report
        json_data = generate_json_report(run_id)
        if "not found" in json_data:
            return JSONResponse(status_code=404, content={"status": "error", "message": f"Run ID {run_id} not found."})
        return Response(
            content=json_data,
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=run_{run_id}_telemetry.json"}
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.get("/api/run/{run_id}/export/pdf")
def export_pdf(run_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        from utils.report_generator import get_run_details, generate_pdf_report
        data = get_run_details(run_id)
        if not data:
            return JSONResponse(status_code=404, content={"status": "error", "message": f"Run ID {run_id} not found."})
        import io
        pdf_buffer = io.BytesIO()
        generate_pdf_report(run_id, pdf_buffer)
        pdf_buffer.seek(0)
        return Response(
            content=pdf_buffer.getvalue(),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=run_{run_id}_report.pdf"}
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


_last_message_bus = None


def set_last_message_bus(bus):
    global _last_message_bus
    _last_message_bus = bus


@app.get("/api/agents/health")
def agents_health(run_id: Optional[str] = None, current_user: Dict[str, Any] = Depends(get_current_user)):
    if _last_message_bus is not None and (not run_id or _last_message_bus.run_id == run_id):
        try:
            status = _last_message_bus.get_health_status()
            if status and any(a.get("messages_processed", 0) > 0 for a in status):
                return {"agents": status}
        except Exception:
            pass
    try:
        return {"agents": get_db_agent_telemetry(run_id=run_id)}
    except Exception:
        return {"agents": []}


@app.get("/api/live-feed/gdacs")
def gdacs_feed():
    try:
        from weather_service import get_gdacs_alerts
        return {"status": "success", "alerts": get_gdacs_alerts()}
    except Exception as e:
        return {"status": "error", "message": str(e), "alerts": []}


@app.get("/api/live-feed/usgs")
def usgs_feed():
    try:
        from weather_service import get_usgs_earthquakes
        return {"status": "success", "earthquakes": get_usgs_earthquakes()}
    except Exception as e:
        return {"status": "error", "message": str(e), "earthquakes": []}


@app.get("/api/geocode/{lat}/{lng}")
def geocode_endpoint(lat: float, lng: float):
    if math.isnan(lat) or math.isnan(lng) or math.isinf(lat) or math.isinf(lng):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": "error", "message": "Coordinates must be finite numbers."},
        )
    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lng <= 180.0):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": "error", "message": "Latitude must be in [-90, 90] and longitude in [-180, 180]."},
        )
    try:
        from weather_service import reverse_geocode
        address = reverse_geocode(lat, lng)
        return {"status": "success", "address": address, "latitude": lat, "longitude": lng}
    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
