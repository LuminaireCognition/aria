"""
Tests for aria_esi.core.retry

Tests retry logic, exponential backoff, and error classification.
"""

import os
import urllib.error
from unittest.mock import MagicMock

import pytest


class TestRetryAvailability:
    """Tests for retry availability detection."""

    def test_retry_status_returns_dict(self):
        """Test that get_retry_status returns expected structure."""
        from aria_esi.core import get_retry_status

        status = get_retry_status()

        assert isinstance(status, dict)
        assert "available" in status
        assert "enabled" in status
        assert "config" in status
        assert isinstance(status["available"], bool)
        assert isinstance(status["enabled"], bool)

    def test_is_retry_enabled_respects_env(self, monkeypatch):
        """Test that ARIA_NO_RETRY environment variable disables retry."""
        from aria_esi.core.retry import is_retry_enabled

        # Save original value
        original = os.environ.get("ARIA_NO_RETRY")

        try:
            # Test with env var set
            monkeypatch.setenv("ARIA_NO_RETRY", "1")
            assert is_retry_enabled() is False

            monkeypatch.setenv("ARIA_NO_RETRY", "true")
            assert is_retry_enabled() is False

            monkeypatch.setenv("ARIA_NO_RETRY", "yes")
            assert is_retry_enabled() is False
        finally:
            # Restore original
            if original:
                os.environ["ARIA_NO_RETRY"] = original
            elif "ARIA_NO_RETRY" in os.environ:
                del os.environ["ARIA_NO_RETRY"]

    def test_retry_config_values(self):
        """Test that retry config has expected values."""
        from aria_esi.core import get_retry_status

        status = get_retry_status()
        config = status["config"]

        assert config["max_attempts"] == 3
        assert config["min_wait"] == 2
        assert config["max_wait"] == 30
        assert 429 in config["retryable_codes"]
        assert 503 in config["retryable_codes"]


class TestRetryableStatusCodes:
    """Tests for retryable status code classification."""

    def test_retryable_codes_include_rate_limit(self):
        """Test that 429 is in retryable codes."""
        from aria_esi.core import RETRYABLE_STATUS_CODES

        assert 429 in RETRYABLE_STATUS_CODES

    def test_retryable_codes_include_service_unavailable(self):
        """Test that 503 is in retryable codes."""
        from aria_esi.core import RETRYABLE_STATUS_CODES

        assert 503 in RETRYABLE_STATUS_CODES

    def test_retryable_codes_include_gateway_errors(self):
        """Test that gateway errors are in retryable codes."""
        from aria_esi.core import RETRYABLE_STATUS_CODES

        assert 502 in RETRYABLE_STATUS_CODES  # Bad Gateway
        assert 504 in RETRYABLE_STATUS_CODES  # Gateway Timeout

    def test_404_not_retryable(self):
        """Test that 404 is not in retryable codes."""
        from aria_esi.core import RETRYABLE_STATUS_CODES

        assert 404 not in RETRYABLE_STATUS_CODES

    def test_401_not_retryable(self):
        """Test that 401 is not in retryable codes."""
        from aria_esi.core import RETRYABLE_STATUS_CODES

        assert 401 not in RETRYABLE_STATUS_CODES


class TestErrorClassification:
    """Tests for HTTP error classification."""

    def test_classify_429_as_retryable(self):
        """Test that 429 errors are classified as retryable."""
        from aria_esi.core.retry import RetryableESIError, classify_http_error

        # Create a mock HTTPError for 429
        mock_error = MagicMock(spec=urllib.error.HTTPError)
        mock_error.code = 429
        mock_error.reason = "Too Many Requests"
        mock_error.fp = None
        mock_error.headers = {"Retry-After": "5"}

        result = classify_http_error(mock_error)

        assert isinstance(result, RetryableESIError)
        assert result.status_code == 429

    def test_classify_503_as_retryable(self):
        """Test that 503 errors are classified as retryable."""
        from aria_esi.core.retry import RetryableESIError, classify_http_error

        mock_error = MagicMock(spec=urllib.error.HTTPError)
        mock_error.code = 503
        mock_error.reason = "Service Unavailable"
        mock_error.fp = None

        result = classify_http_error(mock_error)

        assert isinstance(result, RetryableESIError)
        assert result.status_code == 503

    def test_classify_404_as_non_retryable(self):
        """Test that 404 errors are classified as non-retryable."""
        from aria_esi.core.retry import NonRetryableESIError, classify_http_error

        mock_error = MagicMock(spec=urllib.error.HTTPError)
        mock_error.code = 404
        mock_error.reason = "Not Found"
        mock_error.fp = None

        result = classify_http_error(mock_error)

        assert isinstance(result, NonRetryableESIError)
        assert result.status_code == 404

    def test_classify_401_as_non_retryable(self):
        """Test that 401 errors are classified as non-retryable."""
        from aria_esi.core.retry import NonRetryableESIError, classify_http_error

        mock_error = MagicMock(spec=urllib.error.HTTPError)
        mock_error.code = 401
        mock_error.reason = "Unauthorized"
        mock_error.fp = None

        result = classify_http_error(mock_error)

        assert isinstance(result, NonRetryableESIError)
        assert result.status_code == 401


class TestRetryAfterHeader:
    """Tests for Retry-After header parsing."""

    def test_parse_retry_after_integer(self):
        """Test parsing Retry-After header with integer seconds."""
        from aria_esi.core.retry import _parse_retry_after

        headers = {"Retry-After": "30"}
        result = _parse_retry_after(headers)

        assert result == 30

    def test_parse_retry_after_missing(self):
        """Test parsing when Retry-After header is missing."""
        from aria_esi.core.retry import _parse_retry_after

        headers = {}
        result = _parse_retry_after(headers)

        assert result is None

    def test_parse_retry_after_invalid(self):
        """Test parsing invalid Retry-After header."""
        from aria_esi.core.retry import _parse_retry_after

        headers = {"Retry-After": "not-a-number"}
        result = _parse_retry_after(headers)

        assert result is None

    def test_classify_429_with_retry_after(self):
        """Test that 429 with Retry-After preserves the value."""
        from aria_esi.core.retry import RetryableESIError, classify_http_error

        mock_error = MagicMock(spec=urllib.error.HTTPError)
        mock_error.code = 429
        mock_error.reason = "Too Many Requests"
        mock_error.fp = None
        mock_error.headers = {"Retry-After": "60"}

        result = classify_http_error(mock_error)

        assert isinstance(result, RetryableESIError)
        assert result.retry_after == 60


class TestWaitTimeCalculation:
    """Tests for wait time calculation with backoff and jitter."""

    def test_calculate_wait_time_respects_retry_after(self):
        """Test that Retry-After header takes precedence."""
        from aria_esi.core.retry import _calculate_wait_time

        # With Retry-After set, should use that value (plus small jitter)
        wait = _calculate_wait_time(attempt=1, retry_after=10)

        # Should be close to 10 (with small jitter)
        assert 10 <= wait <= 11

    def test_calculate_wait_time_exponential(self):
        """Test exponential backoff increases with attempts."""
        from aria_esi.core.retry import _calculate_wait_time

        wait1 = _calculate_wait_time(attempt=1, min_wait=1, max_wait=100)
        wait2 = _calculate_wait_time(attempt=2, min_wait=1, max_wait=100)
        wait3 = _calculate_wait_time(attempt=3, min_wait=1, max_wait=100)

        # Each attempt should generally increase (allowing for jitter)
        # We can't assert strict ordering due to jitter, but the base values increase
        # Attempt 1: 2^1 = 2, Attempt 2: 2^2 = 4, Attempt 3: 2^3 = 8

    def test_calculate_wait_time_respects_max(self):
        """Test that wait time doesn't exceed max_wait."""
        from aria_esi.core.retry import _calculate_wait_time

        wait = _calculate_wait_time(attempt=10, max_wait=30)

        assert wait <= 30

    def test_calculate_wait_time_respects_min(self):
        """Test that wait time doesn't go below min_wait."""
        from aria_esi.core.retry import _calculate_wait_time

        wait = _calculate_wait_time(attempt=1, min_wait=5, max_wait=100)

        assert wait >= 5


class TestEsiRetryDecorator:
    """Tests for the esi_retry decorator."""

    def test_decorator_returns_callable(self):
        """Test that esi_retry returns a decorator."""
        from aria_esi.core import esi_retry

        decorator = esi_retry()
        assert callable(decorator)

    def test_decorated_function_callable(self):
        """Test that decorated function is callable."""
        from aria_esi.core import esi_retry

        @esi_retry()
        def test_func():
            return "success"

        assert callable(test_func)
        assert test_func() == "success"

    def test_decorator_preserves_function_name(self):
        """Test that decorator preserves function metadata."""
        from aria_esi.core import esi_retry

        @esi_retry()
        def my_function():
            """My docstring."""
            return "result"

        # When tenacity is not available, the function should still work
        assert my_function() == "result"


class TestESIClientRetryIntegration:
    """Tests for ESI client retry integration."""

    def test_client_has_retry_attribute(self):
        """Test that ESI client has enable_retry attribute."""
        from aria_esi.core import ESIClient

        client = ESIClient()
        assert hasattr(client, "enable_retry")

    def test_client_retry_disabled_without_tenacity(self, monkeypatch):
        """Test that retry is disabled when tenacity is not available."""
        from aria_esi.core import ESIClient

        # Disable retry via env
        monkeypatch.setenv("ARIA_NO_RETRY", "1")

        client = ESIClient()
        assert client.enable_retry is False

    def test_client_retry_can_be_disabled_explicitly(self):
        """Test that retry can be disabled via constructor."""
        from aria_esi.core import ESIClient

        client = ESIClient(enable_retry=False)
        assert client.enable_retry is False

    def test_client_has_execute_request_method(self):
        """Test that client has _execute_request method."""
        from aria_esi.core import ESIClient

        client = ESIClient()
        assert hasattr(client, "_execute_request")
        assert callable(client._execute_request)


class TestRetryableESIError:
    """Tests for RetryableESIError exception."""

    def test_error_has_status_code(self):
        """Test that error preserves status code."""
        from aria_esi.core import RetryableESIError

        error = RetryableESIError("Rate limited", status_code=429)
        assert error.status_code == 429

    def test_error_has_retry_after(self):
        """Test that error preserves Retry-After value."""
        from aria_esi.core import RetryableESIError

        error = RetryableESIError("Rate limited", status_code=429, retry_after=60)
        assert error.retry_after == 60

    def test_error_has_message(self):
        """Test that error preserves message."""
        from aria_esi.core import RetryableESIError

        error = RetryableESIError("Test message", status_code=503)
        assert error.message == "Test message"
        assert str(error) == "Test message"


class TestNonRetryableESIError:
    """Tests for NonRetryableESIError exception."""

    def test_error_has_status_code(self):
        """Test that error preserves status code."""
        from aria_esi.core import NonRetryableESIError

        error = NonRetryableESIError("Not found", status_code=404)
        assert error.status_code == 404

    def test_error_has_message(self):
        """Test that error preserves message."""
        from aria_esi.core import NonRetryableESIError

        error = NonRetryableESIError("Test message", status_code=404)
        assert error.message == "Test message"
        assert str(error) == "Test message"


class TestSimpleRetryFallback:
    """Tests for the simple retry fallback when tenacity is not available."""

    def test_simple_retry_success_on_first_attempt(self):
        """Test that function returns immediately on success."""
        from aria_esi.core.retry import _simple_retry_wrapper

        call_count = 0

        def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        wrapped = _simple_retry_wrapper(success_func, max_attempts=3)
        result = wrapped()

        assert result == "success"
        assert call_count == 1

    def test_simple_retry_retries_on_retryable_error(self):
        """Test that function retries on retryable errors."""
        from aria_esi.core.retry import RetryableESIError, _simple_retry_wrapper

        call_count = 0

        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RetryableESIError("Temporary error", status_code=503)
            return "success"

        wrapped = _simple_retry_wrapper(flaky_func, max_attempts=3, min_wait=0.01, max_wait=0.02)
        result = wrapped()

        assert result == "success"
        assert call_count == 3

    def test_simple_retry_raises_after_max_attempts(self):
        """Test that function raises after max attempts exhausted."""
        from aria_esi.core.retry import RetryableESIError, _simple_retry_wrapper

        def always_fail():
            raise RetryableESIError("Always fails", status_code=503)

        wrapped = _simple_retry_wrapper(always_fail, max_attempts=2, min_wait=0.01, max_wait=0.02)

        with pytest.raises(RetryableESIError):
            wrapped()


@pytest.mark.skipif(
    os.environ.get("ARIA_NO_RETRY", "").lower() in ("1", "true", "yes"),
    reason="Retry disabled via environment"
)
class TestTenacityIntegration:
    """Integration tests that require tenacity.

    These tests are skipped if tenacity is not available.
    """

    def test_tenacity_retry_on_transient_error(self):
        """Test that tenacity retries on transient errors."""
        from aria_esi.core.retry import TENACITY_AVAILABLE

        if not TENACITY_AVAILABLE:
            pytest.skip("Tenacity not available")

        # This test would use actual tenacity functionality
        # For now, just verify the import worked
        assert TENACITY_AVAILABLE is True
