"""Disaster OS — Canonical Metric Semantics & Simulation Performance Scoring.

Implements documented custom simulation performance score formula:
Score = 0.40 * Rescue Rate + 0.25 * (100 - Casualty Rate) + 0.20 * Resource Assignment Rate + 0.15 * max(0, 100 - (Planned ETA Mins * 2))

NOTE:
This metric is a custom simulation heuristic for operational drills.
It is NOT an authoritative real-world disaster-response standard.
"""

from typing import Any, Dict, Optional


def calculate_simulation_performance_score(
    rescue_rate_pct: Optional[float],
    casualty_rate_pct: Optional[float],
    resource_assignment_rate_pct: Optional[float],
    planned_route_eta_mins: Optional[float],
) -> Dict[str, Any]:
    """Calculate the documented Simulation Performance Score heuristic.

    All rate components must be percentages on a 0.0 to 100.0 scale.
    Planned route ETA is in minutes.
    """
    formula_str = "0.40 * rescue_rate + 0.25 * (100 - casualty_rate) + 0.20 * resource_assignment_rate + 0.15 * max(0, 100 - (planned_eta * 2))"
    weights = {
        "rescue_rate": 0.40,
        "survival_rate": 0.25,
        "casualty_factor": 0.25,
        "resource_assignment": 0.20,
        "speed": 0.15,
        "eta_factor": 0.15,
    }
    methodology_str = (
        "Custom simulation heuristic; not an authoritative real-world disaster-response metric."
    )

    # Check for missing components strictly — do not substitute zero silently
    if rescue_rate_pct is None:
        reason = "Missing required score component: rescue_rate_pct is unavailable (insufficient victim data)"
        return {
            "score": None,
            "classification": "UNAVAILABLE",
            "reason": reason,
            "missing_reason": reason,
            "metric_name": "Calculated Simulation Performance Score",
            "formula": formula_str,
            "methodology": methodology_str,
            "components": None,
            "component_values": None,
            "weights": weights,
        }

    if casualty_rate_pct is None:
        reason = "Missing required score component: casualty_rate_pct is unavailable (insufficient victim state data)"
        return {
            "score": None,
            "classification": "UNAVAILABLE",
            "reason": reason,
            "missing_reason": reason,
            "metric_name": "Calculated Simulation Performance Score",
            "formula": formula_str,
            "methodology": methodology_str,
            "components": None,
            "component_values": None,
            "weights": weights,
        }

    if resource_assignment_rate_pct is None:
        reason = "Missing required score component: resource_assignment_rate_pct is unavailable"
        return {
            "score": None,
            "classification": "UNAVAILABLE",
            "reason": reason,
            "missing_reason": reason,
            "metric_name": "Calculated Simulation Performance Score",
            "formula": formula_str,
            "methodology": methodology_str,
            "components": None,
            "component_values": None,
            "weights": weights,
        }

    if planned_route_eta_mins is None:
        reason = "Missing required score component: planned_route_eta_mins is unavailable"
        return {
            "score": None,
            "classification": "UNAVAILABLE",
            "reason": reason,
            "missing_reason": reason,
            "metric_name": "Calculated Simulation Performance Score",
            "formula": formula_str,
            "methodology": methodology_str,
            "components": None,
            "component_values": None,
            "weights": weights,
        }

    # All components present: compute formula
    survival_rate_pct = max(0.0, 100.0 - casualty_rate_pct)
    speed_score = max(0.0, 100.0 - (planned_route_eta_mins * 2.0))

    rescue_comp = 0.40 * rescue_rate_pct
    survival_comp = 0.25 * survival_rate_pct
    resource_comp = 0.20 * resource_assignment_rate_pct
    speed_comp = 0.15 * speed_score

    raw_score = rescue_comp + survival_comp + resource_comp + speed_comp
    score = round(raw_score, 1)

    return {
        "score": score,
        "classification": "CALCULATED",
        "reason": None,
        "missing_reason": None,
        "metric_name": "Calculated Simulation Performance Score",
        "formula": formula_str,
        "methodology": methodology_str,
        "components": {
            "rescue_rate_pct": round(rescue_rate_pct, 1),
            "casualty_rate_pct": round(casualty_rate_pct, 1),
            "survival_rate_pct": round(survival_rate_pct, 1),
            "resource_assignment_rate_pct": round(resource_assignment_rate_pct, 1),
            "planned_route_eta_mins": round(planned_route_eta_mins, 1),
            "speed_score": round(speed_score, 1),
        },
        "component_values": {
            "rescue_component": round(rescue_comp, 2),
            "survival_component": round(survival_comp, 2),
            "resource_assignment_component": round(resource_comp, 2),
            "speed_component": round(speed_comp, 2),
        },
        "weights": weights,
    }
