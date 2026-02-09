"""
ARIA ESI HTTP Client

Unified HTTP client for EVE Online ESI API requests.
Uses httpx for connection pooling and keep-alive support.

Optional retry support with tenacity: pip install aria[resilient]
"""

import json
import logging
import time
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from typing import Any, Optional, Union

import httpx

from .constants import ESI_BASE_URL, ESI_DATASOURCE
from .retry import (
    RetryableESIError,
    classify_httpx_error,
    esi_retry,
    get_retry_status,
    is_retry_enabled,
)

logger = logging.getLogger(__name__)


@dataclass
class ESIResponse:
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
        # Support both title case and lowercase (httpx uses lowercase)
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
        # Support both title case and lowercase (httpx uses lowercase)
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
        # Support both title case and lowercase (httpx uses lowercase)
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


class ESIError(Exception):
    """Exception raised for ESI API errors."""

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


class ESIClient:
    """
    HTTP client for ESI API requests.

    Usage:
        # Public (unauthenticated) client
        client = ESIClient()
        systems = client.get("/universe/systems/30005325/")

        # Authenticated client
        client = ESIClient(token="your_access_token")
        location = client.get("/characters/12345/location/", auth=True)

        # POST for name resolution
        result = client.post("/universe/ids/", ["Jita", "Amarr"])
    """

    def __init__(
        self, token: Optional[str] = None, timeout: int = 30, enable_retry: bool = True
    ) -> None:
        """
        Initialize ESI client.

        Args:
            token: OAuth access token for authenticated requests
            timeout: Request timeout in seconds (default: 30)
            enable_retry: Whether to enable retry logic (default: True)
                         Requires tenacity: pip install aria[resilient]
        """
        self.token: Optional[str] = token
        self.timeout: int = timeout
        self.base_url: str = ESI_BASE_URL
        self.datasource: str = ESI_DATASOURCE
        self.enable_retry: bool = enable_retry and is_retry_enabled()
        self._retry_status: Optional[dict[str, Any]] = get_retry_status() if enable_retry else None

        # Lazy-initialized httpx client for connection pooling
        self._http_client: Optional[httpx.Client] = None

        # Rate limiting state
        self._error_limit_remain: int = 100  # ESI default
        self._error_limit_reset: float = 0  # Unix timestamp when limit resets
        self._rate_limit_backoff_threshold: int = 20  # Back off when fewer errors remain

    def _get_client(self) -> httpx.Client:
        """Get or create the httpx client (lazy initialization)."""
        if self._http_client is None:
            self._http_client = httpx.Client(
                base_url=self.base_url,
                timeout=httpx.Timeout(float(self.timeout)),
                headers={"Accept": "application/json"},
            )
        return self._http_client

    def close(self) -> None:
        """Close the underlying HTTP client and release resources."""
        if self._http_client is not None:
            self._http_client.close()
            self._http_client = None

    def __enter__(self) -> "ESIClient":
        """Enter context manager."""
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        """Exit context manager and close client."""
        self.close()

    def __del__(self) -> None:
        """Cleanup on garbage collection (opportunistic)."""
        if hasattr(self, "_http_client") and self._http_client is not None:
            try:
                self._http_client.close()
            except Exception:
                pass

    def _build_url(self, endpoint: str, params: Optional[dict[str, Any]] = None) -> str:
        """
        Build full URL with datasource parameter.

        Args:
            endpoint: API endpoint path (e.g., "/characters/12345/location/")
            params: Additional query parameters

        Returns:
            Full URL with query string
        """
        # Ensure endpoint starts with /
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint

        url = f"{self.base_url}{endpoint}"

        # Build query string
        query_params = {"datasource": self.datasource}
        if params:
            query_params.update(params)

        # Append query string
        if "?" in url:
            url += "&"
        else:
            url += "?"

        query_string = "&".join(f"{k}={v}" for k, v in query_params.items())
        return url + query_string

    def _update_rate_limits(self, headers: httpx.Headers) -> None:
        """
        Update rate limit tracking from ESI response headers.

        ESI provides these headers:
        - x-esi-error-limit-remain: Errors remaining before rate limit
        - x-esi-error-limit-reset: Seconds until error count resets

        Args:
            headers: httpx response headers (lowercase keys)
        """
        # httpx uses lowercase header keys
        if "x-esi-error-limit-remain" in headers:
            try:
                self._error_limit_remain = int(headers["x-esi-error-limit-remain"])
            except (ValueError, TypeError):
                pass

        if "x-esi-error-limit-reset" in headers:
            try:
                reset_seconds = int(headers["x-esi-error-limit-reset"])
                self._error_limit_reset = time.time() + reset_seconds
            except (ValueError, TypeError):
                pass

    def _check_rate_limit(self) -> None:
        """
        Check rate limit status and back off if approaching limit.

        If we're approaching the error limit, sleep briefly to avoid
        hitting the hard rate limit (which results in 420 errors).
        """
        # Check if limit has reset
        if time.time() > self._error_limit_reset:
            self._error_limit_remain = 100  # Reset to default

        # Back off if approaching limit
        if self._error_limit_remain < self._rate_limit_backoff_threshold:
            # Calculate how long until reset
            wait_time = max(0, self._error_limit_reset - time.time())
            # Cap at 5 seconds to avoid long waits
            wait_time = min(wait_time, 5.0)
            if wait_time > 0:
                time.sleep(wait_time)

    def _execute_request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        data: Optional[bytes] = None,
    ) -> Union[dict, list, int, float, None]:
        """
        Execute an HTTP request with optional retry logic.

        This is the core request method. When retry is enabled, transient
        failures (429, 503, network errors) are automatically retried with
        exponential backoff.

        Args:
            method: HTTP method (GET or POST)
            url: Full URL with query string
            headers: Request headers
            data: Request body bytes for POST requests

        Returns:
            Parsed JSON response

        Raises:
            ESIError: On HTTP errors or request failures
        """
        if self.enable_retry:
            return self._execute_with_retry(method, url, headers, data)
        else:
            return self._execute_once(method, url, headers, data)

    def _execute_once(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        data: Optional[bytes] = None,
    ) -> Union[dict, list, int, float, None]:
        """Execute request without retry logic."""
        # Check rate limit before request
        self._check_rate_limit()

        client = self._get_client()

        try:
            if method == "GET":
                response = client.get(url, headers=headers)
            else:
                response = client.post(url, headers=headers, content=data)

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
            raise ESIError(message, status_code=e.response.status_code)

        except httpx.RequestError as e:
            raise ESIError(f"Network error: {e}")

        except json.JSONDecodeError as e:
            raise ESIError(f"Invalid JSON response: {e}")

    @esi_retry()
    def _execute_with_retry(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        data: Optional[bytes] = None,
    ) -> Union[dict, list, int, float, None]:
        """
        Execute request with retry logic.

        Decorated with @esi_retry() to automatically retry on:
        - 429 Too Many Requests (with Retry-After support)
        - 503 Service Unavailable
        - 502 Bad Gateway
        - 504 Gateway Timeout
        - Network errors (httpx.RequestError)
        """
        # Check rate limit before request
        self._check_rate_limit()

        client = self._get_client()

        try:
            if method == "GET":
                response = client.get(url, headers=headers)
            else:
                response = client.post(url, headers=headers, content=data)

            self._update_rate_limits(response.headers)
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            self._update_rate_limits(e.response.headers)

            # Classify the error for retry logic
            classified = classify_httpx_error(e)
            if isinstance(classified, RetryableESIError):
                raise classified  # Will trigger retry
            else:
                # Non-retryable, convert to ESIError
                raise ESIError(classified.message, status_code=classified.status_code)

        except httpx.RequestError:
            # Network errors are retryable
            raise  # Let retry decorator handle it

        except json.JSONDecodeError as e:
            raise ESIError(f"Invalid JSON response: {e}")

    def get(
        self, endpoint: str, auth: bool = False, params: Optional[dict[str, Any]] = None
    ) -> Union[dict[str, Any], list[Any], int, float, None]:
        """
        Make GET request to ESI.

        When retry is enabled, transient failures (429, 503, network errors)
        are automatically retried with exponential backoff.

        Args:
            endpoint: API endpoint path
            auth: Whether to include authorization header
            params: Additional query parameters

        Returns:
            Parsed JSON response (dict, list, or primitive)

        Raises:
            ESIError: On HTTP errors or request failures
        """
        url = self._build_url(endpoint, params)
        headers: dict[str, str] = {}

        if auth:
            if not self.token:
                raise ESIError("Authentication required but no token provided")
            headers["Authorization"] = f"Bearer {self.token}"

        try:
            return self._execute_request("GET", url, headers)
        except RetryableESIError as e:
            # Convert retry error to ESIError if all retries failed
            raise ESIError(e.message, status_code=e.status_code)
        except httpx.RequestError as e:
            raise ESIError(f"Network error: {e}")

    def get_with_headers(
        self,
        endpoint: str,
        auth: bool = False,
        params: Optional[dict[str, Any]] = None,
        if_modified_since: Optional[str] = None,
    ) -> ESIResponse:
        """
        Make GET request to ESI with header capture.

        Used for conditional requests (If-Modified-Since) and capturing
        response headers like Last-Modified, Expires, and X-Pages.

        Args:
            endpoint: API endpoint path
            auth: Whether to include authorization header
            params: Additional query parameters
            if_modified_since: RFC 2822 timestamp for conditional request

        Returns:
            ESIResponse with data, headers, and status code

        Raises:
            ESIError: On HTTP errors (except 304) or request failures
        """
        url = self._build_url(endpoint, params)
        headers: dict[str, str] = {}

        if auth:
            if not self.token:
                raise ESIError("Authentication required but no token provided")
            headers["Authorization"] = f"Bearer {self.token}"

        if if_modified_since:
            headers["If-Modified-Since"] = if_modified_since

        # Check rate limit before request
        self._check_rate_limit()

        client = self._get_client()

        try:
            response = client.get(url, headers=headers if headers else None)
            self._update_rate_limits(response.headers)

            # Handle 304 Not Modified
            if response.status_code == 304:
                return ESIResponse(
                    data=None,
                    headers=dict(response.headers),
                    status_code=304,
                )

            response.raise_for_status()

            return ESIResponse(
                data=response.json(),
                headers=dict(response.headers),
                status_code=response.status_code,
            )

        except httpx.HTTPStatusError as e:
            self._update_rate_limits(e.response.headers)

            # 304 Not Modified is not an error - return empty response with headers
            if e.response.status_code == 304:
                return ESIResponse(
                    data=None,
                    headers=dict(e.response.headers),
                    status_code=304,
                )

            try:
                error_json = e.response.json()
                message = error_json.get("error", str(e))
            except json.JSONDecodeError:
                message = e.response.text or str(e)
            raise ESIError(message, status_code=e.response.status_code)

        except httpx.RequestError as e:
            raise ESIError(f"Network error: {e}")

        except json.JSONDecodeError as e:
            raise ESIError(f"Invalid JSON response: {e}")

    def get_safe(
        self,
        endpoint: str,
        auth: bool = False,
        params: Optional[dict[str, Any]] = None,
        default: Any = None,
    ) -> Union[dict[str, Any], list[Any], int, float, None]:
        """
        Make GET request, returning default on error instead of raising.

        Useful for optional data fetching where errors are acceptable.

        Args:
            endpoint: API endpoint path
            auth: Whether to include authorization header
            params: Additional query parameters
            default: Value to return on error

        Returns:
            Parsed JSON response, or default on error
        """
        try:
            return self.get(endpoint, auth=auth, params=params)
        except ESIError as e:
            logger.debug(
                "get_safe swallowed error for %s: %s (status=%s)",
                endpoint,
                e.message,
                e.status_code,
            )
            return default

    def get_dict(
        self, endpoint: str, auth: bool = False, params: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """
        Make GET request expecting a dict response.

        Type-safe wrapper that narrows the return type to dict.
        Raises ESIError if the response is not a dict.

        Args:
            endpoint: API endpoint path
            auth: Whether to include authorization header
            params: Additional query parameters

        Returns:
            Parsed JSON dict response

        Raises:
            ESIError: On HTTP errors, request failures, or non-dict response
        """
        result = self.get(endpoint, auth=auth, params=params)
        if not isinstance(result, dict):
            raise ESIError(f"Expected dict response from {endpoint}, got {type(result).__name__}")
        return result

    def get_list(
        self, endpoint: str, auth: bool = False, params: Optional[dict[str, Any]] = None
    ) -> list[Any]:
        """
        Make GET request expecting a list response.

        Type-safe wrapper that narrows the return type to list.
        Raises ESIError if the response is not a list.

        Args:
            endpoint: API endpoint path
            auth: Whether to include authorization header
            params: Additional query parameters

        Returns:
            Parsed JSON list response

        Raises:
            ESIError: On HTTP errors, request failures, or non-list response
        """
        result = self.get(endpoint, auth=auth, params=params)
        if not isinstance(result, list):
            raise ESIError(f"Expected list response from {endpoint}, got {type(result).__name__}")
        return result

    def get_dict_safe(
        self,
        endpoint: str,
        auth: bool = False,
        params: Optional[dict[str, Any]] = None,
        default: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Make GET request expecting dict, returning default on error.

        Type-safe wrapper that narrows the return type to dict.
        Returns default on HTTP errors or non-dict response.

        Args:
            endpoint: API endpoint path
            auth: Whether to include authorization header
            params: Additional query parameters
            default: Value to return on error (defaults to empty dict)

        Returns:
            Parsed JSON dict response, or default on error
        """
        if default is None:
            default = {}
        try:
            result = self.get(endpoint, auth=auth, params=params)
            return result if isinstance(result, dict) else default
        except ESIError as e:
            logger.debug(
                "get_dict_safe swallowed error for %s: %s (status=%s)",
                endpoint,
                e.message,
                e.status_code,
            )
            return default

    def get_list_safe(
        self,
        endpoint: str,
        auth: bool = False,
        params: Optional[dict[str, Any]] = None,
        default: Optional[list[Any]] = None,
    ) -> list[Any]:
        """
        Make GET request expecting list, returning default on error.

        Type-safe wrapper that narrows the return type to list.
        Returns default on HTTP errors or non-list response.

        Args:
            endpoint: API endpoint path
            auth: Whether to include authorization header
            params: Additional query parameters
            default: Value to return on error (defaults to empty list)

        Returns:
            Parsed JSON list response, or default on error
        """
        if default is None:
            default = []
        try:
            result = self.get(endpoint, auth=auth, params=params)
            return result if isinstance(result, list) else default
        except ESIError as e:
            logger.debug(
                "get_list_safe swallowed error for %s: %s (status=%s)",
                endpoint,
                e.message,
                e.status_code,
            )
            return default

    def post(
        self, endpoint: str, data: Union[list[Any], dict[str, Any]], auth: bool = False
    ) -> Union[dict[str, Any], list[Any], None]:
        """
        Make POST request to ESI.

        Primarily used for /universe/ids/ name resolution.
        When retry is enabled, transient failures (429, 503, network errors)
        are automatically retried with exponential backoff.

        Args:
            endpoint: API endpoint path
            data: JSON-serializable data to send
            auth: Whether to include authorization header

        Returns:
            Parsed JSON response

        Raises:
            ESIError: On HTTP errors or request failures
        """
        url = self._build_url(endpoint)
        body = json.dumps(data).encode("utf-8")
        headers: dict[str, str] = {"Content-Type": "application/json"}

        if auth:
            if not self.token:
                raise ESIError("Authentication required but no token provided")
            headers["Authorization"] = f"Bearer {self.token}"

        try:
            result = self._execute_request("POST", url, headers, body)
            # ESI POST responses are always objects or arrays, never primitives
            if isinstance(result, (int, float)):
                return None
            return result
        except RetryableESIError as e:
            # Convert retry error to ESIError if all retries failed
            raise ESIError(e.message, status_code=e.status_code)
        except httpx.RequestError as e:
            raise ESIError(f"Network error: {e}")

    def post_safe(
        self,
        endpoint: str,
        data: Union[list[Any], dict[str, Any]],
        auth: bool = False,
        default: Any = None,
    ) -> Union[dict[str, Any], list[Any], None]:
        """
        Make POST request, returning default on error instead of raising.

        Args:
            endpoint: API endpoint path
            data: JSON-serializable data to send
            auth: Whether to include authorization header
            default: Value to return on error

        Returns:
            Parsed JSON response, or default on error
        """
        try:
            return self.post(endpoint, data, auth=auth)
        except ESIError as e:
            logger.debug(
                "post_safe swallowed error for %s: %s (status=%s)",
                endpoint,
                e.message,
                e.status_code,
            )
            return default

    # =========================================================================
    # Convenience Methods for Common Operations
    # =========================================================================

    def resolve_names(self, names: list[str]) -> dict[str, list[dict[str, Any]]]:
        """
        Resolve names to IDs using POST /universe/ids/.

        Args:
            names: List of names to resolve (systems, characters, items, etc.)

        Returns:
            Dict with keys: agents, alliances, characters, constellations,
            corporations, factions, inventory_types, regions, stations, systems
            Each key maps to a list of {id, name} dicts.
        """
        result = self.post_safe("/universe/ids/", names, default={})
        return result if isinstance(result, dict) else {}

    def resolve_system(self, name: str) -> Optional[int]:
        """
        Resolve system name to ID.

        Args:
            name: System name (case-insensitive)

        Returns:
            System ID, or None if not found
        """
        if name.isdigit():
            return int(name)

        result = self.resolve_names([name])
        systems = result.get("systems", [])
        return systems[0]["id"] if systems else None

    def resolve_item(self, name: str) -> tuple[int | None, str | None]:
        """
        Resolve item name to type_id.

        Args:
            name: Item name (case-insensitive)

        Returns:
            Tuple of (type_id, resolved_name), or (None, None) if not found.
            If input is numeric, returns (type_id, None).
        """
        if name.isdigit():
            return int(name), None

        result = self.resolve_names([name])
        items = result.get("inventory_types", [])
        if items:
            return items[0]["id"], items[0]["name"]
        return None, None

    def resolve_character(self, name: str) -> tuple[int | None, str | None]:
        """
        Resolve character name to ID.

        Args:
            name: Character name (case-insensitive)

        Returns:
            Tuple of (character_id, resolved_name), or (None, None) if not found.
            If input is numeric, returns (character_id, None).
        """
        if name.isdigit():
            return int(name), None

        result = self.resolve_names([name])
        chars = result.get("characters", [])
        if chars:
            return chars[0]["id"], chars[0]["name"]
        return None, None

    def resolve_corporation(self, name: str) -> tuple[int | None, str | None]:
        """
        Resolve corporation name to ID.

        Args:
            name: Corporation name (case-insensitive)

        Returns:
            Tuple of (corp_id, resolved_name), or (None, None) if not found.
            If input is numeric, returns (corp_id, None).
        """
        if name.isdigit():
            return int(name), None

        result = self.resolve_names([name])
        corps = result.get("corporations", [])
        if corps:
            return corps[0]["id"], corps[0]["name"]
        return None, None

    def get_type_name(self, type_id: int) -> Optional[str]:
        """
        Get item/type name from type_id.

        Args:
            type_id: EVE type ID

        Returns:
            Type name, or None if not found
        """
        result = self.get_safe(f"/universe/types/{type_id}/")
        return result.get("name") if isinstance(result, dict) else None

    def get_system_info(self, system_id: int) -> Optional[dict[str, Any]]:
        """
        Get solar system information.

        Args:
            system_id: Solar system ID

        Returns:
            Dict with name, security_status, constellation_id, etc.
        """
        result = self.get_safe(f"/universe/systems/{system_id}/")
        return result if isinstance(result, dict) else None

    def get_station_name(self, station_id: int) -> Optional[str]:
        """
        Get station name from station_id.

        Args:
            station_id: Station ID

        Returns:
            Station name, or None if not found
        """
        # Check cache first (for known trade hubs)
        from .constants import STATION_NAMES

        if station_id in STATION_NAMES:
            return STATION_NAMES[station_id]

        result = self.get_safe(f"/universe/stations/{station_id}/")
        return result.get("name") if isinstance(result, dict) else None

    def get_character_info(self, character_id: int) -> Optional[dict[str, Any]]:
        """
        Get public character information.

        Args:
            character_id: Character ID

        Returns:
            Dict with name, corporation_id, security_status, etc.
        """
        result = self.get_safe(f"/characters/{character_id}/")
        return result if isinstance(result, dict) else None

    def get_corporation_info(self, corporation_id: int) -> Optional[dict[str, Any]]:
        """
        Get public corporation information.

        Args:
            corporation_id: Corporation ID

        Returns:
            Dict with name, ticker, member_count, ceo_id, etc.
        """
        result = self.get_safe(f"/corporations/{corporation_id}/")
        return result if isinstance(result, dict) else None

    def get_alliance_info(self, alliance_id: int) -> Optional[dict[str, Any]]:
        """
        Get alliance information.

        Args:
            alliance_id: Alliance ID

        Returns:
            Dict with name, ticker, etc.
        """
        result = self.get_safe(f"/alliances/{alliance_id}/")
        return result if isinstance(result, dict) else None
