"""
Singleton accessors for AsyncESIClient in MCP context.

Provides shared AsyncESIClient instances for MCP tools, enabling:
- True async I/O without run_in_executor
- Shared rate limit state across all MCP requests
- Proper connection pooling via httpx.AsyncClient

Two singletons:
- Unauthenticated client: For public ESI endpoints (market, universe, SDE)
- Authenticated client: For character-specific endpoints (mail, mining, wallet)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.async_client import AsyncESIClient
    from ..core.auth import Credentials

logger = logging.getLogger(__name__)

# =============================================================================
# Unauthenticated Client (existing)
# =============================================================================

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


# =============================================================================
# Authenticated Client
# =============================================================================

# Token refresh buffer: refresh if token expires within this many seconds
_TOKEN_REFRESH_BUFFER_SECONDS = 300  # 5 minutes


@dataclass
class AuthenticatedESIContext:
    """Container for authenticated ESI client with credential metadata."""

    client: AsyncESIClient
    creds: Credentials
    character_id: int
    token_expiry_ts: float = 0.0  # Unix timestamp of token expiry


_auth_client: AuthenticatedESIContext | None = None
_auth_lock = asyncio.Lock()


async def get_authenticated_async_esi_client() -> AuthenticatedESIContext:
    """
    Get or create the authenticated async ESI client singleton.

    Lazily resolves credentials and creates an authenticated AsyncESIClient.
    Automatically refreshes the token if it's within 5 minutes of expiry.

    Returns:
        AuthenticatedESIContext with client, credentials, and character_id

    Raises:
        RuntimeError: If no credentials are available
    """
    global _auth_client

    if _auth_client is not None:
        # Check if token needs refresh
        if _auth_client.token_expiry_ts > 0:
            time_remaining = _auth_client.token_expiry_ts - time.time()
            if time_remaining < _TOKEN_REFRESH_BUFFER_SECONDS:
                logger.info("Token expiring in %.0fs, refreshing", time_remaining)
                await _refresh_auth_client()
        return _auth_client

    async with _auth_lock:
        # Double-check after acquiring lock
        if _auth_client is not None:
            return _auth_client

        _auth_client = await _create_auth_client()
        return _auth_client


async def _create_auth_client() -> AuthenticatedESIContext:
    """Create a new authenticated ESI client from resolved credentials."""
    from ..core.async_client import AsyncESIClient
    from ..core.auth import Credentials

    # Resolve credentials in executor (sync file I/O)
    creds = await asyncio.to_thread(Credentials.resolve)
    if creds is None:
        raise RuntimeError(
            "No ESI credentials found. Run 'uv run python .claude/scripts/aria-oauth-setup.py' to configure."
        )

    # Refresh token if needed (runs subprocess)
    await asyncio.to_thread(creds.refresh_if_needed)

    # Parse token expiry
    token_expiry_ts = 0.0
    if creds.token_expiry:
        try:
            from datetime import datetime

            dt = datetime.fromisoformat(creds.token_expiry.replace("Z", "+00:00"))
            token_expiry_ts = dt.timestamp()
        except (ValueError, AttributeError):
            pass

    # Create authenticated client
    client = AsyncESIClient(token=creds.access_token)
    await client.__aenter__()

    return AuthenticatedESIContext(
        client=client,
        creds=creds,
        character_id=creds.character_id,
        token_expiry_ts=token_expiry_ts,
    )


async def _refresh_auth_client() -> None:
    """Refresh the authenticated client's token."""
    global _auth_client

    async with _auth_lock:
        if _auth_client is not None:
            await _auth_client.client.__aexit__(None, None, None)

        _auth_client = await _create_auth_client()


async def close_authenticated_async_esi_client() -> None:
    """Close the authenticated singleton client."""
    global _auth_client
    if _auth_client is not None:
        await _auth_client.client.__aexit__(None, None, None)
        _auth_client = None


def reset_authenticated_async_esi_client() -> None:
    """Reset authenticated singleton for testing."""
    global _auth_client
    _auth_client = None
