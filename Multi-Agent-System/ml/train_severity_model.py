"""Train a Random Forest severity classifier on synthetic disaster data.

Usage::

    cd Multi-Agent-System
    python -m ml.train_severity_model          # generates data + trains
    python -m ml.train_severity_model --samples 8000  # more data

The script:
1. Generates synthetic training data with realistic feature→severity
   correlations (floods + heavy rain → high, earthquakes + poor infra → high,
   fires + heat + wind → high, cyclones + wind → high).
2. Splits 80/20 train/test.
3. Trains ``RandomForestClassifier`` with ``GridSearchCV`` (3-fold).
4. Saves model artifacts to ``ml/models/``.
5. Writes ``ml/models/training_report.json`` with accuracy, F1, etc.
"""

import argparse
import json
import os
import random
import sys
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
)
from sklearn.model_selection import GridSearchCV, train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

# Ensure package imports work when executed as ``python -m ml.train_…``
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ml.feature_engineering import (
    DISASTER_TYPES,
    FEATURE_ORDER,
    NUMERIC_FEATURES,
    batch_to_array,
    extract_features,
)

MODELS_DIR = Path(__file__).resolve().parent / "models"


# ---------------------------------------------------------------------------
# Synthetic training data generation
# ---------------------------------------------------------------------------

def _severity_from_features(row: dict) -> str:
    """Deterministic-with-noise severity label based on domain knowledge.

    This encodes the kind of correlations an ML model should learn:
    flood + heavy rain + dense population → high severity, etc.
    Random noise is added so the model learns probabilistic boundaries
    rather than crisp rules.
    """
    score = 0
    rng_noise = random.choice([-1, 0, 0, 0, 0, 1])

    dtype = row.get("disaster_type", "flood")

    if dtype == "flood":
        if row["rainfall_mm"] > 80:
            score += 3
        elif row["rainfall_mm"] > 40:
            score += 1
        if row["population_density"] > 8000:
            score += 2
        elif row["population_density"] > 4000:
            score += 1
        if row["infrastructure_score"] < 4:
            score += 1

    elif dtype == "earthquake":
        if row["infrastructure_score"] < 4:
            score += 3
        elif row["infrastructure_score"] < 6:
            score += 1
        if row["population_density"] > 6000:
            score += 2
        elif row["population_density"] > 3000:
            score += 1

    elif dtype == "fire":
        if row["temperature"] > 40:
            score += 3
        elif row["temperature"] > 35:
            score += 1
        if row["wind_speed"] > 30:
            score += 2
        if row["humidity"] < 30:
            score += 1

    elif dtype == "cyclone":
        if row["wind_speed"] > 60:
            score += 3
        elif row["wind_speed"] > 35:
            score += 1
        if row["rainfall_mm"] > 60:
            score += 2
        elif row["rainfall_mm"] > 30:
            score += 1

    # Universal people-affected factor
    if row["people_affected"] > 400:
        score += 2
    elif row["people_affected"] > 150:
        score += 1

    score += rng_noise

    if score >= 5:
        return "high"
    elif score >= 2:
        return "medium"
    else:
        return "low"


def generate_training_data(n_samples: int = 5000, seed: int = 42) -> pd.DataFrame:
    """Create a synthetic dataset with realistic disaster feature correlations."""
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)

    # Load city data for realistic population/infra distributions
    cities_path = Path(__file__).resolve().parent.parent / "data" / "indian_cities.json"
    if cities_path.exists():
        with open(cities_path, "r", encoding="utf-8") as f:
            cities = json.load(f)
    else:
        cities = [
            {"name": "Default City", "population_density": 5000, "infrastructure_score": 5}
        ]

    rows = []
    for _ in range(n_samples):
        dtype = rng.choice(DISASTER_TYPES)
        city = rng.choice(cities)

        # Weather features correlated with disaster type
        if dtype == "flood":
            temperature = np_rng.normal(28, 4)
            humidity = np_rng.normal(82, 10)
            wind_speed = np_rng.normal(15, 8)
            rainfall_mm = np_rng.exponential(60)
        elif dtype == "earthquake":
            temperature = np_rng.normal(30, 6)
            humidity = np_rng.normal(55, 15)
            wind_speed = np_rng.normal(10, 5)
            rainfall_mm = max(0, np_rng.normal(10, 15))
        elif dtype == "fire":
            temperature = np_rng.normal(38, 5)
            humidity = np_rng.normal(30, 12)
            wind_speed = np_rng.normal(22, 10)
            rainfall_mm = max(0, np_rng.normal(2, 5))
        else:  # cyclone
            temperature = np_rng.normal(27, 3)
            humidity = np_rng.normal(85, 8)
            wind_speed = np_rng.exponential(35)
            rainfall_mm = np_rng.exponential(50)

        people_affected = max(1, int(np_rng.exponential(
            city["population_density"] / 30
        )))
        pop_density = city["population_density"] + int(np_rng.normal(0, 500))
        infra = max(1, min(10, city["infrastructure_score"] + rng.choice([-1, 0, 0, 1])))

        row = {
            "disaster_type": dtype,
            "people_affected": people_affected,
            "temperature": round(max(-5, temperature), 1),
            "humidity": round(max(5, min(100, humidity)), 1),
            "wind_speed": round(max(0, wind_speed), 1),
            "rainfall_mm": round(max(0, rainfall_mm), 1),
            "population_density": max(100, pop_density),
            "infrastructure_score": infra,
            "hour_of_day": rng.randint(0, 23),
            "month": rng.randint(1, 12),
        }
        row["severity"] = _severity_from_features(row)
        rows.append(row)

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Training pipeline
# ---------------------------------------------------------------------------

def train_model(n_samples: int = 5000, seed: int = 42) -> dict:
    """Full training pipeline.  Returns a report dict."""
    print(f"[1/5] Generating {n_samples} synthetic training samples ...")
    df = generate_training_data(n_samples=n_samples, seed=seed)

    # Show class balance
    print(f"       Class distribution:\n{df['severity'].value_counts().to_string()}\n")

    # Feature extraction
    print("[2/5] Extracting features ...")
    feature_dicts = [extract_features(row) for _, row in df.iterrows()]
    X = batch_to_array(feature_dicts)
    y_raw = df["severity"].values

    # Encode labels
    le = LabelEncoder()
    y = le.fit_transform(y_raw)

    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.2, random_state=seed, stratify=y
    )

    # Hyperparameter grid search
    print("[3/5] Training RandomForest with GridSearchCV (3-fold) ...")
    param_grid = {
        "n_estimators": [100, 200],
        "max_depth": [10, 20, None],
        "min_samples_split": [2, 5],
    }
    rf = RandomForestClassifier(random_state=seed, n_jobs=-1)
    gs = GridSearchCV(rf, param_grid, cv=3, scoring="f1_weighted", n_jobs=-1)
    gs.fit(X_train, y_train)

    best_model = gs.best_estimator_
    print(f"       Best params: {gs.best_params_}")

    # Evaluate
    print("[4/5] Evaluating on held-out test set ...")
    y_pred = best_model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred, average="weighted")
    report_str = classification_report(
        y_test, y_pred, target_names=le.classes_
    )
    print(report_str)

    # Feature importances
    importance_dict = {
        name: round(float(imp), 4)
        for name, imp in zip(FEATURE_ORDER, best_model.feature_importances_)
    }

    # Save artefacts
    print("[5/5] Saving model artefacts ...")
    os.makedirs(MODELS_DIR, exist_ok=True)

    joblib.dump(best_model, MODELS_DIR / "severity_model.joblib")
    joblib.dump(le, MODELS_DIR / "label_encoder.joblib")
    joblib.dump(scaler, MODELS_DIR / "feature_scaler.joblib")

    report = {
        "model_name": "RandomForestClassifier",
        "best_params": gs.best_params_,
        "accuracy": round(acc, 4),
        "f1_weighted": round(f1, 4),
        "training_samples": len(X_train),
        "test_samples": len(X_test),
        "feature_importances": importance_dict,
        "classes": list(le.classes_),
        "trained_at": datetime.now().isoformat(),
    }
    with open(MODELS_DIR / "training_report.json", "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n[OK] Model saved to {MODELS_DIR}/")
    print(f"  Accuracy : {acc:.4f}")
    print(f"  F1 (wtd) : {f1:.4f}")
    return report


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train severity prediction model")
    parser.add_argument("--samples", type=int, default=5000,
                        help="Number of synthetic training samples (default: 5000)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility")
    args = parser.parse_args()
    train_model(n_samples=args.samples, seed=args.seed)
