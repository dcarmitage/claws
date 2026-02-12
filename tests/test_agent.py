"""Tests for claws agent command — create, list, info."""

import json
import yaml
from pathlib import Path
from click.testing import CliRunner

from claws.cli import main


def _make_project(td_path: Path):
    """Helper: create a minimal project inside td_path."""
    config = {
        "project": "test-project",
        "version": 2,
        "providers": {
            "default": {
                "type": "anthropic",
                "model": "claude-sonnet-4-5-20250929",
            },
        },
        "agents": {},
        "eval": {"judges": ["logic", "consistency"], "threshold": 8.0},
    }
    (td_path / "claws.yaml").write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))
    (td_path / "agents").mkdir(exist_ok=True)
    (td_path / ".claws").mkdir(exist_ok=True)


class TestAgentCreate:
    def test_creates_agent_directory(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            result = runner.invoke(
                main, ["agent", "create", "scout", "--role", "researcher"],
                catch_exceptions=False,
            )
            assert result.exit_code == 0, result.output
            agent_dir = Path(td) / "agents" / "scout"
            assert agent_dir.is_dir()

    def test_creates_identity_md(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            runner.invoke(
                main, ["agent", "create", "scout", "--role", "researcher"],
                catch_exceptions=False,
            )
            identity = (Path(td) / "agents" / "scout" / "identity.md").read_text()
            assert "scout" in identity
            assert "researcher" in identity

    def test_creates_memory_md(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            runner.invoke(
                main, ["agent", "create", "scout", "--role", "researcher"],
                catch_exceptions=False,
            )
            memory = (Path(td) / "agents" / "scout" / "memory.md").read_text()
            assert "scout" in memory

    def test_creates_output_dir(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            runner.invoke(
                main, ["agent", "create", "scout", "--role", "researcher"],
                catch_exceptions=False,
            )
            assert (Path(td) / "agents" / "scout" / "output").is_dir()

    def test_updates_claws_yaml(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            runner.invoke(
                main, ["agent", "create", "scout", "--role", "researcher"],
                catch_exceptions=False,
            )
            config = yaml.safe_load((Path(td) / "claws.yaml").read_text())
            assert "scout" in config["agents"]
            assert config["agents"]["scout"]["role"] == "researcher"

    def test_emits_agent_created_event(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            runner.invoke(
                main, ["agent", "create", "scout", "--role", "researcher"],
                catch_exceptions=False,
            )
            events = (Path(td) / ".claws" / "events.jsonl").read_text().strip().split("\n")
            event = json.loads(events[-1])
            assert event["type"] == "agent.created"
            assert event["agent"] == "scout"

    def test_duplicate_agent_error(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            runner.invoke(
                main, ["agent", "create", "scout", "--role", "researcher"],
                catch_exceptions=False,
            )
            result = runner.invoke(
                main, ["agent", "create", "scout", "--role", "researcher"],
            )
            assert result.exit_code != 0
            assert "already exists" in result.output

    def test_not_in_project_error(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            # No _make_project — bare directory
            result = runner.invoke(
                main, ["agent", "create", "scout", "--role", "researcher"],
            )
            assert result.exit_code != 0

    def test_custom_provider(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            runner.invoke(
                main,
                ["agent", "create", "scout", "--role", "researcher", "--provider", "fast"],
                catch_exceptions=False,
            )
            config = yaml.safe_load((Path(td) / "claws.yaml").read_text())
            assert config["agents"]["scout"]["provider"] == "fast"


class TestAgentList:
    def test_empty_project(self, tmp_path):
        """Empty project with agents/ dir shows an empty table (Agents header)."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            result = runner.invoke(main, ["agent", "list"], catch_exceptions=False)
            assert result.exit_code == 0
            # agents/ dir exists but is empty -- shows empty table with header
            assert "Agents" in result.output

    def test_lists_agents(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            runner.invoke(
                main, ["agent", "create", "scout", "--role", "researcher"],
                catch_exceptions=False,
            )
            result = runner.invoke(main, ["agent", "list"], catch_exceptions=False)
            assert result.exit_code == 0
            assert "scout" in result.output
            assert "researcher" in result.output


class TestAgentInfo:
    def test_shows_identity(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            runner.invoke(
                main, ["agent", "create", "scout", "--role", "researcher"],
                catch_exceptions=False,
            )
            result = runner.invoke(main, ["agent", "info", "scout"], catch_exceptions=False)
            assert result.exit_code == 0
            assert "scout" in result.output

    def test_nonexistent_agent_error(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            result = runner.invoke(main, ["agent", "info", "ghost"])
            assert result.exit_code != 0
            assert "not found" in result.output


class TestAgentSnapshots:
    def test_snapshot_creates_files(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            root = Path(td)
            _make_project(root)
            runner.invoke(main, ["agent", "create", "scout", "--role", "researcher"], catch_exceptions=False)

            result = runner.invoke(main, ["agent", "snapshot", "scout"], catch_exceptions=False)
            assert result.exit_code == 0, result.output

            snapshots_root = root / ".claws" / "snapshots" / "scout"
            snapshot_dirs = sorted([p for p in snapshots_root.iterdir() if p.is_dir()])
            assert len(snapshot_dirs) == 1
            snap = snapshot_dirs[0]
            assert (snap / "identity.md").exists()
            assert (snap / "memory.md").exists()
            manifest = json.loads((snap / "manifest.json").read_text())
            assert manifest["agent"] == "scout"
            assert manifest["snapshot"] == snap.name

    def test_snapshot_restore_latest(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            root = Path(td)
            _make_project(root)
            runner.invoke(main, ["agent", "create", "scout", "--role", "researcher"], catch_exceptions=False)

            identity_path = root / "agents" / "scout" / "identity.md"
            memory_path = root / "agents" / "scout" / "memory.md"

            identity_path.write_text("identity v1")
            memory_path.write_text("memory v1")
            runner.invoke(main, ["agent", "snapshot", "scout"], catch_exceptions=False)

            identity_path.write_text("identity v2")
            memory_path.write_text("memory v2")
            runner.invoke(main, ["agent", "snapshot", "scout"], catch_exceptions=False)

            identity_path.write_text("dirty")
            memory_path.write_text("dirty")

            result = runner.invoke(main, ["agent", "restore", "scout"], catch_exceptions=False)
            assert result.exit_code == 0, result.output
            assert identity_path.read_text() == "identity v2"
            assert memory_path.read_text() == "memory v2"

    def test_snapshot_restore_specific(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            root = Path(td)
            _make_project(root)
            runner.invoke(main, ["agent", "create", "scout", "--role", "researcher"], catch_exceptions=False)

            identity_path = root / "agents" / "scout" / "identity.md"
            memory_path = root / "agents" / "scout" / "memory.md"

            identity_path.write_text("first")
            memory_path.write_text("first")
            runner.invoke(main, ["agent", "snapshot", "scout"], catch_exceptions=False)

            first_snap = sorted((root / ".claws" / "snapshots" / "scout").iterdir())[0].name

            identity_path.write_text("second")
            memory_path.write_text("second")
            runner.invoke(main, ["agent", "snapshot", "scout"], catch_exceptions=False)

            identity_path.write_text("dirty")
            memory_path.write_text("dirty")

            result = runner.invoke(
                main,
                ["agent", "restore", "scout", "--snapshot", first_snap],
                catch_exceptions=False,
            )
            assert result.exit_code == 0, result.output
            assert identity_path.read_text() == "first"
            assert memory_path.read_text() == "first"

    def test_restore_creates_pre_restore_backup(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            root = Path(td)
            _make_project(root)
            runner.invoke(main, ["agent", "create", "scout", "--role", "researcher"], catch_exceptions=False)

            identity_path = root / "agents" / "scout" / "identity.md"
            memory_path = root / "agents" / "scout" / "memory.md"
            identity_path.write_text("stable")
            memory_path.write_text("stable")
            runner.invoke(main, ["agent", "snapshot", "scout"], catch_exceptions=False)

            identity_path.write_text("mutated")
            memory_path.write_text("mutated")

            result = runner.invoke(main, ["agent", "restore", "scout"], catch_exceptions=False)
            assert result.exit_code == 0, result.output
            assert "backup:" in result.output

            snap_dirs = sorted((root / ".claws" / "snapshots" / "scout").iterdir(), key=lambda p: p.name)
            assert len(snap_dirs) >= 2
            latest = snap_dirs[-1]
            manifest = json.loads((latest / "manifest.json").read_text())
            assert manifest.get("note") == "auto-pre-restore-backup"

    def test_restore_no_backup_option(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            root = Path(td)
            _make_project(root)
            runner.invoke(main, ["agent", "create", "scout", "--role", "researcher"], catch_exceptions=False)

            identity_path = root / "agents" / "scout" / "identity.md"
            memory_path = root / "agents" / "scout" / "memory.md"
            identity_path.write_text("v1")
            memory_path.write_text("v1")
            runner.invoke(main, ["agent", "snapshot", "scout"], catch_exceptions=False)

            identity_path.write_text("v2")
            memory_path.write_text("v2")

            result = runner.invoke(main, ["agent", "restore", "scout", "--no-backup"], catch_exceptions=False)
            assert result.exit_code == 0, result.output
            assert "backup:" not in result.output

            snap_dirs = [p for p in (root / ".claws" / "snapshots" / "scout").iterdir() if p.is_dir()]
            assert len(snap_dirs) == 1

    def test_snapshots_list(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            runner.invoke(main, ["agent", "create", "scout", "--role", "researcher"], catch_exceptions=False)
            runner.invoke(main, ["agent", "snapshot", "scout"], catch_exceptions=False)

            result = runner.invoke(main, ["agent", "snapshots", "list", "scout"], catch_exceptions=False)
            assert result.exit_code == 0
            assert "Snapshots: scout" in result.output

    def test_restore_without_snapshots_fails(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            runner.invoke(main, ["agent", "create", "scout", "--role", "researcher"], catch_exceptions=False)

            result = runner.invoke(main, ["agent", "restore", "scout"])
            assert result.exit_code != 0
            assert "No snapshots found" in result.output
