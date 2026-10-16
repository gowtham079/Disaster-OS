"""Feature engineering pipeline for the disaster severity prediction model.

Extracts and transforms raw incident data into a fixed-size numeric feature
vector that scikit-learn models can consume. All feature names, ordering,
and defaults are defined here so that training and inference share the same
pipeline and cannot drift.
"""

import numpy as np
from typing import Any, Dict, List

# --- Canonical feature definitions ----------------------------------------

DISASTER_TYPES = ["flood", "earthquake", "fire", "cyclone"]

NUMERIC_FEATURES = [
    "people_affected",
    "temperature",
    "humidity",
    "wind_speed",
    "rainfall_mm",
    "population_density",
    "infrastructure_score",
    "hour_of_day",
    "month",
]

# One-hot columns first, then numerics — this order is baked into models.
FEATURE_ORDER: List[str] = [
    f"disaster_type_{dt}" for dt in DISASTER_TYPES
] + NUMERIC_FEATURES

NUMERIC_DEFAULTS: Dict[str, float] = {
    "people_affected": 50,
    "temperature": 30.0,
    "humidity": 60.0,
    "wind_speed": 10.0,
    "rainfall_mm": 0.0,
    "population_density": 3000,
    "infrastructure_score": 5,
    "hour_of_day": 12,
    "month": 6,
}

SEVERITY_CLASSES = ["low", "medium", "high"]


def extract_features(incident: Dict[str, Any]) -> Dict[str, float]:
    """Convert a raw incident dict into a flat feature dict.

    Parameters
    ----------
    incident : dict
        Raw incident with keys like ``disaster_type``, ``people_affected``,
        ``temperature``, etc.  Missing keys fall back to sensible defaults.

    Returns
    -------
    dict
        Feature dict whose keys are exactly ``FEATURE_ORDER``.
    """
    features: Dict[str, float] = {}

    # One-hot encode disaster type
    dtype = incident.get("disaster_type", "unknown").lower()
    for dt in DISASTER_TYPES:
        features[f"disaster_type_{dt}"] = 1.0 if dtype == dt else 0.0

    # Numeric features with defaults
    for feat in NUMERIC_FEATURES:
        val = incident.get(feat)
        if val is None:
            val = NUMERIC_DEFAULTS[feat]
        features[feat] = float(val)

    return features


def features_to_array(features: Dict[str, float]) -> np.ndarray:
    """Convert a feature dict to a 1×N numpy array in canonical order.

    Parameters
    ----------
    features : dict
        Must contain all keys from ``FEATURE_ORDER``.

    Returns
    -------
    np.ndarray
        Shape ``(1, len(FEATURE_ORDER))``.
    """
    return np.array(
        [features.get(k, 0.0) for k in FEATURE_ORDER], dtype=np.float64
    ).reshape(1, -1)


def batch_to_array(feature_dicts: List[Dict[str, float]]) -> np.ndarray:
    """Convert a list of feature dicts to an N×F numpy array.

    Parameters
    ----------
    feature_dicts : list of dict
        Each dict as returned by :func:`extract_features`.

    Returns
    -------
    np.ndarray
        Shape ``(len(feature_dicts), len(FEATURE_ORDER))``.
    """
    rows = []
    for fd in feature_dicts:
        rows.append([fd.get(k, 0.0) for k in FEATURE_ORDER])
    return np.array(rows, dtype=np.float64)
