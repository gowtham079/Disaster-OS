import argparse
import random

from evaluator import Evaluator
from logger import Logger
from state_manager import StateManager


class DispatcherAgent:
    def plan_allocations(self, incidents, teams, mode):
        assignments = []
        available = [t for t in teams if t["available"]]
        for incident in incidents:
            if not available:
                break
            if mode == "baseline":
                chosen = available.pop(0)
            else:
                chosen = min(
                    available,
                    key=lambda t: abs(t["x"] - incident["x"]) + abs(t["y"] - incident["y"]),
                )
                available.remove(chosen)
            assignments.append((chosen["id"], incident["id"]))
        return assignments


class MedicalAgent:
    def resolve(self, incident, response_delay):
        severity = incident["severity"]
        lives_at_risk = incident["lives_at_risk"]
        penalty = min(lives_at_risk, response_delay * max(1, severity - 1))
        saved = max(0, lives_at_risk - penalty)
        return saved


class LogisticsAgent:
    def reposition_idle(self, teams, incidents):
        if not incidents:
            return
        hot_x = round(sum(i["x"] for i in incidents) / len(incidents))
        hot_y = round(sum(i["y"] for i in incidents) / len(incidents))
        for team in teams:
            if team["available"]:
                team["x"] = (team["x"] + hot_x) // 2
                team["y"] = (team["y"] + hot_y) // 2


def build_map(width, height, incidents, teams):
    grid = [["." for _ in range(width)] for _ in range(height)]
    for inc in incidents:
        if not inc["resolved"]:
            grid[inc["y"]][inc["x"]] = "I"
    for team in teams:
        marker = "T" if team["available"] else "B"
        grid[team["y"]][team["x"]] = marker
    return ["".join(row) for row in grid]


def simulate_once(seed, mode, scenario_id, max_ticks=18):
    rng = random.Random(seed)
    state = StateManager()
    logger = Logger(run_id=f"{scenario_id}-{mode}")
    dispatcher = DispatcherAgent()
    medical = MedicalAgent()
    logistics = LogisticsAgent()

    teams = [
        {"id": "team-alpha", "x": 1, "y": 1, "available": True},
        {"id": "team-bravo", "x": 8, "y": 1, "available": True},
        {"id": "team-charlie", "x": 4, "y": 8, "available": True},
    ]

    incidents = []
    incident_counter = 0
    resolved_count = 0
    lives_saved = 0
    response_times = []
    team_busy_ticks = 0
    new_incident_probability = 0.65 if mode == "baseline" else 0.55

    state.transition("SETUP")
    logger.log(0, "System", "setup", "Simulation initialized", "IDLE", "SETUP")
    state.transition("PLANNING")

    for tick in range(1, max_ticks + 1):
        state.set_tick(tick)
        prev = state.get_state()
        state.transition("ALLOCATING")

        if rng.random() < new_incident_probability:
            incident_counter += 1
            incidents.append(
                {
                    "id": f"inc-{incident_counter}",
                    "x": rng.randint(0, 9),
                    "y": rng.randint(0, 9),
                    "severity": rng.randint(1, 4),
                    "lives_at_risk": rng.randint(4, 15),
                    "created_at": tick,
                    "resolved": False,
                }
            )

        open_incidents = [i for i in incidents if not i["resolved"]]
        assignments = dispatcher.plan_allocations(open_incidents, teams, mode)
        logger.log(
            tick,
            "DispatcherAgent",
            "allocate",
            f"{len(assignments)} assignment(s), {len(open_incidents)} active incident(s)",
            prev,
            state.get_state(),
        )

        prev = state.get_state()
        state.transition("RESPONDING")

        for team_id, incident_id in assignments:
            team = next(t for t in teams if t["id"] == team_id)
            incident = next(i for i in incidents if i["id"] == incident_id)
            distance = abs(team["x"] - incident["x"]) + abs(team["y"] - incident["y"])
            response_delay = max(1, distance // (2 if mode == "smart" else 3))
            saved = medical.resolve(incident, response_delay)

            lives_saved += saved
            response_times.append(tick - incident["created_at"] + response_delay)
            incident["resolved"] = True
            resolved_count += 1

            team["available"] = False
            team["x"], team["y"] = incident["x"], incident["y"]
            logger.log(
                tick,
                "MedicalAgent",
                "resolve_incident",
                f"{incident_id} severity={incident['severity']} saved={saved}",
                prev,
                state.get_state(),
            )

        for team in teams:
            if not team["available"] and rng.random() < 0.6:
                team["available"] = True
            if not team["available"]:
                team_busy_ticks += 1

        prev = state.get_state()
        state.transition("REPLANNING")
        logistics.reposition_idle(teams, [i for i in incidents if not i["resolved"]])

        prev = state.get_state()
        state.transition("LOGGING")
        current_map = build_map(10, 10, incidents, teams)
        state.update_map(current_map)
        state.update_resources(
            {team["id"]: "available" if team["available"] else "busy" for team in teams}
        )
        state.update_incidents([i for i in incidents if not i["resolved"]])
        logger.log(
            tick,
            "System",
            "state_snapshot",
            f"open_incidents={len(state.active_incidents)}",
            prev,
            state.get_state(),
        )
        state.transition("PLANNING")

    prev = state.get_state()
    state.transition("ALLOCATING")
    prev = state.get_state()
    state.transition("RESPONDING")
    prev = state.get_state()
    state.transition("EVALUATING")

    incidents_total = len(incidents)
    resource_utilization = team_busy_ticks / max(1, (len(teams) * max_ticks))
    metrics = {
        "incidents_total": incidents_total,
        "incidents_resolved": resolved_count,
        "lives_saved": lives_saved,
        "response_time_avg": (
            sum(response_times) / len(response_times) if response_times else float(max_ticks)
        ),
        "resource_utilization": resource_utilization,
    }

    logger.log(
        max_ticks,
        "System",
        "evaluation_complete",
        f"resolved={resolved_count}/{incidents_total}, lives_saved={lives_saved}",
        prev,
        state.get_state(),
    )
    prev = state.get_state()
    state.transition("COMPLETED")
    logger.log(max_ticks, "System", "completed", "Run completed", prev, state.get_state())

    return metrics, logger, state


def run_experiment(scenarios, base_seed):
    evaluator = Evaluator()
    recent_logs = []

    for scenario in range(1, scenarios + 1):
        scenario_seed = base_seed + scenario
        baseline_metrics, _, _ = simulate_once(
            seed=scenario_seed, mode="baseline", scenario_id=scenario
        )
        smart_metrics, smart_logger, smart_state = simulate_once(
            seed=scenario_seed, mode="smart", scenario_id=scenario
        )

        evaluator.evaluate_scenario(scenario, "baseline", baseline_metrics)
        evaluator.evaluate_scenario(scenario, "smart", smart_metrics)

        if scenario == scenarios:
            recent_logs = smart_logger.get_logs()
            final_state = smart_state.snapshot()

    print("=== Multi-Agent Disaster Management Simulator ===")
    print(f"Scenarios: {scenarios} | Seed: {base_seed}")
    print("\nPer-run metrics:")
    evaluator.print_results()

    print("\nSmart vs baseline delta per scenario:")
    for row in evaluator.paired_report():
        print(row)

    print("\nAggregate summary:")
    print(evaluator.summary())

    print("\nRecent logs from final smart run:")
    for entry in recent_logs[:15]:
        print(entry)

    print("\nFinal state snapshot (smart run):")
    print(final_state)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run disaster-response multi-agent simulation."
    )
    parser.add_argument("--start", action="store_true", help="Start simulation run.")
    parser.add_argument("--stop", action="store_true", help="Stop immediately.")
    parser.add_argument("--reset", action="store_true", help="Reset to default controls.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility.")
    parser.add_argument("--scenarios", type=int, default=10, help="Number of scenarios to simulate.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if args.stop:
        print("Simulation stopped.")
    elif args.reset:
        print("Simulation controls reset. Run again with --start.")
    elif args.start:
        run_experiment(scenarios=max(1, args.scenarios), base_seed=args.seed)
    else:
        print("Use --start to run the simulation.")