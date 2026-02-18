"""Tests for claws scratchpad command and data model."""

import json
import yaml
import pytest
from pathlib import Path
from click.testing import CliRunner

from claws.cli import main
from claws.events import EventSpine
from claws.scratchpad import (
    Scratchpad,
    Thread,
    Decision,
    scratchpad_path,
    load_scratchpad,
    save_scratchpad,
    parse_scratchpad,
)


def _make_project(td_path: Path, agents=None):
    """Helper: create a project with optional agents."""
    if agents is None:
        agents = {}
    config = {
        "project": "test-project",
        "version": 2,
        "providers": {
            "default": {
                "type": "anthropic",
                "model": "claude-sonnet-4-5-20250929",
            },
        },
        "agents": agents,
        "eval": {"judges": ["logic", "consistency"], "threshold": 8.0},
    }
    (td_path / "claws.yaml").write_text(
        yaml.dump(config, default_flow_style=False, sort_keys=False)
    )
    (td_path / "agents").mkdir(exist_ok=True)
    (td_path / ".claws").mkdir(exist_ok=True)


def _make_agent(td_path: Path, name: str, role: str = "researcher"):
    """Helper: create an agent directory and add to config."""
    agent_dir = td_path / "agents" / name
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "identity.md").write_text(f"# {name}\nRole: {role}\n")
    (agent_dir / "memory.md").write_text(f"# {name} Memory\n")

    # Update config
    config_path = td_path / "claws.yaml"
    config = yaml.safe_load(config_path.read_text())
    config["agents"][name] = {"role": role, "provider": "default", "machine": "local"}
    config_path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))


# =============================================================================
# Data Model Tests
# =============================================================================


class TestThread:
    def test_basic_thread(self):
        t = Thread(name="Feature X")
        assert t.name == "Feature X"
        assert t.state == ""
        assert t.next_action == ""
        assert t.blocking == ""
        assert t.notes == []

    def test_thread_to_markdown(self):
        t = Thread(
            name="Feature X",
            state="In progress",
            next_action="Write tests",
            blocking="",
        )
        md = t.to_markdown()
        assert "### Feature X" in md
        assert "**State:** In progress" in md
        assert "→ Write tests" in md
        assert "⏸" not in md

    def test_thread_with_blocking(self):
        t = Thread(
            name="Deploy",
            state="Waiting",
            blocking="Need credentials",
        )
        md = t.to_markdown()
        assert "⏸ Need credentials" in md

    def test_thread_with_notes(self):
        t = Thread(name="Research", notes=["Found paper A", "Paper B is relevant"])
        md = t.to_markdown()
        assert "- Found paper A" in md
        assert "- Paper B is relevant" in md


class TestDecision:
    def test_basic_decision(self):
        d = Decision(number=1, question="Use SQLite or Postgres?")
        assert d.number == 1
        assert d.question == "Use SQLite or Postgres?"
        assert not d.resolved

    def test_decision_to_markdown_row(self):
        d = Decision(
            number=1,
            question="Use SQLite or Postgres?",
            context="Small project",
            urgency="normal",
        )
        row = d.to_markdown_row()
        assert "| 1 |" in row
        assert "Use SQLite or Postgres?" in row
        assert "Small project" in row
        assert "normal" in row

    def test_resolved_decision_to_markdown_row(self):
        d = Decision(
            number=1,
            question="Use SQLite or Postgres?",
            resolved=True,
            resolution="SQLite",
        )
        row = d.to_markdown_row()
        assert "~~1~~" in row
        assert "**SQLite**" in row
        assert "✓ Done" in row


class TestScratchpad:
    def test_empty_scratchpad(self):
        sp = Scratchpad(agent_name="scout")
        assert sp.agent_name == "scout"
        assert sp.threads == []
        assert sp.decisions == []
        assert sp.reflections == []
        assert sp.inbox == []

    def test_next_decision_number_empty(self):
        sp = Scratchpad(agent_name="scout")
        assert sp.next_decision_number == 1

    def test_next_decision_number_with_existing(self):
        sp = Scratchpad(
            agent_name="scout",
            decisions=[
                Decision(number=1, question="A?"),
                Decision(number=3, question="B?"),
            ],
        )
        assert sp.next_decision_number == 4

    def test_find_thread_exact(self):
        t = Thread(name="Feature X")
        sp = Scratchpad(agent_name="scout", threads=[t])
        assert sp.find_thread("Feature X") is t

    def test_find_thread_case_insensitive(self):
        t = Thread(name="Feature X")
        sp = Scratchpad(agent_name="scout", threads=[t])
        assert sp.find_thread("feature x") is t

    def test_find_thread_partial(self):
        t = Thread(name="Feature X — Phase 2")
        sp = Scratchpad(agent_name="scout", threads=[t])
        assert sp.find_thread("Feature X") is t

    def test_find_thread_not_found(self):
        sp = Scratchpad(agent_name="scout", threads=[Thread(name="Feature X")])
        assert sp.find_thread("Feature Y") is None

    def test_find_decision(self):
        d = Decision(number=1, question="A?")
        sp = Scratchpad(agent_name="scout", decisions=[d])
        assert sp.find_decision(1) is d
        assert sp.find_decision(2) is None

    def test_to_markdown_basic(self):
        sp = Scratchpad(agent_name="scout")
        md = sp.to_markdown()
        assert "# Scratchpad — scout" in md
        assert "Last tended:" in md
        assert "🧵 Open Threads" in md
        assert "⚖️ Decisions Waiting" in md
        assert "📬 Inbox" in md
        assert "🪞 Reflections" in md

    def test_to_markdown_with_content(self):
        sp = Scratchpad(
            agent_name="scout",
            threads=[Thread(name="Build API", state="In progress", next_action="Write endpoints")],
            decisions=[Decision(number=1, question="REST or GraphQL?", context="API design", urgency="high")],
            reflections=["Need more error handling"],
            inbox=["Check performance benchmarks"],
        )
        md = sp.to_markdown()
        assert "### Build API" in md
        assert "REST or GraphQL?" in md
        assert "Need more error handling" in md
        assert "Check performance benchmarks" in md


class TestRoundTrip:
    """Test that scratchpad survives write → read → write."""

    def test_empty_roundtrip(self, tmp_path):
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")

        sp = Scratchpad(agent_name="scout")
        save_scratchpad(tmp_path, sp)
        loaded = load_scratchpad(tmp_path, "scout")

        assert loaded is not None
        assert loaded.agent_name == "scout"
        assert loaded.threads == []
        assert loaded.decisions == []

    def test_full_roundtrip(self, tmp_path):
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")

        sp = Scratchpad(
            agent_name="scout",
            threads=[
                Thread(name="Feature A", state="Active", next_action="Write code", blocking=""),
                Thread(name="Feature B", state="Blocked", blocking="Need approval"),
            ],
            decisions=[
                Decision(number=1, question="X or Y?", context="Design", urgency="normal"),
                Decision(number=2, question="A or B?", resolved=True, resolution="A"),
            ],
            reflections=["Improving steadily"],
            inbox=["Review PR #42"],
        )
        save_scratchpad(tmp_path, sp)
        loaded = load_scratchpad(tmp_path, "scout")

        assert loaded is not None
        assert len(loaded.threads) == 2
        assert loaded.threads[0].name == "Feature A"
        assert loaded.threads[0].state == "Active"
        assert loaded.threads[0].next_action == "Write code"
        assert loaded.threads[1].name == "Feature B"
        assert loaded.threads[1].blocking == "Need approval"
        assert len(loaded.decisions) == 2
        assert loaded.decisions[0].question == "X or Y?"
        assert loaded.decisions[1].resolved is True
        assert loaded.reflections == ["Improving steadily"]
        assert loaded.inbox == ["Review PR #42"]

    def test_load_nonexistent(self, tmp_path):
        _make_project(tmp_path)
        assert load_scratchpad(tmp_path, "ghost") is None


class TestParseScratchpad:
    def test_parse_minimal(self):
        text = "# Scratchpad — test\n\n> Last tended: 2026-02-18 01:00 UTC\n"
        sp = parse_scratchpad(text, "test")
        assert sp.agent_name == "test"
        assert "2026-02-18" in sp.last_tended

    def test_parse_threads(self):
        text = """# Scratchpad — test

## 🧵 Open Threads

### Feature X
**State:** In progress
→ Write tests
⏸ Waiting for review

### Feature Y
**State:** Planning
- Note 1
- Note 2

## ⚖️ Decisions Waiting

| # | Decision | Context | Urgency |
|---|----------|---------|---------|
"""
        sp = parse_scratchpad(text, "test")
        assert len(sp.threads) == 2
        assert sp.threads[0].name == "Feature X"
        assert sp.threads[0].state == "In progress"
        assert sp.threads[0].next_action == "Write tests"
        assert sp.threads[0].blocking == "Waiting for review"
        assert sp.threads[1].name == "Feature Y"
        assert sp.threads[1].notes == ["Note 1", "Note 2"]

    def test_parse_decisions(self):
        text = """# Scratchpad — test

## ⚖️ Decisions Waiting

| # | Decision | Context | Urgency |
|---|----------|---------|---------|
| 1 | Use SQLite? | Small project | normal |
| ~~2~~ | ~~Old question~~ → **Resolved** | Was important | ✓ Done |
"""
        sp = parse_scratchpad(text, "test")
        assert len(sp.decisions) == 2
        assert sp.decisions[0].number == 1
        assert sp.decisions[0].question == "Use SQLite?"
        assert not sp.decisions[0].resolved
        assert sp.decisions[1].number == 2
        assert sp.decisions[1].resolved is True
        assert sp.decisions[1].resolution == "Resolved"

    def test_parse_inbox_and_reflections(self):
        text = """# Scratchpad — test

## 📬 Inbox

- Check the logs
- Review config

## 🪞 Reflections

- Getting better at testing
- Need to document more
"""
        sp = parse_scratchpad(text, "test")
        assert sp.inbox == ["Check the logs", "Review config"]
        assert sp.reflections == ["Getting better at testing", "Need to document more"]


# =============================================================================
# CLI Command Tests
# =============================================================================


class TestScratchpadInit:
    def test_init_creates_scratchpad(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            _make_agent(Path(td), "scout")
            result = runner.invoke(main, ["scratchpad", "init", "scout"], catch_exceptions=False)
            assert result.exit_code == 0
            assert "created" in result.output.lower()
            assert (Path(td) / "agents" / "scout" / "scratchpad.md").exists()

    def test_init_no_overwrite(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            _make_agent(Path(td), "scout")
            runner.invoke(main, ["scratchpad", "init", "scout"], catch_exceptions=False)
            result = runner.invoke(main, ["scratchpad", "init", "scout"])
            assert result.exit_code != 0
            assert "already exists" in result.output.lower()

    def test_init_force_overwrite(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            _make_agent(Path(td), "scout")
            runner.invoke(main, ["scratchpad", "init", "scout"], catch_exceptions=False)
            result = runner.invoke(main, ["scratchpad", "init", "scout", "--force"], catch_exceptions=False)
            assert result.exit_code == 0
            assert "created" in result.output.lower()

    def test_init_nonexistent_agent(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            result = runner.invoke(main, ["scratchpad", "init", "ghost"])
            assert result.exit_code != 0
            assert "not found" in result.output.lower()

    def test_init_no_project(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, ["scratchpad", "init", "scout"])
            assert result.exit_code != 0

    def test_init_emits_event(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            _make_agent(Path(td), "scout")
            runner.invoke(main, ["scratchpad", "init", "scout"], catch_exceptions=False)
            spine = EventSpine(Path(td))
            events = spine.read_all()
            assert any(e.type == "scratchpad.created" for e in events)


class TestScratchpadShow:
    def test_show_formatted(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            _make_agent(Path(td), "scout")
            runner.invoke(main, ["scratchpad", "init", "scout"], catch_exceptions=False)
            result = runner.invoke(main, ["scratchpad", "show", "scout"], catch_exceptions=False)
            assert result.exit_code == 0
            assert "scout" in result.output

    def test_show_raw(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            _make_agent(Path(td), "scout")
            runner.invoke(main, ["scratchpad", "init", "scout"], catch_exceptions=False)
            result = runner.invoke(main, ["scratchpad", "show", "scout", "--raw"], catch_exceptions=False)
            assert result.exit_code == 0
            assert "# Scratchpad" in result.output

    def test_show_no_scratchpad(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            _make_agent(Path(td), "scout")
            result = runner.invoke(main, ["scratchpad", "show", "scout"])
            assert result.exit_code != 0
            assert "no scratchpad" in result.output.lower()


class TestScratchpadThreadAdd:
    def test_add_thread(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            _make_agent(Path(td), "scout")
            runner.invoke(main, ["scratchpad", "init", "scout"], catch_exceptions=False)
            result = runner.invoke(
                main,
                ["scratchpad", "thread", "add", "scout", "API Design",
                 "--state", "Planning", "--next", "Draft endpoints"],
                catch_exceptions=False,
            )
            assert result.exit_code == 0
            assert "added" in result.output.lower()

            # Verify it persisted
            sp = load_scratchpad(Path(td), "scout")
            assert len(sp.threads) == 1
            assert sp.threads[0].name == "API Design"
            assert sp.threads[0].state == "Planning"
            assert sp.threads[0].next_action == "Draft endpoints"

    def test_add_duplicate_thread(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            _make_agent(Path(td), "scout")
            runner.invoke(main, ["scratchpad", "init", "scout"], catch_exceptions=False)
            runner.invoke(
                main,
                ["scratchpad", "thread", "add", "scout", "API Design"],
                catch_exceptions=False,
            )
            result = runner.invoke(
                main,
                ["scratchpad", "thread", "add", "scout", "API Design"],
            )
            assert result.exit_code != 0
            assert "already exists" in result.output.lower()

    def test_add_thread_emits_event(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            _make_agent(Path(td), "scout")
            runner.invoke(main, ["scratchpad", "init", "scout"], catch_exceptions=False)
            runner.invoke(
                main,
                ["scratchpad", "thread", "add", "scout", "API Design"],
                catch_exceptions=False,
            )
            spine = EventSpine(Path(td))
            events = spine.read_all()
            assert any(e.type == "scratchpad.thread.added" for e in events)


class TestScratchpadThreadUpdate:
    def test_update_thread_state(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            _make_agent(Path(td), "scout")
            runner.invoke(main, ["scratchpad", "init", "scout"], catch_exceptions=False)
            runner.invoke(
                main,
                ["scratchpad", "thread", "add", "scout", "API Design", "--state", "Planning"],
                catch_exceptions=False,
            )
            result = runner.invoke(
                main,
                ["scratchpad", "thread", "update", "scout", "API Design",
                 "--state", "In progress", "--next", "Write tests"],
                catch_exceptions=False,
            )
            assert result.exit_code == 0
            sp = load_scratchpad(Path(td), "scout")
            assert sp.threads[0].state == "In progress"
            assert sp.threads[0].next_action == "Write tests"

    def test_update_add_note(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            _make_agent(Path(td), "scout")
            runner.invoke(main, ["scratchpad", "init", "scout"], catch_exceptions=False)
            runner.invoke(
                main,
                ["scratchpad", "thread", "add", "scout", "API Design"],
                catch_exceptions=False,
            )
            result = runner.invoke(
                main,
                ["scratchpad", "thread", "update", "scout", "API Design",
                 "--note", "Found a useful library"],
                catch_exceptions=False,
            )
            assert result.exit_code == 0
            sp = load_scratchpad(Path(td), "scout")
            assert "Found a useful library" in sp.threads[0].notes

    def test_update_nonexistent_thread(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            _make_agent(Path(td), "scout")
            runner.invoke(main, ["scratchpad", "init", "scout"], catch_exceptions=False)
            result = runner.invoke(
                main,
                ["scratchpad", "thread", "update", "scout", "Ghost Thread",
                 "--state", "Active"],
            )
            assert result.exit_code != 0
            assert "not found" in result.output.lower()

    def test_update_no_changes(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            _make_agent(Path(td), "scout")
            runner.invoke(main, ["scratchpad", "init", "scout"], catch_exceptions=False)
            runner.invoke(
                main,
                ["scratchpad", "thread", "add", "scout", "API Design"],
                catch_exceptions=False,
            )
            result = runner.invoke(
                main,
                ["scratchpad", "thread", "update", "scout", "API Design"],
                catch_exceptions=False,
            )
            assert result.exit_code == 0
            assert "no changes" in result.output.lower()


class TestScratchpadThreadArchive:
    def test_archive_thread(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            _make_agent(Path(td), "scout")
            runner.invoke(main, ["scratchpad", "init", "scout"], catch_exceptions=False)
            runner.invoke(
                main,
                ["scratchpad", "thread", "add", "scout", "API Design"],
                catch_exceptions=False,
            )
            result = runner.invoke(
                main,
                ["scratchpad", "thread", "archive", "scout", "API Design"],
                catch_exceptions=False,
            )
            assert result.exit_code == 0
            assert "archived" in result.output.lower()
            sp = load_scratchpad(Path(td), "scout")
            assert len(sp.threads) == 0

    def test_archive_nonexistent_thread(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            _make_agent(Path(td), "scout")
            runner.invoke(main, ["scratchpad", "init", "scout"], catch_exceptions=False)
            result = runner.invoke(
                main,
                ["scratchpad", "thread", "archive", "scout", "Ghost Thread"],
            )
            assert result.exit_code != 0
            assert "not found" in result.output.lower()

    def test_archive_emits_event(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            _make_agent(Path(td), "scout")
            runner.invoke(main, ["scratchpad", "init", "scout"], catch_exceptions=False)
            runner.invoke(
                main,
                ["scratchpad", "thread", "add", "scout", "API Design"],
                catch_exceptions=False,
            )
            runner.invoke(
                main,
                ["scratchpad", "thread", "archive", "scout", "API Design"],
                catch_exceptions=False,
            )
            spine = EventSpine(Path(td))
            events = spine.read_all()
            assert any(e.type == "scratchpad.thread.archived" for e in events)


class TestScratchpadThreadList:
    def test_list_threads(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            _make_agent(Path(td), "scout")
            runner.invoke(main, ["scratchpad", "init", "scout"], catch_exceptions=False)
            runner.invoke(
                main,
                ["scratchpad", "thread", "add", "scout", "API Design", "--state", "Active"],
                catch_exceptions=False,
            )
            runner.invoke(
                main,
                ["scratchpad", "thread", "add", "scout", "Deploy", "--blocking", "creds"],
                catch_exceptions=False,
            )
            result = runner.invoke(
                main,
                ["scratchpad", "thread", "list", "scout"],
                catch_exceptions=False,
            )
            assert result.exit_code == 0
            assert "API Design" in result.output
            assert "Deploy" in result.output

    def test_list_empty(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            _make_agent(Path(td), "scout")
            runner.invoke(main, ["scratchpad", "init", "scout"], catch_exceptions=False)
            result = runner.invoke(
                main,
                ["scratchpad", "thread", "list", "scout"],
                catch_exceptions=False,
            )
            assert result.exit_code == 0
            assert "no active threads" in result.output.lower()


class TestScratchpadDecisionAdd:
    def test_add_decision(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            _make_agent(Path(td), "scout")
            runner.invoke(main, ["scratchpad", "init", "scout"], catch_exceptions=False)
            result = runner.invoke(
                main,
                ["scratchpad", "decision", "add", "scout", "Use SQLite or Postgres?",
                 "--context", "Small project", "--urgency", "high"],
                catch_exceptions=False,
            )
            assert result.exit_code == 0
            assert "#1" in result.output

            sp = load_scratchpad(Path(td), "scout")
            assert len(sp.decisions) == 1
            assert sp.decisions[0].question == "Use SQLite or Postgres?"
            assert sp.decisions[0].urgency == "high"

    def test_add_multiple_decisions_auto_number(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            _make_agent(Path(td), "scout")
            runner.invoke(main, ["scratchpad", "init", "scout"], catch_exceptions=False)
            runner.invoke(
                main,
                ["scratchpad", "decision", "add", "scout", "First?"],
                catch_exceptions=False,
            )
            runner.invoke(
                main,
                ["scratchpad", "decision", "add", "scout", "Second?"],
                catch_exceptions=False,
            )
            sp = load_scratchpad(Path(td), "scout")
            assert sp.decisions[0].number == 1
            assert sp.decisions[1].number == 2

    def test_add_decision_emits_event(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            _make_agent(Path(td), "scout")
            runner.invoke(main, ["scratchpad", "init", "scout"], catch_exceptions=False)
            runner.invoke(
                main,
                ["scratchpad", "decision", "add", "scout", "What db?"],
                catch_exceptions=False,
            )
            spine = EventSpine(Path(td))
            events = spine.read_all()
            assert any(e.type == "scratchpad.decision.added" for e in events)


class TestScratchpadDecisionResolve:
    def test_resolve_decision(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            _make_agent(Path(td), "scout")
            runner.invoke(main, ["scratchpad", "init", "scout"], catch_exceptions=False)
            runner.invoke(
                main,
                ["scratchpad", "decision", "add", "scout", "SQLite or Postgres?"],
                catch_exceptions=False,
            )
            result = runner.invoke(
                main,
                ["scratchpad", "decision", "resolve", "scout", "1", "SQLite"],
                catch_exceptions=False,
            )
            assert result.exit_code == 0
            assert "resolved" in result.output.lower()

            sp = load_scratchpad(Path(td), "scout")
            assert sp.decisions[0].resolved is True
            assert sp.decisions[0].resolution == "SQLite"

    def test_resolve_already_resolved(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            _make_agent(Path(td), "scout")
            runner.invoke(main, ["scratchpad", "init", "scout"], catch_exceptions=False)
            runner.invoke(
                main,
                ["scratchpad", "decision", "add", "scout", "SQLite or Postgres?"],
                catch_exceptions=False,
            )
            runner.invoke(
                main,
                ["scratchpad", "decision", "resolve", "scout", "1", "SQLite"],
                catch_exceptions=False,
            )
            result = runner.invoke(
                main,
                ["scratchpad", "decision", "resolve", "scout", "1", "Postgres"],
                catch_exceptions=False,
            )
            assert result.exit_code == 0
            assert "already resolved" in result.output.lower()

    def test_resolve_nonexistent(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            _make_agent(Path(td), "scout")
            runner.invoke(main, ["scratchpad", "init", "scout"], catch_exceptions=False)
            result = runner.invoke(
                main,
                ["scratchpad", "decision", "resolve", "scout", "99", "Something"],
            )
            assert result.exit_code != 0
            assert "not found" in result.output.lower()

    def test_resolve_emits_event(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            _make_agent(Path(td), "scout")
            runner.invoke(main, ["scratchpad", "init", "scout"], catch_exceptions=False)
            runner.invoke(
                main,
                ["scratchpad", "decision", "add", "scout", "What db?"],
                catch_exceptions=False,
            )
            runner.invoke(
                main,
                ["scratchpad", "decision", "resolve", "scout", "1", "SQLite"],
                catch_exceptions=False,
            )
            spine = EventSpine(Path(td))
            events = spine.read_all()
            assert any(e.type == "scratchpad.decision.resolved" for e in events)


class TestScratchpadDecisionList:
    def test_list_decisions(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            _make_agent(Path(td), "scout")
            runner.invoke(main, ["scratchpad", "init", "scout"], catch_exceptions=False)
            runner.invoke(
                main,
                ["scratchpad", "decision", "add", "scout", "What db?"],
                catch_exceptions=False,
            )
            runner.invoke(
                main,
                ["scratchpad", "decision", "add", "scout", "What framework?"],
                catch_exceptions=False,
            )
            result = runner.invoke(
                main,
                ["scratchpad", "decision", "list", "scout"],
                catch_exceptions=False,
            )
            assert result.exit_code == 0
            assert "What db?" in result.output
            assert "What framework?" in result.output

    def test_list_hides_resolved_by_default(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            _make_agent(Path(td), "scout")
            runner.invoke(main, ["scratchpad", "init", "scout"], catch_exceptions=False)
            runner.invoke(
                main,
                ["scratchpad", "decision", "add", "scout", "What db?"],
                catch_exceptions=False,
            )
            runner.invoke(
                main,
                ["scratchpad", "decision", "resolve", "scout", "1", "SQLite"],
                catch_exceptions=False,
            )
            result = runner.invoke(
                main,
                ["scratchpad", "decision", "list", "scout"],
                catch_exceptions=False,
            )
            assert result.exit_code == 0
            assert "no pending" in result.output.lower()

    def test_list_all_shows_resolved(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            _make_agent(Path(td), "scout")
            runner.invoke(main, ["scratchpad", "init", "scout"], catch_exceptions=False)
            runner.invoke(
                main,
                ["scratchpad", "decision", "add", "scout", "What db?"],
                catch_exceptions=False,
            )
            runner.invoke(
                main,
                ["scratchpad", "decision", "resolve", "scout", "1", "SQLite"],
                catch_exceptions=False,
            )
            result = runner.invoke(
                main,
                ["scratchpad", "decision", "list", "scout", "--all"],
                catch_exceptions=False,
            )
            assert result.exit_code == 0
            assert "What db?" in result.output


class TestScratchpadIntegration:
    """End-to-end tests using multiple commands."""

    def test_full_workflow(self, tmp_path):
        """Test init → add threads → add decisions → update → resolve → archive."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            _make_agent(Path(td), "scout")

            # Init
            result = runner.invoke(main, ["scratchpad", "init", "scout"], catch_exceptions=False)
            assert result.exit_code == 0

            # Add threads
            runner.invoke(
                main,
                ["scratchpad", "thread", "add", "scout", "API Design",
                 "--state", "Planning", "--next", "Draft spec"],
                catch_exceptions=False,
            )
            runner.invoke(
                main,
                ["scratchpad", "thread", "add", "scout", "Database",
                 "--state", "Researching", "--blocking", "Need schema review"],
                catch_exceptions=False,
            )

            # Add decisions
            runner.invoke(
                main,
                ["scratchpad", "decision", "add", "scout", "REST or GraphQL?",
                 "--context", "API design", "--urgency", "high"],
                catch_exceptions=False,
            )

            # Show
            result = runner.invoke(main, ["scratchpad", "show", "scout"], catch_exceptions=False)
            assert result.exit_code == 0
            assert "API Design" in result.output
            assert "Database" in result.output

            # Update thread
            runner.invoke(
                main,
                ["scratchpad", "thread", "update", "scout", "API Design",
                 "--state", "In progress", "--next", "Write endpoints"],
                catch_exceptions=False,
            )

            # Resolve decision
            runner.invoke(
                main,
                ["scratchpad", "decision", "resolve", "scout", "1", "REST"],
                catch_exceptions=False,
            )

            # Archive thread
            runner.invoke(
                main,
                ["scratchpad", "thread", "archive", "scout", "Database"],
                catch_exceptions=False,
            )

            # Final state check
            sp = load_scratchpad(Path(td), "scout")
            assert len(sp.threads) == 1
            assert sp.threads[0].name == "API Design"
            assert sp.threads[0].state == "In progress"
            assert sp.decisions[0].resolved is True
            assert sp.decisions[0].resolution == "REST"

            # Verify events were emitted
            spine = EventSpine(Path(td))
            events = spine.read_all()
            event_types = [e.type for e in events]
            assert "scratchpad.created" in event_types
            assert "scratchpad.thread.added" in event_types
            assert "scratchpad.thread.updated" in event_types
            assert "scratchpad.thread.archived" in event_types
            assert "scratchpad.decision.added" in event_types
            assert "scratchpad.decision.resolved" in event_types
