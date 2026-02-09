"""Tests for PoliticsSignal provider."""

from __future__ import annotations

import pytest

from aria_esi.services.redisq.interest_v2.signals.politics import (
    DEFAULT_ROLE_WEIGHTS,
    PoliticsSignal,
)

from .conftest import MockProcessedKill


class TestPoliticsSignalScore:
    """Tests for PoliticsSignal.score() method."""

    @pytest.fixture
    def signal(self) -> PoliticsSignal:
        """Create a PoliticsSignal instance."""
        return PoliticsSignal()

    def test_score_no_groups_configured(self, signal: PoliticsSignal) -> None:
        """Test scoring with no groups configured returns 0."""
        kill = MockProcessedKill()
        result = signal.score(kill, 30000142, {})
        assert result.score == 0.0
        assert "No political groups configured" in result.reason

    def test_score_none_kill(self, signal: PoliticsSignal) -> None:
        """Test scoring with None kill returns 0."""
        config = {
            "groups": {"my_corp": {"corporations": [98000001]}},
        }
        result = signal.score(None, 30000142, config)
        assert result.score == 0.0
        assert "No kill data" in result.reason

    def test_score_victim_corp_match(
        self, signal: PoliticsSignal, mock_kill_corp_victim: MockProcessedKill
    ) -> None:
        """Test scoring when victim corporation matches."""
        config = {
            "groups": {"my_corp": {"corporations": [98000001]}},
        }
        result = signal.score(mock_kill_corp_victim, 30000142, config)
        assert result.score == 1.0  # Victim role weight
        assert "Victim matches group" in result.reason

    def test_score_victim_alliance_match(self, signal: PoliticsSignal) -> None:
        """Test scoring when victim alliance matches."""
        kill = MockProcessedKill(
            victim_corporation_id=98000099,  # Not in group
            victim_alliance_id=99001234,  # In group
        )
        config = {
            "groups": {"my_alliance": {"alliances": [99001234]}},
        }
        result = signal.score(kill, 30000142, config)
        assert result.score == 1.0
        assert "Victim matches group" in result.reason

    def test_score_attacker_corp_match(
        self, signal: PoliticsSignal, mock_kill_corp_attacker: MockProcessedKill
    ) -> None:
        """Test scoring when attacker corporation matches."""
        config = {
            "groups": {"my_corp": {"corporations": [98000001]}},
        }
        result = signal.score(mock_kill_corp_attacker, 30000142, config)
        # Attacker role weight is 0.6
        assert result.score == 0.6
        assert "Attacker matches group" in result.reason

    def test_score_attacker_alliance_match(self, signal: PoliticsSignal) -> None:
        """Test scoring when attacker alliance matches."""
        kill = MockProcessedKill(
            victim_corporation_id=98000099,
            attacker_corps=[98000055],
            attacker_alliances=[99005678],  # In group
        )
        config = {
            "groups": {"my_alliance": {"alliances": [99005678]}},
        }
        result = signal.score(kill, 30000142, config)
        assert result.score == 0.6  # Attacker role weight

    def test_score_solo_modifier(
        self, signal: PoliticsSignal, mock_kill_solo: MockProcessedKill
    ) -> None:
        """Test solo modifier is applied for single attacker."""
        # Solo kill with attacker in group - but default fixture has victim_corp matching
        # So we need to ensure victim doesn't match to test attacker scoring
        mock_kill_solo.victim_corporation_id = 98000099  # Not in group
        mock_kill_solo.victim_alliance_id = None
        mock_kill_solo.attacker_corps = [98000001]  # In group
        config = {
            "groups": {"my_corp": {"corporations": [98000001]}},
        }
        result = signal.score(mock_kill_solo, 30000142, config)
        # Attacker 0.6 * solo 1.0 = 0.6
        assert result.score == 0.6

    def test_score_custom_role_weights(self, signal: PoliticsSignal) -> None:
        """Test custom role weights override defaults."""
        kill = MockProcessedKill()  # Victim corp 98000001
        config = {
            "groups": {"my_corp": {"corporations": [98000001]}},
            "role_weights": {"victim": 0.5},
        }
        result = signal.score(kill, 30000142, config)
        assert result.score == 0.5  # Custom victim weight

    def test_score_no_group_matches(self, signal: PoliticsSignal) -> None:
        """Test scoring when no groups match."""
        kill = MockProcessedKill(
            victim_corporation_id=98000099,
            attacker_corps=[98000055],
        )
        config = {
            "groups": {"my_corp": {"corporations": [98000001]}},
        }
        result = signal.score(kill, 30000142, config)
        assert result.score == 0.0
        assert "No group matches" in result.reason

    def test_score_require_all_met(self, signal: PoliticsSignal) -> None:
        """Test require_all when all groups match."""
        kill = MockProcessedKill(
            victim_corporation_id=98000001,  # Group A
            attacker_corps=[98000002],  # Group B
        )
        config = {
            "groups": {
                "group_a": {"corporations": [98000001]},
                "group_b": {"corporations": [98000002]},
            },
            "require_all": ["group_a", "group_b"],
        }
        result = signal.score(kill, 30000142, config)
        # Min of victim (1.0) and attacker (0.6)
        assert result.score == 0.6

    def test_score_require_all_not_met(self, signal: PoliticsSignal) -> None:
        """Test require_all when not all groups match."""
        kill = MockProcessedKill(
            victim_corporation_id=98000001,  # Group A only
            attacker_corps=[98000055],  # Not in groups
        )
        config = {
            "groups": {
                "group_a": {"corporations": [98000001]},
                "group_b": {"corporations": [98000002]},
            },
            "require_all": ["group_a", "group_b"],
        }
        result = signal.score(kill, 30000142, config)
        assert result.score == 0.0
        assert "require_all not met" in result.reason
        assert "group_b" in result.reason

    def test_score_require_any_met(self, signal: PoliticsSignal) -> None:
        """Test require_any when at least one group matches."""
        kill = MockProcessedKill(victim_corporation_id=98000001)  # Group A
        config = {
            "groups": {
                "group_a": {"corporations": [98000001]},
                "group_b": {"corporations": [98000002]},
            },
            "require_any": ["group_a", "group_b"],
        }
        result = signal.score(kill, 30000142, config)
        assert result.score == 1.0  # Max of matched groups

    def test_score_require_any_not_met(self, signal: PoliticsSignal) -> None:
        """Test require_any when no groups match."""
        kill = MockProcessedKill(
            victim_corporation_id=98000099,
            victim_alliance_id=None,
            attacker_corps=[98000055],
            attacker_alliances=[],
        )
        config = {
            "groups": {
                "group_a": {"corporations": [98000001]},
                "group_b": {"corporations": [98000002]},
            },
            "require_any": ["group_a", "group_b"],
        }
        result = signal.score(kill, 30000142, config)
        assert result.score == 0.0
        # When no groups match at all, return "No group matches" before checking require_any
        assert "No group matches" in result.reason or "require_any not met" in result.reason

    def test_score_penalty_is_pod(
        self, signal: PoliticsSignal, mock_kill_pod: MockProcessedKill
    ) -> None:
        """Test is_pod penalty condition."""
        # Pod kill victim in tracked corp
        mock_kill_pod.victim_corporation_id = 98000001
        config = {
            "groups": {"my_corp": {"corporations": [98000001]}},
            "penalties": [{"condition": "is_pod", "penalty": 0.3}],
        }
        result = signal.score(mock_kill_pod, 30000142, config)
        # 1.0 * (1.0 - 0.3) = 0.7
        assert result.score == pytest.approx(0.7, abs=0.01)
        assert "is_pod" in result.reason

    def test_score_penalty_is_solo(
        self, signal: PoliticsSignal, mock_kill_solo: MockProcessedKill
    ) -> None:
        """Test is_solo penalty condition."""
        mock_kill_solo.victim_corporation_id = 98000001
        config = {
            "groups": {"my_corp": {"corporations": [98000001]}},
            "penalties": [{"condition": "is_solo", "penalty": 0.2}],
        }
        result = signal.score(mock_kill_solo, 30000142, config)
        # 1.0 * (1.0 - 0.2) = 0.8
        assert result.score == pytest.approx(0.8, abs=0.01)

    def test_score_penalty_is_npc_only(
        self, signal: PoliticsSignal, mock_kill_npc_only: MockProcessedKill
    ) -> None:
        """Test is_npc_only penalty condition."""
        mock_kill_npc_only.victim_corporation_id = 98000001
        config = {
            "groups": {"my_corp": {"corporations": [98000001]}},
            "penalties": [{"condition": "is_npc_only", "penalty": 0.5}],
        }
        result = signal.score(mock_kill_npc_only, 30000142, config)
        # 1.0 * (1.0 - 0.5) = 0.5
        assert result.score == pytest.approx(0.5, abs=0.01)

    def test_score_multiple_penalties(self, signal: PoliticsSignal) -> None:
        """Test multiple penalties stack."""
        kill = MockProcessedKill(
            victim_corporation_id=98000001,
            is_pod_kill=True,
            attacker_count=1,  # Solo
        )
        config = {
            "groups": {"my_corp": {"corporations": [98000001]}},
            "penalties": [
                {"condition": "is_pod", "penalty": 0.2},
                {"condition": "is_solo", "penalty": 0.3},
            ],
        }
        result = signal.score(kill, 30000142, config)
        # 1.0 * (1.0 - 0.2 - 0.3) = 0.5
        assert result.score == pytest.approx(0.5, abs=0.01)

    def test_score_penalty_clamped(self, signal: PoliticsSignal) -> None:
        """Test penalty factor is clamped to [0, 1]."""
        kill = MockProcessedKill(
            victim_corporation_id=98000001,
            is_pod_kill=True,
        )
        config = {
            "groups": {"my_corp": {"corporations": [98000001]}},
            "penalties": [
                {"condition": "is_pod", "penalty": 0.7},
                {"condition": "is_pod", "penalty": 0.7},  # Would be -0.4
            ],
        }
        result = signal.score(kill, 30000142, config)
        assert result.score == 0.0  # Clamped to 0

    def test_score_unknown_penalty_condition(self, signal: PoliticsSignal) -> None:
        """Test unknown penalty condition is ignored."""
        kill = MockProcessedKill(victim_corporation_id=98000001)
        config = {
            "groups": {"my_corp": {"corporations": [98000001]}},
            "penalties": [{"condition": "unknown_condition", "penalty": 0.5}],
        }
        result = signal.score(kill, 30000142, config)
        assert result.score == 1.0  # No penalty applied

    def test_score_multiple_groups_max(self, signal: PoliticsSignal) -> None:
        """Test maximum score from multiple matched groups."""
        kill = MockProcessedKill(
            victim_corporation_id=98000001,
            victim_alliance_id=99001234,
        )
        config = {
            "groups": {
                "corp_group": {"corporations": [98000001]},
                "alliance_group": {"alliances": [99001234]},
            },
        }
        result = signal.score(kill, 30000142, config)
        # Both match with victim weight 1.0
        assert result.score == 1.0
        assert "Groups matched" in result.reason

    def test_score_raw_value(self, signal: PoliticsSignal) -> None:
        """Test raw_value includes matched groups and penalty factor."""
        kill = MockProcessedKill(victim_corporation_id=98000001)
        config = {
            "groups": {"my_corp": {"corporations": [98000001]}},
        }
        result = signal.score(kill, 30000142, config)
        assert result.raw_value is not None
        assert "groups" in result.raw_value
        assert "penalty_factor" in result.raw_value


class TestPoliticsSignalValidate:
    """Tests for PoliticsSignal.validate() method."""

    @pytest.fixture
    def signal(self) -> PoliticsSignal:
        """Create a PoliticsSignal instance."""
        return PoliticsSignal()

    def test_validate_empty_config(self, signal: PoliticsSignal) -> None:
        """Test validation fails for empty config."""
        errors = signal.validate({})
        assert len(errors) == 1
        assert "At least one political group" in errors[0]

    def test_validate_valid_config(self, signal: PoliticsSignal) -> None:
        """Test validation passes for valid config."""
        config = {
            "groups": {
                "my_corp": {"corporations": [98000001]},
            }
        }
        errors = signal.validate(config)
        assert errors == []

    def test_validate_group_not_dict(self, signal: PoliticsSignal) -> None:
        """Test validation fails when group is not a dict."""
        config = {"groups": {"my_corp": [98000001]}}
        errors = signal.validate(config)
        assert len(errors) == 1
        assert "must be a dictionary" in errors[0]

    def test_validate_empty_group(self, signal: PoliticsSignal) -> None:
        """Test validation fails for group with no entities."""
        config = {"groups": {"empty_group": {}}}
        errors = signal.validate(config)
        assert len(errors) == 1
        assert "at least one corporation, alliance, or faction" in errors[0]

    def test_validate_group_with_factions(self, signal: PoliticsSignal) -> None:
        """Test validation passes for group with factions."""
        config = {"groups": {"faction_group": {"factions": [500001]}}}
        errors = signal.validate(config)
        assert errors == []

    def test_validate_require_any_unknown_group(self, signal: PoliticsSignal) -> None:
        """Test validation fails for require_any referencing unknown group."""
        config = {
            "groups": {"my_corp": {"corporations": [98000001]}},
            "require_any": ["my_corp", "unknown_group"],
        }
        errors = signal.validate(config)
        assert len(errors) == 1
        assert "require_any" in errors[0]
        assert "unknown_group" in errors[0]

    def test_validate_require_all_unknown_group(self, signal: PoliticsSignal) -> None:
        """Test validation fails for require_all referencing unknown group."""
        config = {
            "groups": {"my_corp": {"corporations": [98000001]}},
            "require_all": ["unknown_group"],
        }
        errors = signal.validate(config)
        assert len(errors) == 1
        assert "require_all" in errors[0]

    def test_validate_unknown_role_weight(self, signal: PoliticsSignal) -> None:
        """Test validation fails for unknown role weight."""
        config = {
            "groups": {"my_corp": {"corporations": [98000001]}},
            "role_weights": {"unknown_role": 0.5},
        }
        errors = signal.validate(config)
        assert len(errors) == 1
        assert "Unknown role weight" in errors[0]

    def test_validate_negative_role_weight(self, signal: PoliticsSignal) -> None:
        """Test validation fails for negative role weight."""
        config = {
            "groups": {"my_corp": {"corporations": [98000001]}},
            "role_weights": {"victim": -0.5},
        }
        errors = signal.validate(config)
        assert len(errors) == 1
        assert "non-negative" in errors[0]

    def test_validate_all_role_weights(self, signal: PoliticsSignal) -> None:
        """Test validation passes for all valid role weights."""
        config = {
            "groups": {"my_corp": {"corporations": [98000001]}},
            "role_weights": {
                "victim": 1.0,
                "final_blow": 0.8,
                "attacker": 0.6,
                "solo": 1.0,
            },
        }
        errors = signal.validate(config)
        assert errors == []


class TestPoliticsSignalProperties:
    """Tests for PoliticsSignal class properties."""

    def test_signal_name(self) -> None:
        """Test signal name is correct."""
        signal = PoliticsSignal()
        assert signal._name == "politics"

    def test_signal_category(self) -> None:
        """Test signal category is correct."""
        signal = PoliticsSignal()
        assert signal._category == "politics"

    def test_prefetch_capable(self) -> None:
        """Test signal is NOT prefetch capable."""
        signal = PoliticsSignal()
        assert signal._prefetch_capable is False


class TestDefaultRoleWeights:
    """Tests for DEFAULT_ROLE_WEIGHTS constant."""

    def test_role_weights_defined(self) -> None:
        """Test expected role weights are defined."""
        assert "victim" in DEFAULT_ROLE_WEIGHTS
        assert "final_blow" in DEFAULT_ROLE_WEIGHTS
        assert "attacker" in DEFAULT_ROLE_WEIGHTS
        assert "solo" in DEFAULT_ROLE_WEIGHTS

    def test_role_weight_values(self) -> None:
        """Test default role weight values."""
        assert DEFAULT_ROLE_WEIGHTS["victim"] == 1.0
        assert DEFAULT_ROLE_WEIGHTS["final_blow"] == 0.8
        assert DEFAULT_ROLE_WEIGHTS["attacker"] == 0.6
        assert DEFAULT_ROLE_WEIGHTS["solo"] == 1.0
