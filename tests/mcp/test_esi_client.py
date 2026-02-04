"""
Tests for AsyncESIClient singleton module.

Verifies:
- Singleton creation and reuse
- Concurrent access (lock works)
- Reset function for test isolation
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from aria_esi.mcp.esi_client import (
    close_async_esi_client,
    get_async_esi_client,
    reset_async_esi_client,
)


class TestAsyncESIClientSingleton:
    """Test singleton behavior of get_async_esi_client."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton before and after each test."""
        reset_async_esi_client()
        yield
        reset_async_esi_client()

    @pytest.mark.asyncio
    async def test_creates_client_on_first_call(self):
        """First call to get_async_esi_client should create a new client."""
        # Patch at the source module where the class is defined
        with patch("aria_esi.core.async_client.AsyncESIClient") as mock_class:
            mock_instance = AsyncMock()
            mock_class.return_value = mock_instance

            client = await get_async_esi_client()

            mock_class.assert_called_once()
            mock_instance.__aenter__.assert_called_once()
            assert client is mock_instance

    @pytest.mark.asyncio
    async def test_returns_same_client_on_subsequent_calls(self):
        """Subsequent calls should return the same client instance."""
        with patch("aria_esi.core.async_client.AsyncESIClient") as mock_class:
            mock_instance = AsyncMock()
            mock_class.return_value = mock_instance

            client1 = await get_async_esi_client()
            client2 = await get_async_esi_client()
            client3 = await get_async_esi_client()

            # Should only create one instance
            mock_class.assert_called_once()
            assert client1 is client2
            assert client2 is client3

    @pytest.mark.asyncio
    async def test_concurrent_access_creates_single_client(self):
        """Concurrent calls should still only create one client."""
        with patch("aria_esi.core.async_client.AsyncESIClient") as mock_class:
            mock_instance = AsyncMock()
            mock_class.return_value = mock_instance

            # Add a small delay to simulate client initialization
            async def slow_aenter(self_arg=None):
                await asyncio.sleep(0.01)
                return mock_instance

            mock_instance.__aenter__ = slow_aenter

            # Make concurrent calls
            clients = await asyncio.gather(
                get_async_esi_client(),
                get_async_esi_client(),
                get_async_esi_client(),
                get_async_esi_client(),
                get_async_esi_client(),
            )

            # Should only create one instance despite concurrent access
            mock_class.assert_called_once()
            assert all(c is clients[0] for c in clients)

    @pytest.mark.asyncio
    async def test_close_cleans_up_client(self):
        """close_async_esi_client should properly clean up."""
        with patch("aria_esi.core.async_client.AsyncESIClient") as mock_class:
            mock_instance = AsyncMock()
            mock_class.return_value = mock_instance

            # Create client
            await get_async_esi_client()

            # Close it
            await close_async_esi_client()

            mock_instance.__aexit__.assert_called_once_with(None, None, None)

    @pytest.mark.asyncio
    async def test_close_allows_recreation(self):
        """After close, a new client can be created."""
        with patch("aria_esi.core.async_client.AsyncESIClient") as mock_class:
            mock_instance1 = AsyncMock()
            mock_instance2 = AsyncMock()
            mock_class.side_effect = [mock_instance1, mock_instance2]

            # Create first client
            client1 = await get_async_esi_client()

            # Close it
            await close_async_esi_client()

            # Create new client
            client2 = await get_async_esi_client()

            assert mock_class.call_count == 2
            assert client1 is mock_instance1
            assert client2 is mock_instance2

    @pytest.mark.asyncio
    async def test_reset_clears_singleton(self):
        """reset_async_esi_client should clear the singleton reference."""
        with patch("aria_esi.core.async_client.AsyncESIClient") as mock_class:
            mock_instance1 = AsyncMock()
            mock_instance2 = AsyncMock()
            mock_class.side_effect = [mock_instance1, mock_instance2]

            # Create first client
            client1 = await get_async_esi_client()

            # Reset (synchronous, doesn't close properly)
            reset_async_esi_client()

            # Create new client
            client2 = await get_async_esi_client()

            assert mock_class.call_count == 2
            assert client1 is mock_instance1
            assert client2 is mock_instance2

    @pytest.mark.asyncio
    async def test_close_when_no_client_is_noop(self):
        """close_async_esi_client should be safe when no client exists."""
        # Should not raise
        await close_async_esi_client()


class TestAsyncESIClientIntegration:
    """Integration tests with real AsyncESIClient (no external calls)."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton before and after each test."""
        reset_async_esi_client()
        yield
        reset_async_esi_client()

    @pytest.mark.asyncio
    async def test_real_client_creation(self):
        """Test that real AsyncESIClient can be created via singleton."""
        # This creates a real client but doesn't make any network calls
        client = await get_async_esi_client()

        # Verify it's an AsyncESIClient instance
        from aria_esi.core.async_client import AsyncESIClient

        assert isinstance(client, AsyncESIClient)

        # Verify it has an active httpx client
        assert client._client is not None

        # Clean up
        await close_async_esi_client()

    @pytest.mark.asyncio
    async def test_real_client_is_reused(self):
        """Test that the same real client instance is reused."""
        client1 = await get_async_esi_client()
        client2 = await get_async_esi_client()

        assert client1 is client2

        # Clean up
        await close_async_esi_client()
