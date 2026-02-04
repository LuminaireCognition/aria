"""
Tests for ARIA ESI Retry Logic.

Tests retry decorators, exception handling, and backoff calculation.
"""

from __future__ import annotations

import urllib.error
from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# Constants Tests
# =============================================================================


class TestRetryConstants:
    """Test module constants."""

    def test_retryable_status_codes(self):
        """Retryable status codes are correctly defined."""
        from aria_esi.core.retry import RETRYABLE_STATUS_CODES

        assert 429 in RETRYABLE_STATUS_CODES  # Too Many Requests
        assert 503 in RETRYABLE_STATUS_CODES  # Service Unavailable
        assert 502 in RETRYABLE_STATUS_CODES  # Bad Gateway
        assert 504 in RETRYABLE_STATUS_CODES  # Gateway Timeout

    def test_non_retryable_status_codes(self):
        """Non-retryable status codes are correctly defined."""
        from aria_esi.core.retry import NON_RETRYABLE_STATUS_CODES

        assert 400 in NON_RETRYABLE_STATUS_CODES  # Bad Request
        assert 401 in NON_RETRYABLE_STATUS_CODES  # Unauthorized
        assert 403 in NON_RETRYABLE_STATUS_CODES  # Forbidden
        assert 404 in NON_RETRYABLE_STATUS_CODES  # Not Found

    def test_default_config(self):
        """Default configuration values are set."""
        from aria_esi.core.retry import (
            DEFAULT_MAX_ATTEMPTS,
            DEFAULT_MAX_WAIT,
            DEFAULT_MIN_WAIT,
        )

        assert DEFAULT_MAX_ATTEMPTS == 3
        assert DEFAULT_MIN_WAIT == 2
        assert DEFAULT_MAX_WAIT == 30


# =============================================================================
# Exception Tests
# =============================================================================


class TestRetryableESIError:
    """Test RetryableESIError exception."""

    def test_can_instantiate(self):
        """Can create RetryableESIError."""
        from aria_esi.core.retry import RetryableESIError

        error = RetryableESIError("Test error")
        assert str(error) == "Test error"
        assert error.message == "Test error"

    def test_with_all_attributes(self):
        """Stores all optional attributes."""
        from aria_esi.core.retry import RetryableESIError

        original = ValueError("original")
        error = RetryableESIError(
            message="Rate limited",
            status_code=429,
            retry_after=60,
            original_error=original,
        )

        assert error.status_code == 429
        assert error.retry_after == 60
        assert error.original_error is original

    def test_is_exception(self):
        """RetryableESIError is an Exception."""
        from aria_esi.core.retry import RetryableESIError

        assert issubclass(RetryableESIError, Exception)


class TestNonRetryableESIError:
    """Test NonRetryableESIError exception."""

    def test_can_instantiate(self):
        """Can create NonRetryableESIError."""
        from aria_esi.core.retry import NonRetryableESIError

        error = NonRetryableESIError("Not found")
        assert str(error) == "Not found"
        assert error.message == "Not found"

    def test_with_all_attributes(self):
        """Stores all optional attributes."""
        from aria_esi.core.retry import NonRetryableESIError

        original = ValueError("original")
        error = NonRetryableESIError(
            message="Not found",
            status_code=404,
            original_error=original,
        )

        assert error.status_code == 404
        assert error.original_error is original


# =============================================================================
# Status Function Tests
# =============================================================================


class TestIsRetryEnabled:
    """Test is_retry_enabled function."""

    def test_returns_boolean(self):
        """Returns a boolean."""
        from aria_esi.core.retry import is_retry_enabled

        result = is_retry_enabled()
        assert isinstance(result, bool)


class TestGetRetryStatus:
    """Test get_retry_status function."""

    def test_returns_dict(self):
        """Returns status dictionary."""
        from aria_esi.core.retry import get_retry_status

        result = get_retry_status()

        assert isinstance(result, dict)
        assert "available" in result
        assert "enabled" in result
        assert "env_disabled" in result
        assert "config" in result

    def test_config_has_expected_keys(self):
        """Config contains expected keys."""
        from aria_esi.core.retry import get_retry_status

        result = get_retry_status()

        config = result["config"]
        assert "max_attempts" in config
        assert "min_wait" in config
        assert "max_wait" in config
        assert "retryable_codes" in config


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestParseRetryAfter:
    """Test _parse_retry_after function."""

    def test_parses_integer(self):
        """Parses integer Retry-After value."""
        from aria_esi.core.retry import _parse_retry_after

        headers = {"Retry-After": "60"}
        result = _parse_retry_after(headers)

        assert result == 60

    def test_returns_none_for_missing(self):
        """Returns None when header missing."""
        from aria_esi.core.retry import _parse_retry_after

        headers = {}
        result = _parse_retry_after(headers)

        assert result is None

    def test_returns_none_for_invalid(self):
        """Returns None for non-integer value."""
        from aria_esi.core.retry import _parse_retry_after

        headers = {"Retry-After": "not a number"}
        result = _parse_retry_after(headers)

        assert result is None

    def test_handles_email_message(self):
        """Handles email.message.Message headers."""
        from email.message import Message

        from aria_esi.core.retry import _parse_retry_after

        msg = Message()
        msg["Retry-After"] = "30"
        result = _parse_retry_after(msg)

        assert result == 30


class TestShouldRetryException:
    """Test _should_retry_exception function."""

    def test_retries_retryable_esi_error(self):
        """Returns True for RetryableESIError."""
        from aria_esi.core.retry import RetryableESIError, _should_retry_exception

        exc = RetryableESIError("Test")
        assert _should_retry_exception(exc) is True

    def test_no_retry_non_retryable_esi_error(self):
        """Returns False for NonRetryableESIError."""
        from aria_esi.core.retry import NonRetryableESIError, _should_retry_exception

        exc = NonRetryableESIError("Test")
        assert _should_retry_exception(exc) is False

    def test_no_retry_generic_exception(self):
        """Returns False for generic exceptions."""
        from aria_esi.core.retry import _should_retry_exception

        exc = ValueError("Test")
        assert _should_retry_exception(exc) is False

    def test_retries_url_error(self):
        """Returns True for URLError (network error)."""
        from aria_esi.core.retry import _should_retry_exception

        exc = urllib.error.URLError("Network error")
        assert _should_retry_exception(exc) is True


class TestCalculateWaitTime:
    """Test _calculate_wait_time function."""

    def test_respects_retry_after(self):
        """Uses Retry-After header when provided."""
        from aria_esi.core.retry import _calculate_wait_time

        result = _calculate_wait_time(1, retry_after=60, min_wait=2, max_wait=100)

        # Should be close to 60 (with small jitter)
        assert 60 <= result <= 60.5

    def test_exponential_backoff(self):
        """Increases wait time exponentially."""
        from aria_esi.core.retry import _calculate_wait_time

        result1 = _calculate_wait_time(1, min_wait=1, max_wait=100, multiplier=1)
        result2 = _calculate_wait_time(2, min_wait=1, max_wait=100, multiplier=1)
        result3 = _calculate_wait_time(3, min_wait=1, max_wait=100, multiplier=1)

        # Each subsequent attempt should generally be longer
        # (allowing for jitter)
        assert result1 < 10  # 2^1 = 2 (with jitter)
        assert result2 < 20  # 2^2 = 4 (with jitter)
        assert result3 < 40  # 2^3 = 8 (with jitter)

    def test_respects_min_wait(self):
        """Never returns less than min_wait."""
        from aria_esi.core.retry import _calculate_wait_time

        result = _calculate_wait_time(1, min_wait=10, max_wait=100, multiplier=0.1)

        assert result >= 10

    def test_respects_max_wait(self):
        """Never returns more than max_wait."""
        from aria_esi.core.retry import _calculate_wait_time

        result = _calculate_wait_time(10, min_wait=1, max_wait=5, multiplier=10)

        assert result <= 5

    def test_retry_after_capped_by_max_wait(self):
        """Retry-After is capped by max_wait."""
        from aria_esi.core.retry import _calculate_wait_time

        result = _calculate_wait_time(1, retry_after=1000, min_wait=1, max_wait=30)

        assert result <= 30


# =============================================================================
# Classify Error Tests
# =============================================================================


class TestClassifyHttpError:
    """Test classify_http_error function."""

    def test_classifies_429_as_retryable(self):
        """Classifies 429 as retryable."""
        from aria_esi.core.retry import RetryableESIError, classify_http_error

        # Create mock HTTP error
        error = urllib.error.HTTPError(
            url="http://test.com",
            code=429,
            msg="Too Many Requests",
            hdrs={"Retry-After": "60"},  # type: ignore
            fp=None,
        )

        result = classify_http_error(error)

        assert isinstance(result, RetryableESIError)
        assert result.status_code == 429

    def test_classifies_503_as_retryable(self):
        """Classifies 503 as retryable."""
        from aria_esi.core.retry import RetryableESIError, classify_http_error

        error = urllib.error.HTTPError(
            url="http://test.com",
            code=503,
            msg="Service Unavailable",
            hdrs={},  # type: ignore
            fp=None,
        )

        result = classify_http_error(error)

        assert isinstance(result, RetryableESIError)
        assert result.status_code == 503

    def test_classifies_404_as_non_retryable(self):
        """Classifies 404 as non-retryable."""
        from aria_esi.core.retry import NonRetryableESIError, classify_http_error

        error = urllib.error.HTTPError(
            url="http://test.com",
            code=404,
            msg="Not Found",
            hdrs={},  # type: ignore
            fp=None,
        )

        result = classify_http_error(error)

        assert isinstance(result, NonRetryableESIError)
        assert result.status_code == 404


class TestHandleEsiError:
    """Test handle_esi_error function."""

    def test_raises_retryable_for_429(self):
        """Raises RetryableESIError for 429."""
        from aria_esi.core.retry import RetryableESIError, handle_esi_error

        error = urllib.error.HTTPError(
            url="http://test.com",
            code=429,
            msg="Too Many Requests",
            hdrs={},  # type: ignore
            fp=None,
        )

        with pytest.raises(RetryableESIError):
            handle_esi_error(error)

    def test_raises_non_retryable_for_404(self):
        """Raises NonRetryableESIError for 404."""
        from aria_esi.core.retry import NonRetryableESIError, handle_esi_error

        error = urllib.error.HTTPError(
            url="http://test.com",
            code=404,
            msg="Not Found",
            hdrs={},  # type: ignore
            fp=None,
        )

        with pytest.raises(NonRetryableESIError):
            handle_esi_error(error)


# =============================================================================
# Decorator Tests
# =============================================================================


class TestEsiRetryDecorator:
    """Test esi_retry decorator."""

    def test_decorator_returns_callable(self):
        """Decorator returns a callable."""
        from aria_esi.core.retry import esi_retry

        @esi_retry()
        def test_func():
            return "test"

        assert callable(test_func)

    def test_successful_call_not_retried(self):
        """Successful calls are not retried."""
        from aria_esi.core.retry import esi_retry

        call_count = 0

        @esi_retry()
        def test_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = test_func()

        assert result == "success"
        assert call_count == 1
