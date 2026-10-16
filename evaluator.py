class Evaluator:
    def __init__(self):
        self.results = []

    def evaluate_scenario(self, scenario_id, mode, metrics):
        entry = {
            "scenario": scenario_id,
            "mode": mode,
            "incidents_total": metrics["incidents_total"],
            "incidents_resolved": metrics["incidents_resolved"],
            "lives_saved": metrics["lives_saved"],
            "response_time_avg": round(metrics["response_time_avg"], 2),
            "resource_utilization": round(metrics["resource_utilization"], 3),
        }
        self.results.append(entry)

    def paired_report(self):
        smart = {r["scenario"]: r for r in self.results if r["mode"] == "smart"}
        baseline = {r["scenario"]: r for r in self.results if r["mode"] == "baseline"}
        report = []

        for scenario in sorted(set(smart.keys()) & set(baseline.keys())):
            s = smart[scenario]
            b = baseline[scenario]
            report.append(
                {
                    "scenario": scenario,
                    "lives_saved_delta": s["lives_saved"] - b["lives_saved"],
                    "response_time_delta": round(
                        b["response_time_avg"] - s["response_time_avg"], 2
                    ),
                    "utilization_delta": round(
                        s["resource_utilization"] - b["resource_utilization"], 3
                    ),
                }
            )
        return report

    def print_results(self):
        for r in self.results:
            print(r)

    def summary(self):
        if not self.results:
            return {}

        smart_runs = [r for r in self.results if r["mode"] == "smart"]
        baseline_runs = [r for r in self.results if r["mode"] == "baseline"]

        def avg(rows, key):
            return sum(r[key] for r in rows) / len(rows) if rows else 0

        return {
            "smart_lives_saved_avg": round(avg(smart_runs, "lives_saved"), 2),
            "baseline_lives_saved_avg": round(avg(baseline_runs, "lives_saved"), 2),
            "smart_response_time_avg": round(avg(smart_runs, "response_time_avg"), 2),
            "baseline_response_time_avg": round(
                avg(baseline_runs, "response_time_avg"), 2
            ),
            "scenarios": len(set(r["scenario"] for r in self.results)),
        }