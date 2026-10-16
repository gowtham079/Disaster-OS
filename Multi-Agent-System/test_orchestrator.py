from orchestrator import Orchestrator
import json

def test():
    orch = Orchestrator()
    print(f"Starting run with ID: {orch.run_id}")
    run_id = orch.run()
    print(f"Finished run: {run_id}")
    
    from logger import get_run_history
    history = get_run_history(run_id)
    print(f"Total states traversed: {len(history)}")
    
    for state in history:
        print(f" - {state['state']} -> {str(state['payload'])[:100]}...")

if __name__ == '__main__':
    test()
