"""Tests for AssetSignal provider."""

from __future__ import annotations

import pytest

from aria_esi.services.redisq.interest_v2.signals.assets import AssetSignal

from .conftest import MockProcessedKill


class TestAssetSignalScore:
    """Tests for AssetSignal.score() method."""

    @pytest.fixture
    def signal(self) -> AssetSignal:
        """Create an AssetSignal instance."""
        return AssetSignal()

    def test_score_no_assets_configured(self, signal: AssetSignal) -> None:
        """Test scoring with no assets configured returns 0."""
        kill = MockProcessedKill()
        result = signal.score(kill, 30000142, {})
        assert result.score == 0.0
        assert "No asset systems configured" in result.reason
        assert result.prefetch_capable is False

    def test_score_empty_asset_lists(self, signal: AssetSignal) -> None:
        """Test scoring with empty asset lists returns 0."""
        kill = MockProcessedKill()
        config = {"structure_systems": [], "office_systems": []}
        result = signal.score(kill, 30000142, config)
        assert result.score == 0.0

    def test_score_structure_match(
        self, signal: AssetSignal, mock_kill_near_structure: MockProcessedKill
    ) -> None:
        """Test scoring when system has corp structure."""
        config = {"structure_systems": [30000142]}  # Jita
        result = signal.score(mock_kill_near_structure, 30000142, config)
        assert result.score == 1.0  # DEFAULT_STRUCTURE_SCORE
        assert "corp structure" in result.reason.lower()

    def test_score_office_match(
        self, signal: AssetSignal, mock_kill_near_office: MockProcessedKill
    ) -> None:
        """Test scoring when system has corp office."""
        config = {"office_systems": [30002187]}  # Amarr
        result = signal.score(mock_kill_near_office, 30002187, config)
        assert result.score == 0.8  # DEFAULT_OFFICE_SCORE
        assert "corp office" in result.reason.lower()

    def test_score_structure_takes_precedence(self, signal: AssetSignal) -> None:
        """Test structure match takes precedence over office."""
        kill = MockProcessedKill()
        config = {
            "structure_systems": [30000142],
            "office_systems": [30000142],  # Same system
        }
        result = signal.score(kill, 30000142, config)
        assert result.score == 1.0  # Structure score, not office
        assert "structure" in result.reason.lower()

    def test_score_no_asset_in_system(self, signal: AssetSignal) -> None:
        """Test scoring when no assets in kill system."""
        kill = MockProcessedKill()
        config = {
            "structure_systems": [30002187],
            "office_systems": [30002659],
        }
        result = signal.score(kill, 30000142, config)  # Jita - no assets
        assert result.score == 0.0
        assert "No corp assets" in result.reason

    def test_score_custom_structure_score(self, signal: AssetSignal) -> None:
        """Test custom structure score."""
        kill = MockProcessedKill()
        config = {
            "structure_systems": [30000142],
            "structures": {"enabled": True, "score": 0.9},
        }
        result = signal.score(kill, 30000142, config)
        assert result.score == 0.9

    def test_score_custom_office_score(self, signal: AssetSignal) -> None:
        """Test custom office score."""
        kill = MockProcessedKill()
        config = {
            "office_systems": [30000142],
            "offices": {"enabled": True, "score": 0.6},
        }
        result = signal.score(kill, 30000142, config)
        assert result.score == 0.6

    def test_score_structures_disabled(self, signal: AssetSignal) -> None:
        """Test structures disabled falls through to offices."""
        kill = MockProcessedKill()
        config = {
            "structure_systems": [30000142],
            "office_systems": [30000142],
            "structures": {"enabled": False},
        }
        result = signal.score(kill, 30000142, config)
        assert result.score == 0.8  # Office score
        assert "office" in result.reason.lower()

    def test_score_offices_disabled(self, signal: AssetSignal) -> None:
        """Test offices disabled returns 0 when no structure."""
        kill = MockProcessedKill()
        config = {
            "office_systems": [30000142],
            "offices": {"enabled": False},
        }
        result = signal.score(kill, 30000142, config)
        assert result.score == 0.0

    def test_score_both_disabled(self, signal: AssetSignal) -> None:
        """Test both structures and offices disabled."""
        kill = MockProcessedKill()
        config = {
            "structure_systems": [30000142],
            "office_systems": [30000142],
            "structures": {"enabled": False},
            "offices": {"enabled": False},
        }
        result = signal.score(kill, 30000142, config)
        assert result.score == 0.0

    def test_score_raw_value_structure(self, signal: AssetSignal) -> None:
        """Test raw_value for structure match."""
        kill = MockProcessedKill()
        config = {"structure_systems": [30000142]}
        result = signal.score(kill, 30000142, config)
        assert result.raw_value is not None
        assert result.raw_value["asset_type"] == "structure"

    def test_score_raw_value_office(self, signal: AssetSignal) -> None:
        """Test raw_value for office match."""
        kill = MockProcessedKill()
        config = {"office_systems": [30000142]}
        result = signal.score(kill, 30000142, config)
        assert result.raw_value is not None
        assert result.raw_value["asset_type"] == "office"

    def test_score_none_kill(self, signal: AssetSignal) -> None:
        """Test scoring with None kill still checks system."""
        config = {"structure_systems": [30000142]}
        # None kill is OK for assets - only need system_id
        result = signal.score(None, 30000142, config)
        assert result.score == 1.0

    def test_score_multiple_structure_systems(self, signal: AssetSignal) -> None:
        """Test multiple structure systems."""
        kill = MockProcessedKill()
        config = {"structure_systems": [30002187, 30000142, 30002659]}
        result = signal.score(kill, 30000142, config)
        assert result.score == 1.0

    def test_score_set_conversion(self, signal: AssetSignal) -> None:
        """Test system lists are converted to sets for efficient lookup."""
        kill = MockProcessedKill()
        # This should work even with duplicates
        config = {"structure_systems": [30000142, 30000142, 30000142]}
        result = signal.score(kill, 30000142, config)
        assert result.score == 1.0


class TestAssetSignalValidate:
    """Tests for AssetSignal.validate() method."""

    @pytest.fixture
    def signal(self) -> AssetSignal:
        """Create an AssetSignal instance."""
        return AssetSignal()

    def test_validate_empty_config(self, signal: AssetSignal) -> None:
        """Test validation passes for empty config."""
        errors = signal.validate({})
        assert errors == []

    def test_validate_valid_config(self, signal: AssetSignal) -> None:
        """Test validation passes for valid config."""
        config = {
            "structures": {"enabled": True, "score": 0.9},
            "offices": {"enabled": True, "score": 0.7},
            "structure_systems": [30000142, 30002187],
            "office_systems": [30002659],
        }
        errors = signal.validate(config)
        assert errors == []

    def test_validate_structures_not_dict(self, signal: AssetSignal) -> None:
        """Test validation fails when structures config is not a dict."""
        config = {"structures": "enabled"}
        errors = signal.validate(config)
        assert len(errors) == 1
        assert "must be a dictionary" in errors[0]

    def test_validate_offices_not_dict(self, signal: AssetSignal) -> None:
        """Test validation fails when offices config is not a dict."""
        config = {"offices": True}
        errors = signal.validate(config)
        assert len(errors) == 1
        assert "must be a dictionary" in errors[0]

    def test_validate_structure_score_out_of_range(self, signal: AssetSignal) -> None:
        """Test validation fails for structure score outside [0, 1]."""
        config = {"structures": {"score": 1.5}}
        errors = signal.validate(config)
        assert len(errors) == 1
        assert "structures.score" in errors[0]
        assert "between 0 and 1" in errors[0]

    def test_validate_office_score_out_of_range(self, signal: AssetSignal) -> None:
        """Test validation fails for office score outside [0, 1]."""
        config = {"offices": {"score": -0.1}}
        errors = signal.validate(config)
        assert len(errors) == 1
        assert "offices.score" in errors[0]

    def test_validate_score_non_numeric(self, signal: AssetSignal) -> None:
        """Test validation fails for non-numeric score."""
        config = {"structures": {"score": "high"}}
        errors = signal.validate(config)
        assert len(errors) == 1

    def test_validate_both_asset_types(self, signal: AssetSignal) -> None:
        """Test validation checks both asset types."""
        config = {
            "structures": {"score": 1.5},
            "offices": {"score": -0.1},
        }
        errors = signal.validate(config)
        assert len(errors) == 2  # Both invalid


class TestAssetSignalProperties:
    """Tests for AssetSignal class properties."""

    def test_signal_name(self) -> None:
        """Test signal name is correct."""
        signal = AssetSignal()
        assert signal._name == "assets"

    def test_signal_category(self) -> None:
        """Test signal category is correct."""
        signal = AssetSignal()
        assert signal._category == "assets"

    def test_prefetch_capable(self) -> None:
        """Test signal is NOT prefetch capable."""
        signal = AssetSignal()
        assert signal._prefetch_capable is False

    def test_default_scores(self) -> None:
        """Test default score constants."""
        signal = AssetSignal()
        assert signal.DEFAULT_STRUCTURE_SCORE == 1.0
        assert signal.DEFAULT_OFFICE_SCORE == 0.8
