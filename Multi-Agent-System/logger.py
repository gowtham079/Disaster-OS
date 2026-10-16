import json
import logging
from datetime import datetime
from typing import Any, Dict, List

from database import DB_PATH, init_db as init_enhanced_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def init_db() -> None:
    init_enhanced_db()


def log_transition(run_id: str, state: str, payload: Dict[str, Any]) -> None:
    logger.info("Run: %s | State: %s | Payload length: %d", run_id, state, len(str(payload)))
    import sqlite3

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO run_logs (run_id, state, payload, timestamp) VALUES (?, ?, ?, ?)",
        (run_id, state, json.dumps(payload), datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_run_history(run_id: str) -> List[Dict[str, Any]]:
    import sqlite3

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT state, payload, timestamp FROM run_logs WHERE run_id = ? ORDER BY timestamp ASC",
        (run_id,),
    )
    rows = cursor.fetchall()
    conn.close()

    history = []
    for row in rows:
        history.append(
            {
                "state": row[0],
                "payload": json.loads(row[1]) if row[1] else {},
                "timestamp": row[2],
            }
        )
    return history


def get_all_runs() -> List[str]:
    import sqlite3

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT run_id FROM run_logs
        GROUP BY run_id
        ORDER BY MAX(timestamp) DESC
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]
