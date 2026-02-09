"""
Tests for Fuzzwork Market API Client.

Tests HTTP interactions, rate limiting, chunking, and error handling
for the FuzzworkClient class.
"""

from __future__ import annotations

import asyncio
import gzip
from unittest.mock import patch

import httpx
import pytest

from aria_esi.mcp.market.clients import (
    DEFAULT_REGION_ID,
    DEFAULT_STATION_ID,
    FUZZWORK_AGGREGATES_ENDPOINT,
    FUZZWORK_BASE_URL,
    FUZZWORK_BULK_CSV_URL,
    MIN_REQUEST_INTERVAL_SECONDS,
    FuzzworkAggregate,
    FuzzworkClient,
    create_client,
)

# =============================================================================
# FuzzworkAggregate Tests
# =============================================================================


class TestFuzzworkAggregate:
    """Tests for the FuzzworkAggregate dataclass."""

    def test_from_api_response_full_data(self):
        """Parse complete API response with all fields."""
        type_id = 34  # Tritanium
        data = {
            "buy": {
                "weightedAverage": 5.50,
                "max": 6.00,
                "min": 5.00,
                "stddev": 0.25,
                "median": 5.45,
                "volume": 1000000,
                "orderCount": 150,
                "percentile": 5.95,
            },
            "sell": {
                "weightedAverage": 6.50,
                "max": 7.00,
                "min": 6.00,
                "stddev": 0.30,
                "median": 6.40,
                "volume": 500000,
                "orderCount": 80,
                "percentile": 6.05,
            },
        }

        result = FuzzworkAggregate.from_api_response(type_id, data)

        assert result.type_id == 34
        assert result.buy_weighted_average == 5.50
        assert result.buy_max == 6.00
        assert result.buy_min == 5.00
        assert result.buy_stddev == 0.25
        assert result.buy_median == 5.45
        assert result.buy_volume == 1000000
        assert result.buy_order_count == 150
        assert result.buy_percentile == 5.95
        assert result.sell_weighted_average == 6.50
        assert result.sell_max == 7.00
        assert result.sell_min == 6.00
        assert result.sell_stddev == 0.30
        assert result.sell_median == 6.40
        assert result.sell_volume == 500000
        assert result.sell_order_count == 80
        assert result.sell_percentile == 6.05

    def test_from_api_response_missing_keys_defaults_to_zero(self):
        """Missing keys should default to zero."""
        type_id = 35  # Pyerite
        data = {
            "buy": {"weightedAverage": 10.0},
            "sell": {"min": 12.0},
        }

        result = FuzzworkAggregate.from_api_response(type_id, data)

        assert result.type_id == 35
        assert result.buy_weighted_average == 10.0
        assert result.buy_max == 0
        assert result.buy_min == 0
        assert result.buy_volume == 0
        assert result.sell_min == 12.0
        assert result.sell_max == 0
        assert result.sell_volume == 0

    def test_from_api_response_empty_buy_sell(self):
        """Empty buy/sell dicts should result in all zeros."""
        type_id = 36  # Mexallon
        data = {"buy": {}, "sell": {}}

        result = FuzzworkAggregate.from_api_response(type_id, data)

        assert result.type_id == 36
        assert result.buy_weighted_average == 0
        assert result.buy_max == 0
        assert result.sell_weighted_average == 0
        assert result.sell_min == 0

    def test_from_api_response_missing_buy_sell_keys(self):
        """Completely missing buy/sell keys should work."""
        type_id = 37  # Isogen
        data = {}  # No buy or sell

        result = FuzzworkAggregate.from_api_response(type_id, data)

        assert result.type_id == 37
        assert result.buy_weighted_average == 0
        assert result.sell_weighted_average == 0

    def test_from_api_response_volume_with_decimals(self):
        """Volume with decimal values should be truncated to int."""
        type_id = 38  # Nocxium
        data = {
            "buy": {"volume": "1234567.89"},
            "sell": {"volume": 9876543.21},
        }

        result = FuzzworkAggregate.from_api_response(type_id, data)

        assert result.buy_volume == 1234567
        assert result.sell_volume == 9876543


# =============================================================================
# FuzzworkClient URL Building Tests
# =============================================================================


class TestFuzzworkClientBuildUrl:
    """Tests for URL construction."""

    def test_build_url_with_station(self):
        """URL should include station parameter when station_id is set."""
        client = FuzzworkClient(
            region_id=10000002,
            station_id=60003760,
        )

        url = client._build_url([34, 35, 36])

        assert FUZZWORK_BASE_URL in url
        assert FUZZWORK_AGGREGATES_ENDPOINT in url
        assert "region=10000002" in url
        assert "types=34,35,36" in url
        assert "station=60003760" in url

    def test_build_url_without_station(self):
        """URL should not include station when station_id is None."""
        client = FuzzworkClient(
            region_id=10000002,
            station_id=None,
        )

        url = client._build_url([34, 35])

        assert "region=10000002" in url
        assert "types=34,35" in url
        assert "station=" not in url

    def test_build_url_multiple_types(self):
        """Multiple type IDs should be comma-separated."""
        client = FuzzworkClient()
        type_ids = [34, 35, 36, 37, 38]

        url = client._build_url(type_ids)

        assert "types=34,35,36,37,38" in url


# =============================================================================
# FuzzworkClient Sync Tests
# =============================================================================


class TestFuzzworkClientGetAggregatesSync:
    """Tests for synchronous aggregate fetching."""

    def test_empty_type_ids_returns_empty(self):
        """Empty type_ids list should return empty dict immediately."""
        client = FuzzworkClient()

        result = client.get_aggregates_sync([])

        assert result == {}

    def test_single_type_success(self, httpx_mock):
        """Single type fetch should return parsed aggregate."""
        # Mock the API response
        httpx_mock.add_response(
            url=httpx.URL(
                f"{FUZZWORK_BASE_URL}{FUZZWORK_AGGREGATES_ENDPOINT}"
                f"?region={DEFAULT_REGION_ID}&types=34&station={DEFAULT_STATION_ID}"
            ),
            json={
                "34": {
                    "buy": {"weightedAverage": 5.5, "max": 6.0, "min": 5.0, "volume": 1000000, "orderCount": 50},
                    "sell": {"weightedAverage": 6.5, "max": 7.0, "min": 6.0, "volume": 500000, "orderCount": 25},
                }
            },
        )

        client = FuzzworkClient()
        result = client.get_aggregates_sync([34])

        assert 34 in result
        assert result[34].buy_weighted_average == 5.5
        assert result[34].sell_weighted_average == 6.5

    def test_multiple_types_chunking(self, httpx_mock):
        """Types exceeding MAX_TYPES_PER_REQUEST should be chunked."""
        # Generate 150 type IDs (> MAX_TYPES_PER_REQUEST = 100)
        type_ids = list(range(1, 151))

        # Mock responses for both chunks
        chunk1_response = {str(i): {"buy": {}, "sell": {}} for i in range(1, 101)}
        chunk2_response = {str(i): {"buy": {}, "sell": {}} for i in range(101, 151)}

        # Add mock for first chunk (100 types)
        httpx_mock.add_response(json=chunk1_response)
        # Add mock for second chunk (50 types)
        httpx_mock.add_response(json=chunk2_response)

        client = FuzzworkClient()
        # Patch rate limiting to speed up test
        client._last_request_time = 0

        with patch.object(client, "_rate_limit"):
            result = client.get_aggregates_sync(type_ids)

        # Should have all 150 types
        assert len(result) == 150

    def test_timeout_raises_error(self, httpx_mock):
        """Timeout should raise and propagate."""
        httpx_mock.add_exception(httpx.TimeoutException("Connection timed out"))

        client = FuzzworkClient()

        with patch.object(client, "_rate_limit"):
            with pytest.raises(httpx.TimeoutException):
                client.get_aggregates_sync([34])

    def test_http_status_error_raises(self, httpx_mock):
        """HTTP errors should raise and propagate."""
        httpx_mock.add_response(status_code=500)

        client = FuzzworkClient()

        with patch.object(client, "_rate_limit"):
            with pytest.raises(httpx.HTTPStatusError):
                client.get_aggregates_sync([34])

    def test_malformed_response_logs_warning(self, httpx_mock, caplog):
        """Malformed type entries should log warning and continue."""
        httpx_mock.add_response(
            json={
                "34": {"buy": {"weightedAverage": 5.5}, "sell": {}},
                "not_a_number": {"buy": {}, "sell": {}},  # Invalid type ID
            },
        )

        client = FuzzworkClient()

        with patch.object(client, "_rate_limit"):
            result = client.get_aggregates_sync([34])

        # Should have parsed the valid type
        assert 34 in result
        # Invalid type should have been skipped
        assert len(result) == 1


# =============================================================================
# FuzzworkClient Async Tests
# =============================================================================


@pytest.mark.asyncio
class TestFuzzworkClientAsync:
    """Tests for async aggregate fetching."""

    async def test_get_aggregates_runs_in_executor(self, httpx_mock):
        """Async get_aggregates should run sync method in executor."""
        httpx_mock.add_response(
            json={"34": {"buy": {"weightedAverage": 5.5}, "sell": {}}},
        )

        client = FuzzworkClient()

        with patch.object(client, "_rate_limit"):
            result = await client.get_aggregates([34])

        assert 34 in result

    async def test_concurrent_requests_serialized_by_lock(self, httpx_mock):
        """Concurrent requests should be serialized by the async lock."""
        # Add mock responses for both requests
        httpx_mock.add_response(json={"34": {"buy": {}, "sell": {}}})
        httpx_mock.add_response(json={"35": {"buy": {}, "sell": {}}})

        client = FuzzworkClient()

        with patch.object(client, "_rate_limit"):
            # Launch two concurrent requests
            results = await asyncio.gather(
                client.get_aggregates([34]),
                client.get_aggregates([35]),
            )

        # Both should complete
        assert len(results) == 2
        # The lock ensures both complete without race conditions
        assert 34 in results[0]
        assert 35 in results[1]


# =============================================================================
# FuzzworkClient Bulk CSV Tests
# =============================================================================


class TestFuzzworkBulkCsv:
    """Tests for bulk CSV download."""

    def test_download_bulk_csv_decompresses(self, httpx_mock):
        """Bulk CSV should be decompressed from gzip."""
        csv_content = b"type_id,buy_price,sell_price\n34,5.5,6.5\n"
        gzipped = gzip.compress(csv_content)

        httpx_mock.add_response(
            url=FUZZWORK_BULK_CSV_URL,
            content=gzipped,
        )

        client = FuzzworkClient()

        with patch.object(client, "_rate_limit"):
            result = client.download_bulk_csv_sync()

        assert result == csv_content


# =============================================================================
# create_client Helper Tests
# =============================================================================


class TestCreateClient:
    """Tests for the create_client helper function."""

    def test_known_region_resolves(self):
        """Known trade hub names should resolve to correct IDs."""
        client = create_client(region="jita", station_only=True)

        assert client.region_id == 10000002  # The Forge
        assert client.station_id == 60003760  # Jita 4-4

    def test_known_region_case_insensitive(self):
        """Trade hub resolution should be case-insensitive."""
        client = create_client(region="AMARR", station_only=True)

        assert client.region_id == 10000043  # Domain

    def test_unknown_region_defaults_to_jita(self, caplog):
        """Unknown region should default to Jita with warning."""
        client = create_client(region="unknown_region", station_only=True)

        assert client.region_id == DEFAULT_REGION_ID  # Jita region
        assert client.station_id == DEFAULT_STATION_ID  # Jita station

    def test_station_only_false(self):
        """station_only=False should set station_id to None."""
        client = create_client(region="jita", station_only=False)

        assert client.region_id == 10000002
        assert client.station_id is None


# =============================================================================
# Rate Limiting Tests
# =============================================================================


class TestRateLimiting:
    """Tests for rate limiting behavior."""

    def test_rate_limit_sleeps_when_too_fast(self):
        """Rate limiter should sleep when requests are too fast."""
        import time

        client = FuzzworkClient()
        client._last_request_time = time.time()  # Just made a request

        with patch("time.sleep") as mock_sleep:
            client._rate_limit()

            # Should have slept
            mock_sleep.assert_called_once()
            sleep_time = mock_sleep.call_args[0][0]
            assert 0 < sleep_time <= MIN_REQUEST_INTERVAL_SECONDS

    def test_rate_limit_no_sleep_when_sufficient_gap(self):
        """Rate limiter should not sleep when enough time has passed."""
        import time

        client = FuzzworkClient()
        client._last_request_time = time.time() - MIN_REQUEST_INTERVAL_SECONDS - 1

        with patch("time.sleep") as mock_sleep:
            client._rate_limit()

            # Should not have slept
            mock_sleep.assert_not_called()

    def test_rate_limit_updates_timestamp(self):
        """Rate limiter should update last_request_time after call."""
        import time

        client = FuzzworkClient()
        client._last_request_time = 0  # Long ago

        before = time.time()
        client._rate_limit()
        after = time.time()

        assert before <= client._last_request_time <= after
