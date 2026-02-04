"""
Tests for async ESI client.
"""

from __future__ import annotations

import pytest

from aria_esi.core.async_client import (
    AsyncESIClient,
    AsyncESIError,
    AsyncESIResponse,
    create_async_client,
)


class TestAsyncESIResponse:
    """Test AsyncESIResponse data class."""

    def test_basic_response(self):
        """Test basic response with data."""
        response = AsyncESIResponse(
            data={"name": "Jita"},
            headers={"Content-Type": "application/json"},
            status_code=200,
        )

        assert response.data == {"name": "Jita"}
        assert response.status_code == 200
        assert response.is_not_modified is False

    def test_not_modified_response(self):
        """Test 304 Not Modified response."""
        response = AsyncESIResponse(
            data=None,
            headers={},
            status_code=304,
        )

        assert response.data is None
        assert response.is_not_modified is True

    def test_last_modified_parsing(self):
        """Test Last-Modified header parsing."""
        response = AsyncESIResponse(
            data={"name": "Jita"},
            headers={"Last-Modified": "Thu, 01 Jan 2026 00:00:00 GMT"},
            status_code=200,
        )

        assert response.last_modified_timestamp is not None
        assert response.last_modified_timestamp > 0

    def test_last_modified_lowercase(self):
        """Test Last-Modified header with lowercase key."""
        response = AsyncESIResponse(
            data={"name": "Jita"},
            headers={"last-modified": "Thu, 01 Jan 2026 00:00:00 GMT"},
            status_code=200,
        )

        assert response.last_modified_timestamp is not None

    def test_expires_parsing(self):
        """Test Expires header parsing."""
        response = AsyncESIResponse(
            data={"name": "Jita"},
            headers={"Expires": "Thu, 01 Jan 2026 01:00:00 GMT"},
            status_code=200,
        )

        assert response.expires_timestamp is not None
        assert response.expires_timestamp > 0

    def test_x_pages_parsing(self):
        """Test X-Pages header parsing."""
        response = AsyncESIResponse(
            data=[1, 2, 3],
            headers={"X-Pages": "10"},
            status_code=200,
        )

        assert response.x_pages == 10

    def test_x_pages_lowercase(self):
        """Test X-Pages header with lowercase key."""
        response = AsyncESIResponse(
            data=[1, 2, 3],
            headers={"x-pages": "5"},
            status_code=200,
        )

        assert response.x_pages == 5

    def test_missing_headers(self):
        """Test response with missing optional headers."""
        response = AsyncESIResponse(
            data={},
            headers={},
            status_code=200,
        )

        assert response.last_modified_timestamp is None
        assert response.expires_timestamp is None
        assert response.x_pages is None

    def test_invalid_header_values(self):
        """Test graceful handling of invalid header values."""
        response = AsyncESIResponse(
            data={},
            headers={
                "Last-Modified": "invalid",
                "Expires": "invalid",
                "X-Pages": "not-a-number",
            },
            status_code=200,
        )

        assert response.last_modified_timestamp is None
        assert response.expires_timestamp is None
        assert response.x_pages is None


class TestAsyncESIError:
    """Test AsyncESIError exception."""

    def test_basic_error(self):
        """Test basic error creation."""
        error = AsyncESIError("Something went wrong")

        assert str(error) == "Something went wrong"
        assert error.message == "Something went wrong"
        assert error.status_code is None

    def test_error_with_status_code(self):
        """Test error with HTTP status code."""
        error = AsyncESIError("Not Found", status_code=404)

        assert error.status_code == 404
        assert error.message == "Not Found"

    def test_error_to_dict(self):
        """Test error serialization."""
        error = AsyncESIError("Rate limited", status_code=429)

        result = error.to_dict()

        assert result["error"] == "esi_error"
        assert result["message"] == "Rate limited"
        assert result["status_code"] == 429

    def test_error_to_dict_without_status(self):
        """Test error serialization without status code."""
        error = AsyncESIError("Network error")

        result = error.to_dict()

        assert "status_code" not in result
        assert result["message"] == "Network error"


class TestAsyncESIClient:
    """Test AsyncESIClient class."""

    def test_client_initialization(self):
        """Test client initializes with defaults."""
        client = AsyncESIClient()

        assert client.token is None
        assert client.timeout == 30.0
        assert client.enable_retry is True
        assert client._client is None

    def test_client_with_token(self):
        """Test client initializes with token."""
        client = AsyncESIClient(token="test_token")

        assert client.token == "test_token"

    def test_client_with_custom_timeout(self):
        """Test client with custom timeout."""
        client = AsyncESIClient(timeout=60.0)

        assert client.timeout == 60.0

    def test_client_retry_can_be_disabled(self):
        """Test retry can be disabled."""
        client = AsyncESIClient(enable_retry=False)

        assert client.enable_retry is False

    def test_build_url_simple(self):
        """Test URL building with simple endpoint."""
        client = AsyncESIClient()

        url = client._build_url("/universe/systems/30000142/")

        assert "/universe/systems/30000142/" in url
        assert "datasource=" in url

    def test_build_url_with_params(self):
        """Test URL building with additional params."""
        client = AsyncESIClient()

        url = client._build_url("/markets/10000002/orders/", {"page": 1})

        assert "/markets/10000002/orders/" in url
        assert "page=1" in url
        assert "datasource=" in url

    def test_build_url_without_leading_slash(self):
        """Test URL building handles missing leading slash."""
        client = AsyncESIClient()

        url = client._build_url("universe/systems/30000142/")

        assert "/universe/systems/30000142/" in url


@pytest.mark.asyncio
class TestAsyncESIClientAsync:
    """Test AsyncESIClient async operations."""

    async def test_context_manager(self):
        """Test client works as async context manager."""
        async with AsyncESIClient() as client:
            assert client._client is not None

        assert client._client is None

    async def test_get_without_context_raises(self):
        """Test get() raises error outside context manager."""
        client = AsyncESIClient()

        with pytest.raises(AsyncESIError, match="Client not initialized"):
            await client.get("/test/")

    async def test_create_async_client_helper(self):
        """Test create_async_client convenience function."""
        client = await create_async_client()

        try:
            assert client._client is not None
        finally:
            await client.__aexit__(None, None, None)


# Skip all tests in this class if pytest-httpx is not installed
try:
    import pytest_httpx  # noqa: F401

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


# These tests require pytest-httpx for mocking HTTP requests
@pytest.mark.asyncio
@pytest.mark.httpx
@pytest.mark.skipif(not HTTPX_AVAILABLE, reason="pytest-httpx not installed")
class TestAsyncESIClientIntegration:
    """Integration tests with mocked HTTP responses."""

    async def test_get_success(self, httpx_mock):
        """Test successful GET request."""
        httpx_mock.add_response(
            url="https://esi.evetech.net/latest/universe/systems/30000142/?datasource=tranquility",
            json={"system_id": 30000142, "name": "Jita"},
        )

        async with AsyncESIClient() as client:
            result = await client.get("/universe/systems/30000142/")

        assert result == {"system_id": 30000142, "name": "Jita"}

    async def test_get_safe_returns_none_on_404(self, httpx_mock):
        """Test get_safe returns None on 404."""
        httpx_mock.add_response(
            url="https://esi.evetech.net/latest/universe/types/99999/?datasource=tranquility",
            status_code=404,
            json={"error": "Type not found"},
        )

        async with AsyncESIClient() as client:
            result = await client.get_safe("/universe/types/99999/")

        assert result is None

    async def test_get_with_auth_header(self, httpx_mock):
        """Test authenticated request includes Authorization header."""
        httpx_mock.add_response(
            url="https://esi.evetech.net/latest/characters/12345/location/?datasource=tranquility",
            json={"solar_system_id": 30000142},
            match_headers={"Authorization": "Bearer test_token"},
        )

        async with AsyncESIClient(token="test_token") as client:
            result = await client.get("/characters/12345/location/", auth=True)

        assert result == {"solar_system_id": 30000142}

    async def test_get_with_headers_returns_response(self, httpx_mock):
        """Test get_with_headers returns full response."""
        httpx_mock.add_response(
            url="https://esi.evetech.net/latest/markets/10000002/orders/?datasource=tranquility",
            json=[{"order_id": 123}],
            headers={"X-Pages": "5", "Last-Modified": "Thu, 01 Jan 2026 00:00:00 GMT"},
        )

        async with AsyncESIClient() as client:
            response = await client.get_with_headers("/markets/10000002/orders/")

        assert response.data == [{"order_id": 123}]
        assert response.x_pages == 5
        assert response.last_modified_timestamp is not None

    async def test_post_request(self, httpx_mock):
        """Test POST request."""
        httpx_mock.add_response(
            url="https://esi.evetech.net/latest/universe/ids/?datasource=tranquility",
            json={"systems": [{"id": 30000142, "name": "Jita"}]},
        )

        async with AsyncESIClient() as client:
            result = await client.post("/universe/ids/", ["Jita"])

        assert result == {"systems": [{"id": 30000142, "name": "Jita"}]}

    async def test_rate_limit_headers_tracked(self, httpx_mock):
        """Test rate limit headers are tracked."""
        httpx_mock.add_response(
            url="https://esi.evetech.net/latest/universe/systems/30000142/?datasource=tranquility",
            json={"name": "Jita"},
            headers={
                "x-esi-error-limit-remain": "50",
                "x-esi-error-limit-reset": "60",
            },
        )

        async with AsyncESIClient() as client:
            await client.get("/universe/systems/30000142/")

            assert client._error_limit_remain == 50
