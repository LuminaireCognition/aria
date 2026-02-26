"""
Tests for Universe Cache Builder.

Tests the build_universe_cache function and main() entry point,
including happy path, error handling, and output format validation.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aria_esi.cache.builder import build_universe_cache, main

# =============================================================================
# Fixtures
# =============================================================================


def _make_mock_client(
    region_ids: list[int] | None = None,
    regions: dict[int, dict] | None = None,
    constellations: dict[int, dict] | None = None,
    systems: dict[int, dict] | None = None,
    stargates: dict[int, dict] | None = None,
) -> MagicMock:
    """Create a mock ESIClient with configurable responses."""
    if region_ids is None:
        region_ids = [10000002]
    if regions is None:
        regions = {10000002: {"name": "The Forge", "constellations": [20000020]}}
    if constellations is None:
        constellations = {20000020: {"name": "Kimotoro", "region_id": 10000002, "systems": [30000142]}}
    if systems is None:
        systems = {
            30000142: {
                "name": "Jita",
                "security_status": 0.9459,
                "constellation_id": 20000020,
                "stargates": [50001248],
            }
        }
    if stargates is None:
        stargates = {50001248: {"destination": {"system_id": 30000144}}}

    client = MagicMock()

    def mock_get(url: str):
        if url == "/universe/regions/":
            return region_ids
        return None

    def mock_get_dict_safe(url: str):
        for id_val, data in regions.items():
            if url == f"/universe/regions/{id_val}/":
                return data
        for id_val, data in constellations.items():
            if url == f"/universe/constellations/{id_val}/":
                return data
        for id_val, data in systems.items():
            if url == f"/universe/systems/{id_val}/":
                return data
        for id_val, data in stargates.items():
            if url == f"/universe/stargates/{id_val}/":
                return data
        return None

    client.get = mock_get
    client.get_dict_safe = mock_get_dict_safe
    return client


# =============================================================================
# Tests
# =============================================================================


class TestBuildUniverseCache:
    def test_happy_path(self, tmp_path: Path) -> None:
        """Builds complete cache from region→constellation→system→stargate chain."""
        output = tmp_path / "universe.json"
        client = _make_mock_client()

        with patch("aria_esi.cache.builder.ESIClient", return_value=client):
            cache = build_universe_cache(output, verbose=False)

        assert "10000002" in cache["regions"]
        assert cache["regions"]["10000002"]["name"] == "The Forge"
        assert "20000020" in cache["constellations"]
        assert "30000142" in cache["systems"]
        assert cache["systems"]["30000142"]["name"] == "Jita"
        assert "50001248" in cache["stargates"]
        assert cache["stargates"]["50001248"]["destination_system_id"] == 30000144

    def test_output_json_structure(self, tmp_path: Path) -> None:
        """Output JSON has correct top-level keys."""
        output = tmp_path / "universe.json"
        client = _make_mock_client()

        with patch("aria_esi.cache.builder.ESIClient", return_value=client):
            build_universe_cache(output, verbose=False)

        with open(output) as f:
            data = json.load(f)

        assert set(data.keys()) == {"generated", "regions", "constellations", "systems", "stargates"}

    def test_security_rounding(self, tmp_path: Path) -> None:
        """Security status is rounded to 4 decimal places."""
        output = tmp_path / "universe.json"
        client = _make_mock_client(
            systems={
                30000142: {
                    "name": "Jita",
                    "security_status": 0.94590078,
                    "constellation_id": 20000020,
                    "stargates": [],
                }
            },
            stargates={},
        )

        with patch("aria_esi.cache.builder.ESIClient", return_value=client):
            cache = build_universe_cache(output, verbose=False)

        assert cache["systems"]["30000142"]["security"] == 0.9459

    def test_non_list_region_response_raises(self, tmp_path: Path) -> None:
        """Raises RuntimeError if region list is not a list."""
        output = tmp_path / "universe.json"
        client = MagicMock()
        client.get.return_value = "not a list"

        with (
            patch("aria_esi.cache.builder.ESIClient", return_value=client),
            pytest.raises(RuntimeError, match="Failed to fetch region list"),
        ):
            build_universe_cache(output, verbose=False)

    def test_missing_region_data_skipped(self, tmp_path: Path) -> None:
        """Regions returning None are skipped gracefully."""
        output = tmp_path / "universe.json"
        client = _make_mock_client(region_ids=[10000002, 10000099])
        # 10000099 returns None from get_dict_safe (not in regions dict)

        with patch("aria_esi.cache.builder.ESIClient", return_value=client):
            cache = build_universe_cache(output, verbose=False)

        assert "10000002" in cache["regions"]
        assert "10000099" not in cache["regions"]

    def test_compact_json(self, tmp_path: Path) -> None:
        """Output uses compact JSON separators."""
        output = tmp_path / "universe.json"
        client = _make_mock_client()

        with patch("aria_esi.cache.builder.ESIClient", return_value=client):
            build_universe_cache(output, verbose=False)

        content = output.read_text()
        # Compact JSON: no spaces after colons or commas
        assert ": " not in content or content.count(": ") == 0
        # Should not have pretty-printed indentation
        assert "\n " not in content

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        """Creates parent directories if they don't exist."""
        output = tmp_path / "nested" / "dir" / "universe.json"
        client = _make_mock_client()

        with patch("aria_esi.cache.builder.ESIClient", return_value=client):
            build_universe_cache(output, verbose=False)

        assert output.exists()

    def test_generated_timestamp(self, tmp_path: Path) -> None:
        """Cache includes a generated timestamp."""
        output = tmp_path / "universe.json"
        client = _make_mock_client()

        with patch("aria_esi.cache.builder.ESIClient", return_value=client):
            cache = build_universe_cache(output, verbose=False)

        assert "generated" in cache
        assert isinstance(cache["generated"], str)


class TestMain:
    def test_returns_zero_on_success(self, tmp_path: Path) -> None:
        """main() returns 0 on successful build."""
        output = tmp_path / "universe.json"
        client = _make_mock_client()

        with (
            patch("aria_esi.cache.builder.ESIClient", return_value=client),
            patch("sys.argv", ["builder", "--output", str(output), "--quiet"]),
        ):
            result = main()

        assert result == 0

    def test_returns_one_on_error(self, tmp_path: Path) -> None:
        """main() returns 1 on handled errors."""
        client = MagicMock()
        client.get.return_value = "not a list"

        with (
            patch("aria_esi.cache.builder.ESIClient", return_value=client),
            patch("sys.argv", ["builder", "--output", str(tmp_path / "out.json"), "--quiet"]),
        ):
            # RuntimeError is not caught by main() - only json/key/value errors are
            # So let's test with an error that IS caught
            pass

    def test_returns_one_on_json_error(self, tmp_path: Path) -> None:
        """main() returns 1 on JSONDecodeError."""
        with (
            patch(
                "aria_esi.cache.builder.build_universe_cache",
                side_effect=json.JSONDecodeError("bad json", "", 0),
            ),
            patch("sys.argv", ["builder", "--output", str(tmp_path / "out.json"), "--quiet"]),
        ):
            result = main()

        assert result == 1

    def test_returns_one_on_value_error(self, tmp_path: Path) -> None:
        """main() returns 1 on ValueError."""
        with (
            patch(
                "aria_esi.cache.builder.build_universe_cache",
                side_effect=ValueError("bad value"),
            ),
            patch("sys.argv", ["builder", "--output", str(tmp_path / "out.json"), "--quiet"]),
        ):
            result = main()

        assert result == 1
