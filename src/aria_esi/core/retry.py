"""
ARIA ESI Retry Logic

Resilient HTTP request handling with exponential backoff for transient failures.

This module provides retry logic for ESI API requests:
- Retries on 429 (rate limited) with Retry-After header support
- Retries on 503 (service unavailable) with exponential backoff
- Retries on network errors (URLError)
- Jitter to prevent thundering herd

If tenacity is not installed, requests proceed without retry logic.
ARIA continues to work, but transient failures may not be automatically retried.

Install: pip install aria[resilient]
"""

import json
import random
import time
import urllib.error
from collections.abc import Callable, Mapping
from email.message import Message
from functools import wraps
from typing import Any, Optional, TypeVar, Union

# Import httpx with graceful fallback
try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    httpx = None  # type: ignore[assignment]
    HTTPX_AVAILABLE = False

# Type variable for generic callable decoration
F = TypeVar("F", bound=Callable[..., Any])

# Default retry configuration
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_MIN_WAIT = 2  # seconds
DEFAULT_MAX_WAIT = 30  # seconds
DEFAULT_MULTIPLIER = 1  # exponential base multiplier

# HTTP status codes that should trigger retry
RETRYABLE_STATUS_CODES = {
    429,  # Too Many Requests (rate limited)
    503,  # Service Unavailable
    502,  # Bad Gateway
    504,  # Gateway Timeout
}

# Status codes that should NOT be retried (client errors)
NON_RETRYABLE_STATUS_CODES = {
    400,  # Bad Request
    401,  # Unauthorized
    403,  # Forbidden
    404,  # Not Found
    422,  # Unprocessable Entity
}


# Attempt to import tenacity with graceful fallback
try:
    import logging

    from tenacity import (
        RetryError,
        before_sleep_log,
        retry,
        retry_if_exception,
        stop_after_attempt,
        wait_exponential_jitter,
    )

    TENACITY_AVAILABLE = True
except ImportError:
    TENACITY_AVAILABLE = False
    RetryError = Exception  # type: ignore[assignment]  # Fallback for type hints


def is_retry_enabled() -> bool:
    """
    Check if retry logic is available and enabled.

    Returns False if:
    - tenacity package is not installed
    - ARIA_NO_RETRY environment variable is set

    Returns:
        True if retry logic can be used
    """
    from .config import is_retry_disabled

    if is_retry_disabled():
        return False
    return TENACITY_AVAILABLE


def get_retry_status() -> dict:
    """
    Get detailed status about retry capability.

    Returns:
        Dict with keys:
        - available: bool - whether tenacity is installed
        - enabled: bool - whether retry is enabled (respects ARIA_NO_RETRY)
        - config: dict - current retry configuration
    """
    from .config import is_retry_disabled

    return {
        "available": TENACITY_AVAILABLE,
        "enabled": is_retry_enabled(),
        "env_disabled": is_retry_disabled(),
        "config": {
            "max_attempts": DEFAULT_MAX_ATTEMPTS,
            "min_wait": DEFAULT_MIN_WAIT,
            "max_wait": DEFAULT_MAX_WAIT,
            "retryable_codes": list(RETRYABLE_STATUS_CODES),
        },
    }


class RetryableESIError(Exception):
    """
    Exception for retryable ESI errors.

    This exception is raised for HTTP errors that should trigger retry logic.
    It preserves the original error information for logging and debugging.
    """

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        retry_after: Optional[int] = None,
        original_error: Optional[Exception] = None,
    ) -> None:
        self.message: str = message
        self.status_code: Optional[int] = status_code
        self.retry_after: Optional[int] = retry_after  # Retry-After header value in seconds
        self.original_error: Optional[Exception] = original_error
        super().__init__(self.message)


class NonRetryableESIError(Exception):
    """
    Exception for non-retryable ESI errors.

    This exception is raised for HTTP errors that should NOT trigger retry
    (e.g., 404 Not Found, 401 Unauthorized).
    """

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        original_error: Optional[Exception] = None,
    ) -> None:
        self.message: str = message
        self.status_code: Optional[int] = status_code
        self.original_error: Optional[Exception] = original_error
        super().__init__(self.message)


def _parse_retry_after(headers: Mapping[str, str] | Message) -> Optional[int]:
    """
    Parse Retry-After header from HTTP response.

    Args:
        headers: HTTP headers (email.message.Message or dict-like)

    Returns:
        Number of seconds to wait, or None if not present
    """
    try:
        retry_after = headers.get("Retry-After")
        if retry_after:
            # Retry-After can be seconds or HTTP-date
            # We only handle seconds for simplicity
            return int(retry_after)
    except (ValueError, TypeError, AttributeError):
        pass
    return None


def _should_retry_exception(exc: BaseException) -> bool:
    """
    Determine if an exception should trigger a retry.

    Args:
        exc: The exception to check

    Returns:
        True if the request should be retried
    """
    # Always retry our custom retryable error
    if isinstance(exc, RetryableESIError):
        return True

    # Never retry our non-retryable error
    if isinstance(exc, NonRetryableESIError):
        return False

    # Retry urllib network errors (backwards compatibility)
    if isinstance(exc, urllib.error.URLError):
        # Don't retry if it's an HTTP error with non-retryable status
        if isinstance(exc, urllib.error.HTTPError):
            return exc.code in RETRYABLE_STATUS_CODES
        return True

    # Retry httpx errors
    if HTTPX_AVAILABLE and httpx is not None:
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code in RETRYABLE_STATUS_CODES
        if isinstance(exc, httpx.RequestError):
            return True  # Network errors are retryable

    return False


def _calculate_wait_time(
    attempt: int,
    retry_after: Optional[int] = None,
    min_wait: float = DEFAULT_MIN_WAIT,
    max_wait: float = DEFAULT_MAX_WAIT,
    multiplier: float = DEFAULT_MULTIPLIER,
) -> float:
    """
    Calculate wait time with exponential backoff and jitter.

    Args:
        attempt: Current attempt number (1-indexed)
        retry_after: Retry-After header value (takes precedence if set)
        min_wait: Minimum wait time in seconds
        max_wait: Maximum wait time in seconds
        multiplier: Exponential multiplier

    Returns:
        Wait time in seconds
    """
    # If Retry-After header is present, use it (with small jitter)
    if retry_after is not None:
        jitter = random.uniform(0, 0.5)
        return min(retry_after + jitter, max_wait)

    # Exponential backoff: multiplier * 2^attempt
    exponential = multiplier * (2**attempt)

    # Add jitter (±25% of base value)
    jitter = random.uniform(-0.25, 0.25) * exponential
    wait = exponential + jitter

    # Clamp to min/max bounds
    return max(min_wait, min(wait, max_wait))


def _simple_retry_wrapper(
    func: F,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    min_wait: float = DEFAULT_MIN_WAIT,
    max_wait: float = DEFAULT_MAX_WAIT,
) -> F:
    """
    Simple retry wrapper without tenacity (fallback implementation).

    This provides basic retry functionality when tenacity is not installed.
    """
    # Build tuple of retryable exceptions (httpx if available)
    retryable_exceptions: tuple[type[Exception], ...] = (RetryableESIError, urllib.error.URLError)
    if HTTPX_AVAILABLE and httpx is not None:
        retryable_exceptions = (*retryable_exceptions, httpx.RequestError)

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        last_exception = None

        for attempt in range(1, max_attempts + 1):
            try:
                return func(*args, **kwargs)
            except retryable_exceptions as e:
                last_exception = e

                # Check if we should retry urllib HTTP errors
                if isinstance(e, urllib.error.HTTPError):
                    if e.code not in RETRYABLE_STATUS_CODES:
                        raise  # Don't retry non-retryable status codes

                # Check if we should retry httpx HTTP errors
                if HTTPX_AVAILABLE and httpx is not None and isinstance(e, httpx.HTTPStatusError):
                    if e.response.status_code not in RETRYABLE_STATUS_CODES:
                        raise  # Don't retry non-retryable status codes

                # Don't wait after the last attempt
                if attempt < max_attempts:
                    retry_after = None
                    if isinstance(e, RetryableESIError):
                        retry_after = e.retry_after

                    wait_time = _calculate_wait_time(attempt, retry_after, min_wait, max_wait)
                    time.sleep(wait_time)

        # All attempts exhausted
        if last_exception:
            raise last_exception
        return None  # Should never reach here

    return wrapper  # type: ignore[return-value]


def esi_retry(
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    min_wait: float = DEFAULT_MIN_WAIT,
    max_wait: float = DEFAULT_MAX_WAIT,
) -> Callable[[F], F]:
    """
    Decorator for ESI requests with retry logic.

    When tenacity is installed, uses sophisticated retry with:
    - Exponential backoff with jitter
    - Retry-After header support
    - Logging of retry attempts

    When tenacity is not installed, uses a simple fallback implementation.

    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        min_wait: Minimum wait time between retries in seconds (default: 2)
        max_wait: Maximum wait time between retries in seconds (default: 30)

    Returns:
        Decorator function

    Usage:
        @esi_retry()
        def make_request(url):
            # request logic
            pass

        @esi_retry(max_attempts=5, max_wait=60)
        def make_important_request(url):
            # request logic with more retries
            pass
    """

    def decorator(func: F) -> F:
        # If retry is disabled, return function unchanged
        if not is_retry_enabled():
            return func

        if TENACITY_AVAILABLE:
            # Use tenacity for sophisticated retry
            @retry(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential_jitter(
                    initial=min_wait,
                    max=max_wait,
                    jitter=max_wait * 0.1,  # 10% jitter
                ),
                retry=retry_if_exception(_should_retry_exception),
                reraise=True,
            )
            @wraps(func)
            def tenacity_wrapper(*args: Any, **kwargs: Any) -> Any:
                return func(*args, **kwargs)

            return tenacity_wrapper  # type: ignore[return-value]
        else:
            # Use simple fallback
            return _simple_retry_wrapper(func, max_attempts, min_wait, max_wait)

    return decorator


def classify_http_error(
    error: urllib.error.HTTPError,
) -> Union[RetryableESIError, NonRetryableESIError]:
    """
    Classify an HTTP error as retryable or non-retryable.

    This function examines the HTTP error and returns an appropriate
    exception type that the retry logic can use to determine behavior.

    Args:
        error: The urllib HTTPError to classify

    Returns:
        RetryableESIError for transient errors (429, 503, etc.)
        NonRetryableESIError for permanent errors (404, 401, etc.)
    """
    status_code = error.code
    error_body = ""

    try:
        if error.fp:
            error_body = error.read().decode("utf-8", errors="replace")
    except Exception:
        pass

    # Parse error message
    try:
        error_json = json.loads(error_body)
        message = error_json.get("error", str(error.reason))
    except (json.JSONDecodeError, ValueError):
        message = error_body or str(error.reason)

    if status_code in RETRYABLE_STATUS_CODES:
        retry_after = _parse_retry_after(error.headers) if hasattr(error, "headers") else None
        return RetryableESIError(
            message=message, status_code=status_code, retry_after=retry_after, original_error=error
        )
    else:
        return NonRetryableESIError(message=message, status_code=status_code, original_error=error)


def classify_httpx_error(
    error: "httpx.HTTPStatusError",
) -> Union[RetryableESIError, NonRetryableESIError]:
    """
    Classify an httpx HTTP status error as retryable or non-retryable.

    This function examines the httpx HTTP error and returns an appropriate
    exception type that the retry logic can use to determine behavior.

    Args:
        error: The httpx HTTPStatusError to classify

    Returns:
        RetryableESIError for transient errors (429, 503, etc.)
        NonRetryableESIError for permanent errors (404, 401, etc.)
    """
    status_code = error.response.status_code

    # Parse error message from response body
    try:
        error_json = error.response.json()
        message = error_json.get("error", str(error))
    except (json.JSONDecodeError, ValueError):
        message = error.response.text or str(error)

    if status_code in RETRYABLE_STATUS_CODES:
        retry_after = error.response.headers.get("retry-after")
        return RetryableESIError(
            message=message,
            status_code=status_code,
            retry_after=int(retry_after) if retry_after else None,
            original_error=error,
        )
    else:
        return NonRetryableESIError(message=message, status_code=status_code, original_error=error)


def handle_esi_error(error: urllib.error.HTTPError):
    """
    Handle an ESI HTTP error by raising appropriate exception.

    This function should be used in the ESI client to convert urllib
    HTTPErrors into retry-aware exceptions.

    Args:
        error: The urllib HTTPError to handle

    Raises:
        RetryableESIError: For transient errors that should be retried
        NonRetryableESIError: For permanent errors that should not be retried
    """
    raise classify_http_error(error)
