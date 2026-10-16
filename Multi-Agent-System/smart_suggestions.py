"""Smart Suggestion Module - analyzes past runs and recommends strategy improvements."""

from typing import Any, Dict, List

from database import get_connection


def get_smart_suggestions(current_seed: int | None = None) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT rm.run_id, rm.total_lives_saved, rm.overall_efficiency,
               sr.seed, sr.strategy
        FROM run_metrics rm
        JOIN simulation_runs sr ON sr.run_id = rm.run_id
        ORDER BY rm.total_lives_saved DESC
        LIMIT 10
        """
    )
    top_runs = [dict(row) for row in cursor.fetchall()]

    cursor.execute(
        """
        SELECT disaster_type, AVG(people_affected) AS avg_affected, COUNT(*) AS count
        FROM incidents
        GROUP BY disaster_type
        ORDER BY avg_affected DESC
        LIMIT 5
        """
    )
    high_risk_types = [dict(row) for row in cursor.fetchall()]

    cursor.execute(
        """
        SELECT strategy,
               AVG(CAST(REPLACE(rm.overall_efficiency, '%', '') AS REAL)) AS avg_eff
        FROM run_metrics rm
        JOIN simulation_runs sr ON sr.run_id = rm.run_id
        GROUP BY strategy
        """
    )
    strategy_perf = {
        row["strategy"]: round(row["avg_eff"] or 0, 2) for row in cursor.fetchall()
    }

    conn.close()

    recommended_strategy = "smart"
    if strategy_perf.get("smart", 0) < strategy_perf.get("baseline", 0):
        recommended_strategy = "baseline"

    recommended_seed = current_seed or 42
    if top_runs:
        recommended_seed = top_runs[0].get("seed", recommended_seed)

    suggestions: List[str] = []
    if high_risk_types:
        risk = high_risk_types[0]["disaster_type"]
        suggestions.append(
            f"Prioritize extra rescue teams for '{risk}' incidents "
            f"(highest average affected population)."
        )

    if strategy_perf:
        best = max(strategy_perf, key=strategy_perf.get)
        suggestions.append(
            f"Use '{best}' strategy for better average efficiency ({strategy_perf[best]}%)."
        )

    if top_runs:
        suggestions.append(
            f"Re-run with seed {top_runs[0]['seed']} - historically achieved "
            f"{top_runs[0]['total_lives_saved']} lives saved."
        )

    suggestions.append(
        "Increase high-priority team allocation when severity is marked 'high'."
    )

    return {
        "recommended_strategy": recommended_strategy,
        "recommended_seed": recommended_seed,
        "strategy_performance": strategy_perf,
        "high_risk_disaster_types": high_risk_types,
        "top_performing_runs": top_runs[:3],
        "suggestions": suggestions,
    }
