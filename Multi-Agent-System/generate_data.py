"""Generate realistic geospatial disaster incident data for simulations.

Usage::

    cd Multi-Agent-System
    python generate_data.py                  # default 150 records
    python generate_data.py --count 500      # custom count
    python generate_data.py --seed 123       # reproducibility

Each generated incident includes:
- Real Indian city coordinates (lat/lng)
- Weather features correlated with disaster type
- Population density and infrastructure score from city data
- Temporal information (hour, month)

The output is written to ``data/input_data.json``.
"""

import argparse
import json
import os
import random
from pathlib import Path


def _load_cities(region: str = "india") -> list:
    """Load city reference data.  Currently only ``india`` is supported."""
    cities_path = Path(__file__).resolve().parent / "data" / "indian_cities.json"
    if not cities_path.exists():
        raise FileNotFoundError(
            f"City data not found at {cities_path}. "
            "Ensure data/indian_cities.json exists."
        )
    with open(cities_path, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_synthetic_data(
    num_records: int = 150,
    seed: int = 42,
    region: str = "india",
) -> list:
    """Generate *num_records* disaster incidents with geospatial + weather features.

    Parameters
    ----------
    num_records : int
        How many incidents to generate.
    seed : int
        Random seed for reproducibility.
    region : str
        Geographic region.  Only ``"india"`` is implemented; the parameter
        exists so other regions can be added later without API changes.

    Returns
    -------
    list of dict
        Each dict is a complete incident record ready for simulation.
    """
    rng = random.Random(seed)
    cities = _load_cities(region)

    disaster_types = ["flood", "earthquake", "fire", "cyclone"]

    data = []
    for _ in range(num_records):
        city = rng.choice(cities)
        dtype = rng.choice(disaster_types)

        # ── Weather features correlated with disaster type ──────────
        if dtype == "flood":
            temperature = round(rng.gauss(28, 4), 1)
            humidity = round(min(100, max(30, rng.gauss(82, 10))), 1)
            wind_speed = round(max(0, rng.gauss(15, 8)), 1)
            rainfall_mm = round(max(0, rng.expovariate(1 / 60)), 1)
        elif dtype == "earthquake":
            temperature = round(rng.gauss(30, 6), 1)
            humidity = round(min(100, max(10, rng.gauss(55, 15))), 1)
            wind_speed = round(max(0, rng.gauss(10, 5)), 1)
            rainfall_mm = round(max(0, rng.gauss(10, 15)), 1)
        elif dtype == "fire":
            temperature = round(rng.gauss(38, 5), 1)
            humidity = round(min(100, max(5, rng.gauss(30, 12))), 1)
            wind_speed = round(max(0, rng.gauss(22, 10)), 1)
            rainfall_mm = round(max(0, rng.gauss(2, 5)), 1)
        else:  # cyclone
            temperature = round(rng.gauss(27, 3), 1)
            humidity = round(min(100, max(40, rng.gauss(85, 8))), 1)
            wind_speed = round(max(0, rng.expovariate(1 / 35)), 1)
            rainfall_mm = round(max(0, rng.expovariate(1 / 50)), 1)

        # ── People affected (loosely proportional to density) ──────
        base = city["population_density"] / 30
        people_affected = max(1, int(rng.expovariate(1 / max(1, base))))

        # ── Severity (rule-based with noise, same logic as training) ──
        score = 0
        if dtype == "flood":
            if rainfall_mm > 80:
                score += 3
            elif rainfall_mm > 40:
                score += 1
            if city["population_density"] > 8000:
                score += 2
            elif city["population_density"] > 4000:
                score += 1
        elif dtype == "earthquake":
            if city["infrastructure_score"] < 4:
                score += 3
            elif city["infrastructure_score"] < 6:
                score += 1
            if city["population_density"] > 6000:
                score += 2
            elif city["population_density"] > 3000:
                score += 1
        elif dtype == "fire":
            if temperature > 40:
                score += 3
            elif temperature > 35:
                score += 1
            if wind_speed > 30:
                score += 2
            if humidity < 30:
                score += 1
        else:  # cyclone
            if wind_speed > 60:
                score += 3
            elif wind_speed > 35:
                score += 1
            if rainfall_mm > 60:
                score += 2
            elif rainfall_mm > 30:
                score += 1

        if people_affected > 400:
            score += 2
        elif people_affected > 150:
            score += 1

        score += rng.choice([-1, 0, 0, 0, 0, 1])
        severity = "high" if score >= 5 else ("medium" if score >= 2 else "low")

        # ── Slight jitter on coordinates so incidents aren't stacked ──
        lat = round(city["lat"] + rng.uniform(-0.05, 0.05), 5)
        lng = round(city["lng"] + rng.uniform(-0.05, 0.05), 5)

        data.append(
            {
                "location": f"{city['name']}, {city['state']}",
                "latitude": lat,
                "longitude": lng,
                "severity": severity,
                "people_affected": people_affected,
                "disaster_type": dtype,
                "temperature": temperature,
                "humidity": humidity,
                "wind_speed": wind_speed,
                "rainfall_mm": rainfall_mm,
                "population_density": city["population_density"],
                "infrastructure_score": city["infrastructure_score"],
                "hour_of_day": rng.randint(0, 23),
                "month": rng.randint(1, 12),
                "state": "INIT",
            }
        )

    return data


def main():
    parser = argparse.ArgumentParser(
        description="Generate geospatial disaster incident data"
    )
    parser.add_argument("--count", type=int, default=150,
                        help="Number of incidents (default: 150)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed")
    parser.add_argument("--region", type=str, default="india",
                        help="Geographic region (default: india)")
    args = parser.parse_args()

    data = generate_synthetic_data(
        num_records=args.count, seed=args.seed, region=args.region
    )

    os.makedirs("data", exist_ok=True)
    with open("data/input_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    # Print summary
    from collections import Counter
    sev_counts = Counter(d["severity"] for d in data)
    type_counts = Counter(d["disaster_type"] for d in data)
    print(f"[OK] Generated {len(data)} disaster records in data/input_data.json")
    print(f"  Region : {args.region}")
    print(f"  Severity : {dict(sev_counts)}")
    print(f"  Types    : {dict(type_counts)}")


if __name__ == "__main__":
    main()
