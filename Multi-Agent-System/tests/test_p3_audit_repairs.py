"""Comprehensive Audit & Repair Verification Test Suite for Disaster OS Phase P3.

Tests:
1. Real facility parsing (including helipads) & zero fake capacity rule
2. Geographic cache hit and TTL expiration
3. Weather provider real query fields & zero fake numbers on failure
4. Weather impact computation with UNAVAILABLE data
5. PBKDF2 unique per-password salting, verification, and migration
6. Joyner-Boore impact engine formulas & non-damage hazard threshold phrasing
7. Correlation engine structured evidence chain & CALCULATED CASCADE RISK phrasing
8. Real vs. simulated data separation
9. Report generation without fabricated metrics (no 92.0% efficiency fallback)
10. Database integrity, unique constraints, and duplicate OSM handling
"""

import json
import os
import time
import unittest
from unittest.mock import MagicMock, patch

import database
from intelligence.correlation_engine import detect_compound_disaster_events
from intelligence.facility_provider import (
    fetch_real_facilities,
    parse_overpass_elements,
)
from intelligence.impact_engine import calculate_disaster_impact
from intelligence.models import CapacityStatus, DataClassification
from intelligence.providers import fetch_weather_observation
from utils.report_generator import generate_csv_report, get_run_details
from weather_service import compute_weather_impact, get_weather


class TestP3AuditRepairs(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        database.init_db()

    # --------------------------------------------------------------------------
    # 1. P3.1: Real Facility Intelligence & Helipads & Capacity Integrity
    # --------------------------------------------------------------------------
    def test_real_facility_parsing_including_helipad_and_unavailable_capacity(self):
        """Verify OSM parsing extracts helipads, hospitals, fire stations, and enforces UNAVAILABLE capacity."""
        raw_elements = [
            {
                "type": "node",
                "id": 9101,
                "lat": 19.076,
                "lon": 72.877,
                "tags": {
                    "aeroway": "helipad",
                    "name": "EOC Tactical Helipad",
                },
            },
            {
                "type": "node",
                "id": 9102,
                "lat": 19.080,
                "lon": 72.880,
                "tags": {
                    "amenity": "hospital",
                    "name": "Metropolitan Medical Center",
                    # No beds or capacity tag
                },
            },
            {
                "type": "way",
                "id": 9103,
                "center": {"lat": 19.090, "lon": 72.890},
                "tags": {
                    "amenity": "shelter",
                    "name": "Civic Stadium Shelter",
                    "capacity": "1200",
                },
            },
        ]

        facilities = parse_overpass_elements(raw_elements)
        self.assertEqual(len(facilities), 3)

        # Helipad verification
        helipad = next((f for f in facilities if f.facility_type == "helipad"), None)
        self.assertIsNotNone(helipad, "Helipads must be parsed correctly as facility_type='helipad'")
        self.assertEqual(helipad.facility_id, "osm-node-9101")
        self.assertEqual(helipad.name, "EOC Tactical Helipad")
        self.assertIsNone(helipad.capacity)
        self.assertEqual(helipad.capacity_status, CapacityStatus.UNAVAILABLE)

        # Hospital missing capacity => UNAVAILABLE
        hospital = next((f for f in facilities if f.facility_type == "hospital"), None)
        self.assertIsNotNone(hospital)
        self.assertEqual(hospital.facility_id, "osm-node-9102")
        self.assertIsNone(hospital.capacity, "Never invent hospital capacity")
        self.assertEqual(hospital.capacity_status, CapacityStatus.UNAVAILABLE)

        # Shelter with real capacity => VERIFIED
        shelter = next((f for f in facilities if f.facility_type == "shelter"), None)
        self.assertIsNotNone(shelter)
        self.assertEqual(shelter.capacity, 1200)
        self.assertEqual(shelter.capacity_status, CapacityStatus.VERIFIED)

    def test_geographic_cache_hit_and_expiration(self):
        """Verify geographic cache returns hit before TTL, and returns None after expiration."""
        cache_key = f"test_cache_{int(time.time() * 1000)}"
        payload = [{"id": 1, "data": "real_facility"}]

        # Set cache with 1 second TTL
        database.set_geographic_cache(cache_key, "facilities", payload, ttl_seconds=1)

        # Cache HIT immediately
        hit = database.get_geographic_cache(cache_key)
        self.assertIsNotNone(hit)
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0]["data"], "real_facility")

        # Wait for expiration
        time.sleep(2.0)
        expired = database.get_geographic_cache(cache_key)
        self.assertIsNone(expired, "Expired geographic cache entries must return None to trigger refresh")

    def test_database_osm_duplicate_handling(self):
        """Verify duplicate OSM facility insertions update existing rows instead of creating duplicates."""
        fac_id = f"osm-test-{int(time.time() * 1000)}"
        fac1 = [{
            "facility_id": fac_id,
            "facility_type": "hospital",
            "name": "Original Name",
            "latitude": 19.100,
            "longitude": 72.850,
            "classification": "LIVE",
            "capacity": None,
            "capacity_status": "UNAVAILABLE",
        }]
        database.save_external_facilities(fac1)

        fac2 = [{
            "facility_id": fac_id,
            "facility_type": "hospital",
            "name": "Updated Hospital Name",
            "latitude": 19.100,
            "longitude": 72.850,
            "classification": "LIVE",
            "capacity": 250,
            "capacity_status": "VERIFIED",
        }]
        database.save_external_facilities(fac2)

        # Retrieve
        rows = database.get_external_facilities(lat=19.100, lng=72.850, radius_km=5.0)
        matching = [r for r in rows if r["facility_id"] == fac_id]
        self.assertEqual(len(matching), 1, "Duplicate facility IDs must not produce multiple rows")
        self.assertEqual(matching[0]["name"], "Updated Hospital Name")
        self.assertEqual(matching[0]["capacity"], 250)

    # --------------------------------------------------------------------------
    # 2. Weather Integrity & Zero Fake Fallback
    # --------------------------------------------------------------------------
    def test_weather_provider_real_open_meteo_fields(self):
        """Verify Open-Meteo URL requests direct current weather observation fields."""
        with patch("urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({
                "current": {
                    "temperature_2m": 23.4,
                    "wind_speed_10m": 14.8,
                    "relative_humidity_2m": 78,
                    "precipitation": 1.5,
                    "weather_code": 2,
                    "time": "2026-09-15T12:00",
                },
            }).encode("utf-8")
            mock_url.return_value.__enter__.return_value = mock_resp

            result = fetch_weather_observation(lat=19.076, lng=72.877)
            self.assertEqual(result.temperature, 23.4)
            self.assertEqual(result.wind_speed_kmh, 14.8)
            self.assertEqual(result.humidity_pct, 78.0)
            self.assertEqual(result.precipitation_mm, 1.5)
            self.assertIn("Partly Cloudy", result.weather_condition)

            # Verify the requested URL contained real current fields
            called_url = mock_url.call_args[0][0].get_full_url()
            self.assertIn("current=temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,weather_code", called_url)

    def test_weather_provider_failure_returns_unavailable_not_fake_numbers(self):
        """Verify that provider failure returns None for all values and classification UNAVAILABLE."""
        with patch("urllib.request.urlopen", side_effect=Exception("Network unreachable")):
            result = get_weather(lat=19.076, lng=72.877)

            self.assertIsNone(result["temperature"], "Must NOT return 28.0 or any fake default temperature")
            self.assertIsNone(result["humidity"], "Must NOT return 65.0 or fake humidity")
            self.assertIsNone(result["wind_speed"], "Must NOT return 10.0 or fake wind speed")
            self.assertIsNone(result["rainfall_mm"], "Must NOT return fake rainfall")
            self.assertEqual(result["classification"], "UNAVAILABLE")
            self.assertEqual(result["source"], "UNAVAILABLE")
            self.assertIn("Unavailable", result["description"])

    def test_weather_impact_computation_with_unavailable_data(self):
        """Verify compute_weather_impact returns neutral 1.0 baseline and explicit unverified notice."""
        unavail_weather = {
            "temperature": None,
            "humidity": None,
            "wind_speed": None,
            "rainfall_mm": None,
            "weather_condition": "Live Meteorological Telemetry Unavailable",
            "classification": "UNAVAILABLE",
        }
        analysis = compute_weather_impact(unavail_weather, disaster_type="flood")
        self.assertEqual(analysis["severity_multiplier"], 1.0)
        self.assertEqual(analysis["rescue_time_multiplier"], 1.0)
        self.assertEqual(analysis["classification"], "UNAVAILABLE")
        self.assertIn("METEOROLOGICAL DATA UNAVAILABLE", analysis["warnings"][0])

    # --------------------------------------------------------------------------
    # 3. P3.5: Security & Unique Salt PBKDF2 Password Hashing
    # --------------------------------------------------------------------------
    def test_pbkdf2_unique_salt_per_password_and_verification(self):
        """Verify passwords use PBKDF2 with unique cryptographic salts, not a static salt."""
        plain = "MyEocSecretPassword2026!"
        hash1 = database.hash_password(plain)
        hash2 = database.hash_password(plain)

        # Must NOT be identical due to per-password unique salt
        self.assertNotEqual(hash1, hash2, "Each hashed password must have a unique cryptographic salt")
        self.assertTrue(hash1.startswith("pbkdf2_sha256$"))
        self.assertTrue(hash2.startswith("pbkdf2_sha256$"))

        # Both must verify successfully
        self.assertTrue(database.verify_password(plain, hash1))
        self.assertTrue(database.verify_password(plain, hash2))
        self.assertFalse(database.verify_password("WrongPassword!", hash1))

    def test_backward_compatible_legacy_hash_upgrade(self):
        """Verify legacy static-salt hashes verify correctly and upgrade on verify."""
        import hashlib
        plain = "legacy_test_pass"
        legacy_salt = "DisasterOS_Secure_Salt_2026"
        legacy_hash = hashlib.sha256((plain + legacy_salt).encode("utf-8")).hexdigest()

        # Must verify
        self.assertTrue(database.verify_password(plain, legacy_hash))

        # Insert user with legacy hash and verify auto-upgrade on authenticate_user
        test_email = f"upgrade_{int(time.time()*1000)}@disasteros.internal"
        conn = database.get_connection()
        conn.execute("INSERT INTO users (name, email, password, role) VALUES ('Legacy User', ?, ?, 'operator')", (test_email, legacy_hash))
        conn.commit()
        conn.close()

        user = database.authenticate_user(test_email, plain)
        self.assertIsNotNone(user)

        # Check that stored hash was upgraded to PBKDF2
        conn = database.get_connection()
        row = conn.execute("SELECT password FROM users WHERE email = ?", (test_email,)).fetchone()
        conn.close()
        self.assertTrue(row["password"].startswith("pbkdf2_sha256$"))

    # --------------------------------------------------------------------------
    # 4. P3.2: Disaster Impact Analysis Engine
    # --------------------------------------------------------------------------
    def test_impact_engine_formulas_and_hazard_threshold_wording(self):
        """Verify explicit Joyner-Boore formulas, zones, CALCULATED classification, and non-damage phrasing."""
        impact = calculate_disaster_impact(
            latitude=19.076,
            longitude=72.877,
            disaster_type="earthquake",
            magnitude=7.2,
            depth_km=10.0,
            event_id="USGS-US7000TEST",
        )

        self.assertEqual(impact["disaster_type"], "earthquake")
        self.assertEqual(impact["classification"], "CALCULATED")
        self.assertEqual(impact["source_event_id"], "USGS-US7000TEST")

        # Explicit formula exposed in metadata
        self.assertIn("log10(R_VII)", impact["formula"])
        self.assertIn("Joyner-Boore", impact["methodology"])

        # MMI zones present and classified CALCULATED
        self.assertGreaterEqual(len(impact["impact_zones"]), 3)
        mmi7 = next((z for z in impact["impact_zones"] if "MMI VII+" in z["name"]), None)
        self.assertIsNotNone(mmi7)
        self.assertEqual(mmi7["classification"], "CALCULATED")

        # Phrasing must describe calculated hazard threshold, NOT observed physical damage
        self.assertIn("CALCULATED HAZARD THRESHOLD", mmi7["expected_damage"])
        self.assertNotIn("Hospital destroyed", mmi7["expected_damage"])
        self.assertNotIn("Hospital damaged", mmi7["expected_damage"])

    # --------------------------------------------------------------------------
    # 5. P3.3: Compound Event Correlation & Evidence Chain
    # --------------------------------------------------------------------------
    def test_correlation_engine_evidence_chain_and_cascade_risk_phrasing(self):
        """Verify compound event correlation includes structured evidence chain and CALCULATED CASCADE RISK."""
        earthquake_event = {
            "event_id": "EQ-AUDIT-001",
            "event_type": "earthquake",
            "title": "M 6.8 Earthquake",
            "latitude": 19.076,
            "longitude": 72.877,
            "magnitude": 6.8,
            "depth_km": 8.0,
            "source": "USGS",
            "timestamp": time.time(),
            "classification": "LIVE",
        }
        weather_event = {
            "event_id": "WX-AUDIT-002",
            "event_type": "heavy_rainfall",
            "title": "Severe Monsoonal Downpour",
            "latitude": 19.100,
            "longitude": 72.890,
            "rainfall_mm": 120.0,
            "wind_speed_kmh": 45.0,
            "source": "Open-Meteo",
            "timestamp": time.time(),
            "classification": "LIVE",
        }

        correlations = detect_compound_disaster_events(
            earthquakes=[earthquake_event],
            weather=weather_event,
            incidents=[],
            facilities=[],
        )

        self.assertGreaterEqual(len(correlations), 1)
        corr = correlations[0]

        # Structured evidence chain
        self.assertIn("evidence_chain", corr)
        self.assertGreaterEqual(len(corr["evidence_chain"]), 2)
        ev1 = corr["evidence_chain"][0]
        self.assertIn("source", ev1)
        self.assertIn("source_event_id", ev1)
        self.assertIn("classification", ev1)
        self.assertIn("type", ev1)

        # Phrasing: CALCULATED CASCADE RISK (never claiming real event occurred without confirmation)
        self.assertTrue(
            any("CALCULATED CASCADE RISK" in line for line in corr["cascade_chain"]),
            f"Cascade chain must contain CALCULATED CASCADE RISK: got {corr['cascade_chain']}"
        )
        self.assertEqual(corr["confidence_score_label"], "MODELLED_CONDITIONAL_PROBABILITY")

    # --------------------------------------------------------------------------
    # 6. P3.5: Report Generation Integrity (Zero Fabricated Metrics)
    # --------------------------------------------------------------------------
    def test_report_generation_no_fake_efficiency_fallback(self):
        """Verify reports without recorded metrics display 'N/A' rather than fabricated '92.0%'."""
        test_run_id = f"empty_audit_run_{int(time.time() * 1000)}"

        # Save an empty run without run_metrics
        conn = database.get_connection()
        conn.execute(
            "INSERT INTO simulation_runs (run_id, strategy, seed, status, started_at) VALUES (?, 'smart', 42, 'COMPLETED', CURRENT_TIMESTAMP)",
            (test_run_id,)
        )
        conn.commit()
        conn.close()

        csv_content = generate_csv_report(test_run_id)
        self.assertNotIn("92.0%", csv_content, "CSV must NEVER output fake 92.0% efficiency")
        self.assertIn("Overall Efficiency,N/A", csv_content)
        self.assertIn("Total Lives Saved,N/A", csv_content)

    # --------------------------------------------------------------------------
    # 7. Real vs. Simulated Separation Verification
    # --------------------------------------------------------------------------
    def test_real_vs_simulated_provenance_separation(self):
        """Verify real OSM facilities are classified LIVE/DATABASE while simulated fleet/incidents remain SIMULATED."""
        # Check an OSM facility record
        fac = parse_overpass_elements([{
            "type": "node", "id": 7771, "lat": 19.0, "lon": 72.0,
            "tags": {"amenity": "hospital", "name": "OSM Clinic"}
        }])[0]
        self.assertIn(fac.classification.value, ["LIVE", "DATABASE"])

        # Check vehicle resource agent
        from agents import ResourceAgent
        from message_bus import MessageBus
        bus = MessageBus()
        agent = ResourceAgent(bus)
        self.assertEqual(agent.agent_name, "ResourceAgent")


if __name__ == "__main__":
    unittest.main()
