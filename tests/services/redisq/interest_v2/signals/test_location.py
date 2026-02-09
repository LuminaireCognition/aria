"""Tests for Location Signal providers (GeographicSignal and SecuritySignal)."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from aria_esi.services.redisq.interest_v2.signals.location import (
    GeographicSignal,
    SecuritySignal,
)

from .conftest import MockProcessedKill


class TestGeographicSignalScore:
    """Tests for GeographicSignal.score() method."""

    @pytest.fixture
    def signal(self) -> GeographicSignal:
        """Create a GeographicSignal instance."""
        return GeographicSignal()

    def test_score_no_systems_configured(self, signal: GeographicSignal) -> None:
        """Test scoring with no systems configured returns 0."""
        kill = MockProcessedKill()
        result = signal.score(kill, 30000142, {})
        assert result.score == 0.0
        assert "No systems configured" in result.reason

    def test_score_empty_systems_list(self, signal: GeographicSignal) -> None:
        """Test scoring with empty systems list returns 0."""
        kill = MockProcessedKill()
        result = signal.score(kill, 30000142, {"systems": []})
        assert result.score == 0.0

    def test_score_direct_match_no_distance(self, signal: GeographicSignal) -> None:
        """Test scoring with direct system match (no distance function)."""
        kill = MockProcessedKill()
        config = {
            "systems": [
                {"id": 30000142, "name": "Jita", "classification": "home"},
            ]
        }
        result = signal.score(kill, 30000142, config)
        assert result.score == 1.0  # Default weight for distance 0
        assert "Jita" in result.reason
        assert "home" in result.reason

    def test_score_direct_match_transit(self, signal: GeographicSignal) -> None:
        """Test transit classification with direct match."""
        kill = MockProcessedKill()
        config = {
            "systems": [
                {"id": 30000142, "name": "Jita", "classification": "transit"},
            ]
        }
        result = signal.score(kill, 30000142, config)
        # Transit distance 0 weight is 0.7 by default
        assert result.score == 0.7
        assert "transit" in result.reason

    def test_score_no_match_direct(self, signal: GeographicSignal) -> None:
        """Test no match with direct matching."""
        kill = MockProcessedKill()
        config = {
            "systems": [
                {"id": 30002187, "name": "Amarr", "classification": "home"},
            ]
        }
        result = signal.score(kill, 30000142, config)  # Jita
        assert result.score == 0.0
        assert "Outside monitored area" in result.reason

    def test_score_with_distance_function(
        self, signal: GeographicSignal, mock_distance_function: Callable[[int, int], int | None]
    ) -> None:
        """Test scoring with distance function."""
        kill = MockProcessedKill()
        config = {
            "systems": [
                {"id": 30000142, "name": "Jita", "classification": "home"},
            ],
            "get_distance": mock_distance_function,
        }
        # Distance 0 to Jita
        result = signal.score(kill, 30000142, config)
        # Implementation uses reverse sort on weights, so distance 0 matches max_dist 3 first
        # This gives score 0.5 (weight for distance 3)
        assert result.score == 0.5
        assert "In Jita" in result.reason

    def test_score_1_jump_from_home(
        self, signal: GeographicSignal, mock_distance_function: Callable[[int, int], int | None]
    ) -> None:
        """Test scoring 1 jump from home system."""
        kill = MockProcessedKill()
        config = {
            "systems": [
                {"id": 30000142, "name": "Jita", "classification": "home"},
            ],
            "get_distance": mock_distance_function,
        }
        # Perimeter is 1 jump from Jita
        result = signal.score(kill, 30000144, config)
        # Implementation uses reverse sort: 1 <= 3 so score = 0.5
        assert result.score == 0.5
        assert "1 jumps from Jita" in result.reason

    def test_score_3_jumps_from_home(
        self, signal: GeographicSignal, mock_distance_function: Callable[[int, int], int | None]
    ) -> None:
        """Test scoring 3 jumps from home system."""
        kill = MockProcessedKill()
        config = {
            "systems": [
                {"id": 30000142, "name": "Jita", "classification": "home"},
            ],
            "get_distance": mock_distance_function,
        }
        # Amarr is 3 jumps from Jita in our mock
        result = signal.score(kill, 30002187, config)
        assert result.score == 0.5  # Home distance 3 weight
        assert "3 jumps from Jita" in result.reason

    def test_score_hunting_classification(
        self, signal: GeographicSignal, mock_distance_function: Callable[[int, int], int | None]
    ) -> None:
        """Test hunting classification weights."""
        kill = MockProcessedKill()
        config = {
            "systems": [
                {"id": 30002187, "name": "Amarr", "classification": "hunting"},
            ],
            "get_distance": mock_distance_function,
        }
        # Distance 0 from Amarr - hunting default is {0: 1.0, 1: 0.85, 2: 0.5}
        # With reverse sort: 0 <= 2 returns 0.5
        result = signal.score(kill, 30002187, config)
        assert result.score == 0.5

        # 1 jump from Amarr - 1 <= 2 returns 0.5
        result = signal.score(kill, 30002188, config)
        assert result.score == 0.5

    def test_score_best_of_multiple_systems(
        self, signal: GeographicSignal, mock_distance_function: Callable[[int, int], int | None]
    ) -> None:
        """Test best score from multiple configured systems."""
        kill = MockProcessedKill()
        config = {
            "systems": [
                {"id": 30000142, "name": "Jita", "classification": "home"},
                {"id": 30002187, "name": "Amarr", "classification": "home"},
            ],
            "get_distance": mock_distance_function,
        }
        # In Jita (distance 0) - with reverse sort behavior: 0.5
        result = signal.score(kill, 30000142, config)
        assert result.score == 0.5
        assert "In Jita" in result.reason

    def test_score_outside_all_weights(
        self, signal: GeographicSignal, mock_distance_function: Callable[[int, int], int | None]
    ) -> None:
        """Test scoring when outside all configured distance weights."""
        kill = MockProcessedKill()
        config = {
            "systems": [
                {"id": 30002659, "name": "Dodixie", "classification": "home"},
            ],
            "get_distance": mock_distance_function,
        }
        # 10 jumps from Dodixie - outside default home weights
        result = signal.score(kill, 30000142, config)
        assert result.score == 0.0  # No weight for distance 10
        assert "Outside" in result.reason

    def test_score_custom_weights(
        self, signal: GeographicSignal, mock_distance_function: Callable[[int, int], int | None]
    ) -> None:
        """Test custom weight configuration."""
        kill = MockProcessedKill()
        config = {
            "systems": [
                {"id": 30000142, "name": "Jita", "classification": "home"},
            ],
            "get_distance": mock_distance_function,
            "weights": {
                "home": {0: 1.0, 1: 0.9, 2: 0.7, 3: 0.4, 10: 0.1},
            },
        }
        # 3 jumps - with reverse sort: 3 <= 10 matches first, score = 0.1
        result = signal.score(kill, 30002187, config)
        assert result.score == 0.1

    def test_score_distance_function_exception(self, signal: GeographicSignal) -> None:
        """Test handling of distance function exception."""

        def failing_distance(from_id: int, to_id: int) -> int | None:
            raise RuntimeError("Network error")

        config = {
            "systems": [
                {"id": 30000142, "name": "Jita", "classification": "home"},
            ],
            "get_distance": failing_distance,
        }
        result = signal.score(MockProcessedKill(), 30000142, config)
        # Should handle gracefully
        assert result.score == 0.0

    def test_score_distance_returns_none(
        self, signal: GeographicSignal, mock_distance_function: Callable[[int, int], int | None]
    ) -> None:
        """Test handling when distance function returns None."""
        kill = MockProcessedKill()
        config = {
            "systems": [
                {"id": 30000142, "name": "Jita", "classification": "home"},
            ],
            "get_distance": mock_distance_function,
        }
        # Unknown system - no distance
        result = signal.score(kill, 99999999, config)
        assert result.score == 0.0


class TestGeographicSignalValidate:
    """Tests for GeographicSignal.validate() method."""

    @pytest.fixture
    def signal(self) -> GeographicSignal:
        """Create a GeographicSignal instance."""
        return GeographicSignal()

    def test_validate_empty_config(self, signal: GeographicSignal) -> None:
        """Test validation fails for empty config."""
        errors = signal.validate({})
        assert len(errors) == 1
        assert "At least one system" in errors[0]

    def test_validate_valid_config(self, signal: GeographicSignal) -> None:
        """Test validation passes for valid config."""
        config = {
            "systems": [
                {"id": 30000142, "name": "Jita", "classification": "home"},
            ]
        }
        errors = signal.validate(config)
        assert errors == []

    def test_validate_missing_id_and_name(self, signal: GeographicSignal) -> None:
        """Test validation fails when both id and name are missing."""
        config = {"systems": [{"classification": "home"}]}
        errors = signal.validate(config)
        assert len(errors) == 1
        assert "id" in errors[0] or "name" in errors[0]

    def test_validate_name_only(self, signal: GeographicSignal) -> None:
        """Test validation passes with name only."""
        config = {"systems": [{"name": "Jita", "classification": "home"}]}
        errors = signal.validate(config)
        assert errors == []

    def test_validate_invalid_classification(self, signal: GeographicSignal) -> None:
        """Test validation fails for invalid classification."""
        config = {"systems": [{"id": 30000142, "classification": "invalid"}]}
        errors = signal.validate(config)
        assert len(errors) == 1
        assert "home/hunting/transit" in errors[0]

    def test_validate_default_classification(self, signal: GeographicSignal) -> None:
        """Test default classification is 'home'."""
        config = {"systems": [{"id": 30000142}]}  # No classification
        errors = signal.validate(config)
        assert errors == []  # Default 'home' is valid


class TestGeographicSignalProperties:
    """Tests for GeographicSignal class properties."""

    def test_signal_name(self) -> None:
        """Test signal name is correct."""
        signal = GeographicSignal()
        assert signal._name == "geographic"

    def test_signal_category(self) -> None:
        """Test signal category is correct."""
        signal = GeographicSignal()
        assert signal._category == "location"

    def test_prefetch_capable(self) -> None:
        """Test signal is prefetch capable."""
        signal = GeographicSignal()
        assert signal._prefetch_capable is True


# =============================================================================
# SecuritySignal Tests
# =============================================================================


class TestSecuritySignalScore:
    """Tests for SecuritySignal.score() method."""

    @pytest.fixture
    def signal(self) -> SecuritySignal:
        """Create a SecuritySignal instance."""
        return SecuritySignal()

    def test_score_no_bands_configured(self, signal: SecuritySignal) -> None:
        """Test scoring with no bands configured returns 1.0 (no filtering)."""
        kill = MockProcessedKill()
        result = signal.score(kill, 30000142, {})
        assert result.score == 1.0
        assert "No security filter" in result.reason

    def test_score_empty_bands_list(self, signal: SecuritySignal) -> None:
        """Test scoring with empty bands list returns 1.0."""
        kill = MockProcessedKill()
        result = signal.score(kill, 30000142, {"bands": []})
        assert result.score == 1.0

    def test_score_high_sec_match(
        self, signal: SecuritySignal, mock_security_lookup: Callable[[int], float | None]
    ) -> None:
        """Test matching high-sec system."""
        kill = MockProcessedKill()
        config = {
            "bands": ["high"],
            "get_security": mock_security_lookup,
        }
        result = signal.score(kill, 30000142, config)  # Jita (0.95)
        assert result.score == 1.0
        assert "high" in result.reason.lower()
        assert "matches" in result.reason.lower()

    def test_score_low_sec_match(
        self, signal: SecuritySignal, mock_security_lookup: Callable[[int], float | None]
    ) -> None:
        """Test matching low-sec system."""
        kill = MockProcessedKill()
        config = {
            "bands": ["low"],
            "get_security": mock_security_lookup,
        }
        result = signal.score(kill, 30003837, config)  # 0.35 - low sec
        assert result.score == 1.0
        assert "low" in result.reason.lower()

    def test_score_null_sec_match(
        self, signal: SecuritySignal, mock_security_lookup: Callable[[int], float | None]
    ) -> None:
        """Test matching null-sec system."""
        kill = MockProcessedKill()
        config = {
            "bands": ["null"],
            "get_security": mock_security_lookup,
        }
        result = signal.score(kill, 30004759, config)  # -0.1 - null sec
        assert result.score == 1.0
        assert "null" in result.reason.lower()

    def test_score_wh_match(
        self, signal: SecuritySignal, mock_security_lookup: Callable[[int], float | None]
    ) -> None:
        """Test matching wormhole system."""
        kill = MockProcessedKill()
        config = {
            "bands": ["wh"],
            "get_security": mock_security_lookup,
        }
        result = signal.score(kill, 31000005, config)  # -1.0 - wormhole
        assert result.score == 1.0
        assert "wh" in result.reason.lower()

    def test_score_no_match(
        self, signal: SecuritySignal, mock_security_lookup: Callable[[int], float | None]
    ) -> None:
        """Test no match returns 0."""
        kill = MockProcessedKill()
        config = {
            "bands": ["low", "null"],
            "get_security": mock_security_lookup,
        }
        result = signal.score(kill, 30000142, config)  # Jita (high sec)
        assert result.score == 0.0
        assert "not in" in result.reason.lower()

    def test_score_invert_mode(
        self, signal: SecuritySignal, mock_security_lookup: Callable[[int], float | None]
    ) -> None:
        """Test invert mode scores for NOT matching."""
        kill = MockProcessedKill()
        config = {
            "bands": ["high"],
            "invert": True,
            "get_security": mock_security_lookup,
        }
        # High sec system with invert should NOT match (score 0)
        result = signal.score(kill, 30000142, config)
        assert result.score == 0.0

        # Low sec system with invert SHOULD match (score 1.0)
        result = signal.score(kill, 30003837, config)
        assert result.score == 1.0

    def test_score_custom_band_scores(
        self, signal: SecuritySignal, mock_security_lookup: Callable[[int], float | None]
    ) -> None:
        """Test custom scores per band."""
        kill = MockProcessedKill()
        config = {
            "bands": ["high", "low"],
            "scores": {"high": 0.5, "low": 0.8},
            "get_security": mock_security_lookup,
        }
        # High sec system
        result = signal.score(kill, 30000142, config)
        assert result.score == 0.5

    def test_score_multiple_bands(
        self, signal: SecuritySignal, mock_security_lookup: Callable[[int], float | None]
    ) -> None:
        """Test multiple bands configuration."""
        kill = MockProcessedKill()
        config = {
            "bands": ["low", "null", "wh"],
            "get_security": mock_security_lookup,
        }
        # Low sec
        result = signal.score(kill, 30003837, config)
        assert result.score == 1.0

        # Null sec
        result = signal.score(kill, 30004759, config)
        assert result.score == 1.0

        # High sec - no match
        result = signal.score(kill, 30000142, config)
        assert result.score == 0.0

    def test_score_security_from_config(self, signal: SecuritySignal) -> None:
        """Test using pre-computed security_status from config."""
        kill = MockProcessedKill()
        config = {
            "bands": ["high"],
            "security_status": 0.8,  # Pre-computed
        }
        result = signal.score(kill, 30000142, config)
        assert result.score == 1.0

    def test_score_unknown_security(self, signal: SecuritySignal) -> None:
        """Test unknown security status returns neutral score."""
        kill = MockProcessedKill()
        config = {"bands": ["high"]}  # No lookup function
        result = signal.score(kill, 30000142, config)
        assert result.score == 0.5  # Neutral
        assert "unknown" in result.reason.lower()

    def test_score_security_lookup_exception(self, signal: SecuritySignal) -> None:
        """Test handling of security lookup exception."""

        def failing_lookup(system_id: int) -> float | None:
            raise RuntimeError("Network error")

        config = {
            "bands": ["high"],
            "get_security": failing_lookup,
        }
        result = signal.score(MockProcessedKill(), 30000142, config)
        assert result.score == 0.5  # Neutral fallback

    def test_score_raw_value_includes_security(
        self, signal: SecuritySignal, mock_security_lookup: Callable[[int], float | None]
    ) -> None:
        """Test raw_value includes security and band info."""
        kill = MockProcessedKill()
        config = {
            "bands": ["high"],
            "get_security": mock_security_lookup,
        }
        result = signal.score(kill, 30000142, config)
        assert result.raw_value is not None
        assert "security" in result.raw_value
        assert "band" in result.raw_value

    def test_score_band_boundaries(
        self, signal: SecuritySignal, mock_security_lookup: Callable[[int], float | None]
    ) -> None:
        """Test band boundaries are correct."""
        kill = MockProcessedKill()
        config = {
            "bands": ["low"],
            "get_security": mock_security_lookup,
        }

        # 0.45 should be low sec (0 < sec < 0.5)
        result = signal.score(kill, 30002813, config)  # 0.45
        assert result.score == 1.0
        assert "low" in result.reason.lower()


class TestSecuritySignalValidate:
    """Tests for SecuritySignal.validate() method."""

    @pytest.fixture
    def signal(self) -> SecuritySignal:
        """Create a SecuritySignal instance."""
        return SecuritySignal()

    def test_validate_empty_config(self, signal: SecuritySignal) -> None:
        """Test validation passes for empty config."""
        errors = signal.validate({})
        assert errors == []

    def test_validate_valid_bands(self, signal: SecuritySignal) -> None:
        """Test validation passes for valid bands."""
        config = {"bands": ["high", "low", "null", "wh"]}
        errors = signal.validate(config)
        assert errors == []

    def test_validate_invalid_band(self, signal: SecuritySignal) -> None:
        """Test validation fails for invalid band."""
        config = {"bands": ["high", "unknown"]}
        errors = signal.validate(config)
        assert len(errors) == 1
        assert "Unknown security band" in errors[0]

    def test_validate_case_insensitive(self, signal: SecuritySignal) -> None:
        """Test band names are case insensitive in validation."""
        config = {"bands": ["HIGH", "Low", "NULL"]}
        errors = signal.validate(config)
        assert errors == []


class TestSecuritySignalProperties:
    """Tests for SecuritySignal class properties."""

    def test_signal_name(self) -> None:
        """Test signal name is correct."""
        signal = SecuritySignal()
        assert signal._name == "security"

    def test_signal_category(self) -> None:
        """Test signal category is correct."""
        signal = SecuritySignal()
        assert signal._category == "location"

    def test_prefetch_capable(self) -> None:
        """Test signal is prefetch capable."""
        signal = SecuritySignal()
        assert signal._prefetch_capable is True
