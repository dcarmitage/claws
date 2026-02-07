"""Tests for claws.events — Event dataclass and EventSpine."""

import json
import pytest
from pathlib import Path

from claws.events import (
    Event,
    EventSpine,
    AGENT_CREATED,
    TASK_STARTED,
    TASK_COMPLETED,
    TASK_FAILED,
    PROJECT_INITIALIZED,
)


# ---------------------------------------------------------------------------
# Event dataclass
# ---------------------------------------------------------------------------

class TestEvent:
    def test_creation_defaults(self):
        e = Event(type=TASK_STARTED)
        assert e.type == TASK_STARTED
        assert e.agent is None
        assert e.data == {}
        assert e.correlation_id is None
        assert len(e.id) == 8
        assert "T" in e.ts  # ISO format

    def test_creation_with_values(self):
        e = Event(
            type=TASK_COMPLETED,
            agent="scout",
            data={"task": "hello"},
            correlation_id="abc",
        )
        assert e.agent == "scout"
        assert e.data == {"task": "hello"}
        assert e.correlation_id == "abc"

    def test_to_dict_removes_none(self):
        e = Event(type=TASK_STARTED, agent=None, correlation_id=None)
        d = e.to_dict()
        assert "agent" not in d
        assert "correlation_id" not in d
        assert "type" in d
        assert "id" in d
        assert "ts" in d

    def test_to_dict_keeps_values(self):
        e = Event(type=TASK_STARTED, agent="a", correlation_id="c")
        d = e.to_dict()
        assert d["agent"] == "a"
        assert d["correlation_id"] == "c"

    def test_to_dict_empty_data_preserved(self):
        """Empty dict is not None, so it should be kept."""
        e = Event(type=TASK_STARTED)
        d = e.to_dict()
        assert d["data"] == {}

    def test_to_json(self):
        e = Event(type=TASK_STARTED, agent="scout", id="abcd1234", ts="2025-01-01T00:00:00+00:00")
        j = e.to_json()
        parsed = json.loads(j)
        assert parsed["type"] == TASK_STARTED
        assert parsed["agent"] == "scout"
        assert parsed["id"] == "abcd1234"

    def test_to_json_compact(self):
        """to_json uses compact separators (no spaces)."""
        e = Event(type=TASK_STARTED, id="x", ts="t")
        j = e.to_json()
        assert " " not in j  # compact separators


# ---------------------------------------------------------------------------
# EventSpine
# ---------------------------------------------------------------------------

class TestEventSpine:
    def test_emit_creates_file(self, tmp_path):
        spine = EventSpine(tmp_path)
        spine.emit(Event(type=PROJECT_INITIALIZED))
        assert (tmp_path / ".claws" / "events.jsonl").exists()

    def test_emit_returns_event(self, tmp_path):
        spine = EventSpine(tmp_path)
        e = Event(type=PROJECT_INITIALIZED)
        result = spine.emit(e)
        assert result is e

    def test_emit_appends(self, tmp_path):
        spine = EventSpine(tmp_path)
        spine.emit(Event(type=TASK_STARTED, agent="a"))
        spine.emit(Event(type=TASK_COMPLETED, agent="a"))
        lines = (tmp_path / ".claws" / "events.jsonl").read_text().strip().split("\n")
        assert len(lines) == 2

    def test_read_all_empty(self, tmp_path):
        spine = EventSpine(tmp_path)
        assert spine.read_all() == []

    def test_read_all(self, tmp_path):
        spine = EventSpine(tmp_path)
        spine.emit(Event(type=TASK_STARTED, agent="a"))
        spine.emit(Event(type=TASK_COMPLETED, agent="a"))
        events = spine.read_all()
        assert len(events) == 2
        assert events[0].type == TASK_STARTED
        assert events[1].type == TASK_COMPLETED

    def test_read_by_type(self, tmp_path):
        spine = EventSpine(tmp_path)
        spine.emit(Event(type=TASK_STARTED, agent="a"))
        spine.emit(Event(type=TASK_COMPLETED, agent="a"))
        spine.emit(Event(type=TASK_STARTED, agent="b"))
        started = spine.read_by_type(TASK_STARTED)
        assert len(started) == 2
        completed = spine.read_by_type(TASK_COMPLETED)
        assert len(completed) == 1

    def test_read_by_agent(self, tmp_path):
        spine = EventSpine(tmp_path)
        spine.emit(Event(type=TASK_STARTED, agent="a"))
        spine.emit(Event(type=TASK_STARTED, agent="b"))
        spine.emit(Event(type=TASK_COMPLETED, agent="a"))
        a_events = spine.read_by_agent("a")
        assert len(a_events) == 2
        b_events = spine.read_by_agent("b")
        assert len(b_events) == 1

    def test_last_event_unfiltered(self, tmp_path):
        spine = EventSpine(tmp_path)
        spine.emit(Event(type=TASK_STARTED, agent="a"))
        spine.emit(Event(type=TASK_COMPLETED, agent="a"))
        last = spine.last_event()
        assert last is not None
        assert last.type == TASK_COMPLETED

    def test_last_event_by_agent(self, tmp_path):
        spine = EventSpine(tmp_path)
        spine.emit(Event(type=TASK_STARTED, agent="a"))
        spine.emit(Event(type=TASK_STARTED, agent="b"))
        last = spine.last_event(agent="a")
        assert last is not None
        assert last.agent == "a"

    def test_last_event_by_type(self, tmp_path):
        spine = EventSpine(tmp_path)
        spine.emit(Event(type=TASK_STARTED, agent="a"))
        spine.emit(Event(type=TASK_COMPLETED, agent="a"))
        spine.emit(Event(type=TASK_FAILED, agent="a"))
        last = spine.last_event(event_type=TASK_COMPLETED)
        assert last is not None
        assert last.type == TASK_COMPLETED

    def test_last_event_combined_filter(self, tmp_path):
        spine = EventSpine(tmp_path)
        spine.emit(Event(type=TASK_COMPLETED, agent="a"))
        spine.emit(Event(type=TASK_COMPLETED, agent="b"))
        last = spine.last_event(agent="a", event_type=TASK_COMPLETED)
        assert last is not None
        assert last.agent == "a"
        assert last.type == TASK_COMPLETED

    def test_last_event_empty(self, tmp_path):
        spine = EventSpine(tmp_path)
        assert spine.last_event() is None

    def test_last_event_no_match(self, tmp_path):
        spine = EventSpine(tmp_path)
        spine.emit(Event(type=TASK_STARTED, agent="a"))
        assert spine.last_event(agent="nonexistent") is None

    def test_event_data_roundtrip(self, tmp_path):
        """Data dict survives emit -> read_all roundtrip."""
        spine = EventSpine(tmp_path)
        spine.emit(Event(
            type=TASK_COMPLETED,
            agent="scout",
            data={"task": "analyze", "tokens_in": 100, "tokens_out": 50},
            correlation_id="c1",
        ))
        events = spine.read_all()
        assert len(events) == 1
        e = events[0]
        assert e.agent == "scout"
        assert e.data["tokens_in"] == 100
        assert e.correlation_id == "c1"

    def test_ensure_dir_creates_parent(self, tmp_path):
        """EventSpine should create .claws directory if it does not exist."""
        fresh = tmp_path / "subdir"
        fresh.mkdir()
        spine = EventSpine(fresh)
        spine.emit(Event(type=PROJECT_INITIALIZED))
        assert (fresh / ".claws").is_dir()
