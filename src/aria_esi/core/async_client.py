"""
ARIA ESI Async HTTP Client

Async HTTP client for EVE Online ESI API using httpx.
Designed for use in MCP handlers and other async contexts.

Uses httpx.AsyncClient for true async I/O (no run_in_executor).
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING, Any, Optional, Union

import httpx

from .constants import ESI_BASE_URL, ESI_DATASOURCE
from .logging import get_logger
from .retry import (
    RETRYABLE_STATUS_CODES,
    RetryableESIError,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

logger = get_logger(__name__)


# =============================================================================
# Response Types
# =============================================================================


@dataclass
class AsyncESIResponse:
    """
    ESI response with headers for conditional requests.

    Used by get_with_headers() to capture HTTP response headers
    like Last-Modified, Expires, and X-Pages for caching and pagination.
    """

    data: dict | list | None
    """Parsed JSON response body."""

    headers: dict[str, str] = field(default_factory=dict)
    """HTTP response headers (case-insensitive keys normalized to title case)."""

    status_code: int = 200
    """HTTP status code."""

    @property
    def last_modified_timestamp(self) -> int | None:
        """Parse Last-Modified header to Unix timestamp."""
        header = self.headers.get("Last-Modified") or self.headers.get("last-modified")
        if not header:
            return None
        try:
            dt = parsedate_to_datetime(header)
            return int(dt.timestamp())
        except (ValueError, TypeError):
            return None

    @property
    def expires_timestamp(self) -> int | None:
        """Parse Expires header to Unix timestamp."""
        header = self.headers.get("Expires") or self.headers.get("expires")
        if not header:
            return None
        try:
            dt = parsedate_to_datetime(header)
            return int(dt.timestamp())
        except (ValueError, TypeError):
            return None

    @property
    def x_pages(self) -> int | None:
        """Parse X-Pages header for pagination."""
        header = self.headers.get("X-Pages") or self.headers.get("x-pages")
        if not header:
            return None
        try:
            return int(header)
        except (ValueError, TypeError):
            return None

    @property
    def is_not_modified(self) -> bool:
        """Check if response was 304 Not Modified."""
        return self.status_code == 304


# =============================================================================
# Exceptions
# =============================================================================


class AsyncESIError(Exception):
    """Exception raised for async ESI API errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response: Optional[dict[str, Any]] = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.response = response or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Convert error to JSON-serializable dict."""
        result: dict[str, Any] = {"error": "esi_error", "message": self.message}
        if self.status_code:
            result["status_code"] = self.status_code
        return result


# =============================================================================
# Async Retry Decorator
# =============================================================================


def esi_retry_async(
    max_attempts: int = 5,
    min_wait: float = 0.5,
    max_wait: float = 30.0,
) -> Any:
    """
    Async retry decorator for ESI requests with exponential backoff.

    Retries on:
    - 429 Too Many Requests (respects Retry-After header)
    - 502/503/504 Gateway errors
    - Network errors (httpx.RequestError)

    Args:
        max_attempts: Maximum retry attempts (default: 5)
        min_wait: Minimum wait between retries in seconds (default: 0.5)
        max_wait: Maximum wait between retries in seconds (default: 30)

    Returns:
        Decorated async function with retry logic
    """
    try:
        from tenacity import (
            retry,
            retry_if_exception_type,
            stop_after_attempt,
            wait_exponential,
        )

        return retry(
            retry=retry_if_exception_type((RetryableESIError, httpx.RequestError)),
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
            reraise=True,
        )
    except ImportError:
        # Fallback: no-op decorator if tenacity not installed
        def passthrough(func: Any) -> Any:
            return func

        return passthrough


# =============================================================================
# Async Client
# =============================================================================


class AsyncESIClient:
    """
    Async HTTP client for ESI API requests.

    Uses httpx.AsyncClient for true async I/O. Must be used as an
    async context manager to ensure proper connection pooling.

    Usage:
        async with AsyncESIClient() as client:
            systems = await client.get("/universe/systems/30005325/")

        # Or with authentication:
        async with AsyncESIClient(token="your_access_token") as client:
            location = await client.get("/characters/12345/location/", auth=True)
    """

    def __init__(
        self,
        token: Optional[str] = None,
        timeout: float = 30.0,
        enable_retry: bool = True,
    ) -> None:
        """
        Initialize async ESI client.

        Args:
            token: OAuth access token for authenticated requests
            timeout: Request timeout in seconds (default: 30)
            enable_retry: Whether to enable retry logic (default: True)
        """
        self.token: Optional[str] = token
        self.timeout: float = timeout
        self.base_url: str = ESI_BASE_URL
        self.datasource: str = ESI_DATASOURCE
        self.enable_retry: bool = enable_retry
        self._client: Optional[httpx.AsyncClient] = None

        # Rate limiting state
        self._error_limit_remain: int = 100
        self._error_limit_reset: float = 0
        self._rate_limit_backoff_threshold: int = 20
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> AsyncESIClient:
        """Enter async context and create httpx client."""
        # Check if http2 is available
        try:
            import h2  # noqa: F401

            http2_available = True
        except ImportError:
            http2_available = False

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout),
            headers={"Accept": "application/json"},
            http2=http2_available,  # Enable HTTP/2 if available
        )
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        """Exit async context and close httpx client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _build_url(self, endpoint: str, params: Optional[dict[str, Any]] = None) -> str:
        """
        Build URL with datasource parameter.

        Args:
            endpoint: API endpoint path (e.g., "/characters/12345/location/")
            params: Additional query parameters

        Returns:
            URL path with query string (base_url is set on client)
        """
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint

        query_params = {"datasource": self.datasource}
        if params:
            query_params.update(params)

        query_string = "&".join(f"{k}={v}" for k, v in query_params.items())
        return f"{endpoint}?{query_string}"

    def _update_rate_limits(self, headers: Mapping[str, str]) -> None:
        """Update rate limit tracking from ESI response headers."""
        if "x-esi-error-limit-remain" in headers:
            try:
                self._error_limit_remain = int(headers["x-esi-error-limit-remain"])
            except (ValueError, TypeError):
                pass

        if "x-esi-error-limit-reset" in headers:
            try:
                import time

                reset_seconds = int(headers["x-esi-error-limit-reset"])
                self._error_limit_reset = time.time() + reset_seconds
            except (ValueError, TypeError):
                pass

    async def _check_rate_limit(self) -> None:
        """Check rate limit status and back off if approaching limit."""
        import time

        async with self._lock:
            if time.time() > self._error_limit_reset:
                self._error_limit_remain = 100

            if self._error_limit_remain < self._rate_limit_backoff_threshold:
                wait_time = max(0, self._error_limit_reset - time.time())
                wait_time = min(wait_time, 5.0)
                if wait_time > 0:
                    await asyncio.sleep(wait_time)

    async def get(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        auth: bool = False,
    ) -> Union[dict, list, int, float, None]:
        """
        Make GET request to ESI API.

        Args:
            endpoint: API endpoint path
            params: Optional query parameters
            auth: Whether to include authentication header

        Returns:
            Parsed JSON response

        Raises:
            AsyncESIError: On HTTP errors or request failures
        """
        if self.enable_retry:
            return await self._get_with_retry(endpoint, params, auth)
        else:
            return await self._get_once(endpoint, params, auth)

    async def _get_once(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        auth: bool = False,
    ) -> Union[dict, list, int, float, None]:
        """Execute GET request without retry."""
        if not self._client:
            raise AsyncESIError("Client not initialized. Use 'async with' context manager.")

        await self._check_rate_limit()

        url = self._build_url(endpoint, params)
        headers: dict[str, str] = {}

        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        try:
            response = await self._client.get(url, headers=headers if headers else None)
            self._update_rate_limits(response.headers)

            if response.status_code == 304:
                return None

            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            self._update_rate_limits(e.response.headers)
            try:
                error_json = e.response.json()
                message = error_json.get("error", str(e))
            except json.JSONDecodeError:
                message = e.response.text or str(e)

            # Convert to retryable error if applicable
            if e.response.status_code in RETRYABLE_STATUS_CODES:
                retry_after = e.response.headers.get("retry-after")
                raise RetryableESIError(
                    message,
                    status_code=e.response.status_code,
                    retry_after=int(retry_after) if retry_after else None,
                )

            raise AsyncESIError(message, status_code=e.response.status_code)

        except httpx.RequestError as e:
            raise AsyncESIError(f"Network error: {e}")

    @esi_retry_async()
    async def _get_with_retry(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        auth: bool = False,
    ) -> Union[dict, list, int, float, None]:
        """Execute GET request with retry logic."""
        return await self._get_once(endpoint, params, auth)

    async def get_safe(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        auth: bool = False,
    ) -> Union[dict, list, int, float, None]:
        """
        Make GET request, returning None on 404 errors.

        Useful for lookups where missing data is expected.

        Args:
            endpoint: API endpoint path
            params: Optional query parameters
            auth: Whether to include authentication header

        Returns:
            Parsed JSON response, or None if 404/not found
        """
        try:
            return await self.get(endpoint, params, auth)
        except AsyncESIError as e:
            if e.status_code == 404:
                logger.debug(
                    "get_safe swallowed 404 for %s: %s",
                    endpoint,
                    e.message,
                )
                return None
            raise

    async def get_with_headers(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        auth: bool = False,
        if_modified_since: Optional[str] = None,
    ) -> AsyncESIResponse:
        """
        Make GET request and return response with headers.

        Useful for conditional requests (If-Modified-Since) and
        pagination (X-Pages header).

        Args:
            endpoint: API endpoint path
            params: Optional query parameters
            auth: Whether to include authentication header
            if_modified_since: Value for If-Modified-Since header

        Returns:
            AsyncESIResponse with data and headers
        """
        if not self._client:
            raise AsyncESIError("Client not initialized. Use 'async with' context manager.")

        await self._check_rate_limit()

        url = self._build_url(endpoint, params)
        headers: dict[str, str] = {}

        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        if if_modified_since:
            headers["If-Modified-Since"] = if_modified_since

        try:
            response = await self._client.get(url, headers=headers if headers else None)
            self._update_rate_limits(response.headers)

            # Handle 304 Not Modified
            if response.status_code == 304:
                return AsyncESIResponse(
                    data=None,
                    headers=dict(response.headers),
                    status_code=304,
                )

            response.raise_for_status()

            return AsyncESIResponse(
                data=response.json(),
                headers=dict(response.headers),
                status_code=response.status_code,
            )

        except httpx.HTTPStatusError as e:
            self._update_rate_limits(e.response.headers)
            try:
                error_json = e.response.json()
                message = error_json.get("error", str(e))
            except json.JSONDecodeError:
                message = e.response.text or str(e)
            raise AsyncESIError(message, status_code=e.response.status_code)

        except httpx.RequestError as e:
            raise AsyncESIError(f"Network error: {e}")

    async def post(
        self,
        endpoint: str,
        data: Any,
        auth: bool = False,
    ) -> Union[dict, list, int, float, None]:
        """
        Make POST request to ESI API.

        Args:
            endpoint: API endpoint path
            data: Request body (will be JSON encoded)
            auth: Whether to include authentication header

        Returns:
            Parsed JSON response

        Raises:
            AsyncESIError: On HTTP errors or request failures
        """
        if not self._client:
            raise AsyncESIError("Client not initialized. Use 'async with' context manager.")

        await self._check_rate_limit()

        url = self._build_url(endpoint)
        headers: dict[str, str] = {"Content-Type": "application/json"}

        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        try:
            response = await self._client.post(url, json=data, headers=headers)
            self._update_rate_limits(response.headers)
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            self._update_rate_limits(e.response.headers)
            try:
                error_json = e.response.json()
                message = error_json.get("error", str(e))
            except json.JSONDecodeError:
                message = e.response.text or str(e)
            raise AsyncESIError(message, status_code=e.response.status_code)

        except httpx.RequestError as e:
            raise AsyncESIError(f"Network error: {e}")


# =============================================================================
# Convenience Functions
# =============================================================================


async def create_async_client(
    token: Optional[str] = None,
    timeout: float = 30.0,
) -> AsyncESIClient:
    """
    Create and enter an async ESI client context.

    This is a convenience function for when you need the client
    outside of an async with block. Remember to call aclose().

    Args:
        token: OAuth access token for authenticated requests
        timeout: Request timeout in seconds

    Returns:
        Initialized AsyncESIClient (must call aclose() when done)
    """
    client = AsyncESIClient(token=token, timeout=timeout)
    await client.__aenter__()
    return client
