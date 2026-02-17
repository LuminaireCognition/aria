"""
Anthropic LLM Provider.

Adapter for the Anthropic Claude API.
"""

from __future__ import annotations

import asyncio
from typing import Any

from ._protocol import LLMResponse


class AnthropicProvider:
    """LLM provider using Anthropic's Claude API."""

    def __init__(self, api_key: str) -> None:
        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            raise RuntimeError("anthropic provider requires 'anthropic' package. Run: uv sync")

        self._client: Any = AsyncAnthropic(api_key=api_key)

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        max_tokens: int,
        timeout_seconds: float,
    ) -> LLMResponse:
        """Generate a response using the Anthropic API."""
        response = await asyncio.wait_for(
            self._client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            ),
            timeout=timeout_seconds,
        )

        text = response.content[0].text.strip() if response.content else ""
        return LLMResponse(
            text=text,
            input_tokens=getattr(response.usage, "input_tokens", 500),
            output_tokens=getattr(response.usage, "output_tokens", 50),
        )

    async def close(self) -> None:
        """Close the Anthropic client."""
        self._client = None
