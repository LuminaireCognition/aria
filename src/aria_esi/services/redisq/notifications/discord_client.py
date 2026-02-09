"""
Discord Webhook HTTP Client.

Handles sending messages to Discord with retry logic and rate limit handling.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

from ....core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SendResult:
    """Result of a webhook send attempt."""

    success: bool
    status_code: int | None = None
    error: str | None = None
    retry_after: float | None = None

    @property
    def is_rate_limited(self) -> bool:
        """Check if this result indicates rate limiting."""
        return self.status_code == 429


@dataclass
class DiscordClient:
    """
    HTTP client for Discord webhook API.

    Features:
    - Retry on 5xx errors with exponential backoff
    - Rate limit handling (429 with Retry-After)
    - No retry on 401/403 (invalid webhook URL)
    """

    webhook_url: str
    max_retries: int = 3
    base_delay: float = 1.0  # seconds

    # Metrics
    _total_sent: int = 0
    _total_failed: int = 0
    _last_success: datetime | None = None
    _last_failure: datetime | None = None
    _consecutive_failures: int = 0

    # HTTP client
    _client: httpx.AsyncClient | None = field(default=None, repr=False)

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def send(self, payload: dict[str, Any]) -> SendResult:
        """
        Send a message to the Discord webhook.

        Implements retry logic:
        - 5xx: Retry with exponential backoff (1s, 2s, 4s)
        - 429: Respect Retry-After header
        - 401/403: No retry (invalid URL)
        - Other 4xx: No retry

        Args:
            payload: Discord webhook payload (embed or content)

        Returns:
            SendResult with success status and details
        """
        client = await self._get_client()

        for attempt in range(self.max_retries):
            try:
                response = await client.post(self.webhook_url, json=payload)

                if response.status_code == 204:
                    # Success - Discord returns 204 No Content
                    self._total_sent += 1
                    self._last_success = datetime.now()
                    self._consecutive_failures = 0
                    return SendResult(success=True, status_code=204)

                if response.status_code == 429:
                    # Rate limited - return with retry_after for caller to handle
                    retry_after = float(response.headers.get("Retry-After", "5"))
                    logger.warning(
                        "Discord rate limited, retry after %.1fs",
                        retry_after,
                    )
                    self._record_failure()
                    return SendResult(
                        success=False,
                        status_code=429,
                        retry_after=retry_after,
                        error="Rate limited",
                    )

                if response.status_code in (401, 403):
                    # Invalid webhook URL - don't retry
                    self._record_failure()
                    error_msg = f"Invalid webhook URL (HTTP {response.status_code})"
                    logger.warning(error_msg)
                    return SendResult(
                        success=False,
                        status_code=response.status_code,
                        error=error_msg,
                    )

                if response.status_code >= 500:
                    # Server error - retry with backoff
                    if attempt < self.max_retries - 1:
                        delay = self.base_delay * (2**attempt)
                        logger.warning(
                            "Discord server error %d, retrying in %.1fs",
                            response.status_code,
                            delay,
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        self._record_failure()
                        return SendResult(
                            success=False,
                            status_code=response.status_code,
                            error=f"Server error after {self.max_retries} retries",
                        )

                # Other 4xx - don't retry
                self._record_failure()
                return SendResult(
                    success=False,
                    status_code=response.status_code,
                    error=f"HTTP {response.status_code}: {response.text[:200]}",
                )

            except httpx.TimeoutException:
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2**attempt)
                    logger.warning("Discord timeout, retrying in %.1fs", delay)
                    await asyncio.sleep(delay)
                    continue
                else:
                    self._record_failure()
                    return SendResult(
                        success=False,
                        error="Timeout after retries",
                    )

            except httpx.RequestError as e:
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2**attempt)
                    logger.warning("Discord request error: %s, retrying", e)
                    await asyncio.sleep(delay)
                    continue
                else:
                    self._record_failure()
                    return SendResult(
                        success=False,
                        error=f"Request error: {e}",
                    )

        # Should not reach here, but handle gracefully
        self._record_failure()
        return SendResult(success=False, error="Unknown error")

    def _record_failure(self) -> None:
        """Record a failed send attempt."""
        self._total_failed += 1
        self._last_failure = datetime.now()
        self._consecutive_failures += 1

    @property
    def success_rate(self) -> float:
        """Calculate success rate (0.0 to 1.0)."""
        total = self._total_sent + self._total_failed
        if total == 0:
            return 1.0
        return self._total_sent / total

    @property
    def is_healthy(self) -> bool:
        """Check if client is healthy (not in extended failure state)."""
        # Healthy if no failures or last success is after last failure
        if self._consecutive_failures >= 10:
            return False
        if self._last_failure is None:
            return True
        if self._last_success is None:
            return self._consecutive_failures < 3
        return self._last_success > self._last_failure

    def get_metrics(self) -> dict[str, Any]:
        """Get client metrics for status reporting."""
        return {
            "total_sent": self._total_sent,
            "total_failed": self._total_failed,
            "success_rate": round(self.success_rate, 3),
            "consecutive_failures": self._consecutive_failures,
            "last_success": self._last_success.isoformat() if self._last_success else None,
            "last_failure": self._last_failure.isoformat() if self._last_failure else None,
            "is_healthy": self.is_healthy,
        }
