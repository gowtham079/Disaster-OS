"""Source Health Tracker Manager.

Tracks real-time health, latency, error states, and record counts for external providers.
"""

import time
import logging
from typing import Dict, List, Optional
from intelligence.models import ExternalDataSourceStatus, SourceHealthStatus

logger = logging.getLogger(__name__)


class SourceHealthManager:
    def __init__(self):
        self._sources: Dict[str, ExternalDataSourceStatus] = {
            "USGS": ExternalDataSourceStatus(name="USGS", status=SourceHealthStatus.UNAVAILABLE),
            "GDACS": ExternalDataSourceStatus(name="GDACS", status=SourceHealthStatus.UNAVAILABLE),
            "OpenWeather": ExternalDataSourceStatus(name="OpenWeather", status=SourceHealthStatus.UNAVAILABLE),
            "Open-Meteo": ExternalDataSourceStatus(name="Open-Meteo", status=SourceHealthStatus.UNAVAILABLE),
            "OSRM": ExternalDataSourceStatus(name="OSRM", status=SourceHealthStatus.UNAVAILABLE),
            "Nominatim": ExternalDataSourceStatus(name="Nominatim", status=SourceHealthStatus.UNAVAILABLE),
            "Overpass": ExternalDataSourceStatus(name="Overpass", status=SourceHealthStatus.UNAVAILABLE),
        }

    def record_success(self, name: str, response_time_ms: float, record_count: int = 0):
        now = time.time()
        source = self._sources.get(name)
        if not source:
            source = ExternalDataSourceStatus(name=name)
            self._sources[name] = source

        source.status = SourceHealthStatus.OPERATIONAL
        source.last_successful_fetch = now
        source.response_time_ms = round(response_time_ms, 2)
        source.error_message = None
        source.record_count = record_count
        source.freshness_seconds = 0.0

    def record_failure(self, name: str, error_message: str):
        now = time.time()
        source = self._sources.get(name)
        if not source:
            source = ExternalDataSourceStatus(name=name)
            self._sources[name] = source

        source.last_failed_fetch = now
        source.error_message = error_message

        # Determine status based on whether we ever had a successful fetch
        if source.last_successful_fetch is not None:
            age = now - source.last_successful_fetch
            if age < 600:
                source.status = SourceHealthStatus.DEGRADED
                source.freshness_seconds = round(age, 1)
            else:
                source.status = SourceHealthStatus.STALE
                source.freshness_seconds = round(age, 1)
        else:
            source.status = SourceHealthStatus.UNAVAILABLE
            source.freshness_seconds = None

    def get_status(self, name: str) -> Optional[ExternalDataSourceStatus]:
        now = time.time()
        source = self._sources.get(name)
        if source and source.last_successful_fetch:
            source.freshness_seconds = round(now - source.last_successful_fetch, 1)
        return source

    def get_all_statuses(self) -> List[ExternalDataSourceStatus]:
        now = time.time()
        results = []
        for source in self._sources.values():
            if source.last_successful_fetch:
                source.freshness_seconds = round(now - source.last_successful_fetch, 1)
            results.append(source)
        return results


# Global singleton instance
health_manager = SourceHealthManager()
