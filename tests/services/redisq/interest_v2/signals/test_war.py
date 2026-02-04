"""Tests for WarSignal provider."""

from __future__ import annotations

import pytest

from aria_esi.services.redisq.interest_v2.signals.war import WarSignal

from .conftest import MockProcessedKill


class TestWarSignalScore:
    """Tests for WarSignal.score() method."""

    @pytest.fixture
    def signal(self) -> WarSignal:
        """Create a WarSignal instance."""
        return WarSignal()

    def test_score_no_config(self, signal: WarSignal) -> None:
        """Test scoring with no war targets or standings configured."""
        kill = MockProcessedKill()
        result = signal.score(kill, 30000142, {})
        assert result.score == 0.0
        assert "No war targets or standings configured" in result.reason
        assert result.prefetch_capable is False

    def test_score_none_kill(self, signal: WarSignal) -> None:
        """Test scoring with None kill returns 0."""
        config = {"war_targets": [98000050]}
        result = signal.score(None, 30000142, config)
        assert result.score == 0.0
        assert "No kill data" in result.reason

    def test_score_war_target_victim_corp(
        self, signal: WarSignal, mock_kill_war_victim: MockProcessedKill
    ) -> None:
        """Test war target as victim (corporation)."""
        config = {"war_targets": [98000050]}  # Victim corp
        result = signal.score(mock_kill_war_victim, 30000142, config)
        assert result.score == 0.95  # DEFAULT_WAR_SCORE
        assert "War target died" in result.reason

    def test_score_war_target_victim_alliance(
        self, signal: WarSignal, mock_kill_war_victim: MockProcessedKill
    ) -> None:
        """Test war target as victim (alliance)."""
        config = {"war_targets": [99005000]}  # Victim alliance
        result = signal.score(mock_kill_war_victim, 30000142, config)
        assert result.score == 0.95
        assert "War target died" in result.reason

    def test_score_war_target_attacker_corp(
        self, signal: WarSignal, mock_kill_war_attacker: MockProcessedKill
    ) -> None:
        """Test war target as attacker (corporation)."""
        config = {"war_targets": [98000050]}  # Attacker corp
        result = signal.score(mock_kill_war_attacker, 30000142, config)
        assert result.score == 0.95
        assert "War target scored a kill" in result.reason

    def test_score_war_target_attacker_alliance(
        self, signal: WarSignal, mock_kill_war_attacker: MockProcessedKill
    ) -> None:
        """Test war target as attacker (alliance)."""
        config = {"war_targets": [99005000]}  # Attacker alliance
        result = signal.score(mock_kill_war_attacker, 30000142, config)
        assert result.score == 0.95

    def test_score_custom_war_score(
        self, signal: WarSignal, mock_kill_war_victim: MockProcessedKill
    ) -> None:
        """Test custom war score."""
        config = {"war_targets": [98000050], "war_score": 0.85}
        result = signal.score(mock_kill_war_victim, 30000142, config)
        assert result.score == 0.85

    def test_score_hostile_victim(self, signal: WarSignal) -> None:
        """Test hostile standing victim."""
        kill = MockProcessedKill(
            victim_corporation_id=98000080,
            victim_alliance_id=None,
        )
        config = {
            "standings": {98000080: -7.0},  # Hostile standing
            "hostile_threshold": -5.0,
        }
        result = signal.score(kill, 30000142, config)
        assert result.score == 0.7  # DEFAULT_HOSTILE_SCORE
        assert "Hostile entity died" in result.reason
        assert "-7" in result.reason

    def test_score_hostile_attacker(self, signal: WarSignal) -> None:
        """Test hostile standing attacker."""
        kill = MockProcessedKill(
            victim_corporation_id=98000099,
            attacker_corps=[98000080],
            attacker_alliances=[],
        )
        config = {
            "standings": {98000080: -6.0},
            "hostile_threshold": -5.0,
        }
        result = signal.score(kill, 30000142, config)
        # Attacker hostile = hostile_score * 0.8
        assert result.score == pytest.approx(0.7 * 0.8, abs=0.01)
        assert "Hostile entity active" in result.reason

    def test_score_custom_hostile_score(self, signal: WarSignal) -> None:
        """Test custom hostile score."""
        kill = MockProcessedKill(victim_corporation_id=98000080)
        config = {
            "standings": {98000080: -7.0},
            "hostile_score": 0.6,
            "hostile_threshold": -5.0,
        }
        result = signal.score(kill, 30000142, config)
        assert result.score == 0.6

    def test_score_custom_hostile_threshold(self, signal: WarSignal) -> None:
        """Test custom hostile threshold."""
        kill = MockProcessedKill(victim_corporation_id=98000080)
        config = {
            "standings": {98000080: -3.0},
            "hostile_threshold": -2.0,  # More strict
        }
        result = signal.score(kill, 30000142, config)
        assert result.score == 0.7  # -3 <= -2, so hostile

    def test_score_standing_above_threshold(self, signal: WarSignal) -> None:
        """Test standing above hostile threshold is not hostile."""
        kill = MockProcessedKill(victim_corporation_id=98000080)
        config = {
            "standings": {98000080: -3.0},
            "hostile_threshold": -5.0,  # Default
        }
        result = signal.score(kill, 30000142, config)
        assert result.score == 0.0  # -3 > -5, not hostile

    def test_score_war_target_takes_precedence(self, signal: WarSignal) -> None:
        """Test war target match takes precedence over hostile standings."""
        kill = MockProcessedKill(
            victim_corporation_id=98000050,
        )
        config = {
            "war_targets": [98000050],
            "standings": {98000050: -7.0},
            "war_score": 0.95,
            "hostile_score": 0.7,
        }
        result = signal.score(kill, 30000142, config)
        assert result.score == 0.95  # War target score, not hostile
        assert "War target" in result.reason

    def test_score_no_involvement(self, signal: WarSignal) -> None:
        """Test no war target or hostile involvement."""
        kill = MockProcessedKill(
            victim_corporation_id=98000099,
            attacker_corps=[98000055],
        )
        config = {
            "war_targets": [98000050],
            "standings": {98000080: -7.0},
        }
        result = signal.score(kill, 30000142, config)
        assert result.score == 0.0
        assert "No war target or hostile involvement" in result.reason

    def test_score_standings_string_key(self, signal: WarSignal) -> None:
        """Test standings with string keys (from JSON)."""
        kill = MockProcessedKill(victim_corporation_id=98000080)
        config = {
            "standings": {"98000080": -7.0},  # String key
            "hostile_threshold": -5.0,
        }
        result = signal.score(kill, 30000142, config)
        assert result.score == 0.7  # Should still match

    def test_score_raw_value_war_target(
        self, signal: WarSignal, mock_kill_war_victim: MockProcessedKill
    ) -> None:
        """Test raw_value for war target match."""
        config = {"war_targets": [98000050]}
        result = signal.score(mock_kill_war_victim, 30000142, config)
        assert result.raw_value is not None
        assert result.raw_value["match_type"] == "war_target"
        assert result.raw_value["role"] == "victim"

    def test_score_raw_value_hostile(self, signal: WarSignal) -> None:
        """Test raw_value for hostile match."""
        kill = MockProcessedKill(victim_corporation_id=98000080)
        config = {
            "standings": {98000080: -7.0},
            "hostile_threshold": -5.0,
        }
        result = signal.score(kill, 30000142, config)
        assert result.raw_value is not None
        assert result.raw_value["match_type"] == "hostile"
        assert result.raw_value["standing"] == -7.0

    def test_score_victim_none_ids(self, signal: WarSignal) -> None:
        """Test victim with None corporation/alliance IDs."""
        kill = MockProcessedKill(
            victim_corporation_id=None,
            victim_alliance_id=None,
        )
        config = {"war_targets": [98000050]}
        result = signal.score(kill, 30000142, config)
        assert result.score == 0.0


class TestWarSignalValidate:
    """Tests for WarSignal.validate() method."""

    @pytest.fixture
    def signal(self) -> WarSignal:
        """Create a WarSignal instance."""
        return WarSignal()

    def test_validate_empty_config(self, signal: WarSignal) -> None:
        """Test validation passes for empty config."""
        errors = signal.validate({})
        assert errors == []

    def test_validate_valid_config(self, signal: WarSignal) -> None:
        """Test validation passes for valid config."""
        config = {
            "war_targets": [98000050, 99005000],
            "standings": {98000080: -7.0},
            "war_score": 0.95,
            "hostile_score": 0.7,
            "hostile_threshold": -5.0,
        }
        errors = signal.validate(config)
        assert errors == []

    def test_validate_war_score_out_of_range(self, signal: WarSignal) -> None:
        """Test validation fails for war_score outside [0, 1]."""
        config = {"war_score": 1.5}
        errors = signal.validate(config)
        assert len(errors) == 1
        assert "war_score" in errors[0]
        assert "between 0 and 1" in errors[0]

    def test_validate_hostile_score_out_of_range(self, signal: WarSignal) -> None:
        """Test validation fails for hostile_score outside [0, 1]."""
        config = {"hostile_score": -0.1}
        errors = signal.validate(config)
        assert len(errors) == 1
        assert "hostile_score" in errors[0]

    def test_validate_hostile_threshold_out_of_range(self, signal: WarSignal) -> None:
        """Test validation fails for hostile_threshold outside [-10, 10]."""
        config = {"hostile_threshold": -15.0}
        errors = signal.validate(config)
        assert len(errors) == 1
        assert "hostile_threshold" in errors[0]
        assert "between -10 and 10" in errors[0]

    def test_validate_threshold_positive(self, signal: WarSignal) -> None:
        """Test validation allows positive threshold."""
        config = {"hostile_threshold": 0.0}
        errors = signal.validate(config)
        assert errors == []


class TestWarSignalProperties:
    """Tests for WarSignal class properties."""

    def test_signal_name(self) -> None:
        """Test signal name is correct."""
        signal = WarSignal()
        assert signal._name == "war"

    def test_signal_category(self) -> None:
        """Test signal category is correct."""
        signal = WarSignal()
        assert signal._category == "war"

    def test_prefetch_capable(self) -> None:
        """Test signal is NOT prefetch capable."""
        signal = WarSignal()
        assert signal._prefetch_capable is False

    def test_default_scores(self) -> None:
        """Test default score constants."""
        signal = WarSignal()
        assert signal.DEFAULT_WAR_SCORE == 0.95
        assert signal.DEFAULT_HOSTILE_SCORE == 0.7
        assert signal.DEFAULT_HOSTILE_THRESHOLD == -5.0
