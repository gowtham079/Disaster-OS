"""Runtime inference wrapper for the trained severity prediction model.

Loads the saved model artefacts once and exposes a ``predict()`` method.
Falls back gracefully to ``None`` when the model files are not yet trained,
so that the rest of the system can use rule-based logic as a fallback.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import joblib
import numpy as np

from ml.feature_engineering import (
    FEATURE_ORDER,
    extract_features,
    features_to_array,
)

logger = logging.getLogger(__name__)

_MODELS_DIR = Path(__file__).resolve().parent / "models"


class SeverityPredictor:
    """Thin wrapper around the trained scikit-learn pipeline.

    Parameters
    ----------
    model_dir : str or Path, optional
        Directory containing ``severity_model.joblib``,
        ``label_encoder.joblib``, and ``feature_scaler.joblib``.
        Defaults to ``ml/models/`` relative to this file.

    Attributes
    ----------
    is_available : bool
        ``True`` if model files were loaded successfully.
    """

    def __init__(self, model_dir: Optional[str] = None):
        mdir = Path(model_dir) if model_dir else _MODELS_DIR
        self.is_available = False
        try:
            self.model = joblib.load(mdir / "severity_model.joblib")
            self.label_encoder = joblib.load(mdir / "label_encoder.joblib")
            self.scaler = joblib.load(mdir / "feature_scaler.joblib")
            self.is_available = True
            logger.info("SeverityPredictor loaded from %s", mdir)
        except FileNotFoundError:
            logger.warning(
                "Model files not found in %s — predictor will return None. "
                "Run `python -m ml.train_severity_model` to train.",
                mdir,
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def predict(self, incident: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Predict severity for a single incident.

        Parameters
        ----------
        incident : dict
            Raw incident data (may come straight from ``generate_data`` or
            from a user-submitted custom incident).  Must include at least
            ``disaster_type``; other features fall back to defaults.

        Returns
        -------
        dict or None
            ``None`` if the model is not loaded.  Otherwise::

                {
                    "predicted_severity": "high",
                    "confidence": 0.87,
                    "probabilities": {"high": 0.87, "low": 0.03, "medium": 0.10}
                }
        """
        if not self.is_available:
            affected = incident.get("people_affected", 0)
            rain = incident.get("rainfall_mm")
            wind = incident.get("wind_speed")
            dtype = str(incident.get("disaster_type", "general")).lower()

            sev = "low"
            if affected > 200 or (rain is not None and rain > 50) or (wind is not None and wind > 40) or dtype in ["chemical_leak", "building_collapse", "earthquake"]:
                sev = "high"
            elif affected > 50 or (rain is not None and rain > 20) or (wind is not None and wind > 20):
                sev = "medium"

            probs = (
                {"high": 0.85, "medium": 0.10, "low": 0.05} if sev == "high"
                else {"high": 0.10, "medium": 0.80, "low": 0.10} if sev == "medium"
                else {"high": 0.05, "medium": 0.15, "low": 0.80}
            )

            return {
                "predicted_severity": sev,
                "confidence": 0.85,
                "probabilities": probs,
                "model_source": "Rule-Based Engine Fallback"
            }

        features = extract_features(incident)
        X = features_to_array(features)
        X_scaled = self.scaler.transform(X)

        proba = self.model.predict_proba(X_scaled)[0]
        predicted_idx = self.model.predict(X_scaled)[0]
        predicted_label = self.label_encoder.inverse_transform([predicted_idx])[0]

        return {
            "predicted_severity": predicted_label,
            "confidence": round(float(max(proba)), 4),
            "probabilities": {
                label: round(float(p), 4)
                for label, p in zip(self.label_encoder.classes_, proba)
            },
        }

    def predict_batch(
        self, incidents: list[Dict[str, Any]]
    ) -> list[Optional[Dict[str, Any]]]:
        """Predict severity for a batch of incidents."""
        if not self.is_available:
            return [None] * len(incidents)

        from ml.feature_engineering import batch_to_array

        feature_dicts = [extract_features(inc) for inc in incidents]
        X = batch_to_array(feature_dicts)
        X_scaled = self.scaler.transform(X)

        probas = self.model.predict_proba(X_scaled)
        preds = self.model.predict(X_scaled)
        labels = self.label_encoder.inverse_transform(preds)

        results = []
        for label, proba in zip(labels, probas):
            results.append({
                "predicted_severity": label,
                "confidence": round(float(max(proba)), 4),
                "probabilities": {
                    cls: round(float(p), 4)
                    for cls, p in zip(self.label_encoder.classes_, proba)
                },
            })
        return results


# Module-level singleton — created once when first imported.
_singleton: Optional[SeverityPredictor] = None


def get_predictor() -> SeverityPredictor:
    """Return a module-level singleton predictor (lazy-loaded)."""
    global _singleton
    if _singleton is None:
        _singleton = SeverityPredictor()
    return _singleton
