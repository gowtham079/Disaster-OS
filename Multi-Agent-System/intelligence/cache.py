"""Configurable Short-Lived Caching Manager.

Provides thread-safe caching with TTL, freshness tracking, and age calculations.
"""

import time
import threading
from typing import Any, Dict, Optional, Tuple


class IntelligenceCache:
    def __init__(self, default_ttl: float = 180.0):
        self.default_ttl = default_ttl
        self._cache: Dict[str, Tuple[Any, float, float]] = {}  # key -> (data, fetched_at, expires_at)
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Tuple[Any, Dict[str, Any]]]:
        """Get cached item along with freshness metadata (data, metadata_dict)."""
        now = time.time()
        with self._lock:
            if key not in self._cache:
                return None
            data, fetched_at, expires_at = self._cache[key]
            if now > expires_at:
                del self._cache[key]
                return None

            meta = {
                "fetched_at": fetched_at,
                "expires_at": expires_at,
                "age_seconds": round(now - fetched_at, 1),
                "ttl_seconds": round(expires_at - now, 1),
                "is_stale": False,
            }
            return data, meta

    def set(self, key: str, data: Any, ttl: Optional[float] = None):
        """Set cache item with TTL in seconds."""
        now = time.time()
        effective_ttl = ttl if ttl is not None else self.default_ttl
        expires_at = now + effective_ttl
        with self._lock:
            self._cache[key] = (data, now, expires_at)

    def clear(self):
        with self._lock:
            self._cache.clear()


# Global cache instance
intelligence_cache = IntelligenceCache()
