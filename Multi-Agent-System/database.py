"""Enhanced SQLite schema & database layer for Multi-Agent Disaster Management System."""

import hashlib
import json
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = str(Path(__file__).resolve().parent / "state_history.db")


def hash_password(password: str) -> str:
    """Hash password securely using PBKDF2-HMAC-SHA256 with a unique per-password cryptographic salt."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 100000).hex()
    return f"pbkdf2_sha256${salt}${key}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify password against stored hash with PBKDF2-SHA256 and backward-compatible legacy support."""
    if not password or not stored_hash:
        return False
    if stored_hash.startswith("pbkdf2_sha256$"):
        parts = stored_hash.split("$")
        if len(parts) != 3:
            return False
        salt = parts[1]
        expected_key = parts[2]
        try:
            computed_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 100000).hex()
            return secrets.compare_digest(computed_key, expected_key)
        except Exception:
            return False
    else:
        # Backward-compatible check for legacy static-salt SHA-256 hashes
        legacy_salt = "DisasterOS_Secure_Salt_2026"
        legacy_hash = hashlib.sha256((password + legacy_salt).encode("utf-8")).hexdigest()
        return secrets.compare_digest(legacy_hash, stored_hash)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA busy_timeout = 30000;")
    except Exception:
        pass
    return conn


def resolve_run_id(run_id: Optional[str]) -> Optional[str]:
    """Resolve a potentially truncated run_id (e.g. 8-char prefix from UI) to its canonical run_id."""
    if not run_id or str(run_id).strip() in ("", "demo", "null", "undefined"):
        return run_id
    clean_id = str(run_id).strip()
    try:
        conn = get_connection()
        exact = conn.execute("SELECT run_id FROM simulation_runs WHERE run_id = ? LIMIT 1", (clean_id,)).fetchone()
        if exact:
            conn.close()
            return exact["run_id"]
        prefix = conn.execute(
            "SELECT run_id FROM simulation_runs WHERE run_id LIKE ? ORDER BY rowid DESC LIMIT 1",
            (f"{clean_id}%",)
        ).fetchone()
        conn.close()
        if prefix:
            return prefix["run_id"]
    except Exception:
        pass
    return clean_id


def should_seed_demo_users() -> bool:
    """Whether init_db should create/reset built-in demo accounts (default: enabled)."""
    raw = os.environ.get("SEED_DEMO_USERS")
    if raw is None:
        return True
    token = raw.strip().lower()
    if not token:
        return True
    if token in ("1", "true", "yes", "on"):
        return True
    if token in ("0", "false", "no", "off"):
        return False
    return True


def _seed_default_demo_users(cursor: sqlite3.Cursor) -> None:
    """Insert or refresh built-in demo operator/admin accounts (PBKDF2 hashed)."""
    default_users = [
        (1, "System Operator", "operator@disaster.local", "operator123", "operator"),
        (2, "Admin User", "admin@disaster.local", "admin123", "admin"),
    ]
    for uid, name, email, raw_pw, role in default_users:
        existing = cursor.execute("SELECT password FROM users WHERE user_id = ?", (uid,)).fetchone()
        if not existing or not verify_password(raw_pw, existing["password"]):
            cursor.execute(
                "INSERT OR REPLACE INTO users (user_id, name, email, password, role) VALUES (?, ?, ?, ?, ?)",
                (uid, name, email, hash_password(raw_pw), role),
            )


def init_db() -> None:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL;")
    except Exception:
        pass

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(120) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            role VARCHAR(20) DEFAULT 'operator'
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS simulation_runs (
            run_id TEXT PRIMARY KEY,
            user_id INTEGER,
            seed INTEGER NOT NULL,
            strategy VARCHAR(20) DEFAULT 'smart',
            status VARCHAR(20) DEFAULT 'RUNNING',
            started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            completed_at DATETIME,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS incidents (
            incident_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            location VARCHAR(120),
            latitude REAL,
            longitude REAL,
            severity VARCHAR(20),
            people_affected INTEGER,
            disaster_type VARCHAR(50),
            priority VARCHAR(20),
            estimated_risk VARCHAR(20),
            ml_predicted_severity VARCHAR(20),
            ml_confidence REAL,
            assigned_team_id TEXT,
            route_path TEXT,
            route_coordinates TEXT,
            route_distance_km REAL,
            route_eta_hours REAL,
            route_source TEXT,
            route_provider TEXT,
            allocation_score REAL,
            allocation_explanation TEXT,
            FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            agent_name VARCHAR(60) NOT NULL,
            state VARCHAR(40) NOT NULL,
            output_json TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS run_metrics (
            metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT UNIQUE NOT NULL,
            total_incidents INTEGER,
            total_affected INTEGER,
            total_lives_saved INTEGER,
            overall_efficiency VARCHAR(20),
            avg_response_time VARCHAR(30),
            resource_utilization VARCHAR(20),
            planned_route_eta_mins REAL,
            actual_response_time_mins REAL,
            status VARCHAR(20),
            FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id)
        )
        """
    )

    try:
        cursor.execute("ALTER TABLE agent_logs ADD COLUMN execution_time_ms REAL")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE run_metrics ADD COLUMN planned_route_eta_mins REAL")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE run_metrics ADD COLUMN actual_response_time_mins REAL")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE run_metrics ADD COLUMN resource_assignment_rate_pct REAL")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE run_metrics ADD COLUMN active_resource_utilization_pct REAL")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE run_metrics ADD COLUMN total_victims INTEGER")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE run_metrics ADD COLUMN rescued_victims INTEGER")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE run_metrics ADD COLUMN waiting_victims INTEGER")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE run_metrics ADD COLUMN casualties INTEGER")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE run_metrics ADD COLUMN rescue_rate_pct REAL")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE run_metrics ADD COLUMN casualty_rate_pct REAL")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE run_metrics ADD COLUMN simulation_performance_score REAL")
    except Exception:
        pass

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS external_disaster_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            source_event_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            severity TEXT,
            classification TEXT DEFAULT 'LIVE',
            latitude REAL,
            longitude REAL,
            magnitude REAL,
            place TEXT,
            observed_at DATETIME,
            fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            raw_payload TEXT,
            UNIQUE(source, source_event_id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS source_health_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name TEXT NOT NULL,
            status TEXT NOT NULL,
            response_time_ms REAL,
            error_message TEXT,
            record_count INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS run_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            state TEXT NOT NULL,
            payload TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS incident_timeline (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id INTEGER NOT NULL,
            previous_status TEXT,
            new_status TEXT NOT NULL,
            operator_name TEXT,
            operator_id INTEGER,
            reason TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (incident_id) REFERENCES incidents(incident_id)
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_incident_timeline_inc_id ON incident_timeline(incident_id);")

    # ── Phase P3.1 Real Facility & Geographic Cache Tables ───────────────────
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS external_facilities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            facility_id TEXT UNIQUE NOT NULL,
            facility_type TEXT NOT NULL,
            name TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            address TEXT,
            city TEXT,
            source TEXT NOT NULL,
            source_id TEXT,
            classification TEXT DEFAULT 'LIVE',
            capacity INTEGER,
            available_capacity INTEGER,
            capacity_status TEXT DEFAULT 'UNAVAILABLE',
            phone TEXT,
            emergency_service INTEGER DEFAULT 1,
            metadata_json TEXT,
            fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ext_facilities_type ON external_facilities(facility_type);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ext_facilities_coords ON external_facilities(latitude, longitude);")

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS geographic_cache (
            cache_key TEXT PRIMARY KEY,
            query_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME NOT NULL
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_geo_cache_expires ON geographic_cache(expires_at);")

    # ── Phase P3.2 Impact Analysis Assessment Table ──────────────────────────
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS impact_assessments (
            assessment_id TEXT PRIMARY KEY,
            source_event_id TEXT NOT NULL,
            source_event_type TEXT NOT NULL,
            epicenter_lat REAL NOT NULL,
            epicenter_lng REAL NOT NULL,
            magnitude REAL,
            depth_km REAL,
            max_radius_km REAL NOT NULL,
            impact_zones_json TEXT,
            facilities_json TEXT,
            summary_json TEXT,
            route_accessibility_status TEXT DEFAULT 'CLEAR',
            methodology TEXT NOT NULL,
            assumptions_json TEXT,
            limitations_json TEXT,
            confidence TEXT,
            calculated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_impact_source_event ON impact_assessments(source_event_id);")

    # ── Phase P3.3 Compound Events & Cascading Hazards Table ─────────────────
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS compound_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            compound_id TEXT UNIQUE NOT NULL,
            correlation_type TEXT NOT NULL,
            primary_event_id TEXT NOT NULL,
            secondary_event_id TEXT,
            secondary_event_type TEXT,
            confidence_score REAL NOT NULL,
            cascade_risk_level TEXT NOT NULL,
            classification TEXT DEFAULT 'CALCULATED',
            affected_facilities_json TEXT,
            cascade_chain_json TEXT,
            recommendations_json TEXT,
            trigger_parameters_json TEXT,
            detected_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_compound_type ON compound_events(correlation_type);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_compound_primary ON compound_events(primary_event_id);")

    # ── Phase P3.4 Evacuation Corridors Table ────────────────────────────────
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS evacuation_corridors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            corridor_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            profile TEXT NOT NULL,
            profile_label TEXT,
            status TEXT NOT NULL,
            origin_lat REAL NOT NULL,
            origin_lng REAL NOT NULL,
            dest_lat REAL NOT NULL,
            dest_lng REAL NOT NULL,
            distance_km REAL NOT NULL,
            transit_time_minutes INTEGER NOT NULL,
            population_to_evacuate INTEGER NOT NULL,
            bottleneck_throughput_per_hour INTEGER NOT NULL,
            estimated_clearance_hours REAL NOT NULL,
            path_coordinates_json TEXT,
            hazard_intersections_json TEXT,
            safety_tier TEXT NOT NULL,
            classification TEXT DEFAULT 'CALCULATED',
            route_provider TEXT DEFAULT 'CALCULATED',
            route_type TEXT DEFAULT 'GRAPH_ESTIMATE',
            methodology TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_corridor_status ON evacuation_corridors(status);")

    if should_seed_demo_users():
        _seed_default_demo_users(cursor)

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS system_config (
            key VARCHAR(50) PRIMARY KEY,
            value VARCHAR(255) NOT NULL
        )
        """
    )

    default_configs = [
        ("high_severity_teams", "8"),
        ("low_severity_teams", "3"),
        ("smart_team_capacity", "18"),
        ("baseline_team_capacity", "12"),
        ("smart_loss_factor", "0.08"),
        ("baseline_loss_factor", "0.22")
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO system_config (key, value) VALUES (?, ?)",
        default_configs,
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS custom_incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location VARCHAR(120) NOT NULL,
            latitude REAL,
            longitude REAL,
            severity VARCHAR(20) NOT NULL,
            people_affected INTEGER NOT NULL,
            disaster_type VARCHAR(50) NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS citizen_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location VARCHAR(120) NOT NULL,
            latitude REAL,
            longitude REAL,
            severity VARCHAR(20) DEFAULT 'high',
            people_affected INTEGER DEFAULT 1,
            disaster_type VARCHAR(50) NOT NULL,
            sos_type VARCHAR(50) DEFAULT 'SOS',
            media_url TEXT,
            description TEXT,
            status VARCHAR(20) DEFAULT 'pending_validation',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            sender VARCHAR(60) NOT NULL,
            receiver VARCHAR(60) NOT NULL,
            message_type VARCHAR(30) NOT NULL,
            payload TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ml_models (
            model_id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_name VARCHAR(100) NOT NULL,
            model_path VARCHAR(255) NOT NULL,
            accuracy REAL,
            f1_score REAL,
            training_samples INTEGER,
            trained_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS rescue_teams (
            team_id VARCHAR(50) PRIMARY KEY,
            team_name VARCHAR(100) NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            status VARCHAR(20) DEFAULT 'available',
            capacity INTEGER DEFAULT 10,
            specialization VARCHAR(50)
        )
        """
    )

    # ── Hybrid Dynamic Simulation Tables ───────────────────────
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS simulation_resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            resource_id VARCHAR(50) NOT NULL,
            resource_name VARCHAR(100) NOT NULL,
            resource_type VARCHAR(50) NOT NULL,
            city VARCHAR(100),
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            status VARCHAR(30) DEFAULT 'available',
            capacity INTEGER DEFAULT 4,
            specialization VARCHAR(50),
            speed_kmh REAL DEFAULT 60.0,
            heading REAL DEFAULT 0.0,
            assigned_incident TEXT,
            current_eta_min REAL DEFAULT 0.0
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS facilities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            facility_id VARCHAR(50) NOT NULL,
            facility_name VARCHAR(100) NOT NULL,
            facility_type VARCHAR(50) NOT NULL,
            city VARCHAR(100),
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            total_capacity INTEGER DEFAULT 100,
            available_capacity INTEGER DEFAULT 100,
            status VARCHAR(30) DEFAULT 'operational',
            phone VARCHAR(30)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS blocked_roads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            blockage_id VARCHAR(30) NOT NULL,
            from_city VARCHAR(100) NOT NULL,
            to_city VARCHAR(100) NOT NULL,
            reason VARCHAR(150),
            status VARCHAR(30) DEFAULT 'blocked'
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS disaster_zones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            zone_id VARCHAR(50) NOT NULL,
            zone_name VARCHAR(100) NOT NULL,
            zone_type VARCHAR(50) NOT NULL,
            center_latitude REAL NOT NULL,
            center_longitude REAL NOT NULL,
            radius_meters REAL DEFAULT 20000.0,
            color VARCHAR(30),
            opacity REAL DEFAULT 0.2
        )
        """
    )

    # Performance B-Tree Indexes for sub-millisecond queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_incidents_run_id ON incidents(run_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_agent_logs_run_agent ON agent_logs(run_id, agent_name);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sim_resources_run_id ON simulation_resources(run_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_facilities_run_id ON facilities(run_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_zones_run_id ON disaster_zones(run_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_blocked_roads_run_id ON blocked_roads(run_id);")

    # Seed default rescue teams
    default_teams = [
        ("team-alpha", "Alpha Response Unit", 19.076, 72.878, "available", 12, "flood"),
        ("team-bravo", "Bravo Medical Corps", 28.644, 77.216, "available", 10, "medical"),
        ("team-charlie", "Charlie Fire Brigade", 12.972, 77.595, "available", 8, "fire"),
        ("team-delta", "Delta Search & Rescue", 22.573, 88.364, "available", 15, "earthquake"),
        ("team-echo", "Echo Cyclone Unit", 13.083, 80.271, "available", 10, "cyclone"),
        ("team-foxtrot", "Foxtrot Rapid Response", 17.385, 78.487, "available", 12, "general"),
        ("team-golf", "Golf Airlift Squad", 26.912, 75.787, "available", 6, "airlift"),
        ("team-hotel", "Hotel Engineering Corps", 23.023, 72.571, "available", 10, "infrastructure"),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO rescue_teams (team_id, team_name, latitude, longitude, status, capacity, specialization) VALUES (?, ?, ?, ?, ?, ?, ?)",
        default_teams,
    )

    _migrate_existing_tables(cursor)

    conn.commit()
    conn.close()


# Valid incident statuses for validation
VALID_INCIDENT_STATUSES = {"NEW", "ASSESSED", "RESPONDING", "CONTAINED", "RESOLVED"}


def _migrate_existing_tables(cursor) -> None:
    """Add new columns to existing tables safely."""
    cursor.execute("PRAGMA table_info(incidents)")
    incident_cols = {row[1] for row in cursor.fetchall()}
    for col, ctype in [("latitude", "REAL"), ("longitude", "REAL"),
                       ("ml_predicted_severity", "VARCHAR(20)"),
                       ("ml_confidence", "REAL"),
                       ("assigned_team_id", "TEXT"),
                       ("route_path", "TEXT"),
                       ("route_coordinates", "TEXT"),
                       ("route_distance_km", "REAL"),
                       ("route_eta_hours", "REAL"),
                       ("route_source", "TEXT"),
                       ("route_provider", "TEXT"),
                       ("allocation_score", "REAL"),
                       ("allocation_explanation", "TEXT")]:
        if col not in incident_cols:
            cursor.execute(f"ALTER TABLE incidents ADD COLUMN {col} {ctype}")

    if "location_unverified" not in incident_cols:
        cursor.execute("ALTER TABLE incidents ADD COLUMN location_unverified INTEGER DEFAULT 0")

    # Add status column to incidents if missing
    if "status" not in incident_cols:
        cursor.execute("ALTER TABLE incidents ADD COLUMN status VARCHAR(20) DEFAULT 'NEW'")
        # Intelligent backfill: only update rows where status is NULL or empty
        cursor.execute("""
            UPDATE incidents SET status = 'RESOLVED'
            WHERE (status IS NULL OR status = '' OR status = 'NEW')
            AND run_id IN (SELECT run_id FROM simulation_runs WHERE UPPER(status) = 'COMPLETED')
        """)
        cursor.execute("""
            UPDATE incidents SET status = 'RESPONDING'
            WHERE (status IS NULL OR status = '' OR status = 'NEW')
            AND run_id IN (SELECT run_id FROM simulation_runs WHERE UPPER(status) = 'RUNNING')
        """)
        # Remaining incidents with NULL/empty status get 'NEW'
        cursor.execute("UPDATE incidents SET status = 'NEW' WHERE status IS NULL OR status = ''")

    # Add metadata columns to external_disaster_events
    cursor.execute("PRAGMA table_info(external_disaster_events)")
    ext_cols = {row[1] for row in cursor.fetchall()}
    for col, ctype in [
        ("freshness_seconds", "REAL"),
        ("confidence", "REAL"),
        ("correlation_status", "TEXT DEFAULT 'UNCONFIRMED'"),
    ]:
        if col not in ext_cols:
            cursor.execute(f"ALTER TABLE external_disaster_events ADD COLUMN {col} {ctype}")

    # Ensure incident_timeline table exists
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS incident_timeline (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id INTEGER NOT NULL,
            previous_status TEXT,
            new_status TEXT NOT NULL,
            operator_name TEXT,
            operator_id INTEGER,
            reason TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (incident_id) REFERENCES incidents(incident_id)
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_incident_timeline_inc_id ON incident_timeline(incident_id);")

    # Ensure Phase P3.1 external_facilities and geographic_cache exist
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS external_facilities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            facility_id TEXT UNIQUE NOT NULL,
            facility_type TEXT NOT NULL,
            name TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            address TEXT,
            city TEXT,
            source TEXT NOT NULL,
            source_id TEXT,
            classification TEXT DEFAULT 'LIVE',
            capacity INTEGER,
            available_capacity INTEGER,
            capacity_status TEXT DEFAULT 'UNAVAILABLE',
            phone TEXT,
            emergency_service INTEGER DEFAULT 1,
            metadata_json TEXT,
            fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ext_facilities_type ON external_facilities(facility_type);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ext_facilities_coords ON external_facilities(latitude, longitude);")

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS geographic_cache (
            cache_key TEXT PRIMARY KEY,
            query_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME NOT NULL
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_geo_cache_expires ON geographic_cache(expires_at);")

    # Ensure Phase P3.2 impact_assessments table exists
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS impact_assessments (
            assessment_id TEXT PRIMARY KEY,
            source_event_id TEXT NOT NULL,
            source_event_type TEXT NOT NULL,
            epicenter_lat REAL NOT NULL,
            epicenter_lng REAL NOT NULL,
            magnitude REAL,
            depth_km REAL,
            max_radius_km REAL NOT NULL,
            impact_zones_json TEXT,
            facilities_json TEXT,
            summary_json TEXT,
            route_accessibility_status TEXT DEFAULT 'CLEAR',
            methodology TEXT NOT NULL,
            assumptions_json TEXT,
            limitations_json TEXT,
            confidence TEXT,
            calculated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_impact_source_event ON impact_assessments(source_event_id);")

    # Ensure Phase P3.3 compound_events table exists
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS compound_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            compound_id TEXT UNIQUE NOT NULL,
            correlation_type TEXT NOT NULL,
            primary_event_id TEXT NOT NULL,
            secondary_event_id TEXT,
            secondary_event_type TEXT,
            confidence_score REAL NOT NULL,
            cascade_risk_level TEXT NOT NULL,
            classification TEXT DEFAULT 'CALCULATED',
            affected_facilities_json TEXT,
            cascade_chain_json TEXT,
            recommendations_json TEXT,
            trigger_parameters_json TEXT,
            detected_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_compound_type ON compound_events(correlation_type);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_compound_primary ON compound_events(primary_event_id);")

    # Ensure Phase P3.4 evacuation_corridors table exists
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS evacuation_corridors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            corridor_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            profile TEXT NOT NULL,
            profile_label TEXT,
            status TEXT NOT NULL,
            origin_lat REAL NOT NULL,
            origin_lng REAL NOT NULL,
            dest_lat REAL NOT NULL,
            dest_lng REAL NOT NULL,
            distance_km REAL NOT NULL,
            transit_time_minutes INTEGER NOT NULL,
            population_to_evacuate INTEGER NOT NULL,
            bottleneck_throughput_per_hour INTEGER NOT NULL,
            estimated_clearance_hours REAL NOT NULL,
            path_coordinates_json TEXT,
            hazard_intersections_json TEXT,
            safety_tier TEXT NOT NULL,
            classification TEXT DEFAULT 'CALCULATED',
            route_provider TEXT DEFAULT 'CALCULATED',
            route_type TEXT DEFAULT 'GRAPH_ESTIMATE',
            methodology TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_corridor_status ON evacuation_corridors(status);")

    # Ensure Phase P3.6 columns exist in evacuation_corridors
    try:
        corr_cols = {c[1] for c in cursor.execute("PRAGMA table_info(evacuation_corridors);").fetchall()}
        if "route_provider" not in corr_cols:
            cursor.execute("ALTER TABLE evacuation_corridors ADD COLUMN route_provider TEXT DEFAULT 'CALCULATED';")
        if "route_type" not in corr_cols:
            cursor.execute("ALTER TABLE evacuation_corridors ADD COLUMN route_type TEXT DEFAULT 'GRAPH_ESTIMATE';")
    except Exception:
        pass

    # Data Integrity Cleanup (never fabricate coordinates; map known city names or mark unverified)
    try:
        cursor.execute("UPDATE simulation_runs SET status = 'COMPLETED', completed_at = CURRENT_TIMESTAMP WHERE status = 'RUNNING' AND completed_at IS NULL;")
        cursor.execute("UPDATE incidents SET latitude = 13.083, longitude = 80.271 WHERE LOWER(location) = 'chennai' AND (latitude IS NULL OR latitude = 19.076);")
        cursor.execute("UPDATE incidents SET location_unverified = 1 WHERE latitude IS NULL OR longitude IS NULL;")
    except Exception:
        pass


# ── ML Model Metadata Saver (FIX FOR MISSING FUNCTION BUG) ─────────────────

def save_ml_model_meta(
    model_name: str, model_path: str, accuracy: float, f1: float, training_samples: int
) -> None:
    """Save trained ML model metadata to SQLite."""
    conn = get_connection()
    cursor = conn.cursor()
    # Deactivate previous models
    cursor.execute("UPDATE ml_models SET is_active = 0")
    cursor.execute(
        """
        INSERT INTO ml_models (model_name, model_path, accuracy, f1_score, training_samples, is_active)
        VALUES (?, ?, ?, ?, ?, 1)
        """,
        (model_name, model_path, accuracy, f1, training_samples),
    )
    conn.commit()
    conn.close()


def create_run(run_id: str, seed: int, strategy: str = "smart", user_id: int = 1) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO simulation_runs (run_id, user_id, seed, strategy, status) VALUES (?, ?, ?, ?, 'RUNNING')",
        (run_id, user_id, seed, strategy),
    )
    conn.commit()
    conn.close()


def complete_run(run_id: str, status: str = "COMPLETED") -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE simulation_runs SET status = ?, completed_at = ? WHERE run_id = ?",
        (status, datetime.now().isoformat(), run_id),
    )
    conn.commit()
    conn.close()


def get_run_db_status(run_id: str) -> Optional[Dict[str, Any]]:
    run_id = resolve_run_id(run_id)
    conn = get_connection()
    row = conn.execute(
        "SELECT run_id, status, strategy, seed, started_at, completed_at "
        "FROM simulation_runs WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_runs_with_metadata() -> List[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT sr.run_id, sr.status, sr.strategy, sr.seed, sr.started_at, sr.completed_at, "
        "rm.total_incidents, rm.total_lives_saved, rm.overall_efficiency "
        "FROM simulation_runs sr "
        "LEFT JOIN run_metrics rm ON sr.run_id = rm.run_id "
        "ORDER BY sr.started_at DESC "
        "LIMIT 50"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def save_incidents(run_id: str, incidents: List[Dict[str, Any]]) -> None:
    if not incidents:
        return
    conn = get_connection()
    records = [
        (
            run_id,
            item.get("affected_area") or item.get("location"),
            item.get("latitude"),
            item.get("longitude"),
            item.get("severity", "medium"),
            item.get("people_affected", 0),
            item.get("disaster_type", "unknown"),
            item.get("priority"),
            item.get("estimated_risk"),
            item.get("ml_predicted_severity"),
            item.get("ml_confidence"),
            item.get("assigned_team_id"),
            item.get("route_path"),
            item.get("route_coordinates"),
            item.get("route_distance_km"),
            item.get("route_eta_hours"),
            item.get("route_source", "UNAVAILABLE"),
            item.get("route_provider", "UNAVAILABLE"),
        )
        for item in incidents
    ]
    conn.executemany(
        """
        INSERT INTO incidents
        (run_id, location, latitude, longitude, severity, people_affected,
         disaster_type, priority, estimated_risk, ml_predicted_severity, ml_confidence,
         assigned_team_id, route_path, route_coordinates, route_distance_km, route_eta_hours,
         route_source, route_provider)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        records,
    )
    conn.commit()
    conn.close()


def save_agent_log(run_id: str, agent_name: str, state: str, output: Dict[str, Any]) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO agent_logs (run_id, agent_name, state, output_json) VALUES (?, ?, ?, ?)",
        (run_id, agent_name, state, json.dumps(output)),
    )
    conn.commit()
    conn.close()


def save_agent_logs_bulk(run_id: str, agent_name: str, state: str, outputs: List[Dict[str, Any]]) -> None:
    if not outputs:
        return
    conn = get_connection()
    records = [(run_id, agent_name, state, json.dumps(item)) for item in outputs]
    conn.executemany(
        "INSERT INTO agent_logs (run_id, agent_name, state, output_json) VALUES (?, ?, ?, ?)",
        records,
    )
    conn.commit()
    conn.close()


def save_run_metrics(run_id: str, metrics: Dict[str, Any]) -> None:
    conn = get_connection()
    assign_rate = metrics.get("resource_assignment_rate_pct")
    if assign_rate is None and metrics.get("resource_utilization"):
        try:
            assign_rate = float(str(metrics.get("resource_utilization")).replace("%", "").strip())
        except Exception:
            assign_rate = None

    active_util = metrics.get("active_resource_utilization_pct", 0.0)

    total_victims = metrics.get("total_victims", metrics.get("total_affected", 0))
    rescued_victims = metrics.get("rescued_victims", metrics.get("total_lives_saved", 0))
    casualties = metrics.get("casualties", metrics.get("casualties_count", 0))
    waiting_victims = metrics.get("waiting_victims")
    if waiting_victims is None:
        waiting_victims = max(0, total_victims - rescued_victims - casualties)

    rescue_rate = metrics.get("rescue_rate_pct")
    if rescue_rate is None and total_victims > 0:
        rescue_rate = round((rescued_victims / total_victims) * 100, 1)

    casualty_rate = metrics.get("casualty_rate_pct")
    if casualty_rate is None and total_victims > 0:
        casualty_rate = round((casualties / total_victims) * 100, 1)

    sim_score = metrics.get("simulation_performance_score")
    if sim_score is None and metrics.get("overall_score") is not None:
        sim_score = metrics.get("overall_score")

    conn.execute(
        """
        INSERT OR REPLACE INTO run_metrics
        (run_id, total_incidents, total_affected, total_lives_saved,
         overall_efficiency, avg_response_time, resource_utilization, status,
         planned_route_eta_mins, actual_response_time_mins,
         resource_assignment_rate_pct, active_resource_utilization_pct,
         total_victims, rescued_victims, waiting_victims, casualties,
         rescue_rate_pct, casualty_rate_pct, simulation_performance_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            metrics.get("total_incidents", 0),
            total_victims,
            rescued_victims,
            metrics.get("overall_efficiency", f"{sim_score}%" if sim_score is not None else "N/A"),
            metrics.get("avg_response_time", "N/A"),
            metrics.get("resource_utilization", "N/A"),
            metrics.get("status", "completed"),
            metrics.get("planned_route_eta_mins"),
            metrics.get("actual_response_time_mins"),
            assign_rate,
            active_util,
            total_victims,
            rescued_victims,
            waiting_victims,
            casualties,
            rescue_rate,
            casualty_rate,
            sim_score,
        ),
    )
    conn.commit()
    conn.close()


def get_run_metrics(run_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM run_metrics WHERE run_id = ?", (run_id,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    if "resource_assignment_rate_pct" not in d or d.get("resource_assignment_rate_pct") is None:
        ru_str = str(d.get("resource_utilization", "0.0%")).replace("%", "").strip()
        try:
            d["resource_assignment_rate_pct"] = float(ru_str)
        except Exception:
            d["resource_assignment_rate_pct"] = 0.0
    if "active_resource_utilization_pct" not in d or d.get("active_resource_utilization_pct") is None:
        d["active_resource_utilization_pct"] = 0.0

    tot = d.get("total_victims") if d.get("total_victims") is not None else d.get("total_affected", 0)
    resc = d.get("rescued_victims") if d.get("rescued_victims") is not None else d.get("total_lives_saved", 0)
    cas = d.get("casualties") if d.get("casualties") is not None else 0
    wait = d.get("waiting_victims") if d.get("waiting_victims") is not None else max(0, tot - resc - cas)

    d["total_victims"] = tot
    d["rescued_victims"] = resc
    d["waiting_victims"] = wait
    d["casualties"] = cas

    if "rescue_rate_pct" not in d or d.get("rescue_rate_pct") is None:
        d["rescue_rate_pct"] = round((resc / tot) * 100, 1) if tot > 0 else None
    if "casualty_rate_pct" not in d or d.get("casualty_rate_pct") is None:
        d["casualty_rate_pct"] = round((cas / tot) * 100, 1) if tot > 0 else None

    if "simulation_performance_score" not in d or d.get("simulation_performance_score") is None:
        from utils.metrics import calculate_simulation_performance_score
        res = calculate_simulation_performance_score(
            rescue_rate_pct=d["rescue_rate_pct"],
            casualty_rate_pct=d["casualty_rate_pct"],
            resource_assignment_rate_pct=d["resource_assignment_rate_pct"],
            planned_route_eta_mins=d.get("planned_route_eta_mins"),
        )
        d["simulation_performance_score"] = res.get("score")
    d["overall_score"] = d["simulation_performance_score"]
    return d


# ── Dynamic Simulation Entities Persistence ────────────────────────────────

def save_simulation_resources(run_id: str, resources: List[Dict[str, Any]]) -> None:
    if not resources:
        return
    conn = get_connection()
    records = [
        (
            run_id,
            r["resource_id"],
            r["resource_name"],
            r["resource_type"],
            r.get("city", "Unknown"),
            r["latitude"],
            r["longitude"],
            r.get("status", "available"),
            r.get("capacity", 4),
            r.get("specialization", "general"),
            r.get("speed_kmh", 60.0),
            r.get("heading", 0.0),
            r.get("assigned_incident"),
            r.get("current_eta_min", 0.0),
        )
        for r in resources
    ]
    conn.executemany(
        """
        INSERT INTO simulation_resources
        (run_id, resource_id, resource_name, resource_type, city, latitude, longitude,
         status, capacity, specialization, speed_kmh, heading, assigned_incident, current_eta_min)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        records,
    )
    conn.commit()
    conn.close()


def get_simulation_resources(run_id: str) -> List[Dict[str, Any]]:
    run_id = resolve_run_id(run_id)
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM simulation_resources WHERE run_id = ?", (run_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_facilities(run_id: str, facilities: List[Dict[str, Any]]) -> None:
    if not facilities:
        return
    conn = get_connection()
    records = [
        (
            run_id,
            f["facility_id"],
            f["facility_name"],
            f["facility_type"],
            f.get("city", "Unknown"),
            f["latitude"],
            f["longitude"],
            f.get("total_capacity", 100),
            f.get("available_capacity", 100),
            f.get("status", "operational"),
            f.get("phone", ""),
        )
        for f in facilities
    ]
    conn.executemany(
        """
        INSERT INTO facilities
        (run_id, facility_id, facility_name, facility_type, city, latitude, longitude,
         total_capacity, available_capacity, status, phone)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        records,
    )
    conn.commit()
    conn.close()


def get_facilities(run_id: str) -> List[Dict[str, Any]]:
    run_id = resolve_run_id(run_id)
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM facilities WHERE run_id = ?", (run_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_blocked_roads(run_id: str, blocked: List[Dict[str, Any]]) -> None:
    if not blocked:
        return
    conn = get_connection()
    records = [
        (run_id, b["blockage_id"], b["from_city"], b["to_city"], b.get("reason"), b.get("status", "blocked"))
        for b in blocked
    ]
    conn.executemany(
        "INSERT INTO blocked_roads (run_id, blockage_id, from_city, to_city, reason, status) VALUES (?, ?, ?, ?, ?, ?)",
        records,
    )
    conn.commit()
    conn.close()


def get_blocked_roads(run_id: str) -> List[Dict[str, Any]]:
    run_id = resolve_run_id(run_id)
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM blocked_roads WHERE run_id = ?", (run_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_disaster_zones(run_id: str, zones: List[Dict[str, Any]]) -> None:
    if not zones:
        return
    conn = get_connection()
    records = [
        (
            run_id,
            z["zone_id"],
            z["zone_name"],
            z["zone_type"],
            z["center_latitude"],
            z["center_longitude"],
            z.get("radius_meters", 20000.0),
            z.get("color", "#38bdf8"),
            z.get("opacity", 0.2),
        )
        for z in zones
    ]
    conn.executemany(
        """
        INSERT INTO disaster_zones
        (run_id, zone_id, zone_name, zone_type, center_latitude, center_longitude, radius_meters, color, opacity)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        records,
    )
    conn.commit()
    conn.close()


def get_disaster_zones(run_id: str) -> List[Dict[str, Any]]:
    run_id = resolve_run_id(run_id)
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM disaster_zones WHERE run_id = ?", (run_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_analytics_summary() -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) AS c FROM simulation_runs")
    total_runs = cursor.fetchone()["c"]

    cursor.execute("SELECT COUNT(*) AS c FROM incidents")
    total_incidents = cursor.fetchone()["c"]

    cursor.execute("SELECT COALESCE(SUM(total_lives_saved), 0) AS lives FROM run_metrics")
    total_lives_saved = cursor.fetchone()["lives"]

    cursor.execute("SELECT strategy, COUNT(*) AS runs FROM simulation_runs GROUP BY strategy")
    strategy_breakdown = {row["strategy"]: row["runs"] for row in cursor.fetchall()}

    cursor.execute("SELECT run_id, total_lives_saved, overall_efficiency FROM run_metrics ORDER BY total_lives_saved DESC LIMIT 5")
    top_runs = [dict(row) for row in cursor.fetchall()]

    cursor.execute("SELECT total_lives_saved FROM run_metrics ORDER BY metric_id ASC LIMIT 20")
    lives_saved_trend = [row["total_lives_saved"] for row in cursor.fetchall()]

    cursor.execute(
        "SELECT sr.strategy, AVG(CAST(REPLACE(rm.overall_efficiency, '%', '') AS REAL)) AS avg_eff "
        "FROM run_metrics rm JOIN simulation_runs sr ON sr.run_id = rm.run_id GROUP BY sr.strategy"
    )
    strategy_efficiency = {row["strategy"]: round(row["avg_eff"] or 0, 2) for row in cursor.fetchall()}

    conn.close()
    return {
        "total_runs": total_runs,
        "total_incidents": total_incidents,
        "total_lives_saved": total_lives_saved,
        "strategy_breakdown": strategy_breakdown,
        "top_runs": top_runs,
        "lives_saved_trend": lives_saved_trend,
        "strategy_efficiency": strategy_efficiency,
    }


def get_incidents_by_run(run_id: str) -> List[Dict[str, Any]]:
    run_id = resolve_run_id(run_id)
    conn = get_connection()
    rows = conn.execute("SELECT * FROM incidents WHERE run_id = ? ORDER BY incident_id ASC", (run_id,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_system_config() -> Dict[str, str]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM system_config")
    rows = cursor.fetchall()
    conn.close()
    return {row["key"]: row["value"] for row in rows}


def update_system_config(configs: Dict[str, str]) -> None:
    conn = get_connection()
    for key, value in configs.items():
        conn.execute("INSERT OR REPLACE INTO system_config (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()


def get_custom_incidents() -> List[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT location, latitude, longitude, severity, people_affected, disaster_type FROM custom_incidents ORDER BY id ASC"
    ).fetchall()
    conn.close()
    return [
        {
            "location": row["location"],
            "latitude": row["latitude"],
            "longitude": row["longitude"],
            "severity": row["severity"],
            "people_affected": row["people_affected"],
            "disaster_type": row["disaster_type"],
            "state": "INIT"
        }
        for row in rows
    ]


def save_custom_incident(
    location: str, severity: str, people_affected: int, disaster_type: str,
    latitude: Optional[float] = None, longitude: Optional[float] = None,
) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO custom_incidents (location, latitude, longitude, severity, people_affected, disaster_type) VALUES (?, ?, ?, ?, ?, ?)",
        (location, latitude, longitude, severity, people_affected, disaster_type)
    )
    conn.commit()
    conn.close()


def clear_custom_incidents() -> None:
    conn = get_connection()
    conn.execute("DELETE FROM custom_incidents")
    conn.commit()
    conn.close()


def save_citizen_report(
    location: str, latitude: float, longitude: float, disaster_type: str,
    people_affected: int = 1, severity: str = "high", sos_type: str = "SOS",
    media_url: str = "", description: str = "", status: str = "pending_review",
) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO citizen_reports
        (location, latitude, longitude, severity, people_affected, disaster_type, sos_type, media_url, description, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (location, latitude, longitude, severity, people_affected, disaster_type, sos_type, media_url, description, status),
    )
    report_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return report_id


def get_citizen_reports() -> List[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM citizen_reports ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_users() -> List[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute("SELECT user_id, name, email, role FROM users ORDER BY user_id ASC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def delete_user(user_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def update_user_role(user_id: int, role: str) -> None:
    conn = get_connection()
    conn.execute("UPDATE users SET role = ? WHERE user_id = ?", (role, user_id))
    conn.commit()
    conn.close()


def create_user_in_db(name: str, email: str, password: str, role: str = "operator") -> int:
    conn = get_connection()
    cursor = conn.cursor()
    hashed_pw = hash_password(password)
    cursor.execute(
        "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
        (name, email, hashed_pw, role)
    )
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return user_id


def get_rescue_teams() -> List[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute("SELECT team_id, team_name, latitude, longitude, status, capacity, specialization FROM rescue_teams ORDER BY team_id").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def upsert_rescue_team(
    team_id: str, team_name: str, latitude: float, longitude: float,
    status: str = "available", capacity: int = 10, specialization: str = "general",
) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO rescue_teams (team_id, team_name, latitude, longitude, status, capacity, specialization) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (team_id, team_name, latitude, longitude, status, capacity, specialization),
    )
    conn.commit()
    conn.close()


def save_agent_message(
    run_id: str, sender: str, receiver: str, message_type: str, payload: Dict[str, Any],
) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO agent_messages (run_id, sender, receiver, message_type, payload) VALUES (?, ?, ?, ?, ?)",
        (run_id, sender, receiver, message_type, json.dumps(payload)),
    )
    conn.commit()
    conn.close()


def get_agent_messages(run_id: str) -> List[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute("SELECT sender, receiver, message_type, payload, timestamp FROM agent_messages WHERE run_id = ? ORDER BY message_id ASC", (run_id,)).fetchall()
    conn.close()
    return [
        {
            "sender": row["sender"],
            "receiver": row["receiver"],
            "message_type": row["message_type"],
            "payload": json.loads(row["payload"]) if row["payload"] else {},
            "timestamp": row["timestamp"],
        }
        for row in rows
    ]


def save_agent_log(
    run_id: str,
    agent_name: str,
    state: str,
    output_json: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    execution_time_ms: Optional[float] = None,
) -> None:
    conn = get_connection()
    json_str = output_json or (json.dumps(payload) if payload else "{}")
    conn.execute(
        "INSERT INTO agent_logs (run_id, agent_name, state, output_json, execution_time_ms) VALUES (?, ?, ?, ?, ?)",
        (run_id, agent_name, state, json_str, execution_time_ms),
    )
    conn.commit()
    conn.close()


def log_run_event(run_id: str, state: str, payload: Dict[str, Any]) -> None:
    conn = get_connection()
    conn.execute("INSERT INTO run_logs (run_id, state, payload) VALUES (?, ?, ?)", (run_id, state, json.dumps(payload)))
    conn.commit()
    conn.close()


def get_run_events(run_id: str) -> List[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute("SELECT state, payload, timestamp FROM run_logs WHERE run_id = ? ORDER BY id ASC", (run_id,)).fetchall()
    conn.close()
    return [
        {
            "state": row["state"],
            "payload": json.loads(row["payload"]) if row["payload"] else {},
            "timestamp": row["timestamp"],
        }
        for row in rows
    ]


def update_incidents_routing_bulk(run_id: str, items: List[Dict[str, Any]]) -> None:
    if not items:
        return
    conn = get_connection()
    records = []
    for alloc, orig in items:
        location = orig.get("location") or orig.get("affected_area")
        team_id = alloc.get("assigned_team_id", "")
        route_path = json.dumps(alloc.get("route_path", []))
        route_coords = json.dumps(alloc.get("route_coordinates", []))
        dist = alloc.get("route_distance_km")
        eta = alloc.get("route_eta_hours")
        src = alloc.get("route_source", "UNAVAILABLE")
        provider = alloc.get("route_provider", "UNAVAILABLE")
        score = alloc.get("allocation_score")
        explanation = alloc.get("allocation_explanation")
        records.append((team_id, route_path, route_coords, dist, eta, src, provider, score, explanation, run_id, location))

    conn.executemany(
        "UPDATE incidents SET assigned_team_id = ?, route_path = ?, route_coordinates = ?, "
        "route_distance_km = ?, route_eta_hours = ?, route_source = ?, route_provider = ?, "
        "allocation_score = ?, allocation_explanation = ? "
        "WHERE run_id = ? AND location = ?",
        records,
    )
    conn.commit()
    conn.close()


def get_db_agent_telemetry(run_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Compute real agent telemetry dynamically from agent_logs table."""
    # 14 Operational Response Agents + 1 Post-Mission Evaluation Service (15 total registered entities)
    # plus legacy stage log aliases for compatibility
    agents = [
        "IncidentAgent",
        "WeatherAgent",
        "VictimAgent",
        "ResourceAgent",
        "HospitalAgent",
        "ShelterAgent",
        "TrafficAgent",
        "PoliceAgent",
        "FireAgent",
        "DroneAgent",
        "RouteAgent",
        "RescueAgent",
        "CommunicationAgent",
        "AIAgent",
        "EvaluationAgent",
        "IncidentDetectionAgent",
        "SituationAnalysisAgent",
        "WeatherAnalysisAgent",
        "ResourceAllocationAgent",
        "RoutePlanningAgent",
        "HospitalManagementAgent",
        "ShelterManagementAgent",
        "RescueCoordinationAgent",
        "AIRecommendationAgent",
    ]
    conn = get_connection()
    results = []
    for name in agents:
        if run_id:
            row = conn.execute(
                "SELECT COUNT(*) as processed_cnt, MAX(created_at) as last_act, AVG(execution_time_ms) as avg_lat FROM agent_logs WHERE agent_name = ? AND run_id = ?",
                (name, run_id),
            ).fetchone()
            fail_row = conn.execute(
                "SELECT COUNT(*) as fail_cnt FROM agent_logs WHERE agent_name = ? AND run_id = ? AND state = 'ERROR'",
                (name, run_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) as processed_cnt, MAX(created_at) as last_act, AVG(execution_time_ms) as avg_lat FROM agent_logs WHERE agent_name = ?",
                (name,),
            ).fetchone()
            fail_row = conn.execute(
                "SELECT COUNT(*) as fail_cnt FROM agent_logs WHERE agent_name = ? AND state = 'ERROR'",
                (name,),
            ).fetchone()

        cnt = row["processed_cnt"] if row else 0
        last_act = row["last_act"] if row and row["last_act"] else ""
        fails = fail_row["fail_cnt"] if fail_row else 0
        raw_lat = row["avg_lat"] if row and row["avg_lat"] is not None else None
        avg_lat = round(float(raw_lat), 2) if (raw_lat is not None and cnt > 0) else None

        results.append({
            "agent_name": name,
            "status": "healthy" if fails < 3 else "degraded",
            "messages_processed": cnt,
            "messages_failed": fails,
            "avg_latency_ms": avg_lat,
            "last_active": last_act,
        })
    conn.close()
    return results


def get_incidents_with_geo(run_id: str) -> List[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM incidents WHERE run_id = ? ORDER BY incident_id ASC", (run_id,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_active_ml_model() -> Optional[Dict[str, Any]]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM ml_models ORDER BY trained_at DESC LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else None


def save_external_disaster_events(events: List[Dict[str, Any]]):
    """Save or update external disaster events with deduplication."""
    if not events:
        return
    conn = get_connection()
    cursor = conn.cursor()
    for ev in events:
        cursor.execute(
            """
            INSERT OR REPLACE INTO external_disaster_events 
            (source, source_event_id, event_type, severity, classification, latitude, longitude, magnitude, place, observed_at, raw_payload)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ev.get("source"),
                ev.get("source_event_id"),
                ev.get("event_type"),
                ev.get("severity"),
                ev.get("classification", "LIVE"),
                ev.get("latitude"),
                ev.get("longitude"),
                ev.get("magnitude"),
                ev.get("place"),
                ev.get("observed_at"),
                json.dumps(ev.get("raw_payload") or {})
            )
        )
    conn.commit()
    conn.close()


def get_external_disaster_events(source: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieve persisted external disaster events."""
    conn = get_connection()
    if source:
        rows = conn.execute(
            "SELECT * FROM external_disaster_events WHERE source = ? ORDER BY id DESC LIMIT ?",
            (source, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM external_disaster_events ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Phase P3.1 Real Facility & Geographic Cache Persistence ────────────────

def save_external_facilities(facilities: List[Dict[str, Any]]) -> None:
    """Save or update real external facilities with deduplication and provenance."""
    if not facilities:
        return
    conn = get_connection()
    cursor = conn.cursor()
    for f in facilities:
        meta = f.get("metadata") or {}
        cursor.execute(
            """
            INSERT INTO external_facilities
            (facility_id, facility_type, name, latitude, longitude, address, city,
             source, source_id, classification, capacity, available_capacity, capacity_status,
             phone, emergency_service, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(facility_id) DO UPDATE SET
                facility_type = excluded.facility_type,
                name = excluded.name,
                latitude = excluded.latitude,
                longitude = excluded.longitude,
                address = COALESCE(excluded.address, external_facilities.address),
                city = COALESCE(excluded.city, external_facilities.city),
                capacity = COALESCE(excluded.capacity, external_facilities.capacity),
                available_capacity = excluded.available_capacity,
                capacity_status = excluded.capacity_status,
                phone = COALESCE(excluded.phone, external_facilities.phone),
                metadata_json = excluded.metadata_json,
                fetched_at = CURRENT_TIMESTAMP
            """,
            (
                f.get("facility_id"),
                f.get("facility_type"),
                f.get("name"),
                f.get("latitude"),
                f.get("longitude"),
                f.get("address"),
                f.get("city"),
                f.get("source", "OpenStreetMap"),
                f.get("source_id"),
                f.get("classification", "LIVE"),
                f.get("capacity"),
                f.get("available_capacity"),
                f.get("capacity_status", "UNAVAILABLE"),
                f.get("phone"),
                1 if f.get("emergency_service", True) else 0,
                json.dumps(meta) if isinstance(meta, dict) else str(meta),
            ),
        )
    conn.commit()
    conn.close()


def get_external_facilities(
    facility_type: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    radius_km: float = 25.0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Retrieve persisted external facilities with optional spatial radius filter."""
    import math

    conn = get_connection()
    if lat is not None and lng is not None:
        lat_delta = (radius_km * 1.5) / 110.0
        lng_delta = (radius_km * 1.5) / (110.0 * max(0.1, math.cos(math.radians(lat))))
        min_lat, max_lat = lat - lat_delta, lat + lat_delta
        min_lng, max_lng = lng - abs(lng_delta), lng + abs(lng_delta)

        if facility_type:
            rows = conn.execute(
                "SELECT * FROM external_facilities WHERE facility_type = ? AND latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ? ORDER BY id DESC LIMIT ?",
                (facility_type, min_lat, max_lat, min_lng, max_lng, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM external_facilities WHERE latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ? ORDER BY id DESC LIMIT ?",
                (min_lat, max_lat, min_lng, max_lng, limit),
            ).fetchall()
    else:
        if facility_type:
            rows = conn.execute(
                "SELECT * FROM external_facilities WHERE facility_type = ? ORDER BY id DESC LIMIT ?",
                (facility_type, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM external_facilities ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
    conn.close()

    def _haversine(lat1, lon1, lat2, lon2):
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2.0) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
        return R * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    results = []
    for r in rows:
        d = dict(r)
        if d.get("metadata_json"):
            try:
                d["metadata"] = json.loads(d["metadata_json"])
            except Exception:
                d["metadata"] = {}
        else:
            d["metadata"] = {}

        if lat is not None and lng is not None:
            f_lat = d.get("latitude")
            f_lng = d.get("longitude")
            if f_lat is not None and f_lng is not None:
                dist = _haversine(lat, lng, float(f_lat), float(f_lng))
                if dist <= radius_km:
                    d["distance_km"] = round(dist, 2)
                    results.append(d)
        else:
            results.append(d)

    if lat is not None and lng is not None:
        results.sort(key=lambda x: x.get("distance_km", 999.0))

    return results


def get_geographic_cache(cache_key: str) -> Optional[Any]:
    """Retrieve unexpired payload from SQLite geographic cache."""
    conn = get_connection()
    row = conn.execute(
        "SELECT payload_json, expires_at FROM geographic_cache WHERE cache_key = ? AND expires_at > CURRENT_TIMESTAMP",
        (cache_key,),
    ).fetchone()
    conn.close()
    if row and row["payload_json"]:
        try:
            return json.loads(row["payload_json"])
        except Exception:
            return None
    return None


def set_geographic_cache(cache_key: str, query_type: str, data: Any, ttl_seconds: int = 86400) -> None:
    """Store serializable payload in SQLite geographic cache with TTL."""
    conn = get_connection()
    cursor = conn.cursor()
    exp_time = (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).strftime("%Y-%m-%d %H:%M:%S")
    payload = json.dumps(data) if not isinstance(data, str) else data
    cursor.execute(
        """
        INSERT INTO geographic_cache (cache_key, query_type, payload_json, expires_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(cache_key) DO UPDATE SET
            payload_json = excluded.payload_json,
            created_at = CURRENT_TIMESTAMP,
            expires_at = excluded.expires_at
        """,
        (cache_key, query_type, payload, exp_time),
    )
    conn.commit()
    conn.close()


# ── Phase P3.2 Impact Analysis Assessment Persistence ──────────────────────

def save_impact_assessment(assessment: Dict[str, Any]) -> None:
    """Save or update calculated disaster impact assessment."""
    if not assessment or not assessment.get("assessment_id"):
        return
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO impact_assessments
        (assessment_id, source_event_id, source_event_type, epicenter_lat, epicenter_lng,
         magnitude, depth_km, max_radius_km, impact_zones_json, facilities_json,
         summary_json, route_accessibility_status, methodology, assumptions_json,
         limitations_json, confidence, calculated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(assessment_id) DO UPDATE SET
            max_radius_km = excluded.max_radius_km,
            impact_zones_json = excluded.impact_zones_json,
            facilities_json = excluded.facilities_json,
            summary_json = excluded.summary_json,
            route_accessibility_status = excluded.route_accessibility_status,
            methodology = excluded.methodology,
            assumptions_json = excluded.assumptions_json,
            limitations_json = excluded.limitations_json,
            confidence = excluded.confidence,
            calculated_at = CURRENT_TIMESTAMP
        """,
        (
            assessment.get("assessment_id"),
            assessment.get("source_event_id") or assessment.get("event_id", "UNKNOWN"),
            assessment.get("source_event_type") or assessment.get("disaster_type", "general"),
            assessment.get("epicenter_latitude") if assessment.get("epicenter_latitude") is not None else (assessment.get("epicenter", {}).get("latitude", 0.0) if isinstance(assessment.get("epicenter"), dict) else 0.0),
            assessment.get("epicenter_longitude") if assessment.get("epicenter_longitude") is not None else (assessment.get("epicenter", {}).get("longitude", 0.0) if isinstance(assessment.get("epicenter"), dict) else 0.0),
            assessment.get("magnitude"),
            assessment.get("depth_km"),
            assessment.get("max_radius_km", 25.0),
            json.dumps(assessment.get("impact_zones") or []),
            json.dumps(assessment.get("facilities_in_impact_zone") or assessment.get("facilities") or []),
            json.dumps(assessment.get("summary") or {}),
            assessment.get("route_accessibility_status", "CLEAR"),
            assessment.get("methodology", "Joyner-Boore Attenuation"),
            json.dumps(assessment.get("assumptions") or []),
            json.dumps(assessment.get("limitations") or []),
            assessment.get("confidence", "APPROXIMATE_ANALYTICAL"),
        ),
    )
    conn.commit()
    conn.close()


def get_impact_assessment(
    assessment_id: Optional[str] = None, event_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Retrieve full detail of an impact assessment."""
    conn = get_connection()
    if assessment_id:
        row = conn.execute(
            "SELECT * FROM impact_assessments WHERE assessment_id = ?", (assessment_id,)
        ).fetchone()
    elif event_id:
        row = conn.execute(
            "SELECT * FROM impact_assessments WHERE source_event_id = ? ORDER BY rowid DESC LIMIT 1",
            (event_id,),
        ).fetchone()
    else:
        conn.close()
        return None
    conn.close()

    if not row:
        return None

    d = dict(row)
    for k in ["impact_zones_json", "facilities_json", "summary_json", "assumptions_json", "limitations_json"]:
        target_key = k.replace("_json", "")
        if d.get(k):
            try:
                d[target_key] = json.loads(d[k])
            except Exception:
                d[target_key] = [] if k != "summary_json" else {}
        else:
            d[target_key] = [] if k != "summary_json" else {}

    return d


def get_latest_impact_assessments(limit: int = 20) -> List[Dict[str, Any]]:
    """Retrieve list of latest calculated impact assessments."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM impact_assessments ORDER BY rowid DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()

    results = []
    for r in rows:
        d = dict(r)
        for k in ["impact_zones_json", "summary_json"]:
            target_key = k.replace("_json", "")
            if d.get(k):
                try:
                    d[target_key] = json.loads(d[k])
                except Exception:
                    d[target_key] = {}
        results.append(d)
    return results


# ── Phase P3.3 Compound Disaster Event Persistence ─────────────────────────

def save_compound_event(compound: Dict[str, Any]) -> None:
    """Save or update detected compound disaster event in SQLite."""
    if not compound or not compound.get("compound_id"):
        return
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO compound_events
        (compound_id, correlation_type, primary_event_id, secondary_event_id, secondary_event_type,
         confidence_score, cascade_risk_level, classification, affected_facilities_json,
         cascade_chain_json, recommendations_json, trigger_parameters_json, detected_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(compound_id) DO UPDATE SET
            confidence_score = excluded.confidence_score,
            cascade_risk_level = excluded.cascade_risk_level,
            affected_facilities_json = excluded.affected_facilities_json,
            cascade_chain_json = excluded.cascade_chain_json,
            recommendations_json = excluded.recommendations_json,
            trigger_parameters_json = excluded.trigger_parameters_json,
            detected_at = CURRENT_TIMESTAMP
        """,
        (
            compound.get("compound_id"),
            compound.get("correlation_type", "GENERAL_CORRELATION"),
            str(compound.get("primary_event_id", "UNKNOWN")),
            str(compound.get("secondary_event_id") or ""),
            str(compound.get("secondary_event_type") or ""),
            float(compound.get("confidence_score") or 0.5),
            compound.get("cascade_risk_level", "ELEVATED"),
            compound.get("classification", "CALCULATED"),
            json.dumps(compound.get("affected_facilities") or []),
            json.dumps(compound.get("cascade_chain") or []),
            json.dumps(compound.get("recommendations") or []),
            json.dumps(compound.get("trigger_parameters") or {}),
        ),
    )
    conn.commit()
    conn.close()


def get_compound_events(limit: int = 30) -> List[Dict[str, Any]]:
    """Retrieve list of latest detected compound events."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM compound_events ORDER BY detected_at DESC, rowid DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()

    results = []
    for r in rows:
        d = dict(r)
        for k in ["affected_facilities_json", "cascade_chain_json", "recommendations_json", "trigger_parameters_json"]:
            target_key = k.replace("_json", "")
            if d.get(k):
                try:
                    d[target_key] = json.loads(d[k])
                except Exception:
                    d[target_key] = [] if "chain" in k or "facilities" in k or "rec" in k else {}
            else:
                d[target_key] = [] if "chain" in k or "facilities" in k or "rec" in k else {}
        results.append(d)
        if isinstance(d.get("trigger_parameters"), dict):
            d["evidence_chain"] = d["trigger_parameters"].get("evidence_chain", [])
    return results


def get_compound_event_by_id(compound_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve details of a single compound disaster event."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM compound_events WHERE compound_id = ?", (compound_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None

    d = dict(row)
    for k in ["affected_facilities_json", "cascade_chain_json", "recommendations_json", "trigger_parameters_json"]:
        target_key = k.replace("_json", "")
        if d.get(k):
            try:
                d[target_key] = json.loads(d[k])
            except Exception:
                d[target_key] = [] if "chain" in k or "facilities" in k or "rec" in k else {}
        else:
            d[target_key] = [] if "chain" in k or "facilities" in k or "rec" in k else {}

    if isinstance(d.get("trigger_parameters"), dict):
        d["evidence_chain"] = d["trigger_parameters"].get("evidence_chain", [])

    return d


# ── Phase P3.4 Evacuation Corridors Persistence ────────────────────────────

def save_evacuation_corridor(corridor: Dict[str, Any]) -> None:
    """Persist calculated evacuation corridor into SQLite."""
    if not corridor or not corridor.get("corridor_id"):
        return
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO evacuation_corridors
        (corridor_id, name, profile, profile_label, status, origin_lat, origin_lng,
         dest_lat, dest_lng, distance_km, transit_time_minutes, population_to_evacuate,
         bottleneck_throughput_per_hour, estimated_clearance_hours, path_coordinates_json,
         hazard_intersections_json, safety_tier, classification, route_provider, route_type, methodology, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(corridor_id) DO UPDATE SET
            status = excluded.status,
            safety_tier = excluded.safety_tier,
            bottleneck_throughput_per_hour = excluded.bottleneck_throughput_per_hour,
            estimated_clearance_hours = excluded.estimated_clearance_hours,
            hazard_intersections_json = excluded.hazard_intersections_json,
            route_provider = excluded.route_provider,
            route_type = excluded.route_type
        """,
        (
            corridor.get("corridor_id"),
            corridor.get("name", "Evacuation Route"),
            corridor.get("profile", "car"),
            corridor.get("profile_label", "Standard Motor Corridor"),
            corridor.get("status", "SAFE_PASSABLE"),
            corridor.get("origin_lat") if corridor.get("origin_lat") is not None else (corridor.get("origin", {}).get("latitude", 0.0) if isinstance(corridor.get("origin"), dict) else 0.0),
            corridor.get("origin_lng") if corridor.get("origin_lng") is not None else (corridor.get("origin", {}).get("longitude", 0.0) if isinstance(corridor.get("origin"), dict) else 0.0),
            corridor.get("dest_lat") if corridor.get("dest_lat") is not None else (corridor.get("destination", {}).get("latitude", 0.0) if isinstance(corridor.get("destination"), dict) else 0.0),
            corridor.get("dest_lng") if corridor.get("dest_lng") is not None else (corridor.get("destination", {}).get("longitude", 0.0) if isinstance(corridor.get("destination"), dict) else 0.0),
            corridor.get("distance_km", 0.0),
            corridor.get("transit_time_minutes", 0),
            corridor.get("population_to_evacuate", 500),
            corridor.get("bottleneck_throughput_per_hour", 1200),
            corridor.get("estimated_clearance_hours", 1.0),
            json.dumps(corridor.get("path_coordinates") or []),
            json.dumps(corridor.get("hazard_intersections") or []),
            corridor.get("safety_tier", "TIER_1_OPTIMAL"),
            corridor.get("classification", "CALCULATED"),
            corridor.get("route_provider", corridor.get("provider", "CALCULATED")),
            corridor.get("route_type", "GRAPH_ESTIMATE"),
            corridor.get("methodology", "Lighthill-Whitham-Richards Flow Dynamics"),
        ),
    )
    conn.commit()
    conn.close()


def get_evacuation_corridors(limit: int = 20) -> List[Dict[str, Any]]:
    """Retrieve list of recently evaluated evacuation corridors."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM evacuation_corridors ORDER BY rowid DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()

    results = []
    for r in rows:
        d = dict(r)
        for k in ["path_coordinates_json", "hazard_intersections_json"]:
            target_key = k.replace("_json", "")
            if d.get(k):
                try:
                    d[target_key] = json.loads(d[k])
                except Exception:
                    d[target_key] = []
            else:
                d[target_key] = []
        d["origin"] = {"latitude": d.get("origin_lat"), "longitude": d.get("origin_lng")}
        d["destination"] = {"latitude": d.get("dest_lat"), "longitude": d.get("dest_lng")}
        results.append(d)
    return results


def save_incident_timeline_entry(
    incident_id: int,
    previous_status: Optional[str],
    new_status: str,
    operator_name: Optional[str] = None,
    operator_id: Optional[int] = None,
    reason: Optional[str] = None,
) -> int:
    """Record an audited status transition in the incident timeline."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO incident_timeline (incident_id, previous_status, new_status, operator_name, operator_id, reason)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            incident_id,
            previous_status,
            new_status,
            operator_name or "System Operator",
            operator_id,
            reason or f"Transitioned from {previous_status or 'INITIAL'} to {new_status}",
        ),
    )
    timeline_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return timeline_id


def get_incident_timeline(incident_id: int) -> List[Dict[str, Any]]:
    """Retrieve full chronological timeline history for a specific incident."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT id, incident_id, previous_status, new_status, operator_name, operator_id, reason, timestamp
        FROM incident_timeline
        WHERE incident_id = ?
        ORDER BY id ASC
        """,
        (incident_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_incident_status(
    incident_id: int,
    new_status: str,
    operator_name: Optional[str] = None,
    operator_id: Optional[int] = None,
    reason: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Update incident status with validation and record audit timeline. Returns the updated incident or None."""
    new_status = new_status.upper().strip()
    if new_status not in VALID_INCIDENT_STATUSES:
        return None
    conn = get_connection()
    cursor = conn.cursor()

    # Get current status before updating
    curr_row = cursor.execute(
        "SELECT status FROM incidents WHERE incident_id = ?", (incident_id,)
    ).fetchone()
    if not curr_row:
        conn.close()
        return None

    prev_status = curr_row["status"] or "NEW"

    cursor.execute(
        "UPDATE incidents SET status = ? WHERE incident_id = ?",
        (new_status, incident_id),
    )
    if cursor.rowcount == 0:
        conn.close()
        return None

    # Record timeline entry
    cursor.execute(
        """
        INSERT INTO incident_timeline (incident_id, previous_status, new_status, operator_name, operator_id, reason)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            incident_id,
            prev_status,
            new_status,
            operator_name or "System Operator",
            operator_id,
            reason or f"Status changed from {prev_status} to {new_status}",
        ),
    )

    conn.commit()
    row = conn.execute(
        "SELECT * FROM incidents WHERE incident_id = ?", (incident_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_incident_analytics(run_id: Optional[str] = None) -> Dict[str, Any]:
    """Calculate incident analytics strictly from SQLite records."""
    run_id = resolve_run_id(run_id)
    conn = get_connection()
    if run_id:
        rows = conn.execute("SELECT * FROM incidents WHERE run_id = ?", (run_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM incidents ORDER BY incident_id DESC LIMIT 500").fetchall()
    conn.close()

    incidents = [dict(r) for r in rows]
    if not incidents:
        return {
            "insufficient_data": True,
            "total_incidents": 0,
            "active_incidents": 0,
            "resolved_incidents": 0,
            "severity_breakdown": {"high": 0, "medium": 0, "low": 0},
            "status_breakdown": {s: 0 for s in sorted(VALID_INCIDENT_STATUSES)},
            "type_breakdown": {},
            "avg_response_time_mins": None,
            "total_people_affected": 0,
            "time_series": [],
        }

    sev_counts = {"high": 0, "medium": 0, "low": 0}
    status_counts = {s: 0 for s in sorted(VALID_INCIDENT_STATUSES)}
    type_counts: Dict[str, int] = {}
    etas: List[float] = []
    total_affected = 0
    active_count = 0
    resolved_count = 0

    for inc in incidents:
        s = str(inc.get("severity") or "low").lower()
        if s in sev_counts:
            sev_counts[s] += 1

        st = str(inc.get("status") or "NEW").upper()
        status_counts[st] = status_counts.get(st, 0) + 1
        if st == "RESOLVED":
            resolved_count += 1
        else:
            active_count += 1

        t = str(inc.get("disaster_type") or "other").title()
        type_counts[t] = type_counts.get(t, 0) + 1

        affected = inc.get("people_affected") or 0
        total_affected += affected

        eta = inc.get("route_eta_hours")
        if eta is not None:
            etas.append(float(eta) * 60)

    avg_eta = round(sum(etas) / len(etas), 1) if etas else None

    # Time series aggregation
    time_series = []
    for i, inc in enumerate(incidents[:15]):
        time_series.append({
            "label": f"INC-{inc.get('incident_id')}",
            "people_affected": inc.get("people_affected", 0),
            "severity": inc.get("severity", "low"),
            "status": inc.get("status", "NEW"),
            "eta_mins": round(float(inc.get("route_eta_hours", 0)) * 60, 1) if inc.get("route_eta_hours") else 0,
        })

    return {
        "insufficient_data": False,
        "total_incidents": len(incidents),
        "active_incidents": active_count,
        "resolved_incidents": resolved_count,
        "severity_breakdown": sev_counts,
        "status_breakdown": status_counts,
        "type_breakdown": type_counts,
        "planned_route_eta_mins": avg_eta,
        "actual_response_time_mins": None,
        "avg_response_time_mins": None,
        "total_people_affected": total_affected,
        "time_series": time_series,
    }


def get_resource_analytics(run_id: Optional[str] = None) -> Dict[str, Any]:
    """Calculate resource and facility utilization analytics strictly from SQLite records."""
    run_id = resolve_run_id(run_id)
    conn = get_connection()
    if run_id:
        res_rows = conn.execute("SELECT * FROM simulation_resources WHERE run_id = ?", (run_id,)).fetchall()
        fac_rows = conn.execute("SELECT * FROM facilities WHERE run_id = ?", (run_id,)).fetchall()
    else:
        res_rows = conn.execute("SELECT * FROM simulation_resources LIMIT 500").fetchall()
        fac_rows = conn.execute("SELECT * FROM facilities LIMIT 500").fetchall()
    conn.close()

    resources = [dict(r) for r in res_rows]
    facilities = [dict(r) for r in fac_rows]

    if not resources and not facilities:
        return {
            "insufficient_data": True,
            "fleet_total": 0,
            "fleet_available": 0,
            "fleet_dispatched": 0,
            "fleet_utilization_pct": 0.0,
            "fleet_by_type": {},
            "hospitals": {"total_beds": 0, "available_beds": 0, "occupancy_pct": 0.0, "items": []},
            "shelters": {"total_capacity": 0, "available_capacity": 0, "occupancy_pct": 0.0, "items": []},
        }

    # Fleet breakdown
    fleet_by_type: Dict[str, Dict[str, int]] = {}
    dispatched_count = 0
    available_count = 0

    for r in resources:
        rtype = r.get("resource_type", "other")
        st = str(r.get("status", "available")).lower()
        if rtype not in fleet_by_type:
            fleet_by_type[rtype] = {"total": 0, "available": 0, "dispatched": 0}
        fleet_by_type[rtype]["total"] += 1
        if st in ["available", "ready", "idle"]:
            fleet_by_type[rtype]["available"] += 1
            available_count += 1
        else:
            fleet_by_type[rtype]["dispatched"] += 1
            dispatched_count += 1

    tot_fleet = len(resources)
    fleet_util_pct = round((dispatched_count / max(1, tot_fleet)) * 100, 1) if tot_fleet > 0 else 0.0

    # Facilities breakdown
    hospitals = [f for f in facilities if f.get("facility_type") == "hospital"]
    shelters = [f for f in facilities if f.get("facility_type") == "shelter"]

    tot_beds = sum(h.get("total_capacity", 0) for h in hospitals)
    avail_beds = sum(h.get("available_capacity", 0) for h in hospitals)
    used_beds = max(0, tot_beds - avail_beds)
    hosp_occ_pct = round((used_beds / max(1, tot_beds)) * 100, 1) if tot_beds > 0 else 0.0

    tot_shelter = sum(s.get("total_capacity", 0) for s in shelters)
    avail_shelter = sum(s.get("available_capacity", 0) for s in shelters)
    used_shelter = max(0, tot_shelter - avail_shelter)
    shelter_occ_pct = round((used_shelter / max(1, tot_shelter)) * 100, 1) if tot_shelter > 0 else 0.0

    # Check run_metrics for authoritative assignment and active utilization
    assignment_rate = fleet_util_pct
    active_rate = 0.0
    if run_id:
        try:
            c2 = get_connection()
            rm_row = c2.execute("SELECT resource_assignment_rate_pct, active_resource_utilization_pct FROM run_metrics WHERE run_id = ?", (run_id,)).fetchone()
            c2.close()
            if rm_row:
                if rm_row["resource_assignment_rate_pct"] is not None:
                    assignment_rate = rm_row["resource_assignment_rate_pct"]
                if rm_row["active_resource_utilization_pct"] is not None:
                    active_rate = rm_row["active_resource_utilization_pct"]
        except Exception:
            pass

    return {
        "insufficient_data": False,
        "fleet_total": tot_fleet,
        "fleet_available": available_count,
        "fleet_dispatched": dispatched_count,
        "fleet_utilization_pct": fleet_util_pct,
        "resource_assignment_rate_pct": assignment_rate,
        "active_resource_utilization_pct": active_rate,
        "fleet_assignment_rate_pct": assignment_rate,
        "active_utilization_pct": active_rate,
        "fleet_by_type": fleet_by_type,
        "hospitals": {
            "total_beds": tot_beds,
            "available_beds": avail_beds,
            "occupancy_pct": hosp_occ_pct,
            "items": [{"name": h.get("facility_name"), "total": h.get("total_capacity", 0), "available": h.get("available_capacity", 0)} for h in hospitals],
        },
        "shelters": {
            "total_capacity": tot_shelter,
            "available_capacity": avail_shelter,
            "occupancy_pct": shelter_occ_pct,
            "items": [{"name": s.get("facility_name"), "total": s.get("total_capacity", 0), "available": s.get("available_capacity", 0)} for s in shelters],
        },
    }


def get_intelligence_analytics() -> Dict[str, Any]:
    """Calculate external intelligence analytics strictly from persisted SQLite records."""
    conn = get_connection()
    events_rows = conn.execute("SELECT * FROM external_disaster_events ORDER BY id DESC LIMIT 500").fetchall()
    health_rows = conn.execute("SELECT * FROM source_health_logs ORDER BY id DESC LIMIT 200").fetchall()
    conn.close()

    events = [dict(r) for r in events_rows]
    health = [dict(r) for r in health_rows]

    source_counts: Dict[str, int] = {}
    mag_buckets = {"< 4.5": 0, "4.5 - 5.5": 0, "5.5 - 6.5": 0, "6.5+": 0}
    gdacs_levels = {"Green": 0, "Orange": 0, "Red": 0, "Other": 0}
    latest_fetch = None

    for ev in events:
        src = ev.get("source", "Unknown")
        source_counts[src] = source_counts.get(src, 0) + 1
        fetched = ev.get("fetched_at")
        if fetched and (latest_fetch is None or fetched > latest_fetch):
            latest_fetch = fetched

        mag = ev.get("magnitude")
        if mag is not None:
            m = float(mag)
            if m < 4.5:
                mag_buckets["< 4.5"] += 1
            elif m <= 5.5:
                mag_buckets["4.5 - 5.5"] += 1
            elif m <= 6.5:
                mag_buckets["5.5 - 6.5"] += 1
            else:
                mag_buckets["6.5+"] += 1

        sev = str(ev.get("severity") or "").capitalize()
        if sev in gdacs_levels:
            gdacs_levels[sev] += 1
        elif sev:
            gdacs_levels["Other"] += 1

    # Source uptime & avg latency from health logs
    source_stats: Dict[str, Dict[str, Any]] = {}
    for h in health:
        sname = h.get("source_name", "Unknown")
        st = str(h.get("status", "")).lower()
        lat = h.get("response_time_ms")
        if sname not in source_stats:
            source_stats[sname] = {"total_checks": 0, "operational_checks": 0, "latencies": []}
        source_stats[sname]["total_checks"] += 1
        if "operational" in st:
            source_stats[sname]["operational_checks"] += 1
        if lat is not None:
            source_stats[sname]["latencies"].append(float(lat))

    source_health_summary = []
    for sname, sdata in source_stats.items():
        tot = sdata["total_checks"]
        op = sdata["operational_checks"]
        lats = sdata["latencies"]
        uptime = round((op / max(1, tot)) * 100, 1)
        avg_lat = round(sum(lats) / len(lats), 1) if lats else 0.0
        source_health_summary.append({
            "source_name": sname,
            "uptime_pct": uptime,
            "avg_latency_ms": avg_lat,
            "total_checks": tot,
        })

    return {
        "insufficient_data": len(events) == 0 and len(health) == 0,
        "total_external_events": len(events),
        "events_by_source": source_counts,
        "earthquake_magnitude_distribution": mag_buckets,
        "gdacs_alert_distribution": gdacs_levels,
        "source_health_summary": source_health_summary,
        "latest_fetched_at": latest_fetch,
    }


def get_response_performance_analytics(run_id: Optional[str] = None) -> Dict[str, Any]:
    """Calculate response performance and mission success metrics strictly from records."""
    run_id = resolve_run_id(run_id)
    conn = get_connection()
    if run_id:
        rm_row = conn.execute("SELECT * FROM run_metrics WHERE run_id = ?", (run_id,)).fetchone()
        inc_rows = conn.execute("SELECT status, route_eta_hours, route_distance_km FROM incidents WHERE run_id = ?", (run_id,)).fetchall()
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
    else:
        rm_row = conn.execute("SELECT AVG(total_lives_saved) as avg_saved, AVG(total_affected) as avg_affected FROM run_metrics").fetchone()
        inc_rows = conn.execute("SELECT status, route_eta_hours, route_distance_km FROM incidents LIMIT 500").fetchall()
        resp_row = conn.execute(
            """
            SELECT AVG((julianday(t2.timestamp) - julianday(t1.timestamp)) * 86400) as avg_sec
            FROM incident_timeline t1
            JOIN incident_timeline t2 ON t1.incident_id = t2.incident_id
            WHERE t1.new_status = 'DISPATCHED' AND t2.new_status = 'ARRIVED'
            """
        ).fetchone()
    conn.close()

    etas = [float(r["route_eta_hours"]) * 60 for r in inc_rows if r["route_eta_hours"] is not None]
    dists = [float(r["route_distance_km"]) for r in inc_rows if r["route_distance_km"] is not None]

    avg_eta = round(sum(etas) / len(etas), 1) if etas else None
    avg_dist = round(sum(dists) / len(dists), 1) if dists else None
    actual_resp_mins = round(float(resp_row["avg_sec"]) / 60, 1) if (resp_row and resp_row["avg_sec"] is not None) else None

    total_incs = len(inc_rows)
    contained_count = len([r for r in inc_rows if str(r["status"]).upper() in ("CONTAINED", "RESOLVED")])
    containment_rate = round((contained_count / total_incs) * 100, 1) if total_incs > 0 else None

    sim_score = None
    rescue_rate = None
    casualty_rate = None
    total_victims = None
    rescued_victims = None
    waiting_victims = None
    casualties = None
    eff = None

    if rm_row:
        rm = dict(rm_row)
        total_victims = rm.get("total_victims") if rm.get("total_victims") is not None else rm.get("total_affected", 0)
        rescued_victims = rm.get("rescued_victims") if rm.get("rescued_victims") is not None else rm.get("total_lives_saved", 0)
        casualties = rm.get("casualties") if rm.get("casualties") is not None else 0
        waiting_victims = rm.get("waiting_victims") if rm.get("waiting_victims") is not None else max(0, (total_victims or 0) - (rescued_victims or 0) - (casualties or 0))
        
        rescue_rate = rm.get("rescue_rate_pct")
        if rescue_rate is None and total_victims and total_victims > 0:
            rescue_rate = round((rescued_victims / total_victims) * 100, 1)
        casualty_rate = rm.get("casualty_rate_pct")
        if casualty_rate is None and total_victims and total_victims > 0:
            casualty_rate = round((casualties / total_victims) * 100, 1)
        
        sim_score = rm.get("simulation_performance_score")
        if sim_score is None and rescue_rate is not None and casualty_rate is not None:
            from utils.metrics import calculate_simulation_performance_score
            score_res = calculate_simulation_performance_score(
                rescue_rate_pct=rescue_rate,
                casualty_rate_pct=casualty_rate,
                resource_assignment_rate_pct=rm.get("resource_assignment_rate_pct"),
                planned_route_eta_mins=avg_eta,
            )
            sim_score = score_res.get("score")
        
        eff = f"{sim_score}%" if sim_score is not None else rm.get("overall_efficiency")
    elif total_incs > 0:
        eff = f"{containment_rate}%" if containment_rate is not None else None

    return {
        "insufficient_data": len(inc_rows) == 0 and rm_row is None,
        "total_victims": total_victims,
        "rescued_victims": rescued_victims,
        "waiting_victims": waiting_victims,
        "casualties": casualties,
        "rescue_rate_pct": rescue_rate,
        "casualty_rate_pct": casualty_rate,
        "simulation_performance_score": sim_score,
        "calculated_simulation_performance_score": sim_score,
        "mission_success_rate": sim_score if sim_score is not None else rescue_rate,
        "overall_efficiency": eff,
        "planned_route_eta_mins": avg_eta,
        "actual_response_time_mins": actual_resp_mins,
        "avg_eta_mins": avg_eta,
        "avg_distance_km": avg_dist,
        "detection_latency_secs": None,
        "containment_rate_pct": containment_rate,
    }


def get_data_quality_metrics() -> Dict[str, Any]:
    """Inspect SQLite database health, record completeness, and provider freshness."""
    conn = get_connection()
    tables = [
        "incidents",
        "simulation_runs",
        "simulation_resources",
        "facilities",
        "external_disaster_events",
        "source_health_logs",
        "agent_logs",
        "incident_timeline",
        "citizen_reports",
        "users",
        "sessions",
    ]

    record_counts: Dict[str, int] = {}
    for tbl in tables:
        try:
            cnt = conn.execute(f"SELECT COUNT(*) as c FROM {tbl}").fetchone()["c"]
            record_counts[tbl] = cnt
        except Exception:
            record_counts[tbl] = 0

    # Coordinate completeness on incidents
    try:
        total_inc = record_counts.get("incidents", 0)
        missing_coords = conn.execute(
            "SELECT COUNT(*) as c FROM incidents WHERE latitude IS NULL OR longitude IS NULL"
        ).fetchone()["c"]
        coord_completeness = round(((total_inc - missing_coords) / max(1, total_inc)) * 100, 1) if total_inc > 0 else 100.0
    except Exception:
        missing_coords = 0
        coord_completeness = 100.0

    # SQLite integrity check
    try:
        integrity_row = conn.execute("PRAGMA integrity_check(1);").fetchone()
        db_integrity = integrity_row[0] if integrity_row else "ok"
    except Exception as e:
        db_integrity = f"error: {str(e)}"

    # Recent provider fetch logs
    recent_fetches = []
    try:
        rows = conn.execute(
            """
            SELECT source_name, status, response_time_ms, timestamp
            FROM source_health_logs
            ORDER BY id DESC
            LIMIT 6
            """
        ).fetchall()
        recent_fetches = [dict(r) for r in rows]
    except Exception:
        pass

    conn.close()

    return {
        "status": "success",
        "db_integrity": db_integrity,
        "coordinate_completeness_pct": coord_completeness,
        "missing_coordinate_records": missing_coords,
        "record_counts": record_counts,
        "recent_provider_checks": recent_fetches,
        "data_provenance_model": "5-Tier (LIVE, DATABASE, CALCULATED, SIMULATED, UNAVAILABLE)",
    }


def get_run_summary(run_id: str) -> Dict[str, Any]:
    """Aggregated dashboard data in a single request for the EOC Command Overview."""
    run_id = resolve_run_id(run_id)
    conn = get_connection()

    # Incidents
    incidents = [dict(r) for r in conn.execute(
        "SELECT * FROM incidents WHERE run_id = ? ORDER BY incident_id DESC", (run_id,)
    ).fetchall()]

    # Resources
    resources = [dict(r) for r in conn.execute(
        "SELECT * FROM simulation_resources WHERE run_id = ?", (run_id,)
    ).fetchall()]

    # Facilities
    facilities = [dict(r) for r in conn.execute(
        "SELECT * FROM facilities WHERE run_id = ?", (run_id,)
    ).fetchall()]

    # Blocked roads
    blocked = [dict(r) for r in conn.execute(
        "SELECT * FROM blocked_roads WHERE run_id = ?", (run_id,)
    ).fetchall()]

    # Disaster zones
    zones = [dict(r) for r in conn.execute(
        "SELECT * FROM disaster_zones WHERE run_id = ?", (run_id,)
    ).fetchall()]

    # Run status
    run_row = conn.execute(
        "SELECT * FROM simulation_runs WHERE run_id = ?", (run_id,)
    ).fetchone()
    run_info = dict(run_row) if run_row else {}

    # Run metrics
    rm_row = conn.execute(
        "SELECT * FROM run_metrics WHERE run_id = ?", (run_id,)
    ).fetchone()
    run_metrics = dict(rm_row) if rm_row else {}

    conn.close()

    return {
        "run_id": run_id,
        "run_info": run_info,
        "run_metrics": run_metrics,
        "incidents": incidents,
        "resources": resources,
        "facilities": facilities,
        "blocked_roads": blocked,
        "disaster_zones": zones,
    }


# ── Authentication & Session Layer ─────────────────────────────────────────

def authenticate_user(email: str, password: str) -> Optional[Dict[str, Any]]:
    """Validate credentials securely against the users table. Returns user dict or None."""
    if not email or not password:
        return None
    email_clean = email.strip().lower()
    conn = get_connection()
    row = conn.execute(
        "SELECT user_id, name, email, password, role FROM users WHERE LOWER(email) = ?",
        (email_clean,),
    ).fetchone()
    if not row:
        conn.close()
        return None

    stored_hash = row["password"]
    if verify_password(password, stored_hash):
        # Auto-upgrade legacy static-salt hash to modern PBKDF2 unique salt
        if not stored_hash.startswith("pbkdf2_sha256$"):
            new_hash = hash_password(password)
            conn.execute("UPDATE users SET password = ? WHERE user_id = ?", (new_hash, row["user_id"]))
            conn.commit()
        conn.close()
        return {
            "user_id": row["user_id"],
            "name": row["name"],
            "email": row["email"],
            "role": row["role"],
        }
    conn.close()
    return None


def create_session(user_id: int, duration_hours: int = 24) -> str:
    """Create a cryptographically secure session token persisted in SQLite."""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=duration_hours)
    conn = get_connection()
    conn.execute(
        "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
        (token, user_id, expires_at.isoformat()),
    )
    conn.commit()
    conn.close()
    return token


def get_user_by_session(token: str) -> Optional[Dict[str, Any]]:
    """Retrieve user associated with an active, unexpired session token."""
    if not token:
        return None
    conn = get_connection()
    row = conn.execute(
        """
        SELECT u.user_id, u.name, u.email, u.role, s.expires_at
        FROM sessions s
        JOIN users u ON s.user_id = u.user_id
        WHERE s.token = ?
        """,
        (token,),
    ).fetchone()
    conn.close()
    if not row:
        return None

    # Check expiration
    try:
        exp_dt = datetime.fromisoformat(row["expires_at"])
        if exp_dt.tzinfo is None:
            exp_dt = exp_dt.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > exp_dt:
            revoke_session(token)
            return None
    except Exception:
        pass

    return {
        "user_id": row["user_id"],
        "name": row["name"],
        "email": row["email"],
        "role": row["role"],
    }


def revoke_session(token: str) -> bool:
    """Revoke/delete an active session token upon logout."""
    if not token:
        return False
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
    revoked = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return revoked


def cleanup_expired_sessions() -> None:
    """Purge expired session records from the database."""
    conn = get_connection()
    conn.execute("DELETE FROM sessions WHERE expires_at < ?", (datetime.utcnow().isoformat(),))
    conn.commit()
    conn.close()


def get_users() -> List[Dict[str, Any]]:
    """List all registered users without exposing password hashes."""
    conn = get_connection()
    rows = conn.execute("SELECT user_id, name, email, role FROM users ORDER BY user_id ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_user(user_id: int) -> bool:
    """Delete a user and their sessions."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


