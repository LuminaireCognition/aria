"""
Tests for webhook queue.
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from aria_esi.services.redisq.notifications.discord_client import DiscordClient, SendResult
from aria_esi.services.redisq.notifications.queue import QueuedMessage, WebhookQueue


@pytest.fixture
def mock_client():
    """Create a mock Discord client."""
    client = MagicMock(spec=DiscordClient)
    client.send = AsyncMock(return_value=SendResult(success=True, status_code=204))
    client.success_rate = 1.0
    client.is_healthy = True
    client._last_success = None
    return client


class TestQueuedMessage:
    """Tests for QueuedMessage."""

    def test_creation(self):
        """Test message creation."""
        msg = QueuedMessage(
            payload={"content": "test"},
            queued_at=time.time(),
            kill_id=12345678,
            trigger_type="watchlist_activity",
        )

        assert msg.payload == {"content": "test"}
        assert msg.kill_id == 12345678
        assert msg.trigger_type == "watchlist_activity"


class TestWebhookQueue:
    """Tests for WebhookQueue."""

    def test_enqueue(self, mock_client):
        """Test enqueueing messages."""
        queue = WebhookQueue(client=mock_client)

        result = queue.enqueue(
            payload={"content": "test"},
            kill_id=12345678,
            trigger_type="watchlist_activity",
        )

        assert result is True
        assert queue.depth == 1

    def test_max_size(self, mock_client):
        """Test queue respects max size."""
        queue = WebhookQueue(client=mock_client, max_size=3)

        # Fill queue
        for i in range(5):
            queue.enqueue(payload={"id": i}, kill_id=i)

        # Should be capped at max_size
        assert queue.depth == 3

    @pytest.mark.asyncio
    async def test_process_queue_success(self, mock_client):
        """Test successful queue processing."""
        queue = WebhookQueue(client=mock_client)

        # Add messages
        queue.enqueue(payload={"content": "test1"}, kill_id=1)
        queue.enqueue(payload={"content": "test2"}, kill_id=2)

        sent = await queue.process_queue()

        assert sent == 2
        assert queue.depth == 0
        assert mock_client.send.call_count == 2

    @pytest.mark.asyncio
    async def test_process_queue_skips_stale(self, mock_client):
        """Test stale messages are skipped."""
        queue = WebhookQueue(client=mock_client)

        # Add a stale message (>5 minutes old)
        stale_msg = QueuedMessage(
            payload={"content": "stale"},
            queued_at=time.time() - 400,  # 6+ minutes old
            kill_id=1,
        )
        queue._queue.append(stale_msg)

        # Add a fresh message
        queue.enqueue(payload={"content": "fresh"}, kill_id=2)

        sent = await queue.process_queue()

        assert sent == 1  # Only fresh message sent
        assert mock_client.send.call_count == 1

    @pytest.mark.asyncio
    async def test_paused_queue_skips_processing(self, mock_client):
        """Test paused queue doesn't process."""
        queue = WebhookQueue(client=mock_client)
        queue._is_paused = True
        queue._pause_start = time.time()

        queue.enqueue(payload={"content": "test"}, kill_id=1)

        sent = await queue.process_queue()

        assert sent == 0
        assert mock_client.send.call_count == 0

    def test_manual_resume(self, mock_client):
        """Test manual queue resume."""
        queue = WebhookQueue(client=mock_client)
        queue._is_paused = True
        queue._pause_start = time.time()

        assert queue.is_paused is True

        result = queue.resume()

        assert result is True
        assert queue.is_paused is False

    def test_resume_not_paused(self, mock_client):
        """Resume returns False if not paused."""
        queue = WebhookQueue(client=mock_client)

        result = queue.resume()

        assert result is False

    def test_get_health(self, mock_client):
        """Test health status reporting."""
        queue = WebhookQueue(client=mock_client)
        queue.enqueue(payload={"content": "test"}, kill_id=1)

        health = queue.get_health()

        assert health.is_healthy is True
        assert health.is_paused is False
        assert health.queue_depth == 1
        assert health.success_rate == 1.0


class TestCircuitBreaker:
    """Tests for circuit breaker behavior."""

    def test_should_pause_after_failures(self, mock_client):
        """Circuit breaker triggers after consecutive failures over time."""
        queue = WebhookQueue(client=mock_client)

        # Simulate failure start time >5 minutes ago
        queue._consecutive_failures = 3
        queue._failure_start = time.time() - 400

        assert queue._should_pause() is True

    def test_should_not_pause_quick_failures(self, mock_client):
        """Circuit breaker doesn't trigger for quick consecutive failures."""
        queue = WebhookQueue(client=mock_client)

        # Failures just started
        queue._consecutive_failures = 3
        queue._failure_start = time.time() - 60  # Just 1 minute

        assert queue._should_pause() is False

    def test_should_not_pause_few_failures(self, mock_client):
        """Circuit breaker doesn't trigger for few failures."""
        queue = WebhookQueue(client=mock_client)

        queue._consecutive_failures = 2
        queue._failure_start = time.time() - 400

        assert queue._should_pause() is False
