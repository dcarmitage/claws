"""Configuration system for claws projects.

Reads claws.yaml from the project root and provides typed access
to project settings, provider configs, and agent definitions.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


CONFIG_FILENAME = "claws.yaml"
EVENTS_DIR = ".claws"
EVENTS_FILE = "events.jsonl"


@dataclass
class ProviderConfig:
    """Configuration for an LLM provider."""
    name: str
    type: str  # "anthropic", "openai", "ollama", "openai-compatible"
    model: str
    base_url: str | None = None
    api_key_env: str | None = None  # env var name holding the key

    @property
    def api_key(self) -> str | None:
        if self.api_key_env:
            return os.environ.get(self.api_key_env)
        # Auto-discover from standard env vars
        if self.type == "anthropic":
            return os.environ.get("ANTHROPIC_API_KEY")
        if self.type in ("openai", "openai-compatible"):
            return os.environ.get("OPENAI_API_KEY")
        return None


@dataclass
class EvalConfig:
    """Configuration for the evaluation pipeline."""
    judges: list[str] = field(default_factory=lambda: ["logic", "consistency"])
    threshold: float = 8.0
    provider: str | None = None


@dataclass
class AgentConfig:
    """Configuration for a single agent."""
    name: str
    role: str
    provider: str = "default"
    machine: str = "local"


@dataclass
class ProjectConfig:
    """Full project configuration from claws.yaml."""
    project: str
    version: int = 2
    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    agents: dict[str, AgentConfig] = field(default_factory=dict)
    eval: EvalConfig = field(default_factory=EvalConfig)

    @property
    def default_provider(self) -> ProviderConfig | None:
        return self.providers.get("default")


def find_project_root(start: Path | None = None) -> Path | None:
    """Walk up from start directory to find claws.yaml."""
    current = start or Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / CONFIG_FILENAME).exists():
            return parent
    return None


def load_config(project_root: Path | None = None) -> ProjectConfig:
    """Load and parse claws.yaml from the project root."""
    if project_root is None:
        project_root = find_project_root()
    if project_root is None:
        raise FileNotFoundError(
            f"No {CONFIG_FILENAME} found. Run 'claws init' to create a project."
        )

    config_path = project_root / CONFIG_FILENAME
    with open(config_path) as f:
        raw = yaml.safe_load(f) or {}

    # Parse providers
    providers = {}
    for name, prov in raw.get("providers", {}).items():
        providers[name] = ProviderConfig(
            name=name,
            type=prov.get("type", "openai-compatible"),
            model=prov.get("model", ""),
            base_url=prov.get("base_url"),
            api_key_env=prov.get("api_key_env"),
        )

    # Parse agents
    agents = {}
    for name, agent in raw.get("agents", {}).items():
        agents[name] = AgentConfig(
            name=name,
            role=agent.get("role", "general"),
            provider=agent.get("provider", "default"),
            machine=agent.get("machine", "local"),
        )

    # Parse eval
    eval_raw = raw.get("eval", {})
    eval_config = EvalConfig(
        judges=eval_raw.get("judges", ["logic", "consistency"]),
        threshold=eval_raw.get("threshold", 8.0),
        provider=eval_raw.get("provider"),
    )

    return ProjectConfig(
        project=raw.get("project", project_root.name),
        version=raw.get("version", 2),
        providers=providers,
        agents=agents,
        eval=eval_config,
    )
