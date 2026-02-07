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
                "Anthropic API key not found. Set it with:\n"
                "  export ANTHROPIC_API_KEY=your-key\n"
                "Get a key at: https://console.anthropic.com\n"
                "Or run: claws doctor"
            )
        return AnthropicProvider(api_key=api_key, model=config.model)

    # Everything else uses OpenAI-compatible format
    from claws.providers.openai_compat import OpenAICompatProvider

    base_url = config.base_url
    if config.type == "ollama" and not base_url:
        base_url = "http://localhost:11434/v1"
    elif not base_url:
        base_url = "https://api.openai.com/v1"

    # Check if API key is likely needed but missing (only for known commercial APIs
    # when the user explicitly configured the type or base_url)
    api_key = config.api_key
    if not api_key and config.base_url:
        if "openai.com" in config.base_url:
            raise ValueError(
                f"API key not found for {base_url}. Set it with:\n"
                "  export OPENAI_API_KEY=your-key\n"
                "Get a key at: https://platform.openai.com/api-keys\n"
                "Or run: claws doctor"
            )
        elif "openrouter.ai" in config.base_url:
            raise ValueError(
                f"API key not found for {base_url}. Set it with:\n"
                "  export OPENROUTER_API_KEY=your-key\n"
                "Get a key at: https://openrouter.ai/keys\n"
                "Or run: claws doctor"
            )
    elif not api_key and config.type in ("openai", "openai-compatible") and not config.base_url:
        # Type explicitly set to openai/openai-compatible but no base_url and no key
        if "openai.com" in base_url:
            raise ValueError(
                f"API key not found for {base_url}. Set it with:\n"
                "  export OPENAI_API_KEY=your-key\n"
                "Get a key at: https://platform.openai.com/api-keys\n"
                "Or run: claws doctor"
            )

    return OpenAICompatProvider(
        model=config.model,
        api_key=api_key,
        base_url=base_url,
    )
