"""
OpenAI LLM Provider.

Adapter for the OpenAI Chat Completions API.
"""

from __future__ import annotations

import asyncio
from typing import Any

from ._protocol import LLMResponse


class OpenAIProvider:
    """LLM provider using OpenAI's Chat Completions API."""

    def __init__(self, api_key: str) -> None:
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise RuntimeError(
                "openai provider requires 'openai' package. Run: uv sync --extra openai"
            ) from None

        self._client: Any = AsyncOpenAI(api_key=api_key)

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        max_tokens: int,
        timeout_seconds: float,
    ) -> LLMResponse:
        """Generate a response using the OpenAI API."""
        response = await asyncio.wait_for(
            self._client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            ),
            timeout=timeout_seconds,
        )

        text = response.choices[0].message.content.strip() if response.choices else ""
        usage = response.usage
        return LLMResponse(
            text=text,
            input_tokens=getattr(usage, "prompt_tokens", 500),
            output_tokens=getattr(usage, "completion_tokens", 50),
        )

    async def close(self) -> None:
        """Close the OpenAI client."""
        if self._client is not None:
            await self._client.close()
            self._client = None
