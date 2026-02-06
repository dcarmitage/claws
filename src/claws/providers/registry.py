"""Provider registry — resolves config to provider instances."""

from __future__ import annotations

from claws.config import ProviderConfig
from claws.providers.base import Provider


def get_provider(config: ProviderConfig) -> Provider:
    """Create a provider instance from config."""
    if config.type == "anthropic":
        from claws.providers.anthropic import AnthropicProvider
        api_key = config.api_key
        if not api_key:
            raise ValueError(
                "Anthropic API key not found. Set ANTHROPIC_API_KEY or "
                "configure api_key_env in claws.yaml"
            )
        return AnthropicProvider(api_key=api_key, model=config.model)

    # Everything else uses OpenAI-compatible format
    from claws.providers.openai_compat import OpenAICompatProvider

    base_url = config.base_url
    if config.type == "ollama" and not base_url:
        base_url = "http://localhost:11434/v1"
    elif not base_url:
        base_url = "https://api.openai.com/v1"

    return OpenAICompatProvider(
        model=config.model,
        api_key=config.api_key,
        base_url=base_url,
    )
