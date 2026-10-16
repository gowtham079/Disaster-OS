from datetime import datetime


class Logger:
    def __init__(self, run_id):
        self.logs = []
        self.run_id = run_id

    def log(
        self,
        tick,
        agent,
        action,
        details,
        previous_state,
        current_state,
        severity="INFO",
    ):
        entry = {
            "run_id": self.run_id,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "tick": tick,
            "severity": severity,
            "agent": agent,
            "action": action,
            "details": details,
            "previous_state": previous_state,
            "current_state": current_state,
        }
        self.logs.append(entry)

    def get_logs(self):
        return self.logs

    def print_logs(self, limit=20):
        for log in self.logs[:limit]:
            print(
                f"[Run {log['run_id']}] T{log['tick']:02d} "
                f"{log['timestamp']} | {log['severity']} | "
                f"{log['agent']}:{log['action']} | "
                f"{log['previous_state']} -> {log['current_state']} | "
                f"{log['details']}"
            )

        if len(self.logs) > limit:
            print(f"... {len(self.logs) - limit} more log entries")