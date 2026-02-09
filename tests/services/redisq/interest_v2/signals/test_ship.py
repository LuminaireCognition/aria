"""Tests for ShipSignal provider."""

from __future__ import annotations

import pytest

from aria_esi.services.redisq.interest_v2.signals.ship import SHIP_CLASSES, ShipSignal

from .conftest import MockProcessedKill


class TestShipSignalScore:
    """Tests for ShipSignal.score() method."""

    @pytest.fixture
    def signal(self) -> ShipSignal:
        """Create a ShipSignal instance."""
        return ShipSignal()

    def test_score_none_kill(self, signal: ShipSignal) -> None:
        """Test scoring with None kill returns 0."""
        result = signal.score(None, 30000142, {})
        assert result.score == 0.0
        assert result.signal == "ship"
        assert result.prefetch_capable is True
        assert "No kill data" in result.reason

    def test_score_unknown_ship_type(self, signal: ShipSignal) -> None:
        """Test kill with unknown ship type returns default score."""
        kill = MockProcessedKill(victim_ship_type_id=None)
        result = signal.score(kill, 30000142, {})
        assert result.score == 0.5  # DEFAULT_SCORE
        assert "Unknown ship type" in result.reason

    def test_score_default_no_match(self, signal: ShipSignal) -> None:
        """Test scoring with no config returns default score."""
        kill = MockProcessedKill(victim_ship_type_id=24690)  # Vexor - not in any class
        result = signal.score(kill, 30000142, {})
        assert result.score == 0.5  # DEFAULT_SCORE
        assert "No ship class match" in result.reason

    def test_score_prefer_freighter(
        self, signal: ShipSignal, mock_kill_freighter: MockProcessedKill
    ) -> None:
        """Test preferred ship class scores high."""
        config = {"prefer": ["freighter"]}
        result = signal.score(mock_kill_freighter, 30000142, config)
        assert result.score == 1.0  # DEFAULT_PREFER_SCORE
        assert "Preferred ship class: freighter" in result.reason

    def test_score_prefer_with_custom_score(
        self, signal: ShipSignal, mock_kill_freighter: MockProcessedKill
    ) -> None:
        """Test preferred ship class with custom score."""
        config = {"prefer": ["freighter"], "prefer_score": 0.8}
        result = signal.score(mock_kill_freighter, 30000142, config)
        assert result.score == 0.8
        assert "Preferred" in result.reason

    def test_score_exclude_capsule(
        self, signal: ShipSignal, mock_kill_pod: MockProcessedKill
    ) -> None:
        """Test excluded ship class scores low."""
        config = {"exclude": ["capsule"]}
        result = signal.score(mock_kill_pod, 30000142, config)
        assert result.score == 0.0  # DEFAULT_EXCLUDE_SCORE
        assert "Excluded ship class: capsule" in result.reason

    def test_score_exclude_with_custom_score(
        self, signal: ShipSignal, mock_kill_pod: MockProcessedKill
    ) -> None:
        """Test excluded ship class with custom score."""
        config = {"exclude": ["capsule"], "exclude_score": 0.1}
        result = signal.score(mock_kill_pod, 30000142, config)
        assert result.score == 0.1

    def test_score_exclude_takes_precedence(
        self, signal: ShipSignal, mock_kill_freighter: MockProcessedKill
    ) -> None:
        """Test exclusion takes precedence over preference."""
        config = {"prefer": ["freighter"], "exclude": ["freighter"]}
        result = signal.score(mock_kill_freighter, 30000142, config)
        assert result.score == 0.0
        assert "Excluded" in result.reason

    def test_score_capitals_only_carrier(
        self, signal: ShipSignal, mock_kill_capital: MockProcessedKill
    ) -> None:
        """Test capitals_only matches carrier."""
        config = {"capitals_only": True}
        result = signal.score(mock_kill_capital, 30000142, config)
        assert result.score == 1.0  # DEFAULT_PREFER_SCORE
        assert "Capital ship" in result.reason

    def test_score_capitals_only_rorqual(
        self, signal: ShipSignal, mock_kill_rorqual: MockProcessedKill
    ) -> None:
        """Test capitals_only matches Rorqual."""
        config = {"capitals_only": True}
        result = signal.score(mock_kill_rorqual, 30000142, config)
        assert result.score == 1.0
        assert "rorqual" in result.reason.lower()

    def test_score_capitals_only_non_capital(self, signal: ShipSignal) -> None:
        """Test capitals_only rejects non-capital ships."""
        kill = MockProcessedKill(victim_ship_type_id=24690)  # Vexor
        config = {"capitals_only": True}
        result = signal.score(kill, 30000142, config)
        assert result.score == 0.0
        assert "Not a capital" in result.reason

    def test_score_custom_default_score(self, signal: ShipSignal) -> None:
        """Test custom default score for unmatched ships."""
        kill = MockProcessedKill(victim_ship_type_id=24690)  # Vexor
        config = {"default_score": 0.7}
        result = signal.score(kill, 30000142, config)
        assert result.score == 0.7

    def test_score_jump_freighter(
        self, signal: ShipSignal, mock_kill_jump_freighter: MockProcessedKill
    ) -> None:
        """Test jump freighter detection."""
        config = {"prefer": ["jump_freighter"]}
        result = signal.score(mock_kill_jump_freighter, 30000142, config)
        assert result.score == 1.0
        assert "jump_freighter" in result.reason.lower()

    def test_score_mining_barge(
        self, signal: ShipSignal, mock_kill_mining_barge: MockProcessedKill
    ) -> None:
        """Test mining barge detection."""
        config = {"prefer": ["mining_barge"]}
        result = signal.score(mock_kill_mining_barge, 30000142, config)
        assert result.score == 1.0
        assert "mining_barge" in result.reason.lower()

    def test_score_multiple_prefer(self, signal: ShipSignal) -> None:
        """Test multiple preferred classes."""
        kill = MockProcessedKill(victim_ship_type_id=17478)  # Retriever
        config = {"prefer": ["freighter", "mining_barge", "orca"]}
        result = signal.score(kill, 30000142, config)
        assert result.score == 1.0
        assert "mining_barge" in result.reason.lower()

    def test_score_class_normalization(self, signal: ShipSignal) -> None:
        """Test ship class name normalization (spaces, hyphens)."""
        kill = MockProcessedKill(victim_ship_type_id=28844)  # JF
        config = {"prefer": ["jump-freighter"]}  # With hyphen
        result = signal.score(kill, 30000142, config)
        assert result.score == 1.0

    def test_score_raw_value_included(
        self, signal: ShipSignal, mock_kill_freighter: MockProcessedKill
    ) -> None:
        """Test raw_value includes ship type info."""
        config = {"prefer": ["freighter"]}
        result = signal.score(mock_kill_freighter, 30000142, config)
        assert result.raw_value is not None
        assert "type_id" in result.raw_value
        assert "class" in result.raw_value


class TestShipSignalValidate:
    """Tests for ShipSignal.validate() method."""

    @pytest.fixture
    def signal(self) -> ShipSignal:
        """Create a ShipSignal instance."""
        return ShipSignal()

    def test_validate_empty_config(self, signal: ShipSignal) -> None:
        """Test validation passes for empty config."""
        errors = signal.validate({})
        assert errors == []

    def test_validate_valid_prefer(self, signal: ShipSignal) -> None:
        """Test validation passes for valid prefer list."""
        config = {"prefer": ["freighter", "jump_freighter", "carrier"]}
        errors = signal.validate(config)
        assert errors == []

    def test_validate_valid_exclude(self, signal: ShipSignal) -> None:
        """Test validation passes for valid exclude list."""
        config = {"exclude": ["capsule", "mining_barge"]}
        errors = signal.validate(config)
        assert errors == []

    def test_validate_unknown_prefer_class(self, signal: ShipSignal) -> None:
        """Test validation fails for unknown ship class in prefer."""
        config = {"prefer": ["battleship"]}  # Not a defined class
        errors = signal.validate(config)
        assert len(errors) == 1
        assert "Unknown ship class" in errors[0]
        assert "prefer" in errors[0]

    def test_validate_unknown_exclude_class(self, signal: ShipSignal) -> None:
        """Test validation fails for unknown ship class in exclude."""
        config = {"exclude": ["shuttle"]}  # Not a defined class
        errors = signal.validate(config)
        assert len(errors) == 1
        assert "Unknown ship class" in errors[0]
        assert "exclude" in errors[0]

    def test_validate_score_out_of_range(self, signal: ShipSignal) -> None:
        """Test validation fails for scores outside [0, 1]."""
        config = {"prefer_score": 1.5}
        errors = signal.validate(config)
        assert len(errors) == 1
        assert "between 0 and 1" in errors[0]

    def test_validate_negative_score(self, signal: ShipSignal) -> None:
        """Test validation fails for negative scores."""
        config = {"exclude_score": -0.5}
        errors = signal.validate(config)
        assert len(errors) == 1
        assert "between 0 and 1" in errors[0]

    def test_validate_all_score_fields(self, signal: ShipSignal) -> None:
        """Test validation checks all score fields."""
        config = {
            "prefer_score": 0.8,
            "exclude_score": 0.1,
            "default_score": 0.5,
        }
        errors = signal.validate(config)
        assert errors == []

    def test_validate_invalid_score_type(self, signal: ShipSignal) -> None:
        """Test validation fails for non-numeric scores."""
        config = {"prefer_score": "high"}
        errors = signal.validate(config)
        assert len(errors) == 1


class TestShipSignalProperties:
    """Tests for ShipSignal class properties."""

    def test_signal_name(self) -> None:
        """Test signal name is correct."""
        signal = ShipSignal()
        assert signal._name == "ship"

    def test_signal_category(self) -> None:
        """Test signal category is correct."""
        signal = ShipSignal()
        assert signal._category == "ship"

    def test_prefetch_capable(self) -> None:
        """Test signal is prefetch capable."""
        signal = ShipSignal()
        assert signal._prefetch_capable is True


class TestShipClasses:
    """Tests for SHIP_CLASSES constant."""

    def test_ship_classes_defined(self) -> None:
        """Test expected ship classes are defined."""
        expected = [
            "freighter",
            "jump_freighter",
            "industrial",
            "dst",
            "blockade_runner",
            "orca",
            "bowhead",
            "rorqual",
            "mining_barge",
            "exhumer",
            "mining_frigate",
            "carrier",
            "supercarrier",
            "dreadnought",
            "titan",
            "fax",
            "capsule",
        ]
        for ship_class in expected:
            assert ship_class in SHIP_CLASSES, f"Missing ship class: {ship_class}"

    def test_ship_classes_have_type_ids(self) -> None:
        """Test each ship class has at least one type ID."""
        for name, type_ids in SHIP_CLASSES.items():
            # Industrial might be empty in some implementations
            if name != "industrial":
                assert len(type_ids) > 0, f"Ship class '{name}' has no type IDs"

    def test_capsule_type_ids(self) -> None:
        """Test capsule includes standard capsule type."""
        assert 670 in SHIP_CLASSES["capsule"]  # Standard capsule
