"""
LLM Provider Registry and Factory.

Supports multiple LLM backends for notification commentary generation.
Each provider is lazily imported to avoid requiring all SDK packages.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._protocol import LLMProvider

# Provider defaults: model and settings key field per provider
PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "anthropic": {"model": "claude-sonnet-4-5-20241022", "key_field": "anthropic_api_key"},
    "openai": {"model": "gpt-4o-mini", "key_field": "openai_api_key"},
    "gemini": {"model": "gemini-2.0-flash", "key_field": "gemini_api_key"},
}

# Valid provider names for validation
VALID_PROVIDERS = frozenset(PROVIDER_DEFAULTS.keys())

# Approximate cost per 1K tokens by provider (for budget tracking)
COST_PER_1K_TOKENS: dict[str, dict[str, float]] = {
    "anthropic": {"input": 0.00025, "output": 0.00125},  # Haiku-class
    "openai": {"input": 0.00015, "output": 0.00060},  # GPT-4o-mini
    "gemini": {"input": 0.00010, "output": 0.00040},  # Flash
}


def create_provider(provider_name: str, api_key: str | None = None) -> LLMProvider:
    """
    Create an LLM provider by name.

    Falls back to AriaSettings for API key if not provided explicitly.

    Args:
        provider_name: One of "anthropic", "openai", "gemini"
        api_key: Optional API key (reads from settings if None)

    Returns:
        LLMProvider instance

    Raises:
        ValueError: If provider_name is not recognized
        RuntimeError: If API key is not configured or package not installed
    """
    if provider_name not in PROVIDER_DEFAULTS:
        raise ValueError(
            f"Unknown provider: {provider_name}. "
            f"Valid providers: {', '.join(sorted(PROVIDER_DEFAULTS))}"
        )

    if not api_key:
        from aria_esi.core.config import get_settings

        settings = get_settings()
        key_field = PROVIDER_DEFAULTS[provider_name]["key_field"]
        api_key = getattr(settings, key_field)

    if not api_key:
        key_env_var = PROVIDER_DEFAULTS[provider_name]["key_field"].upper()
        raise RuntimeError(f"{key_env_var} not configured for provider '{provider_name}'")

    if provider_name == "anthropic":
        from ._anthropic import AnthropicProvider

        return AnthropicProvider(api_key)
    elif provider_name == "openai":
        from ._openai import OpenAIProvider

        return OpenAIProvider(api_key)
    elif provider_name == "gemini":
        from ._gemini import GeminiProvider

        return GeminiProvider(api_key)
    else:
        # Should not reach here due to earlier validation
        raise ValueError(f"Unknown provider: {provider_name}")
