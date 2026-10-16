class StateManager:
    VALID_TRANSITIONS = {
        "IDLE": {"SETUP"},
        "SETUP": {"PLANNING"},
        "PLANNING": {"ALLOCATING"},
        "ALLOCATING": {"RESPONDING", "LOGGING"},
        "RESPONDING": {"REPLANNING", "LOGGING", "EVALUATING"},
        "REPLANNING": {"ALLOCATING", "LOGGING"},
        "LOGGING": {"PLANNING", "ALLOCATING", "RESPONDING", "EVALUATING"},
        "EVALUATING": {"COMPLETED"},
        "COMPLETED": {"IDLE"},
    }

    def __init__(self):
        self.current_state = "IDLE"
        self.history = []
        self.tick = 0
        self.map_state = {}
        self.resources = {}
        self.active_incidents = []

    def transition(self, new_state):
        allowed = self.VALID_TRANSITIONS.get(self.current_state, set())
        if new_state not in allowed:
            raise ValueError(
                f"Invalid transition: {self.current_state} -> {new_state}"
            )
        self.history.append((self.current_state, new_state))
        self.current_state = new_state

    def set_tick(self, tick):
        self.tick = tick

    def update_map(self, map_state):
        self.map_state = map_state

    def update_resources(self, resources):
        self.resources = resources

    def update_incidents(self, incidents):
        self.active_incidents = incidents

    def snapshot(self):
        return {
            "tick": self.tick,
            "state": self.current_state,
            "resources": self.resources,
            "active_incidents": len(self.active_incidents),
            "map": self.map_state,
        }

    def get_state(self):
        return self.current_state

    def get_history(self):
        return self.history