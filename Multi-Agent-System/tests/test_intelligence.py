"""Unit Tests for Live Intelligence & Provenance Module.

Uses unittest and unittest.mock to test providers, health tracking, caching, retries,
deduplication, and classification without making live network requests.
"""

import json
import time
import unittest
from unittest.mock import MagicMock, patch

from intelligence.cache import IntelligenceCache, intelligence_cache
from intelligence.models import (
    DataClassification,
    EarthquakeEvent,
    ExternalDisasterEvent,
    RouteClassification,
    RouteResult,
    SourceHealthStatus,
    WeatherObservation,
)
from intelligence.providers import (
    fetch_gdacs_disasters,
    fetch_usgs_earthquakes,
    fetch_weather_observation,
)
from intelligence.source_health import SourceHealthManager


class TestIntelligenceModule(unittest.TestCase):

    def setUp(self):
        self.health_mgr = SourceHealthManager()
        self.cache = IntelligenceCache(default_ttl=10.0)
        intelligence_cache.clear()

    # 1. Test USGS Earthquake Fetching & Deduplication
    @patch("intelligence.providers._http_get_with_retry")
    def test_usgs_success_and_deduplication(self, mock_http):
        mock_geojson = {
            "features": [
                {
                    "id": "us7000abc1",
                    "properties": {"title": "M 5.2 - 10km N of City A", "mag": 5.2, "time": 1600000000000, "place": "City A"},
                    "geometry": {"coordinates": [75.5, 25.1, 10.0]},
                },
                {
                    "id": "us7000abc1",  # Duplicate ID
                    "properties": {"title": "M 5.2 - Duplicate Event", "mag": 5.2, "time": 1600000000000, "place": "City A"},
                    "geometry": {"coordinates": [75.5, 25.1, 10.0]},
                },
                {
                    "id": "us7000xyz2",
                    "properties": {"title": "M 6.1 - 25km S of City B", "mag": 6.1, "time": 1600000500000, "place": "City B"},
                    "geometry": {"coordinates": [80.2, 13.1, 15.0]},
                },
            ]
        }
        mock_http.return_value = json.dumps(mock_geojson).encode("utf-8")

        events = fetch_usgs_earthquakes(mag_min=4.5)
        self.assertEqual(len(events), 2)  # Deduplicated from 3 to 2
        self.assertEqual(events[0].source_event_id, "us7000abc1")
        self.assertEqual(events[0].classification, DataClassification.LIVE)
        self.assertEqual(events[0].magnitude, 5.2)
        self.assertEqual(events[1].magnitude, 6.1)
        self.assertEqual(events[1].severity, "high")

    @patch("intelligence.providers._http_get_with_retry")
    def test_usgs_failure_returns_empty(self, mock_http):
        mock_http.side_effect = TimeoutError("Connection timed out")

        events = fetch_usgs_earthquakes(mag_min=4.5)
        self.assertEqual(events, [])  # Zero fake data on failure

    # 2. Test GDACS Alerts Parsing
    @patch("intelligence.providers._http_get_with_retry")
    def test_gdacs_rss_parsing(self, mock_http):
        mock_rss = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0" xmlns:georss="http://www.georss.org/georss">
          <channel>
            <item>
              <title>Red Alert for Tropical Cyclone Impact</title>
              <link>https://www.gdacs.org/report.aspx?eventid=101</link>
              <guid>gdacs-101</guid>
              <georss:point>19.07 72.87</georss:point>
            </item>
          </channel>
        </rss>
        """
        mock_http.return_value = mock_rss.encode("utf-8")

        alerts = fetch_gdacs_disasters()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].source, "GDACS")
        self.assertEqual(alerts[0].severity, "high")
        self.assertEqual(alerts[0].latitude, 19.07)
        self.assertEqual(alerts[0].longitude, 72.87)

    # 3. Test Weather Provider Fallback & Zero Fake Data
    @patch.dict("os.environ", {"OPENWEATHER_API_KEY": "test_key"})
    @patch("intelligence.providers._http_get_with_retry")
    def test_weather_openweather_success(self, mock_http):
        mock_ow = {
            "main": {"temp": 28.4, "feels_like": 31.0, "humidity": 70},
            "wind": {"speed": 5.0},
            "weather": [{"description": "heavy rain"}],
            "rain": {"1h": 4.5},
        }
        mock_http.return_value = json.dumps(mock_ow).encode("utf-8")

        obs = fetch_weather_observation(19.07, 72.87)
        self.assertIsNotNone(obs)
        self.assertEqual(obs.provider, "OpenWeather")
        self.assertEqual(obs.temperature, 28.4)
        self.assertEqual(obs.classification, DataClassification.LIVE)

    @patch.dict("os.environ", {"OPENWEATHER_API_KEY": ""})
    @patch("intelligence.providers._http_get_with_retry")
    def test_weather_fallback_to_openmeteo(self, mock_http):
        mock_om = {"current_weather": {"temperature": 26.2, "windspeed": 14.5}}
        mock_http.return_value = json.dumps(mock_om).encode("utf-8")

        obs = fetch_weather_observation(19.08, 72.88)
        self.assertIsNotNone(obs)
        self.assertEqual(obs.provider, "Open-Meteo")
        self.assertEqual(obs.temperature, 26.2)

    @patch.dict("os.environ", {"OPENWEATHER_API_KEY": "test_key"})
    @patch("intelligence.providers._http_get_with_retry")
    def test_weather_complete_failure(self, mock_http):
        mock_http.side_effect = Exception("Service unavailable")

        obs = fetch_weather_observation(19.09, 72.89)
        self.assertIsNone(obs)  # Never returns fake live data

    # 4. Test Caching TTL & Freshness Metadata
    def test_cache_expiration(self):
        self.cache.set("test_key", {"val": 123}, ttl=0.1)
        res1 = self.cache.get("test_key")
        self.assertIsNotNone(res1)
        self.assertEqual(res1[0]["val"], 123)

        time.sleep(0.15)
        res2 = self.cache.get("test_key")
        self.assertIsNone(res2)

    # 5. Test Source Health Status Transitions
    def test_source_health_manager_transitions(self):
        mgr = SourceHealthManager()
        mgr.record_success("USGS", response_time_ms=120.5, record_count=10)

        status = mgr.get_status("USGS")
        self.assertEqual(status.status, SourceHealthStatus.OPERATIONAL)
        self.assertEqual(status.record_count, 10)

        mgr.record_failure("USGS", "HTTP 503 Server Error")
        status2 = mgr.get_status("USGS")
        self.assertEqual(status2.status, SourceHealthStatus.DEGRADED)
        self.assertEqual(status2.error_message, "HTTP 503 Server Error")


if __name__ == "__main__":
    unittest.main()
