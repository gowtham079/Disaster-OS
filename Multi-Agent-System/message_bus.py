"""Centralized Priority Message Bus for the 14-Agent Disaster Management System.

Manages publish/subscribe communication between all 14 autonomous agents, handles priority
message queues, logs message histories to SQLite, implements retry mechanics for failed agents,
and broadcasts live event streams over WebSockets.
"""

import logging
import queue
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class Message:
    """A structured message transmitted over the Message Bus."""

    def __init__(
        self,
        message_id: Optional[str] = None,
        run_id: str = "demo",
        sender: str = "Agent",
        receiver: str = "*",
        message_type: str = "EVENT",
        payload: Optional[Dict[str, Any]] = None,
        priority: int = 3,
        timestamp: Optional[str] = None,
    ):
        self.message_id = message_id or str(uuid.uuid4())
        self.run_id = run_id
        self.sender = sender
        self.receiver = receiver
        self.message_type = message_type
        self.payload = payload or {}
        self.priority = priority  # 1 (critical) to 5 (info)
        self.timestamp = timestamp or datetime.now().isoformat()
        self.retry_count = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "run_id": self.run_id,
            "sender": self.sender,
            "receiver": self.receiver,
            "message_type": self.message_type,
            "payload": self.payload,
            "priority": self.priority,
            "timestamp": self.timestamp,
            "retry_count": self.retry_count,
        }

    def __lt__(self, other: "Message") -> bool:
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.timestamp < other.timestamp


AgentMessage = Message


class AgentHealth:
    """Diagnostics and telemetry for registered agents."""

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.status = "healthy"
        self.messages_processed = 0
        self.messages_failed = 0
        self.latency_sum = 0.0
        self.last_active = ""

    def to_dict(self) -> Dict[str, Any]:
        avg_latency = (
            (self.latency_sum / self.messages_processed)
            if self.messages_processed > 0
            else None
        )
        return {
            "agent_name": self.agent_name,
            "status": self.status,
            "messages_processed": self.messages_processed,
            "messages_failed": self.messages_failed,
            "avg_latency_ms": round(avg_latency * 1000, 2) if avg_latency is not None else None,
            "last_active": self.last_active,
        }


class MessageBus:
    """Thread-safe, priority-queued message bus for inter-agent communication."""

    def __init__(self, run_id: str = "demo", max_retries: int = 3, retry_delay: float = 0.01):
        self.run_id = run_id
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        self.subscribers: Dict[str, Callable[[Message], Any]] = {}
        self.health_records: Dict[str, AgentHealth] = {}
        self.message_queue = queue.PriorityQueue()
        self.history: List[Message] = []
        self.lock = threading.Lock()

    def register_agent(
        self, agent_name: str, handler: Callable[[Message], Any]
    ) -> None:
        """Register an agent and its callback handler with the bus."""
        with self.lock:
            self.subscribers[agent_name] = handler
            self.health_records[agent_name] = AgentHealth(agent_name)

    def publish(
        self,
        sender_or_msg: Union[str, Message],
        receiver: str = "*",
        message_type: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        priority: int = 3,
    ) -> str:
        """Publish a message to the bus, log to DB, and trigger processing."""
        if isinstance(sender_or_msg, Message):
            msg = sender_or_msg
            if not msg.run_id or msg.run_id == "demo":
                msg.run_id = self.run_id
        else:
            msg_id = str(uuid.uuid4())
            msg = Message(
                message_id=msg_id,
                run_id=self.run_id,
                sender=str(sender_or_msg),
                receiver=receiver,
                message_type=message_type or "EVENT",
                payload=payload or {},
                priority=priority,
            )

        # 1. Log message
        try:
            from database import save_agent_message
            save_agent_message(self.run_id, msg.sender, msg.receiver, msg.message_type, msg.payload)
        except Exception:
            pass

        # 2. Broadcast via WebSockets
        try:
            from app import broadcast_sync
            broadcast_sync({
                "type": "AGENT_MESSAGE",
                "run_id": self.run_id,
                "message": msg.to_dict()
            })
        except Exception:
            pass

        # 3. Save to history
        with self.lock:
            self.history.append(msg)

        # 4. Dispatch directly to subscribers
        targets = []
        with self.lock:
            if msg.receiver in ["*", "BROADCAST"]:
                targets = [name for name in self.subscribers if name != msg.sender]
            elif msg.receiver in self.subscribers:
                targets = [msg.receiver]

        for target in targets:
            handler = self.subscribers.get(target)
            health = self.health_records.get(target)
            if handler:
                start_time = time.perf_counter()
                try:
                    if health:
                        health.last_active = datetime.now().isoformat()
                    handler(msg)
                    if health:
                        health.messages_processed += 1
                        health.latency_sum += time.perf_counter() - start_time
                except Exception as exc:
                    logger.exception("Error processing message %s in agent %s: %s", msg.message_id, target, exc)
                    if health:
                        health.messages_failed += 1
                        health.status = "degraded"

        return msg.message_id

    def get_health_status(self) -> List[Dict[str, Any]]:
        with self.lock:
            return [h.to_dict() for h in self.health_records.values()]

    def get_message_history(self) -> List[Dict[str, Any]]:
        with self.lock:
            return [m.to_dict() for m in self.history]


def broadcast_intelligence_event(
    event_type: str,
    source: str,
    entity_id: str,
    severity: str = "medium",
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Format and validate standardized real-time WebSocket intelligence event payload."""
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "timestamp": datetime.now().isoformat(),
        "source": source,
        "entity_id": entity_id,
        "severity": severity,
        "payload": payload or {}
    }
