"""Event log — append-only typed event log.

Every significant action in claws emits an event. Events are immutable
and ordered. The event log is the single source of truth for system state.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass
class Event:
    """A single immutable event in the spine."""
    type: str
    agent: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))


# Event types
AGENT_CREATED = "agent.created"
TASK_STARTED = "task.started"
TASK_COMPLETED = "task.completed"
TASK_FAILED = "task.failed"
EVAL_STARTED = "eval.started"
EVAL_COMPLETED = "eval.completed"
DEPLOY_COMPLETED = "deploy.completed"
PROJECT_INITIALIZED = "project.initialized"
AGENT_SNAPSHOT_CREATED = "agent.snapshot.created"
AGENT_SNAPSHOT_RESTORED = "agent.snapshot.restored"

# Onboarding events
ONBOARD_STARTED = "onboard.started"
ONBOARD_PHASE_STARTED = "onboard.phase.started"
ONBOARD_TASK_COMPLETED = "onboard.task.completed"
ONBOARD_TASK_FAILED = "onboard.task.failed"
ONBOARD_PHASE_COMPLETED = "onboard.phase.completed"
ONBOARD_COMPLETED = "onboard.completed"

# Scratchpad events
SCRATCHPAD_CREATED = "scratchpad.created"
SCRATCHPAD_THREAD_ADDED = "scratchpad.thread.added"
SCRATCHPAD_THREAD_UPDATED = "scratchpad.thread.updated"
SCRATCHPAD_THREAD_ARCHIVED = "scratchpad.thread.archived"
SCRATCHPAD_DECISION_ADDED = "scratchpad.decision.added"
SCRATCHPAD_DECISION_RESOLVED = "scratchpad.decision.resolved"

# Decision protocol events (first-class, independent of scratchpad)
DECISION_PRESENTED = "decision.presented"
DECISION_RESOLVED = "decision.resolved"

# Session continuity events
SESSION_STARTED = "session.started"
SESSION_ENDED = "session.ended"


class EventSpine:
    """Append-only event log backed by a JSONL file."""

    def __init__(self, project_root: Path):
        self.events_dir = project_root / ".claws"
        self.events_file = self.events_dir / "events.jsonl"

    def _ensure_dir(self):
        self.events_dir.mkdir(parents=True, exist_ok=True)

    def emit(self, event: Event) -> Event:
        """Append an event to the spine. Returns the event."""
        self._ensure_dir()
        with open(self.events_file, "a") as f:
            f.write(event.to_json() + "\n")
        return event

    def read_all(self) -> list[Event]:
        """Read all events from the spine."""
        if not self.events_file.exists():
            return []
        events = []
        with open(self.events_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                events.append(Event(
                    type=d["type"],
                    agent=d.get("agent"),
                    data=d.get("data", {}),
                    correlation_id=d.get("correlation_id"),
                    id=d.get("id", ""),
                    ts=d.get("ts", ""),
                ))
        return events

    def read_by_type(self, event_type: str) -> list[Event]:
        """Read events filtered by type."""
        return [e for e in self.read_all() if e.type == event_type]

    def read_by_agent(self, agent: str) -> list[Event]:
        """Read events filtered by agent."""
        return [e for e in self.read_all() if e.agent == agent]

    def last_event(self, agent: str | None = None, event_type: str | None = None) -> Event | None:
        """Get the most recent event, optionally filtered."""
        events = self.read_all()
        if agent:
            events = [e for e in events if e.agent == agent]
        if event_type:
            events = [e for e in events if e.type == event_type]
        return events[-1] if events else None
