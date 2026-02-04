"""
Tests for aria_esi.core.client

Tests the ESI HTTP client with mocked network responses.
Uses pytest-httpx for httpx mocking.
"""

import pytest

# Check if pytest-httpx is available
try:
    import pytest_httpx  # noqa: F401

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


class TestESIClientInit:
    """Tests for ESIClient initialization."""

    def test_default_init(self):
        from aria_esi.core import ESIClient

        client = ESIClient()

        assert client.token is None
        assert client.timeout == 30
        assert "esi.evetech.net" in client.base_url
        assert client._http_client is None  # Lazy initialization

    def test_init_with_token(self):
        from aria_esi.core import ESIClient

        client = ESIClient(token="test_token")

        assert client.token == "test_token"

    def test_init_with_custom_timeout(self):
        from aria_esi.core import ESIClient

        client = ESIClient(timeout=60)

        assert client.timeout == 60


class TestESIClientLifecycle:
    """Tests for ESIClient lifecycle management."""

    def test_lazy_client_initialization(self):
        """Test that httpx client is lazily initialized."""
        from aria_esi.core import ESIClient

        client = ESIClient()

        # Client should be None until first request
        assert client._http_client is None

        # Access _get_client to trigger initialization
        http_client = client._get_client()
        assert http_client is not None
        assert client._http_client is not None

        client.close()

    def test_context_manager(self):
        """Test that context manager properly closes client."""
        from aria_esi.core import ESIClient

        with ESIClient() as client:
            # Force client creation
            _ = client._get_client()
            assert client._http_client is not None

        # After exit, client should be closed
        assert client._http_client is None

    def test_close_method(self):
        """Test that close() properly releases resources."""
        from aria_esi.core import ESIClient

        client = ESIClient()
        _ = client._get_client()  # Initialize client
        assert client._http_client is not None

        client.close()
        assert client._http_client is None

    def test_close_when_not_initialized(self):
        """Test that close() works even when client was never used."""
        from aria_esi.core import ESIClient

        client = ESIClient()
        assert client._http_client is None

        # Should not raise
        client.close()
        assert client._http_client is None


class TestESIClientBuildUrl:
    """Tests for URL building."""

    def test_build_url_basic(self):
        from aria_esi.core import ESIClient

        client = ESIClient()
        url = client._build_url("/characters/12345/")

        assert "esi.evetech.net" in url
        assert "/characters/12345/" in url
        assert "datasource=tranquility" in url

    def test_build_url_without_leading_slash(self):
        from aria_esi.core import ESIClient

        client = ESIClient()
        url = client._build_url("characters/12345/")

        assert "/characters/12345/" in url

    def test_build_url_with_params(self):
        from aria_esi.core import ESIClient

        client = ESIClient()
        url = client._build_url("/route/1/2/", params={"flag": "secure"})

        assert "flag=secure" in url
        assert "datasource=tranquility" in url


@pytest.mark.httpx
@pytest.mark.skipif(not HTTPX_AVAILABLE, reason="pytest-httpx not installed")
class TestESIClientGet:
    """Tests for GET requests."""

    def test_get_public_success(self, httpx_mock, mock_system_response):
        from aria_esi.core import ESIClient

        httpx_mock.add_response(
            url="https://esi.evetech.net/latest/universe/systems/30000142/?datasource=tranquility",
            json=mock_system_response,
        )

        with ESIClient() as client:
            result = client.get("/universe/systems/30000142/")

            assert result["name"] == "Jita"
            assert result["system_id"] == 30000142

    def test_get_authenticated_success(self, httpx_mock, mock_character_response):
        from aria_esi.core import ESIClient

        httpx_mock.add_response(
            url="https://esi.evetech.net/latest/characters/12345/?datasource=tranquility",
            json=mock_character_response,
            match_headers={"Authorization": "Bearer test_token"},
        )

        with ESIClient(token="test_token") as client:
            result = client.get("/characters/12345/", auth=True)

            assert result["name"] == "Test Pilot"

    def test_get_auth_required_no_token(self):
        from aria_esi.core import ESIClient, ESIError

        client = ESIClient()  # No token

        with pytest.raises(ESIError) as exc_info:
            client.get("/characters/12345/location/", auth=True)

        assert "Authentication required" in str(exc_info.value.message)

    def test_get_http_error(self, httpx_mock):
        from aria_esi.core import ESIClient, ESIError

        httpx_mock.add_response(
            url="https://esi.evetech.net/latest/nonexistent/?datasource=tranquility",
            status_code=404,
            json={"error": "Not found"},
        )

        with ESIClient() as client:
            with pytest.raises(ESIError) as exc_info:
                client.get("/nonexistent/")

            assert exc_info.value.status_code == 404

    def test_get_network_error(self, httpx_mock):
        import httpx

        from aria_esi.core import ESIClient, ESIError

        httpx_mock.add_exception(
            httpx.ConnectError("Network unreachable"),
            url="https://esi.evetech.net/latest/universe/systems/1/?datasource=tranquility",
        )

        # Disable retry to avoid multiple requests
        with ESIClient(enable_retry=False) as client:
            with pytest.raises(ESIError) as exc_info:
                client.get("/universe/systems/1/")

            assert "Network error" in str(exc_info.value.message)


@pytest.mark.httpx
@pytest.mark.skipif(not HTTPX_AVAILABLE, reason="pytest-httpx not installed")
class TestESIClientGetSafe:
    """Tests for safe GET requests (returns default on error)."""

    def test_get_safe_success(self, httpx_mock, mock_system_response):
        from aria_esi.core import ESIClient

        httpx_mock.add_response(
            url="https://esi.evetech.net/latest/universe/systems/30000142/?datasource=tranquility",
            json=mock_system_response,
        )

        with ESIClient() as client:
            result = client.get_safe("/universe/systems/30000142/")

            assert result is not None
            assert result["name"] == "Jita"

    def test_get_safe_error_returns_default(self, httpx_mock):
        import httpx

        from aria_esi.core import ESIClient

        httpx_mock.add_exception(
            httpx.ConnectError("Network error"),
            url="https://esi.evetech.net/latest/nonexistent/?datasource=tranquility",
        )

        # Disable retry to avoid multiple requests
        with ESIClient(enable_retry=False) as client:
            result = client.get_safe("/nonexistent/", default={"fallback": True})

            assert result == {"fallback": True}

    def test_get_safe_error_returns_none(self, httpx_mock):
        import httpx

        from aria_esi.core import ESIClient

        httpx_mock.add_exception(
            httpx.ConnectError("Network error"),
            url="https://esi.evetech.net/latest/nonexistent/?datasource=tranquility",
        )

        # Disable retry to avoid multiple requests
        with ESIClient(enable_retry=False) as client:
            result = client.get_safe("/nonexistent/")

            assert result is None

    def test_get_safe_logs_swallowed_error(self, httpx_mock, caplog):
        """Verify get_safe logs when swallowing errors."""
        import logging

        from aria_esi.core import ESIClient

        httpx_mock.add_response(
            url="https://esi.evetech.net/latest/failing/?datasource=tranquility",
            status_code=500,
            json={"error": "Internal server error"},
        )

        with caplog.at_level(logging.DEBUG, logger="aria_esi.core.client"):
            with ESIClient(enable_retry=False) as client:
                result = client.get_safe("/failing/")

                assert result is None
                assert "get_safe swallowed error" in caplog.text
                assert "/failing/" in caplog.text
                assert "status=500" in caplog.text

    def test_get_dict_safe_logs_swallowed_error(self, httpx_mock, caplog):
        """Verify get_dict_safe logs when swallowing errors."""
        import logging

        from aria_esi.core import ESIClient

        httpx_mock.add_response(
            url="https://esi.evetech.net/latest/failing/?datasource=tranquility",
            status_code=503,
            json={"error": "Service unavailable"},
        )

        with caplog.at_level(logging.DEBUG, logger="aria_esi.core.client"):
            with ESIClient(enable_retry=False) as client:
                result = client.get_dict_safe("/failing/")

                assert result == {}
                assert "get_dict_safe swallowed error" in caplog.text
                assert "status=503" in caplog.text

    def test_get_list_safe_logs_swallowed_error(self, httpx_mock, caplog):
        """Verify get_list_safe logs when swallowing errors."""
        import logging

        from aria_esi.core import ESIClient

        httpx_mock.add_response(
            url="https://esi.evetech.net/latest/failing/?datasource=tranquility",
            status_code=404,
            json={"error": "Not found"},
        )

        with caplog.at_level(logging.DEBUG, logger="aria_esi.core.client"):
            with ESIClient(enable_retry=False) as client:
                result = client.get_list_safe("/failing/")

                assert result == []
                assert "get_list_safe swallowed error" in caplog.text
                assert "status=404" in caplog.text


@pytest.mark.httpx
@pytest.mark.skipif(not HTTPX_AVAILABLE, reason="pytest-httpx not installed")
class TestESIClientPost:
    """Tests for POST requests."""

    def test_post_success(self, httpx_mock):
        from aria_esi.core import ESIClient

        response_data = {"systems": [{"id": 30000142, "name": "Jita"}]}

        httpx_mock.add_response(
            url="https://esi.evetech.net/latest/universe/ids/?datasource=tranquility",
            json=response_data,
        )

        with ESIClient() as client:
            result = client.post("/universe/ids/", ["Jita"])

            assert result == response_data

    def test_post_safe_error_returns_default(self, httpx_mock):
        import httpx

        from aria_esi.core import ESIClient

        httpx_mock.add_exception(
            httpx.ConnectError("Network error"),
            url="https://esi.evetech.net/latest/universe/ids/?datasource=tranquility",
        )

        # Disable retry to avoid multiple requests
        with ESIClient(enable_retry=False) as client:
            result = client.post_safe("/universe/ids/", ["Test"], default={})

            assert result == {}

    def test_post_safe_logs_swallowed_error(self, httpx_mock, caplog):
        """Verify post_safe logs when swallowing errors."""
        import logging

        from aria_esi.core import ESIClient

        httpx_mock.add_response(
            url="https://esi.evetech.net/latest/universe/ids/?datasource=tranquility",
            status_code=400,
            json={"error": "Bad request"},
        )

        with caplog.at_level(logging.DEBUG, logger="aria_esi.core.client"):
            with ESIClient(enable_retry=False) as client:
                result = client.post_safe("/universe/ids/", ["Invalid"], default={})

                assert result == {}
                assert "post_safe swallowed error" in caplog.text
                assert "/universe/ids/" in caplog.text
                assert "status=400" in caplog.text


@pytest.mark.httpx
@pytest.mark.skipif(not HTTPX_AVAILABLE, reason="pytest-httpx not installed")
class TestESIClientGetWithHeaders:
    """Tests for GET requests with header capture."""

    def test_get_with_headers_success(self, httpx_mock):
        from aria_esi.core import ESIClient

        httpx_mock.add_response(
            url="https://esi.evetech.net/latest/markets/10000002/orders/?datasource=tranquility",
            json=[{"order_id": 123}],
            headers={
                "X-Pages": "5",
                "Last-Modified": "Thu, 01 Jan 2026 00:00:00 GMT",
            },
        )

        with ESIClient() as client:
            response = client.get_with_headers("/markets/10000002/orders/")

            assert response.data == [{"order_id": 123}]
            assert response.x_pages == 5
            assert response.status_code == 200

    def test_get_with_headers_304(self, httpx_mock):
        from aria_esi.core import ESIClient

        httpx_mock.add_response(
            url="https://esi.evetech.net/latest/markets/10000002/orders/?datasource=tranquility",
            status_code=304,
        )

        with ESIClient() as client:
            response = client.get_with_headers(
                "/markets/10000002/orders/",
                if_modified_since="Wed, 31 Dec 2025 00:00:00 GMT",
            )

            assert response.is_not_modified
            assert response.data is None
            assert response.status_code == 304


@pytest.mark.httpx
@pytest.mark.skipif(not HTTPX_AVAILABLE, reason="pytest-httpx not installed")
class TestESIClientRateLimits:
    """Tests for rate limit tracking."""

    def test_rate_limit_headers_tracked(self, httpx_mock):
        from aria_esi.core import ESIClient

        httpx_mock.add_response(
            url="https://esi.evetech.net/latest/universe/systems/30000142/?datasource=tranquility",
            json={"name": "Jita"},
            headers={
                "x-esi-error-limit-remain": "50",
                "x-esi-error-limit-reset": "60",
            },
        )

        with ESIClient() as client:
            client.get("/universe/systems/30000142/")

            assert client._error_limit_remain == 50


class TestESIClientConvenienceMethods:
    """Tests for convenience methods."""

    def test_resolve_names(self):
        from unittest.mock import patch

        from aria_esi.core import ESIClient

        client = ESIClient()

        response_data = {
            "systems": [{"id": 30000142, "name": "Jita"}],
            "characters": [{"id": 12345, "name": "Test Pilot"}],
        }

        with patch.object(client, "post_safe", return_value=response_data):
            result = client.resolve_names(["Jita", "Test Pilot"])

            assert result["systems"][0]["name"] == "Jita"
            assert result["characters"][0]["name"] == "Test Pilot"

    def test_resolve_system_by_name(self):
        from unittest.mock import patch

        from aria_esi.core import ESIClient

        client = ESIClient()

        with patch.object(
            client,
            "resolve_names",
            return_value={"systems": [{"id": 30000142, "name": "Jita"}]},
        ):
            result = client.resolve_system("Jita")

            assert result == 30000142

    def test_resolve_system_by_id(self):
        from aria_esi.core import ESIClient

        client = ESIClient()

        result = client.resolve_system("30000142")

        assert result == 30000142

    def test_resolve_system_not_found(self):
        from unittest.mock import patch

        from aria_esi.core import ESIClient

        client = ESIClient()

        with patch.object(client, "resolve_names", return_value={}):
            result = client.resolve_system("NonexistentSystem")

            assert result is None

    def test_resolve_item(self):
        from unittest.mock import patch

        from aria_esi.core import ESIClient

        client = ESIClient()

        with patch.object(
            client,
            "resolve_names",
            return_value={"inventory_types": [{"id": 34, "name": "Tritanium"}]},
        ):
            type_id, name = client.resolve_item("Tritanium")

            assert type_id == 34
            assert name == "Tritanium"

    def test_resolve_character(self):
        from unittest.mock import patch

        from aria_esi.core import ESIClient

        client = ESIClient()

        with patch.object(
            client,
            "resolve_names",
            return_value={"characters": [{"id": 12345, "name": "Test Pilot"}]},
        ):
            char_id, name = client.resolve_character("Test Pilot")

            assert char_id == 12345
            assert name == "Test Pilot"

    def test_resolve_corporation(self):
        from unittest.mock import patch

        from aria_esi.core import ESIClient

        client = ESIClient()

        with patch.object(
            client,
            "resolve_names",
            return_value={"corporations": [{"id": 98000001, "name": "Test Corp"}]},
        ):
            corp_id, name = client.resolve_corporation("Test Corp")

            assert corp_id == 98000001
            assert name == "Test Corp"

    def test_get_type_name(self, mock_type_response):
        from unittest.mock import patch

        from aria_esi.core import ESIClient

        client = ESIClient()

        with patch.object(client, "get_safe", return_value=mock_type_response):
            result = client.get_type_name(2454)

            assert result == "Hobgoblin I"

    def test_get_system_info(self, mock_system_response):
        from unittest.mock import patch

        from aria_esi.core import ESIClient

        client = ESIClient()

        with patch.object(client, "get_safe", return_value=mock_system_response):
            result = client.get_system_info(30000142)

            assert result["name"] == "Jita"
            assert result["security_status"] > 0.9


class TestESIError:
    """Tests for ESIError exception class."""

    def test_basic_error(self):
        from aria_esi.core import ESIError

        error = ESIError("Test error")

        assert error.message == "Test error"
        assert error.status_code is None
        assert error.response == {}

    def test_error_with_status(self):
        from aria_esi.core import ESIError

        error = ESIError("Not found", status_code=404)

        assert error.status_code == 404

    def test_to_dict(self):
        from aria_esi.core import ESIError

        error = ESIError("Server error", status_code=500)
        result = error.to_dict()

        assert result["error"] == "esi_error"
        assert result["message"] == "Server error"
        assert result["status_code"] == 500
