"""Unit Tests for Weather Data Integrity & Zero Fabricated Defaults (P3 Step 3).

Verifies all 12 operational requirements:
1. Valid Open-Meteo response returns real values.
2. Missing humidity returns None.
3. Missing precipitation returns None.
4. Missing wind returns None.
5. Missing temperature returns None.
6. Provider failure returns UNAVAILABLE.
7. Partial response preserves available values.
8. Actual rainfall 0 remains exactly 0.
9. Missing rainfall does NOT become 0.
10. Weather impact with unavailable input does not claim a verified weather hazard.
11. WeatherAgent does not fabricate values.
12. Frontend/backend payload does not introduce weather defaults.
"""

import json
import os
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app import app
from intelligence.cache import intelligence_cache
from intelligence.models import DataClassification
from intelligence.providers import fetch_weather_observation
from message_bus import AgentMessage, MessageBus
from models import WeatherAnalysis
from weather_service import compute_weather_impact, get_weather
from agents import WeatherAgent


class TestWeatherDataIntegrity(unittest.TestCase):
    def setUp(self):
        intelligence_cache.clear()
        self.client = TestClient(app)

    def tearDown(self):
        intelligence_cache.clear()

    # 1. Valid Open-Meteo response returns real values
    @patch.dict("os.environ", {"OPENWEATHER_API_KEY": ""})
    @patch("intelligence.providers._http_get_with_retry")
    def test_01_valid_open_meteo_returns_real_values(self, mock_http):
        mock_payload = {
            "current": {
                "temperature_2m": 29.5,
                "relative_humidity_2m": 62,
                "precipitation": 4.5,
                "wind_speed_10m": 18.2,
                "weather_code": 3,
                "time": "2026-09-20T12:00",
            }
        }
        mock_http.return_value = json.dumps(mock_payload).encode("utf-8")

        obs = fetch_weather_observation(19.076, 72.878)
        self.assertIsNotNone(obs)
        self.assertEqual(obs.provider, "Open-Meteo")
        self.assertEqual(obs.temperature, 29.5)
        self.assertEqual(obs.humidity_pct, 62.0)
        self.assertEqual(obs.precipitation_mm, 4.5)
        self.assertEqual(obs.wind_speed_kmh, 18.2)
        self.assertEqual(obs.weather_condition, "Overcast")
        self.assertEqual(obs.classification, DataClassification.LIVE)

        w_data = get_weather(19.076, 72.878)
        self.assertEqual(w_data["temperature"], 29.5)
        self.assertEqual(w_data["humidity"], 62.0)
        self.assertEqual(w_data["rainfall_mm"], 4.5)
        self.assertEqual(w_data["wind_speed"], 18.2)
        self.assertEqual(w_data["classification"], "LIVE")

    # 2. Missing humidity returns None
    @patch.dict("os.environ", {"OPENWEATHER_API_KEY": ""})
    @patch("intelligence.providers._http_get_with_retry")
    def test_02_missing_humidity_returns_none(self, mock_http):
        mock_payload = {
            "current": {
                "temperature_2m": 25.0,
                "precipitation": 1.0,
                "wind_speed_10m": 10.0,
                "weather_code": 1,
            }
        }
        mock_http.return_value = json.dumps(mock_payload).encode("utf-8")

        obs = fetch_weather_observation(19.076, 72.878)
        self.assertIsNotNone(obs)
        self.assertIsNone(obs.humidity_pct, "Missing humidity must remain None, not 0 or 65")

        w_data = get_weather(19.076, 72.878)
        self.assertIsNone(w_data["humidity"], "get_weather must return None for missing humidity")

    # 3. Missing precipitation returns None
    @patch.dict("os.environ", {"OPENWEATHER_API_KEY": ""})
    @patch("intelligence.providers._http_get_with_retry")
    def test_03_missing_precipitation_returns_none(self, mock_http):
        mock_payload = {
            "current": {
                "temperature_2m": 26.0,
                "relative_humidity_2m": 70,
                "wind_speed_10m": 12.0,
                "weather_code": 0,
            }
        }
        mock_http.return_value = json.dumps(mock_payload).encode("utf-8")

        obs = fetch_weather_observation(19.076, 72.878)
        self.assertIsNotNone(obs)
        self.assertIsNone(obs.precipitation_mm, "Missing precipitation must remain None, never 0.0")

        w_data = get_weather(19.076, 72.878)
        self.assertIsNone(w_data["rainfall_mm"], "get_weather must return None for missing precipitation")

    # 4. Missing wind returns None
    @patch.dict("os.environ", {"OPENWEATHER_API_KEY": ""})
    @patch("intelligence.providers._http_get_with_retry")
    def test_04_missing_wind_returns_none(self, mock_http):
        mock_payload = {
            "current": {
                "temperature_2m": 27.0,
                "relative_humidity_2m": 60,
                "precipitation": 0.0,
                "weather_code": 0,
            }
        }
        mock_http.return_value = json.dumps(mock_payload).encode("utf-8")

        obs = fetch_weather_observation(19.076, 72.878)
        self.assertIsNotNone(obs)
        self.assertIsNone(obs.wind_speed_kmh, "Missing wind must remain None, never 0.0 or 15.0")

        w_data = get_weather(19.076, 72.878)
        self.assertIsNone(w_data["wind_speed"], "get_weather must return None for missing wind speed")

    # 5. Missing temperature returns None
    @patch.dict("os.environ", {"OPENWEATHER_API_KEY": ""})
    @patch("intelligence.providers._http_get_with_retry")
    def test_05_missing_temperature_returns_none(self, mock_http):
        mock_payload = {
            "current": {
                "relative_humidity_2m": 60,
                "precipitation": 2.0,
                "wind_speed_10m": 15.0,
                "weather_code": 1,
            }
        }
        mock_http.return_value = json.dumps(mock_payload).encode("utf-8")

        obs = fetch_weather_observation(19.076, 72.878)
        self.assertIsNotNone(obs)
        self.assertIsNone(obs.temperature, "Missing temperature must remain None, never 28.0")

        w_data = get_weather(19.076, 72.878)
        self.assertIsNone(w_data["temperature"], "get_weather must return None for missing temperature")

    # 6. Provider failure returns UNAVAILABLE
    @patch.dict("os.environ", {"OPENWEATHER_API_KEY": ""})
    @patch("intelligence.providers._http_get_with_retry")
    def test_06_provider_failure_returns_unavailable(self, mock_http):
        mock_http.side_effect = Exception("Open-Meteo connection reset")

        w_data = get_weather(19.076, 72.878)
        self.assertEqual(w_data["classification"], "UNAVAILABLE")
        self.assertEqual(w_data["source"], "UNAVAILABLE")
        self.assertIsNone(w_data["temperature"])
        self.assertIsNone(w_data["humidity"])
        self.assertIsNone(w_data["wind_speed"])
        self.assertIsNone(w_data["rainfall_mm"])

    # 7. Partial response preserves available values
    @patch.dict("os.environ", {"OPENWEATHER_API_KEY": ""})
    @patch("intelligence.providers._http_get_with_retry")
    def test_07_partial_response_preserves_available_values(self, mock_http):
        mock_payload = {
            "current": {
                "temperature_2m": 21.3,
                "precipitation": 12.5,
                # humidity and wind are missing
                "weather_code": 61,
            }
        }
        mock_http.return_value = json.dumps(mock_payload).encode("utf-8")

        obs = fetch_weather_observation(19.076, 72.878)
        self.assertIsNotNone(obs)
        self.assertEqual(obs.temperature, 21.3)
        self.assertEqual(obs.precipitation_mm, 12.5)
        self.assertIsNone(obs.humidity_pct)
        self.assertIsNone(obs.wind_speed_kmh)
        self.assertEqual(obs.classification, DataClassification.LIVE)

        w_data = get_weather(19.076, 72.878)
        self.assertEqual(w_data["temperature"], 21.3)
        self.assertEqual(w_data["rainfall_mm"], 12.5)
        self.assertIsNone(w_data["humidity"])
        self.assertIsNone(w_data["wind_speed"])

    # 8. Actual rainfall 0 remains exactly 0
    @patch.dict("os.environ", {"OPENWEATHER_API_KEY": ""})
    @patch("intelligence.providers._http_get_with_retry")
    def test_08_actual_rainfall_zero_remains_zero(self, mock_http):
        mock_payload = {
            "current": {
                "temperature_2m": 28.0,
                "relative_humidity_2m": 50,
                "precipitation": 0.0,
                "wind_speed_10m": 12.0,
                "weather_code": 0,
            }
        }
        mock_http.return_value = json.dumps(mock_payload).encode("utf-8")

        obs = fetch_weather_observation(19.076, 72.878)
        self.assertIsNotNone(obs)
        self.assertIsNotNone(obs.precipitation_mm)
        self.assertEqual(obs.precipitation_mm, 0.0)

        w_data = get_weather(19.076, 72.878)
        self.assertIsNotNone(w_data["rainfall_mm"])
        self.assertEqual(w_data["rainfall_mm"], 0.0)

    # 9. Missing rainfall does NOT become 0
    @patch.dict("os.environ", {"OPENWEATHER_API_KEY": ""})
    @patch("intelligence.providers._http_get_with_retry")
    def test_09_missing_rainfall_does_not_become_zero(self, mock_http):
        mock_payload = {
            "current": {
                "temperature_2m": 28.0,
                "relative_humidity_2m": 50,
                "wind_speed_10m": 12.0,
                # precipitation completely omitted
                "weather_code": 0,
            }
        }
        mock_http.return_value = json.dumps(mock_payload).encode("utf-8")

        obs = fetch_weather_observation(19.076, 72.878)
        self.assertIsNotNone(obs)
        self.assertIsNone(obs.precipitation_mm, "Missing precipitation key must be None, NOT 0.0")

        w_data = get_weather(19.076, 72.878)
        self.assertIsNone(w_data["rainfall_mm"], "Missing rainfall in get_weather must be None, NOT 0.0")

    # 10. Weather impact with unavailable input does not claim a verified weather hazard
    def test_10_weather_impact_unavailable_does_not_claim_verified_hazard(self):
        # Case A: Explicit UNAVAILABLE classification
        unavail_payload = {
            "classification": "UNAVAILABLE",
            "temperature": None,
            "rainfall_mm": None,
            "wind_speed": None,
        }
        impact_a = compute_weather_impact(unavail_payload)
        self.assertEqual(impact_a["classification"], "UNAVAILABLE")
        self.assertEqual(impact_a["status"], "INSUFFICIENT_EVIDENCE")
        self.assertFalse(impact_a["verified"])
        self.assertEqual(impact_a["severity_multiplier"], 1.0)
        self.assertIn("METEOROLOGICAL DATA UNAVAILABLE", impact_a["warnings"][0])
        self.assertIn("NOT VERIFIED", impact_a["notes"])

        # Case B: All metrics None
        empty_payload = {
            "classification": "LIVE",
            "temperature": None,
            "rainfall_mm": None,
            "wind_speed": None,
        }
        impact_b = compute_weather_impact(empty_payload)
        self.assertEqual(impact_b["classification"], "UNAVAILABLE")
        self.assertEqual(impact_b["status"], "INSUFFICIENT_EVIDENCE")
        self.assertFalse(impact_b["verified"])
        self.assertIn("NOT VERIFIED", impact_b["notes"])

    # 11. WeatherAgent does not fabricate values
    @patch("agents.get_weather")
    def test_11_weather_agent_does_not_fabricate_values(self, mock_get_weather):
        bus = MessageBus()
        agent = WeatherAgent(bus)

        # Mock unavailable weather
        mock_get_weather.return_value = {
            "source": "UNAVAILABLE",
            "temperature": None,
            "humidity": None,
            "wind_speed": None,
            "rainfall_mm": None,
            "description": "UNAVAILABLE",
            "timestamp": 1726830000.0,
            "classification": "UNAVAILABLE",
        }

        published_messages = []
        def listener(msg):
            if msg.message_type == "WEATHER_ANALYZED":
                published_messages.append(msg)
        bus.register_agent("TestListener", listener)

        # Trigger WeatherAgent
        trigger = AgentMessage(
            sender="TestRunner",
            receiver="WeatherAgent",
            message_type="INCIDENT_REPORTED",
            payload={"latitude": 19.076, "longitude": 72.878},
        )
        agent.process_message(trigger)

        self.assertEqual(len(published_messages), 1)
        p = published_messages[0].payload

        self.assertIsNone(p["temperature"])
        self.assertIsNone(p["humidity"])
        self.assertIsNone(p["wind_speed"])
        self.assertIsNone(p["rainfall_mm"])
        self.assertIsNone(p["fire_spread_speed_kmh"], "Fire spread speed must be None when wind is unavailable")
        self.assertIsNone(p["flood_rise_rate_cmh"], "Flood rise rate must be None when rainfall is unavailable")
        self.assertEqual(p["classification"], "UNAVAILABLE")

    # 12. Frontend/backend payload does not introduce weather defaults
    @patch("app.fetch_weather_observation")
    @patch("weather_service.fetch_weather_observation")
    def test_12_frontend_backend_payload_does_not_introduce_weather_defaults(self, mock_ws_fetch, mock_app_fetch):
        # When weather service is unreachable
        mock_ws_fetch.return_value = None
        mock_app_fetch.return_value = None

        # Endpoint 1: /api/weather/{lat}/{lng}
        res1 = self.client.get("/api/weather/19.076/72.878")
        self.assertEqual(res1.status_code, 200)
        d1 = res1.json()
        self.assertEqual(d1["weather"]["classification"], "UNAVAILABLE")
        self.assertIsNone(d1["weather"]["temperature"])
        self.assertIsNone(d1["weather"]["rainfall_mm"])
        self.assertIsNone(d1["weather"]["humidity"])
        self.assertEqual(d1["impact"]["status"], "INSUFFICIENT_EVIDENCE")
        self.assertFalse(d1["impact"]["verified"])

        # Endpoint 2: /api/intelligence/weather/{lat}/{lng}
        res2 = self.client.get("/api/intelligence/weather/19.076/72.878")
        self.assertEqual(res2.status_code, 503)
        d2 = res2.json()
        self.assertEqual(d2["classification"], "UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
