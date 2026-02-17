"""
LLM Provider Protocol.

Defines the interface that all LLM provider adapters must implement.
"""

from __future__ import annotations

from typing import NamedTuple, Protocol


class LLMResponse(NamedTuple):
    """Response from an LLM provider."""

    text: str
    input_tokens: int
    output_tokens: int


class LLMProvider(Protocol):
    """Protocol for LLM provider adapters."""

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        max_tokens: int,
        timeout_seconds: float,
    ) -> LLMResponse: ...

    async def close(self) -> None: ...
