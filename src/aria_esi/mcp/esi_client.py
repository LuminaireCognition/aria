"""
Singleton accessor for AsyncESIClient in MCP context.

Provides a shared AsyncESIClient instance for MCP tools, enabling:
- True async I/O without run_in_executor
- Shared rate limit state across all MCP requests
- Proper connection pooling via httpx.AsyncClient
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.async_client import AsyncESIClient

_client: AsyncESIClient | None = None
_lock = asyncio.Lock()


async def get_async_esi_client() -> AsyncESIClient:
    """
    Get or create the async ESI client singleton.

    The client is lazily initialized on first call and shared across
    all MCP tool invocations. This enables:
    - Connection pooling via httpx.AsyncClient
    - Shared rate limit tracking
    - True async I/O (no thread pool)

    Returns:
        Initialized AsyncESIClient ready for requests
    """
    global _client
    if _client is None:
        async with _lock:
            # Double-check after acquiring lock
            if _client is None:
                from ..core.async_client import AsyncESIClient

                _client = AsyncESIClient()
                await _client.__aenter__()
    return _client


async def close_async_esi_client() -> None:
    """
    Close the singleton client.

    Should be called during MCP server shutdown to cleanly close
    the httpx.AsyncClient connection pool.
    """
    global _client
    if _client is not None:
        await _client.__aexit__(None, None, None)
        _client = None


def reset_async_esi_client() -> None:
    """
    Reset singleton for testing.

    This is a synchronous reset that simply clears the reference.
    Use close_async_esi_client() for proper cleanup in production.
    """
    global _client
    _client = None
