"""
Tests for built-in rules in Interest Engine v2.

Coverage target: 90%+ for src/aria_esi/services/redisq/interest_v2/rules/builtin.py
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from aria_esi.services.redisq.interest_v2.rules.builtin import (
    CAPSULE_TYPE_IDS,
    STRUCTURE_GROUP_IDS,
    AllianceMemberVictimRule,
    CorpMemberVictimRule,
    GatecampDetectedRule,
    HighValueRule,
    NpcOnlyRule,
    PodOnlyRule,
    StructureKillRule,
    WarTargetActivityRule,
    WatchlistMatchRule,
    _format_isk,
)

# =============================================================================
# Mock Data Classes
# =============================================================================


@dataclass
class MockProcessedKill:
    """Mock ProcessedKill for testing rules."""

    kill_id: int = 12345678
    solar_system_id: int = 30000142  # Jita
    victim_ship_type_id: int | None = 24690  # Vexor
    victim_corporation_id: int | None = 98000001
    victim_alliance_id: int | None = 99001234
    is_pod_kill: bool = False
    attacker_count: int = 3
    attacker_corps: list[int] = field(default_factory=lambda: [98000002, 98000003])
    attacker_alliances: list[int] = field(default_factory=lambda: [99005678])
    attacker_ship_types: list[int] = field(default_factory=lambda: [17703, 17703])
    final_blow_ship_type_id: int | None = 17703
    total_value: float = 150_000_000.0  # 150M ISK


@dataclass
class MockGatecampStatus:
    """Mock gatecamp status object."""

    confidence: str | None = "medium"


# =============================================================================
# Test _format_isk() Helper
# =============================================================================


class TestFormatIsk:
    """Tests for the _format_isk helper function."""

    def test_billions_format(self) -> None:
        """Values >= 1B should format as X.XB."""
        assert _format_isk(5_500_000_000.0) == "5.5B"
        assert _format_isk(1_234_567_890.0) == "1.2B"
        assert _format_isk(150_000_000_000.0) == "150.0B"

    def test_millions_format(self) -> None:
        """Values >= 1M and < 1B should format as X.XM."""
        assert _format_isk(150_000_000.0) == "150.0M"
        assert _format_isk(5_500_000.0) == "5.5M"
        assert _format_isk(999_999_999.0) == "1000.0M"

    def test_thousands_format(self) -> None:
        """Values >= 1K and < 1M should format as X.XK."""
        assert _format_isk(50_000.0) == "50.0K"
        assert _format_isk(999_999.0) == "1000.0K"
        assert _format_isk(1_000.0) == "1.0K"

    def test_small_values(self) -> None:
        """Values < 1K should format as integer."""
        assert _format_isk(999.0) == "999"
        assert _format_isk(0.0) == "0"
        assert _format_isk(1.0) == "1"
        assert _format_isk(500.5) == "500"

    def test_exact_billion_boundary(self) -> None:
        """Exactly 1B should format as 1.0B."""
        assert _format_isk(1_000_000_000.0) == "1.0B"

    def test_exact_million_boundary(self) -> None:
        """Exactly 1M should format as 1.0M."""
        assert _format_isk(1_000_000.0) == "1.0M"


# =============================================================================
# Test NpcOnlyRule
# =============================================================================


class TestNpcOnlyRule:
    """Tests for NpcOnlyRule."""

    @pytest.fixture
    def rule(self) -> NpcOnlyRule:
        return NpcOnlyRule()

    def test_name_and_prefetch_capability(self, rule: NpcOnlyRule) -> None:
        """Rule should have correct name and be prefetch capable."""
        assert rule.name == "npc_only"
        assert rule.prefetch_capable is True

    def test_none_kill_returns_not_matched(self, rule: NpcOnlyRule) -> None:
        """None kill should return not matched with prefetch_capable=False."""
        result = rule.evaluate(None, 30000142, {})
        assert result.matched is False
        assert result.rule_id == "npc_only"
        assert result.prefetch_capable is False
        assert "Requires kill data" in (result.reason or "")

    def test_all_npc_attackers_matches(self, rule: NpcOnlyRule) -> None:
        """Kill with only NPC attackers (corp_id < 2M) should match."""
        kill = MockProcessedKill(
            attacker_corps=[1000125, 1000127, 500000],  # All NPC corps
            attacker_alliances=[],
        )
        result = rule.evaluate(kill, 30000142, {})
        assert result.matched is True
        assert "All attackers are NPCs" in (result.reason or "")

    def test_mixed_attackers_not_matched(self, rule: NpcOnlyRule) -> None:
        """Kill with mix of NPC and player attackers should not match."""
        kill = MockProcessedKill(
            attacker_corps=[1000125, 98000001],  # NPC + player
            attacker_alliances=[],
        )
        result = rule.evaluate(kill, 30000142, {})
        assert result.matched is False
        assert "Has player attackers" in (result.reason or "")

    def test_all_player_attackers_not_matched(self, rule: NpcOnlyRule) -> None:
        """Kill with only player attackers should not match."""
        kill = MockProcessedKill(
            attacker_corps=[98000001, 98000002, 98000003],  # All player corps
            attacker_alliances=[99005678],
        )
        result = rule.evaluate(kill, 30000142, {})
        assert result.matched is False
        assert "Has player attackers" in (result.reason or "")

    def test_empty_attacker_corps_not_matched(self, rule: NpcOnlyRule) -> None:
        """Kill with no attacker corp info should not match."""
        kill = MockProcessedKill(
            attacker_corps=[],
            attacker_alliances=[],
        )
        result = rule.evaluate(kill, 30000142, {})
        assert result.matched is False
        assert "No attacker corporation data" in (result.reason or "")

    def test_attacker_corps_with_none_values(self, rule: NpcOnlyRule) -> None:
        """Kill with None values in attacker_corps should handle gracefully."""
        # Simulate corps list with None values (filtered out by generator)
        kill = MockProcessedKill(
            attacker_corps=[1000125, 0, 1000127],  # 0 is falsy, will be filtered
            attacker_alliances=[],
        )
        result = rule.evaluate(kill, 30000142, {})
        # 0 is filtered out by "if corp_id", remaining are all NPC
        assert result.matched is True


# =============================================================================
# Test PodOnlyRule
# =============================================================================


class TestPodOnlyRule:
    """Tests for PodOnlyRule."""

    @pytest.fixture
    def rule(self) -> PodOnlyRule:
        return PodOnlyRule()

    def test_name_and_prefetch_capability(self, rule: PodOnlyRule) -> None:
        """Rule should have correct name and be prefetch capable."""
        assert rule.name == "pod_only"
        assert rule.prefetch_capable is True

    def test_none_kill_returns_not_matched(self, rule: PodOnlyRule) -> None:
        """None kill should return not matched."""
        result = rule.evaluate(None, 30000142, {})
        assert result.matched is False
        assert result.rule_id == "pod_only"
        assert result.prefetch_capable is True
        assert "No kill data" in (result.reason or "")

    def test_standard_capsule_matches(self, rule: PodOnlyRule) -> None:
        """Standard capsule (type_id 670) should match."""
        kill = MockProcessedKill(victim_ship_type_id=670)
        result = rule.evaluate(kill, 30000142, {})
        assert result.matched is True
        assert "capsule" in (result.reason or "").lower()

    def test_genolution_capsule_matches(self, rule: PodOnlyRule) -> None:
        """Genolution capsule (type_id 33328) should match."""
        kill = MockProcessedKill(victim_ship_type_id=33328)
        result = rule.evaluate(kill, 30000142, {})
        assert result.matched is True
        assert "capsule" in (result.reason or "").lower()

    def test_ship_not_matched(self, rule: PodOnlyRule) -> None:
        """Non-capsule ship should not match."""
        kill = MockProcessedKill(victim_ship_type_id=24690)  # Vexor
        result = rule.evaluate(kill, 30000142, {})
        assert result.matched is False
        assert "not a capsule" in (result.reason or "").lower()

    def test_capsule_type_ids_constant(self) -> None:
        """Verify CAPSULE_TYPE_IDS contains expected values."""
        assert 670 in CAPSULE_TYPE_IDS  # Standard Capsule
        assert 33328 in CAPSULE_TYPE_IDS  # Genolution variant


# =============================================================================
# Test CorpMemberVictimRule
# =============================================================================


class TestCorpMemberVictimRule:
    """Tests for CorpMemberVictimRule."""

    @pytest.fixture
    def rule(self) -> CorpMemberVictimRule:
        return CorpMemberVictimRule()

    def test_name_and_prefetch_capability(self, rule: CorpMemberVictimRule) -> None:
        """Rule should have correct name and be prefetch capable."""
        assert rule.name == "corp_member_victim"
        assert rule.prefetch_capable is True

    def test_no_corp_id_configured(self, rule: CorpMemberVictimRule) -> None:
        """No corp_id in config should return not matched."""
        kill = MockProcessedKill(victim_corporation_id=98000001)
        result = rule.evaluate(kill, 30000142, {})
        assert result.matched is False
        assert "No corp_id configured" in (result.reason or "")

    def test_none_kill_with_config(self, rule: CorpMemberVictimRule) -> None:
        """None kill with valid config should return not matched."""
        result = rule.evaluate(None, 30000142, {"corp_id": 98000001})
        assert result.matched is False
        assert result.prefetch_capable is True
        assert "No kill data" in (result.reason or "")

    def test_victim_matches_corp(self, rule: CorpMemberVictimRule) -> None:
        """Victim in configured corp should match."""
        kill = MockProcessedKill(victim_corporation_id=98000001)
        result = rule.evaluate(kill, 30000142, {"corp_id": 98000001})
        assert result.matched is True
        assert "corp member" in (result.reason or "").lower()
        assert "98000001" in (result.reason or "")

    def test_victim_different_corp(self, rule: CorpMemberVictimRule) -> None:
        """Victim in different corp should not match."""
        kill = MockProcessedKill(victim_corporation_id=98000001)
        result = rule.evaluate(kill, 30000142, {"corp_id": 98000002})
        assert result.matched is False
        assert "not a corp member" in (result.reason or "").lower()


# =============================================================================
# Test AllianceMemberVictimRule
# =============================================================================


class TestAllianceMemberVictimRule:
    """Tests for AllianceMemberVictimRule."""

    @pytest.fixture
    def rule(self) -> AllianceMemberVictimRule:
        return AllianceMemberVictimRule()

    def test_name_and_prefetch_capability(self, rule: AllianceMemberVictimRule) -> None:
        """Rule should have correct name and be prefetch capable."""
        assert rule.name == "alliance_member_victim"
        assert rule.prefetch_capable is True

    def test_no_alliance_id_configured(self, rule: AllianceMemberVictimRule) -> None:
        """No alliance_id in config should return not matched."""
        kill = MockProcessedKill(victim_alliance_id=99001234)
        result = rule.evaluate(kill, 30000142, {})
        assert result.matched is False
        assert "No alliance_id configured" in (result.reason or "")

    def test_none_kill_with_config(self, rule: AllianceMemberVictimRule) -> None:
        """None kill with valid config should return not matched."""
        result = rule.evaluate(None, 30000142, {"alliance_id": 99001234})
        assert result.matched is False
        assert result.prefetch_capable is True
        assert "No kill data" in (result.reason or "")

    def test_victim_matches_alliance(self, rule: AllianceMemberVictimRule) -> None:
        """Victim in configured alliance should match."""
        kill = MockProcessedKill(victim_alliance_id=99001234)
        result = rule.evaluate(kill, 30000142, {"alliance_id": 99001234})
        assert result.matched is True
        assert "alliance member" in (result.reason or "").lower()
        assert "99001234" in (result.reason or "")

    def test_victim_different_alliance(self, rule: AllianceMemberVictimRule) -> None:
        """Victim in different alliance should not match."""
        kill = MockProcessedKill(victim_alliance_id=99001234)
        result = rule.evaluate(kill, 30000142, {"alliance_id": 99005678})
        assert result.matched is False
        assert "not an alliance member" in (result.reason or "").lower()

    def test_victim_no_alliance(self, rule: AllianceMemberVictimRule) -> None:
        """Victim with no alliance should not match."""
        kill = MockProcessedKill(victim_alliance_id=None)
        result = rule.evaluate(kill, 30000142, {"alliance_id": 99001234})
        assert result.matched is False
        assert "not an alliance member" in (result.reason or "").lower()


# =============================================================================
# Test WarTargetActivityRule
# =============================================================================


class TestWarTargetActivityRule:
    """Tests for WarTargetActivityRule."""

    @pytest.fixture
    def rule(self) -> WarTargetActivityRule:
        return WarTargetActivityRule()

    def test_name_and_prefetch_capability(self, rule: WarTargetActivityRule) -> None:
        """Rule should have correct name and NOT be prefetch capable."""
        assert rule.name == "war_target_activity"
        assert rule.prefetch_capable is False

    def test_no_war_targets_configured(self, rule: WarTargetActivityRule) -> None:
        """No war_targets in config should return not matched."""
        kill = MockProcessedKill()
        result = rule.evaluate(kill, 30000142, {})
        assert result.matched is False
        assert "No war targets configured" in (result.reason or "")

    def test_empty_war_targets_configured(self, rule: WarTargetActivityRule) -> None:
        """Empty war_targets list should return not matched."""
        kill = MockProcessedKill()
        result = rule.evaluate(kill, 30000142, {"war_targets": []})
        assert result.matched is False
        assert "No war targets configured" in (result.reason or "")

    def test_none_kill_returns_not_matched(self, rule: WarTargetActivityRule) -> None:
        """None kill with valid config should return not matched."""
        result = rule.evaluate(None, 30000142, {"war_targets": {98000050}})
        assert result.matched is False
        assert result.prefetch_capable is False
        assert "Requires kill data" in (result.reason or "")

    def test_victim_corp_is_war_target(self, rule: WarTargetActivityRule) -> None:
        """Victim corp in war targets should match."""
        kill = MockProcessedKill(victim_corporation_id=98000050)
        result = rule.evaluate(kill, 30000142, {"war_targets": {98000050}})
        assert result.matched is True
        assert "Victim corp is a war target" in (result.reason or "")

    def test_victim_alliance_is_war_target(self, rule: WarTargetActivityRule) -> None:
        """Victim alliance in war targets should match."""
        kill = MockProcessedKill(
            victim_corporation_id=98000001,
            victim_alliance_id=99005000,
        )
        result = rule.evaluate(kill, 30000142, {"war_targets": {99005000}})
        assert result.matched is True
        assert "Victim alliance is a war target" in (result.reason or "")

    def test_attacker_corp_is_war_target(self, rule: WarTargetActivityRule) -> None:
        """Attacker corp in war targets should match."""
        kill = MockProcessedKill(
            victim_corporation_id=98000001,
            attacker_corps=[98000050, 98000002],
        )
        result = rule.evaluate(kill, 30000142, {"war_targets": {98000050}})
        assert result.matched is True
        assert "Attacker corp is a war target" in (result.reason or "")

    def test_attacker_alliance_is_war_target(self, rule: WarTargetActivityRule) -> None:
        """Attacker alliance in war targets should match."""
        kill = MockProcessedKill(
            victim_corporation_id=98000001,
            attacker_corps=[98000002],
            attacker_alliances=[99005000],
        )
        result = rule.evaluate(kill, 30000142, {"war_targets": {99005000}})
        assert result.matched is True
        assert "Attacker alliance is a war target" in (result.reason or "")

    def test_no_war_target_involvement(self, rule: WarTargetActivityRule) -> None:
        """Kill with no war target involvement should not match."""
        kill = MockProcessedKill(
            victim_corporation_id=98000001,
            victim_alliance_id=99001234,
            attacker_corps=[98000002, 98000003],
            attacker_alliances=[99005678],
        )
        result = rule.evaluate(
            kill, 30000142, {"war_targets": {98000050, 99005000}}
        )
        assert result.matched is False
        assert "No war target involvement" in (result.reason or "")

    def test_list_converted_to_set(self, rule: WarTargetActivityRule) -> None:
        """War targets as list should be converted to set."""
        kill = MockProcessedKill(victim_corporation_id=98000050)
        # Pass as list, should work the same
        result = rule.evaluate(kill, 30000142, {"war_targets": [98000050, 99005000]})
        assert result.matched is True

    def test_victim_alliance_none_not_matched(
        self, rule: WarTargetActivityRule
    ) -> None:
        """Victim with no alliance shouldn't match alliance war targets."""
        kill = MockProcessedKill(
            victim_corporation_id=98000001,
            victim_alliance_id=None,
            attacker_corps=[98000002],
            attacker_alliances=[],
        )
        # War target is an alliance, victim has no alliance
        result = rule.evaluate(kill, 30000142, {"war_targets": {99005000}})
        assert result.matched is False


# =============================================================================
# Test WatchlistMatchRule
# =============================================================================


class TestWatchlistMatchRule:
    """Tests for WatchlistMatchRule."""

    @pytest.fixture
    def rule(self) -> WatchlistMatchRule:
        return WatchlistMatchRule()

    def test_name_and_prefetch_capability(self, rule: WatchlistMatchRule) -> None:
        """Rule should have correct name and be prefetch capable."""
        assert rule.name == "watchlist_match"
        assert rule.prefetch_capable is True

    def test_empty_watchlist(self, rule: WatchlistMatchRule) -> None:
        """Empty watchlist should return not matched."""
        kill = MockProcessedKill()
        result = rule.evaluate(kill, 30000142, {})
        assert result.matched is False
        assert "Watchlist is empty" in (result.reason or "")

    def test_both_watchlists_empty(self, rule: WatchlistMatchRule) -> None:
        """Both empty watchlists should return not matched."""
        kill = MockProcessedKill()
        result = rule.evaluate(
            kill, 30000142, {"watched_corps": [], "watched_alliances": []}
        )
        assert result.matched is False
        assert "Watchlist is empty" in (result.reason or "")

    def test_none_kill_with_config(self, rule: WatchlistMatchRule) -> None:
        """None kill with valid config should return not matched."""
        result = rule.evaluate(None, 30000142, {"watched_corps": {98000001}})
        assert result.matched is False
        assert result.prefetch_capable is True
        assert "No kill data" in (result.reason or "")

    def test_victim_corp_on_watchlist(self, rule: WatchlistMatchRule) -> None:
        """Victim corp on watchlist should match."""
        kill = MockProcessedKill(victim_corporation_id=98000001)
        result = rule.evaluate(kill, 30000142, {"watched_corps": {98000001}})
        assert result.matched is True
        assert "Victim corp is on watchlist" in (result.reason or "")

    def test_victim_alliance_on_watchlist(self, rule: WatchlistMatchRule) -> None:
        """Victim alliance on watchlist should match."""
        kill = MockProcessedKill(
            victim_corporation_id=98000001,
            victim_alliance_id=99001234,
        )
        result = rule.evaluate(kill, 30000142, {"watched_alliances": {99001234}})
        assert result.matched is True
        assert "Victim alliance is on watchlist" in (result.reason or "")

    def test_victim_not_on_watchlist(self, rule: WatchlistMatchRule) -> None:
        """Victim not on watchlist should not match."""
        kill = MockProcessedKill(
            victim_corporation_id=98000001,
            victim_alliance_id=99001234,
        )
        result = rule.evaluate(
            kill,
            30000142,
            {"watched_corps": {98000050}, "watched_alliances": {99005000}},
        )
        assert result.matched is False
        assert "Victim not on watchlist" in (result.reason or "")

    def test_list_converted_to_set(self, rule: WatchlistMatchRule) -> None:
        """Watchlists as lists should be converted to sets."""
        kill = MockProcessedKill(victim_corporation_id=98000001)
        # Pass as lists, should work the same
        result = rule.evaluate(
            kill,
            30000142,
            {
                "watched_corps": [98000001, 98000002],
                "watched_alliances": [99001234],
            },
        )
        assert result.matched is True

    def test_victim_with_no_alliance(self, rule: WatchlistMatchRule) -> None:
        """Victim with no alliance shouldn't match alliance watchlist."""
        kill = MockProcessedKill(
            victim_corporation_id=98000099,  # Not on corp watchlist
            victim_alliance_id=None,
        )
        result = rule.evaluate(
            kill,
            30000142,
            {
                "watched_corps": {98000001},
                "watched_alliances": {99001234},
            },
        )
        assert result.matched is False

    def test_only_alliance_watchlist_with_matching_alliance(
        self, rule: WatchlistMatchRule
    ) -> None:
        """Only alliance watchlist should still match."""
        kill = MockProcessedKill(
            victim_corporation_id=98000099,
            victim_alliance_id=99001234,
        )
        result = rule.evaluate(
            kill,
            30000142,
            {
                "watched_corps": set(),  # Empty corp watchlist
                "watched_alliances": {99001234},
            },
        )
        assert result.matched is True


# =============================================================================
# Test HighValueRule
# =============================================================================


class TestHighValueRule:
    """Tests for HighValueRule."""

    @pytest.fixture
    def rule(self) -> HighValueRule:
        return HighValueRule()

    def test_name_and_prefetch_capability(self, rule: HighValueRule) -> None:
        """Rule should have correct name and be prefetch capable."""
        assert rule.name == "high_value"
        assert rule.prefetch_capable is True

    def test_none_kill_returns_not_matched(self, rule: HighValueRule) -> None:
        """None kill should return not matched."""
        result = rule.evaluate(None, 30000142, {})
        assert result.matched is False
        assert result.prefetch_capable is True
        assert "No kill data" in (result.reason or "")

    def test_default_threshold_exceeded(self, rule: HighValueRule) -> None:
        """Kill exceeding default 1B threshold should match."""
        kill = MockProcessedKill(total_value=3_500_000_000.0)  # 3.5B
        result = rule.evaluate(kill, 30000142, {})
        assert result.matched is True
        assert "3.5B" in (result.reason or "")
        assert "1.0B" in (result.reason or "")

    def test_default_threshold_not_met(self, rule: HighValueRule) -> None:
        """Kill below default 1B threshold should not match."""
        kill = MockProcessedKill(total_value=150_000_000.0)  # 150M
        result = rule.evaluate(kill, 30000142, {})
        assert result.matched is False
        assert "below threshold" in (result.reason or "").lower()

    def test_custom_threshold_from_config(self, rule: HighValueRule) -> None:
        """Custom high_value_threshold should be used."""
        kill = MockProcessedKill(total_value=150_000_000.0)  # 150M
        result = rule.evaluate(
            kill, 30000142, {"high_value_threshold": 100_000_000.0}
        )
        assert result.matched is True
        assert "150.0M" in (result.reason or "")

    def test_threshold_from_signals_config(self, rule: HighValueRule) -> None:
        """signals.value.min should override high_value_threshold."""
        kill = MockProcessedKill(total_value=150_000_000.0)  # 150M
        result = rule.evaluate(
            kill,
            30000142,
            {
                "high_value_threshold": 1_000_000_000.0,  # 1B
                "signals": {"value": {"min": 100_000_000.0}},  # 100M
            },
        )
        assert result.matched is True

    def test_exact_threshold_matches(self, rule: HighValueRule) -> None:
        """Kill at exactly threshold should match (>=)."""
        kill = MockProcessedKill(total_value=1_000_000_000.0)  # Exactly 1B
        result = rule.evaluate(kill, 30000142, {})
        assert result.matched is True

    def test_format_isk_in_reason(self, rule: HighValueRule) -> None:
        """Reason should contain formatted ISK values."""
        kill = MockProcessedKill(total_value=5_500_000_000.0)  # 5.5B
        result = rule.evaluate(kill, 30000142, {})
        assert result.matched is True
        # Check formatted values are in reason
        assert "5.5B" in (result.reason or "")
        assert "1.0B" in (result.reason or "")


# =============================================================================
# Test GatecampDetectedRule
# =============================================================================


class TestGatecampDetectedRule:
    """Tests for GatecampDetectedRule."""

    @pytest.fixture
    def rule(self) -> GatecampDetectedRule:
        return GatecampDetectedRule()

    def test_name_and_prefetch_capability(self, rule: GatecampDetectedRule) -> None:
        """Rule should have correct name and NOT be prefetch capable."""
        assert rule.name == "gatecamp_detected"
        assert rule.prefetch_capable is False

    def test_no_gatecamp_status(self, rule: GatecampDetectedRule) -> None:
        """No gatecamp_status in config should return not matched."""
        kill = MockProcessedKill()
        result = rule.evaluate(kill, 30000142, {})
        assert result.matched is False
        assert result.prefetch_capable is False
        assert "No gatecamp analysis available" in (result.reason or "")

    def test_high_confidence_matches(self, rule: GatecampDetectedRule) -> None:
        """High confidence gatecamp should match."""
        kill = MockProcessedKill()
        gatecamp = MockGatecampStatus(confidence="high")
        result = rule.evaluate(kill, 30000142, {"gatecamp_status": gatecamp})
        assert result.matched is True
        assert "high confidence" in (result.reason or "").lower()

    def test_medium_confidence_matches(self, rule: GatecampDetectedRule) -> None:
        """Medium confidence gatecamp should match."""
        kill = MockProcessedKill()
        gatecamp = MockGatecampStatus(confidence="medium")
        result = rule.evaluate(kill, 30000142, {"gatecamp_status": gatecamp})
        assert result.matched is True
        assert "medium confidence" in (result.reason or "").lower()

    def test_low_confidence_not_matched(self, rule: GatecampDetectedRule) -> None:
        """Low confidence gatecamp should not match."""
        kill = MockProcessedKill()
        gatecamp = MockGatecampStatus(confidence="low")
        result = rule.evaluate(kill, 30000142, {"gatecamp_status": gatecamp})
        assert result.matched is False
        assert "No gatecamp pattern detected" in (result.reason or "")

    def test_none_confidence_not_matched(self, rule: GatecampDetectedRule) -> None:
        """None confidence should not match."""
        kill = MockProcessedKill()
        gatecamp = MockGatecampStatus(confidence=None)
        result = rule.evaluate(kill, 30000142, {"gatecamp_status": gatecamp})
        assert result.matched is False

    def test_rule_not_prefetch_capable(self, rule: GatecampDetectedRule) -> None:
        """Rule should declare it's not prefetch capable."""
        result = rule.evaluate(None, 30000142, {})
        assert result.prefetch_capable is False


# =============================================================================
# Test StructureKillRule
# =============================================================================


class TestStructureKillRule:
    """Tests for StructureKillRule."""

    @pytest.fixture
    def rule(self) -> StructureKillRule:
        return StructureKillRule()

    def test_name_and_prefetch_capability(self, rule: StructureKillRule) -> None:
        """Rule should have correct name and be prefetch capable."""
        assert rule.name == "structure_kill"
        assert rule.prefetch_capable is True

    def test_none_kill_returns_not_matched(self, rule: StructureKillRule) -> None:
        """None kill should return not matched."""
        result = rule.evaluate(None, 30000142, {})
        assert result.matched is False
        assert result.prefetch_capable is True
        assert "No kill data" in (result.reason or "")

    def test_citadel_group_matches(self, rule: StructureKillRule) -> None:
        """Citadel group (1657) should match."""
        kill = MockProcessedKill()
        result = rule.evaluate(kill, 30000142, {"victim_group_id": 1657})
        assert result.matched is True
        assert "Structure destroyed" in (result.reason or "")
        assert "1657" in (result.reason or "")

    def test_engineering_complex_matches(self, rule: StructureKillRule) -> None:
        """Engineering complex group (1404) should match."""
        kill = MockProcessedKill()
        result = rule.evaluate(kill, 30000142, {"victim_group_id": 1404})
        assert result.matched is True

    def test_refinery_matches(self, rule: StructureKillRule) -> None:
        """Refinery group (1406) should match."""
        kill = MockProcessedKill()
        result = rule.evaluate(kill, 30000142, {"victim_group_id": 1406})
        assert result.matched is True

    def test_pos_matches(self, rule: StructureKillRule) -> None:
        """Control Tower/POS group (365) should match."""
        kill = MockProcessedKill()
        result = rule.evaluate(kill, 30000142, {"victim_group_id": 365})
        assert result.matched is True

    def test_ansiblex_matches(self, rule: StructureKillRule) -> None:
        """Ansiblex Jump Gate group (2016) should match."""
        kill = MockProcessedKill()
        result = rule.evaluate(kill, 30000142, {"victim_group_id": 2016})
        assert result.matched is True

    def test_metenox_matches(self, rule: StructureKillRule) -> None:
        """Metenox Moon Drill group (2233) should match."""
        kill = MockProcessedKill()
        result = rule.evaluate(kill, 30000142, {"victim_group_id": 2233})
        assert result.matched is True

    def test_name_fallback_astrahus(self, rule: StructureKillRule) -> None:
        """Astrahus in ship name should match via fallback."""
        kill = MockProcessedKill()
        result = rule.evaluate(
            kill, 30000142, {"victim_ship_name": "Astrahus"}
        )
        assert result.matched is True
        assert "astrahus" in (result.reason or "").lower()

    def test_name_fallback_keepstar(self, rule: StructureKillRule) -> None:
        """Keepstar in ship name should match via fallback."""
        kill = MockProcessedKill()
        result = rule.evaluate(
            kill, 30000142, {"victim_ship_name": "Keepstar"}
        )
        assert result.matched is True

    def test_name_fallback_fortizar(self, rule: StructureKillRule) -> None:
        """Fortizar in ship name should match via fallback."""
        kill = MockProcessedKill()
        result = rule.evaluate(
            kill, 30000142, {"victim_ship_name": "Fortizar"}
        )
        assert result.matched is True

    def test_name_fallback_case_insensitive(self, rule: StructureKillRule) -> None:
        """Ship name matching should be case insensitive."""
        kill = MockProcessedKill()
        result = rule.evaluate(
            kill, 30000142, {"victim_ship_name": "ASTRAHUS"}
        )
        assert result.matched is True

        result = rule.evaluate(
            kill, 30000142, {"victim_ship_name": "raitaru"}
        )
        assert result.matched is True

    def test_name_fallback_engineering_complex(self, rule: StructureKillRule) -> None:
        """Engineering complex names should match."""
        for name in ["Raitaru", "Azbel", "Sotiyo"]:
            kill = MockProcessedKill()
            result = rule.evaluate(kill, 30000142, {"victim_ship_name": name})
            assert result.matched is True, f"{name} should match"

    def test_name_fallback_refinery(self, rule: StructureKillRule) -> None:
        """Refinery names should match."""
        for name in ["Athanor", "Tatara"]:
            kill = MockProcessedKill()
            result = rule.evaluate(kill, 30000142, {"victim_ship_name": name})
            assert result.matched is True, f"{name} should match"

    def test_name_fallback_metenox(self, rule: StructureKillRule) -> None:
        """Metenox should match via name."""
        kill = MockProcessedKill()
        result = rule.evaluate(kill, 30000142, {"victim_ship_name": "Metenox Moon Drill"})
        assert result.matched is True

    def test_ship_not_structure(self, rule: StructureKillRule) -> None:
        """Regular ship should not match."""
        kill = MockProcessedKill(victim_ship_type_id=24690)  # Vexor
        result = rule.evaluate(kill, 30000142, {"victim_ship_name": "Vexor"})
        assert result.matched is False
        assert "Victim is not a structure" in (result.reason or "")

    def test_no_group_id_no_name_not_matched(self, rule: StructureKillRule) -> None:
        """Kill with no group ID and no name should not match."""
        kill = MockProcessedKill()
        result = rule.evaluate(kill, 30000142, {})
        assert result.matched is False

    def test_structure_group_ids_constant(self) -> None:
        """Verify STRUCTURE_GROUP_IDS contains expected values."""
        assert 365 in STRUCTURE_GROUP_IDS  # Control Tower
        assert 1657 in STRUCTURE_GROUP_IDS  # Citadel
        assert 1404 in STRUCTURE_GROUP_IDS  # Engineering Complex
        assert 1406 in STRUCTURE_GROUP_IDS  # Refinery
        assert 1408 in STRUCTURE_GROUP_IDS  # Orbital Infrastructure
        assert 2016 in STRUCTURE_GROUP_IDS  # Ansiblex
        assert 2017 in STRUCTURE_GROUP_IDS  # Cyno Beacon
        assert 2233 in STRUCTURE_GROUP_IDS  # Metenox


# =============================================================================
# Test Rule Base Class Behavior
# =============================================================================


class TestBaseRuleProviderBehavior:
    """Tests for common base class behavior across rules."""

    def test_all_rules_have_validate_method(self) -> None:
        """All rules should have a validate method that returns empty list."""
        rules = [
            NpcOnlyRule(),
            PodOnlyRule(),
            CorpMemberVictimRule(),
            AllianceMemberVictimRule(),
            WarTargetActivityRule(),
            WatchlistMatchRule(),
            HighValueRule(),
            GatecampDetectedRule(),
            StructureKillRule(),
        ]
        for rule in rules:
            errors = rule.validate({})
            assert errors == [], f"{rule.name} validate() should return empty list"

    def test_all_rules_return_rule_match(self) -> None:
        """All rules should return RuleMatch objects."""
        from aria_esi.services.redisq.interest_v2.models import RuleMatch

        rules = [
            NpcOnlyRule(),
            PodOnlyRule(),
            CorpMemberVictimRule(),
            AllianceMemberVictimRule(),
            WarTargetActivityRule(),
            WatchlistMatchRule(),
            HighValueRule(),
            GatecampDetectedRule(),
            StructureKillRule(),
        ]
        kill = MockProcessedKill()
        for rule in rules:
            result = rule.evaluate(kill, 30000142, {})
            assert isinstance(result, RuleMatch), f"{rule.name} should return RuleMatch"
            assert result.rule_id == rule.name
