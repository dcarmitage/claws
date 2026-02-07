"""claws doctor -- diagnostic check for project setup."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from claws.config import find_project_root, load_config, ProviderConfig
from claws.providers.registry import get_provider as _get_provider
from claws.providers.base import Message as _Message

console = Console()


def _check_project() -> tuple[bool, str, Path | None]:
    """Check if we're in a claws project. Returns (passed, detail, project_root)."""
    project_root = find_project_root()
    if project_root is None:
        return False, "No claws.yaml found", None
    return True, str(project_root), project_root


def _check_provider(project_root: Path) -> tuple[bool, str, ProviderConfig | None]:
    """Check if a provider is configured. Returns (passed, detail, provider_config)."""
    try:
        config = load_config(project_root)
    except Exception as e:
        return False, f"Error loading config: {e}", None

    provider_cfg = config.default_provider
    if provider_cfg is None:
        # Try to find any provider
        if config.providers:
            name = next(iter(config.providers))
            provider_cfg = config.providers[name]
        else:
            return False, "No providers configured in claws.yaml", None

    return True, f"{provider_cfg.type} / {provider_cfg.model}", provider_cfg


def _get_expected_env_var(provider_cfg: ProviderConfig) -> str | None:
    """Determine the expected env var for a provider config."""
    if provider_cfg.api_key_env:
        return provider_cfg.api_key_env
    if provider_cfg.type == "anthropic":
        return "ANTHROPIC_API_KEY"
    if provider_cfg.type in ("openai-compatible", "openai"):
        base_url = provider_cfg.base_url or ""
        if "openai.com" in base_url:
            return "OPENAI_API_KEY"
        if "openrouter.ai" in base_url:
            return "OPENROUTER_API_KEY"
        # For other openai-compatible, check if any standard key is set
        return None
    return None


def _get_help_url(provider_cfg: ProviderConfig) -> str | None:
    """Get the URL where the user can obtain an API key."""
    if provider_cfg.type == "anthropic":
        return "https://console.anthropic.com"
    base_url = provider_cfg.base_url or ""
    if "openai.com" in base_url:
        return "https://platform.openai.com/api-keys"
    if "openrouter.ai" in base_url:
        return "https://openrouter.ai/keys"
    return None


def _check_api_key(provider_cfg: ProviderConfig) -> tuple[bool, str]:
    """Check if the API key is available. Returns (passed, detail)."""
    # If the provider already resolves an api_key, it's available
    if provider_cfg.api_key:
        return True, "Found via environment"

    # For localhost/local providers, keys are often optional
    base_url = provider_cfg.base_url or ""
    if "localhost" in base_url or "127.0.0.1" in base_url:
        return True, "Local provider (no key required)"

    expected_var = _get_expected_env_var(provider_cfg)
    if expected_var:
        help_url = _get_help_url(provider_cfg)
        detail = f"Set your key: export {expected_var}=your-key"
        if help_url:
            detail += f"\n    \u2192 Get a key at: {help_url}"
        return False, detail

    # openai-compatible with unknown base_url - check common vars
    for var in ("OPENAI_API_KEY", "OPENROUTER_API_KEY"):
        if os.environ.get(var):
            return True, f"Found via {var}"

    return False, "No API key found. Set api_key_env in claws.yaml or set an API key env var"


def _check_connectivity(provider_cfg: ProviderConfig) -> tuple[bool, str]:
    """Check if we can reach the provider. Returns (passed, detail)."""
    try:
        provider = _get_provider(provider_cfg)
    except ValueError as e:
        return False, f"Provider init failed: {e}"

    messages = [_Message(role="user", content="Say hello in one word")]

    try:
        response = asyncio.run(provider.complete(messages, max_tokens=32))
        if response.content and response.content.strip():
            return True, f"Got response ({response.total_tokens} tokens)"
        return False, "Empty response from provider"
    except Exception as e:
        error_str = str(e)
        if len(error_str) > 120:
            error_str = error_str[:120] + "..."
        return False, f"Connection failed: {error_str}"


@click.command()
def doctor():
    """Check your claws project setup.

    Runs diagnostic checks on your project configuration, provider
    settings, API keys, and connectivity.
    """
    table = Table(show_header=True, box=None, padding=(0, 2))
    table.add_column("Setup Check", style="bold", min_width=30)
    table.add_column("Status", min_width=6)

    checks_passed = True

    # 1. Project check
    project_ok, project_detail, project_root = _check_project()
    if project_ok:
        table.add_row("Project (claws.yaml)", "[green]\u2713 Pass[/]")
    else:
        table.add_row("Project (claws.yaml)", "[red]\u2717 Fail[/]")
        table.add_row("", f"  [dim]\u2192 {project_detail}[/]")
        table.add_row("", "  [dim]\u2192 Run: claws init my-project[/]")
        checks_passed = False

    if not project_ok:
        # Skip all downstream checks
        table.add_row("Provider configured", "[dim]- Skipped[/] (needs project)")
        table.add_row("API key available", "[dim]- Skipped[/] (needs project)")
        table.add_row("Provider reachable", "[dim]- Skipped[/] (needs project)")
        console.print()
        console.print(table)
        if not checks_passed:
            raise SystemExit(1)
        return

    # 2. Provider check
    provider_ok, provider_detail, provider_cfg = _check_provider(project_root)
    if provider_ok:
        table.add_row("Provider configured", f"[green]\u2713 Pass[/]  ({provider_detail})")
    else:
        table.add_row("Provider configured", "[red]\u2717 Fail[/]")
        table.add_row("", f"  [dim]\u2192 {provider_detail}[/]")
        table.add_row("", "  [dim]\u2192 Add a provider to claws.yaml[/]")
        checks_passed = False

    if not provider_ok:
        table.add_row("API key available", "[dim]- Skipped[/] (needs provider)")
        table.add_row("Provider reachable", "[dim]- Skipped[/] (needs provider)")
        console.print()
        console.print(table)
        if not checks_passed:
            raise SystemExit(1)
        return

    # 3. API key check
    key_ok, key_detail = _check_api_key(provider_cfg)
    if key_ok:
        table.add_row("API key available", f"[green]\u2713 Pass[/]  ({key_detail})")
    else:
        table.add_row("API key available", "[red]\u2717 Fail[/]")
        for line in key_detail.split("\n"):
            table.add_row("", f"  [dim]\u2192 {line.strip()}[/]")
        checks_passed = False

    if not key_ok:
        table.add_row("Provider reachable", "[dim]- Skipped[/] (needs API key)")
        console.print()
        console.print(table)
        if not checks_passed:
            raise SystemExit(1)
        return

    # 4. Connectivity check
    conn_ok, conn_detail = _check_connectivity(provider_cfg)
    if conn_ok:
        table.add_row("Provider reachable", f"[green]\u2713 Pass[/]  ({conn_detail})")
    else:
        table.add_row("Provider reachable", "[red]\u2717 Fail[/]")
        table.add_row("", f"  [dim]\u2192 {conn_detail}[/]")
        table.add_row("", "  [dim]\u2192 Run: claws doctor (to retry)[/]")
        checks_passed = False

    console.print()
    console.print(table)

    if not checks_passed:
        raise SystemExit(1)
