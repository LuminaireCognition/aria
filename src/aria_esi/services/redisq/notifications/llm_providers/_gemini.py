"""
Google Gemini LLM Provider.

Adapter for the Google Gemini API.
"""

from __future__ import annotations

import asyncio
from typing import Any

from ._protocol import LLMResponse


class GeminiProvider:
    """LLM provider using Google's Gemini API."""

    def __init__(self, api_key: str) -> None:
        try:
            from google import genai  # noqa: F401
        except ImportError:
            raise RuntimeError(
                "gemini provider requires 'google-genai' package. Run: uv sync --extra gemini"
            ) from None

        self._client: Any = genai.Client(api_key=api_key)

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        max_tokens: int,
        timeout_seconds: float,
    ) -> LLMResponse:
        """Generate a response using the Gemini API."""
        response = await asyncio.wait_for(
            self._client.aio.models.generate_content(
                model=model,
                contents=user_prompt,
                config={
                    "system_instruction": system_prompt,
                    "max_output_tokens": max_tokens,
                },
            ),
            timeout=timeout_seconds,
        )

        text = response.text.strip() if response.text else ""
        usage = response.usage_metadata
        return LLMResponse(
            text=text,
            input_tokens=getattr(usage, "prompt_token_count", 500),
            output_tokens=getattr(usage, "candidates_token_count", 50),
        )

    async def close(self) -> None:
        """Close the Gemini client."""
        self._client = None
