"""Tests for sovereignty ESI fetcher."""

import pytest

from aria_esi.services.sovereignty.fetcher import (
    fetch_sovereignty_map,
    fetch_alliance_info,
    fetch_alliances_batch,
    fetch_sovereignty_map_sync,
    fetch_alliances_batch_sync,
    ESI_BASE_URL,
    SOV_MAP_ENDPOINT,
    ALLIANCE_ENDPOINT,
)


@pytest.fixture
def mock_sov_map_response():
    """Mock sovereignty map response from ESI."""
    return [
        {
            "system_id": 30004759,
            "alliance_id": 1354830081,
            "corporation_id": 98169165,
        },
        {
            "system_id": 30003135,
            "faction_id": 500010,
        },
        {
            "system_id": 30000001,
            "alliance_id": 99005338,
        },
    ]


@pytest.fixture
def mock_alliance_response():
    """Mock alliance info response from ESI."""
    return {
        "name": "Goonswarm Federation",
        "ticker": "CONDI",
        "creator_corporation_id": 667531913,
        "creator_id": 443630591,
        "date_founded": "2010-06-01T00:00:00Z",
        "executor_corporation_id": 98169165,
    }


class TestFetchSovereigntyMap:
    """Tests for fetch_sovereignty_map function."""

    @pytest.mark.asyncio
    async def test_fetch_success(self, mock_sov_map_response, httpx_mock):
        """Test successful sovereignty map fetch."""
        url = f"{ESI_BASE_URL}{SOV_MAP_ENDPOINT}?datasource=tranquility"
        httpx_mock.add_response(url=url, json=mock_sov_map_response)

        result = await fetch_sovereignty_map()

        assert len(result) == 3
        assert result[0]["system_id"] == 30004759
        assert result[0]["alliance_id"] == 1354830081
        assert result[1]["faction_id"] == 500010

    @pytest.mark.asyncio
    async def test_fetch_http_error(self, httpx_mock):
        """Test handling of HTTP errors."""
        import httpx

        url = f"{ESI_BASE_URL}{SOV_MAP_ENDPOINT}?datasource=tranquility"
        httpx_mock.add_response(url=url, status_code=500)

        with pytest.raises(httpx.HTTPStatusError):
            await fetch_sovereignty_map()


class TestFetchAllianceInfo:
    """Tests for fetch_alliance_info function."""

    @pytest.mark.asyncio
    async def test_fetch_success(self, mock_alliance_response, httpx_mock):
        """Test successful alliance info fetch."""
        alliance_id = 1354830081
        url = f"{ESI_BASE_URL}{ALLIANCE_ENDPOINT.format(alliance_id=alliance_id)}?datasource=tranquility"
        httpx_mock.add_response(url=url, json=mock_alliance_response)

        result = await fetch_alliance_info(alliance_id)

        assert result is not None
        assert result["name"] == "Goonswarm Federation"
        assert result["ticker"] == "CONDI"

    @pytest.mark.asyncio
    async def test_fetch_not_found(self, httpx_mock):
        """Test handling of 404 response."""
        alliance_id = 99999999
        url = f"{ESI_BASE_URL}{ALLIANCE_ENDPOINT.format(alliance_id=alliance_id)}?datasource=tranquility"
        httpx_mock.add_response(url=url, status_code=404)

        result = await fetch_alliance_info(alliance_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_error(self, httpx_mock):
        """Test handling of other errors."""
        alliance_id = 1354830081
        url = f"{ESI_BASE_URL}{ALLIANCE_ENDPOINT.format(alliance_id=alliance_id)}?datasource=tranquility"
        httpx_mock.add_response(url=url, status_code=500)

        result = await fetch_alliance_info(alliance_id)
        assert result is None


class TestFetchAlliancesBatch:
    """Tests for fetch_alliances_batch function."""

    @pytest.mark.asyncio
    async def test_fetch_batch_success(self, mock_alliance_response, httpx_mock):
        """Test successful batch fetch of alliances."""
        alliance_ids = [1000001, 1000002, 1000003]

        for aid in alliance_ids:
            url = f"{ESI_BASE_URL}{ALLIANCE_ENDPOINT.format(alliance_id=aid)}?datasource=tranquility"
            response = {**mock_alliance_response, "ticker": f"A{aid}"}
            httpx_mock.add_response(url=url, json=response)

        results = await fetch_alliances_batch(alliance_ids)

        assert len(results) == 3
        assert all(aid in results for aid in alliance_ids)

    @pytest.mark.asyncio
    async def test_fetch_batch_partial_failure(self, mock_alliance_response, httpx_mock):
        """Test batch fetch with some failures."""
        alliance_ids = [1000001, 1000002]

        # First succeeds
        url1 = f"{ESI_BASE_URL}{ALLIANCE_ENDPOINT.format(alliance_id=1000001)}?datasource=tranquility"
        httpx_mock.add_response(url=url1, json=mock_alliance_response)

        # Second fails
        url2 = f"{ESI_BASE_URL}{ALLIANCE_ENDPOINT.format(alliance_id=1000002)}?datasource=tranquility"
        httpx_mock.add_response(url=url2, status_code=500)

        results = await fetch_alliances_batch(alliance_ids)

        assert len(results) == 1
        assert 1000001 in results

    @pytest.mark.asyncio
    async def test_fetch_batch_empty(self, httpx_mock):
        """Test batch fetch with empty list."""
        results = await fetch_alliances_batch([])
        assert results == {}

    @pytest.mark.asyncio
    async def test_fetch_batch_deduplicates(self, mock_alliance_response, httpx_mock):
        """Test that batch fetch deduplicates alliance IDs."""
        alliance_ids = [1000001, 1000001, 1000001]

        url = f"{ESI_BASE_URL}{ALLIANCE_ENDPOINT.format(alliance_id=1000001)}?datasource=tranquility"
        httpx_mock.add_response(url=url, json=mock_alliance_response)

        results = await fetch_alliances_batch(alliance_ids)

        # Should only have one result despite three IDs
        assert len(results) == 1
        # Should only have made one request
        assert len(httpx_mock.get_requests()) == 1


class TestSyncWrappers:
    """Tests for synchronous wrapper functions."""

    def test_fetch_sovereignty_map_sync(self, mock_sov_map_response, httpx_mock):
        """Test synchronous sovereignty map fetch."""
        url = f"{ESI_BASE_URL}{SOV_MAP_ENDPOINT}?datasource=tranquility"
        httpx_mock.add_response(url=url, json=mock_sov_map_response)

        result = fetch_sovereignty_map_sync()
        assert len(result) == 3

    def test_fetch_alliances_batch_sync(self, mock_alliance_response, httpx_mock):
        """Test synchronous batch alliance fetch."""
        alliance_ids = [1000001]

        url = f"{ESI_BASE_URL}{ALLIANCE_ENDPOINT.format(alliance_id=1000001)}?datasource=tranquility"
        httpx_mock.add_response(url=url, json=mock_alliance_response)

        results = fetch_alliances_batch_sync(alliance_ids)
        assert len(results) == 1
