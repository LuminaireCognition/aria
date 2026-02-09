"""
Tests for Discord webhook client.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from aria_esi.services.redisq.notifications.discord_client import DiscordClient, SendResult


class TestSendResult:
    """Tests for SendResult."""

    def test_success_result(self):
        """Test successful send result."""
        result = SendResult(success=True, status_code=204)
        assert result.success is True
        assert result.status_code == 204
        assert result.error is None

    def test_failure_result(self):
        """Test failed send result."""
        result = SendResult(success=False, status_code=500, error="Server error")
        assert result.success is False
        assert result.status_code == 500
        assert result.error == "Server error"


class TestDiscordClient:
    """Tests for DiscordClient."""

    def test_initialization(self):
        """Test client initialization."""
        client = DiscordClient(webhook_url="https://discord.com/api/webhooks/123/abc")

        assert client.webhook_url == "https://discord.com/api/webhooks/123/abc"
        assert client.max_retries == 3
        assert client._total_sent == 0
        assert client._total_failed == 0

    def test_success_rate_initial(self):
        """Initial success rate is 1.0."""
        client = DiscordClient(webhook_url="https://example.com/webhook")
        assert client.success_rate == 1.0

    def test_success_rate_after_sends(self):
        """Success rate calculated correctly."""
        client = DiscordClient(webhook_url="https://example.com/webhook")
        client._total_sent = 8
        client._total_failed = 2

        assert client.success_rate == 0.8

    def test_is_healthy_initial(self):
        """Client starts healthy."""
        client = DiscordClient(webhook_url="https://example.com/webhook")
        assert client.is_healthy is True

    def test_is_healthy_after_failures(self):
        """Client unhealthy after many failures."""
        client = DiscordClient(webhook_url="https://example.com/webhook")
        client._consecutive_failures = 10

        assert client.is_healthy is False

    def test_get_metrics(self):
        """Test metrics reporting."""
        client = DiscordClient(webhook_url="https://example.com/webhook")
        client._total_sent = 5
        client._total_failed = 1

        metrics = client.get_metrics()

        assert metrics["total_sent"] == 5
        assert metrics["total_failed"] == 1
        assert metrics["success_rate"] == pytest.approx(0.833, abs=0.01)
        assert metrics["is_healthy"] is True

    @pytest.mark.asyncio
    async def test_close(self):
        """Test client close."""
        client = DiscordClient(webhook_url="https://example.com/webhook")

        # First get a client so we have something to close
        mock_http_client = AsyncMock()
        mock_http_client.aclose = AsyncMock()
        client._client = mock_http_client

        await client.close()

        mock_http_client.aclose.assert_called_once()
        assert client._client is None

    @pytest.mark.asyncio
    async def test_close_no_client(self):
        """Test close when no client exists."""
        client = DiscordClient(webhook_url="https://example.com/webhook")

        # Should not raise even if _client is None
        await client.close()
        assert client._client is None


class TestDiscordClientSend:
    """Tests for DiscordClient.send method."""

    @pytest.mark.asyncio
    async def test_send_success(self):
        """Test successful send."""
        client = DiscordClient(webhook_url="https://example.com/webhook")

        mock_response = MagicMock()
        mock_response.status_code = 204

        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_response)

        with patch.object(client, "_get_client", return_value=mock_http_client):
            result = await client.send({"content": "test"})

        assert result.success is True
        assert result.status_code == 204
        assert client._total_sent == 1
        assert client._consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_send_invalid_url(self):
        """Test 401/403 does not retry."""
        client = DiscordClient(webhook_url="https://example.com/webhook")

        mock_response = MagicMock()
        mock_response.status_code = 401

        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_response)

        with patch.object(client, "_get_client", return_value=mock_http_client):
            result = await client.send({"content": "test"})

        assert result.success is False
        assert result.status_code == 401
        assert "Invalid webhook URL" in result.error
        # Should only attempt once (no retry)
        assert mock_http_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_send_server_error_retries(self):
        """Test 5xx errors trigger retries."""
        client = DiscordClient(
            webhook_url="https://example.com/webhook",
            max_retries=3,
            base_delay=0.01,  # Fast for testing
        )

        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_response)

        with patch.object(client, "_get_client", return_value=mock_http_client):
            result = await client.send({"content": "test"})

        assert result.success is False
        # Should retry max_retries times
        assert mock_http_client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_send_rate_limit(self):
        """Test 429 returns immediately with rate limit info for caller handling."""
        client = DiscordClient(
            webhook_url="https://example.com/webhook",
            max_retries=3,
            base_delay=0.01,
        )

        # 429 response with Retry-After header
        rate_limited_response = MagicMock()
        rate_limited_response.status_code = 429
        rate_limited_response.headers = {"Retry-After": "30"}

        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=rate_limited_response)

        with patch.object(client, "_get_client", return_value=mock_http_client):
            result = await client.send({"content": "test"})

        # Returns immediately without retrying - caller handles backoff
        assert result.success is False
        assert result.status_code == 429
        assert result.is_rate_limited is True
        assert result.retry_after == 30.0
        # Should NOT retry on 429 - return immediately for caller to handle
        assert mock_http_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_send_timeout_retries(self):
        """Test timeout errors trigger retries."""
        client = DiscordClient(
            webhook_url="https://example.com/webhook",
            max_retries=3,
            base_delay=0.01,
        )

        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        with patch.object(client, "_get_client", return_value=mock_http_client):
            result = await client.send({"content": "test"})

        assert result.success is False
        assert "Timeout" in result.error
        assert mock_http_client.post.call_count == 3
