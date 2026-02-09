"""
Tests for Asset Interest Layer.
"""

from __future__ import annotations

import time

from aria_esi.services.redisq.interest.layers import (
    OFFICE_INTEREST,
    STRUCTURE_INTEREST,
    AssetConfig,
    AssetLayer,
)

# =============================================================================
# Configuration Tests
# =============================================================================


class TestAssetConfig:
    """Tests for AssetConfig."""

    def test_from_dict_parses_all_fields(self) -> None:
        """Config parses all fields from dict."""
        data = {
            "structures": True,
            "offices": True,
            "structure_interest": 1.0,
            "office_interest": 0.8,
            "refresh_hours": 4,
        }

        config = AssetConfig.from_dict(data)

        assert config.structures is True
        assert config.offices is True
        assert config.structure_interest == 1.0
        assert config.office_interest == 0.8
        assert config.refresh_hours == 4

    def test_default_config(self) -> None:
        """Default config has sensible values."""
        config = AssetConfig.from_dict(None)

        assert config.structures is True
        assert config.offices is True
        assert config.structure_interest == STRUCTURE_INTEREST
        assert config.office_interest == OFFICE_INTEREST


# =============================================================================
# Scoring Tests
# =============================================================================


class TestAssetLayerScoring:
    """Tests for asset layer scoring."""

    def test_structure_system_returns_1_0(self) -> None:
        """System with structure returns 1.0 interest."""
        layer = AssetLayer.from_config(AssetConfig())
        layer.add_structure(30000142)

        score = layer.score_system(30000142)

        assert score.score == STRUCTURE_INTEREST
        assert score.score == 1.0
        assert "structure" in score.reason

    def test_office_system_returns_0_8(self) -> None:
        """System with office returns 0.8 interest."""
        layer = AssetLayer.from_config(AssetConfig())
        layer.add_office(30000142)

        score = layer.score_system(30000142)

        assert score.score == OFFICE_INTEREST
        assert score.score == 0.8
        assert "office" in score.reason

    def test_unknown_system_returns_zero(self) -> None:
        """System without assets returns 0."""
        layer = AssetLayer.from_config(AssetConfig())

        score = layer.score_system(30000142)

        assert score.score == 0.0
        assert score.reason is None

    def test_structure_overrides_office(self) -> None:
        """Structure interest takes precedence over office."""
        layer = AssetLayer.from_config(AssetConfig())

        # Add office first, then structure in same system
        layer.add_office(30000142)
        layer.add_structure(30000142)

        score = layer.score_system(30000142)

        assert score.score == STRUCTURE_INTEREST
        assert "structure" in score.reason

    def test_office_doesnt_override_structure(self) -> None:
        """Adding office doesn't downgrade existing structure."""
        layer = AssetLayer.from_config(AssetConfig())

        # Add structure first, then try to add office
        layer.add_structure(30000142)
        layer.add_office(30000142)

        score = layer.score_system(30000142)

        assert score.score == STRUCTURE_INTEREST


# =============================================================================
# Asset Management Tests
# =============================================================================


class TestAssetManagement:
    """Tests for adding/removing assets."""

    def test_add_and_remove_structure(self) -> None:
        """Can add and remove structure."""
        layer = AssetLayer.from_config(AssetConfig())

        layer.add_structure(30000142)
        assert layer.score_system(30000142).score == STRUCTURE_INTEREST

        layer.remove_asset(30000142)
        assert layer.score_system(30000142).score == 0.0

    def test_get_structure_systems(self) -> None:
        """Can list all structure systems."""
        layer = AssetLayer.from_config(AssetConfig())
        layer.add_structure(30000142)
        layer.add_structure(30002537)
        layer.add_office(30000144)

        structures = layer.get_structure_systems()

        assert 30000142 in structures
        assert 30002537 in structures
        assert 30000144 not in structures  # It's an office

    def test_get_office_systems(self) -> None:
        """Can list all office systems."""
        layer = AssetLayer.from_config(AssetConfig())
        layer.add_structure(30000142)
        layer.add_office(30000144)
        layer.add_office(30002538)

        offices = layer.get_office_systems()

        assert 30000144 in offices
        assert 30002538 in offices
        assert 30000142 not in offices  # It's a structure

    def test_clear_assets(self) -> None:
        """Can clear all assets."""
        layer = AssetLayer.from_config(AssetConfig())
        layer.add_structure(30000142)
        layer.add_office(30000144)

        assert layer.total_systems == 2

        layer.clear_assets()

        assert layer.total_systems == 0

    def test_config_disables_structures(self) -> None:
        """Config can disable structure tracking."""
        config = AssetConfig(structures=False, offices=True)
        layer = AssetLayer.from_config(config)

        layer.add_structure(30000142)  # Should be ignored

        assert layer.total_systems == 0

    def test_config_disables_offices(self) -> None:
        """Config can disable office tracking."""
        config = AssetConfig(structures=True, offices=False)
        layer = AssetLayer.from_config(config)

        layer.add_office(30000142)  # Should be ignored

        assert layer.total_systems == 0


# =============================================================================
# Refresh Tests
# =============================================================================


class TestRefresh:
    """Tests for refresh functionality."""

    def test_needs_refresh_initially(self) -> None:
        """New layer needs refresh."""
        layer = AssetLayer.from_config(AssetConfig())

        assert layer.needs_refresh() is True

    def test_needs_refresh_after_interval(self) -> None:
        """Layer needs refresh after interval."""
        config = AssetConfig(refresh_hours=1)
        layer = AssetLayer.from_config(config)

        # Simulate recent refresh
        layer._last_refresh = time.time()
        assert layer.needs_refresh() is False

        # Simulate old refresh
        layer._last_refresh = time.time() - 3700  # Just over 1 hour
        assert layer.needs_refresh() is True


# =============================================================================
# Serialization Tests
# =============================================================================


class TestSerialization:
    """Tests for serialization."""

    def test_to_dict_includes_assets(self) -> None:
        """to_dict includes asset data."""
        layer = AssetLayer.from_config(AssetConfig())
        layer.add_structure(30000142)
        layer.add_office(30000144)

        data = layer.to_dict()

        assert "30000142" in data["asset_systems"]
        assert data["asset_systems"]["30000142"] == "structure"
        assert "30000144" in data["asset_systems"]
        assert data["asset_systems"]["30000144"] == "office"

    def test_from_dict_restores_assets(self) -> None:
        """from_dict restores asset data."""
        layer = AssetLayer.from_config(AssetConfig())
        layer.add_structure(30000142)
        layer.add_office(30000144)

        data = layer.to_dict()
        restored = AssetLayer.from_dict(data)

        assert restored.score_system(30000142).score == STRUCTURE_INTEREST
        assert restored.score_system(30000144).score == OFFICE_INTEREST
