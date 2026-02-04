"""
Built-in Rules for Interest Engine v2.

These rules are always available and can be referenced by ID in
rules.always_notify and rules.always_ignore.

| Rule ID                  | Prefetch | Description                    |
|--------------------------|----------|--------------------------------|
| npc_only                 | ✓        | Exclude NPC-only deaths        |
| pod_only                 | ✓        | Exclude/include pod kills      |
| corp_member_victim       | Partial  | Corp member losses             |
| alliance_member_victim   | Partial  | Alliance member losses         |
| war_target_activity      | ✗        | War target kills/losses        |
| watchlist_match          | ✓        | Watchlist victim detection     |
| high_value               | ✓        | High-value kills               |
| gatecamp_detected        | ✗        | Gatecamp activity              |
| structure_kill           | ✓        | Structure destruction          |
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..models import RuleMatch
from ..providers.base import BaseRuleProvider

if TYPE_CHECKING:
    from ...models import ProcessedKill


# =============================================================================
# Ship Type Constants
# =============================================================================

# Capsule (pod) type IDs
CAPSULE_TYPE_IDS = {
    670,  # Capsule
    33328,  # Capsule - Genolution 'Auroral' 197-variant
}

# Structure group IDs (for structure_kill detection)
STRUCTURE_GROUP_IDS = {
    365,  # Control Tower (POS)
    1657,  # Citadel (Astrahus, Fortizar, Keepstar)
    1404,  # Engineering Complex
    1406,  # Refinery
    1408,  # Orbital Infrastructure (POCO, etc.)
    2016,  # Upwell Jump Gate (Ansiblex)
    2017,  # Upwell Cyno Beacon
    2233,  # Metenox Moon Drill
}


# =============================================================================
# Built-in Rules
# =============================================================================


class NpcOnlyRule(BaseRuleProvider):
    """
    Detect kills with no player attackers (NPC-only).

    Use in always_ignore to filter out NPC deaths (ratting losses, etc.)

    Prefetch capable: YES (attacker count visible in RedisQ, but not NPC flag)
    Note: For accurate detection, requires post-fetch to check corporation IDs.
    At prefetch, uses heuristics (NPC corps have ID < 2000000).
    """

    _name = "npc_only"
    _prefetch_capable = True  # Heuristic available at prefetch

    def evaluate(
        self,
        kill: ProcessedKill | None,
        system_id: int,
        config: dict[str, Any],
    ) -> RuleMatch:
        """Check if kill has no player attackers."""
        if kill is None:
            # At prefetch, we can't determine this accurately
            return RuleMatch(
                rule_id=self._name,
                matched=False,
                reason="Requires kill data for accurate NPC detection",
                prefetch_capable=False,
            )

        # Check if all attackers are NPCs
        # NPC corporations have IDs < 2,000,000
        npc_threshold = 2_000_000

        if not kill.attacker_corps:
            # No attacker corp info = unknown
            return RuleMatch(
                rule_id=self._name,
                matched=False,
                reason="No attacker corporation data",
            )

        all_npc = all(corp_id < npc_threshold for corp_id in kill.attacker_corps if corp_id)

        if all_npc:
            return RuleMatch(
                rule_id=self._name,
                matched=True,
                reason="All attackers are NPCs",
            )

        return RuleMatch(
            rule_id=self._name,
            matched=False,
            reason="Has player attackers",
        )


class PodOnlyRule(BaseRuleProvider):
    """
    Detect pod (capsule) kills.

    Use in always_ignore to filter out pods, or always_notify to prioritize them.

    Prefetch capable: YES (victim ship_type_id visible in RedisQ)
    """

    _name = "pod_only"
    _prefetch_capable = True

    def evaluate(
        self,
        kill: ProcessedKill | None,
        system_id: int,
        config: dict[str, Any],
    ) -> RuleMatch:
        """Check if victim is a pod."""
        if kill is None:
            return RuleMatch(
                rule_id=self._name,
                matched=False,
                reason="No kill data",
                prefetch_capable=True,
            )

        is_pod = kill.victim_ship_type_id in CAPSULE_TYPE_IDS

        if is_pod:
            return RuleMatch(
                rule_id=self._name,
                matched=True,
                reason="Victim is a capsule (pod)",
            )

        return RuleMatch(
            rule_id=self._name,
            matched=False,
            reason="Victim is not a capsule",
        )


class CorpMemberVictimRule(BaseRuleProvider):
    """
    Detect when a corporation member is the victim.

    Configuration required: corp_id in profile entity config.

    Prefetch capable: PARTIAL (victim corp_id visible, but need config access)
    """

    _name = "corp_member_victim"
    _prefetch_capable = True  # Victim corp is in RedisQ

    def evaluate(
        self,
        kill: ProcessedKill | None,
        system_id: int,
        config: dict[str, Any],
    ) -> RuleMatch:
        """Check if victim is a corp member."""
        corp_id = config.get("corp_id")

        if not corp_id:
            return RuleMatch(
                rule_id=self._name,
                matched=False,
                reason="No corp_id configured",
            )

        if kill is None:
            return RuleMatch(
                rule_id=self._name,
                matched=False,
                reason="No kill data",
                prefetch_capable=True,
            )

        if kill.victim_corporation_id == corp_id:
            return RuleMatch(
                rule_id=self._name,
                matched=True,
                reason=f"Victim is corp member (corp {corp_id})",
            )

        return RuleMatch(
            rule_id=self._name,
            matched=False,
            reason="Victim is not a corp member",
        )


class AllianceMemberVictimRule(BaseRuleProvider):
    """
    Detect when an alliance member is the victim.

    Configuration required: alliance_id in profile entity config.

    Prefetch capable: PARTIAL (victim alliance_id visible in RedisQ)
    """

    _name = "alliance_member_victim"
    _prefetch_capable = True

    def evaluate(
        self,
        kill: ProcessedKill | None,
        system_id: int,
        config: dict[str, Any],
    ) -> RuleMatch:
        """Check if victim is an alliance member."""
        alliance_id = config.get("alliance_id")

        if not alliance_id:
            return RuleMatch(
                rule_id=self._name,
                matched=False,
                reason="No alliance_id configured",
            )

        if kill is None:
            return RuleMatch(
                rule_id=self._name,
                matched=False,
                reason="No kill data",
                prefetch_capable=True,
            )

        if kill.victim_alliance_id == alliance_id:
            return RuleMatch(
                rule_id=self._name,
                matched=True,
                reason=f"Victim is alliance member (alliance {alliance_id})",
            )

        return RuleMatch(
            rule_id=self._name,
            matched=False,
            reason="Victim is not an alliance member",
        )


class WarTargetActivityRule(BaseRuleProvider):
    """
    Detect kills involving war targets.

    Configuration required: war_targets list of entity IDs.

    Prefetch capable: NO (requires attacker details)
    """

    _name = "war_target_activity"
    _prefetch_capable = False

    def evaluate(
        self,
        kill: ProcessedKill | None,
        system_id: int,
        config: dict[str, Any],
    ) -> RuleMatch:
        """Check if kill involves war targets."""
        war_targets = config.get("war_targets", set())

        if not war_targets:
            return RuleMatch(
                rule_id=self._name,
                matched=False,
                reason="No war targets configured",
            )

        if kill is None:
            return RuleMatch(
                rule_id=self._name,
                matched=False,
                reason="Requires kill data for war target detection",
                prefetch_capable=False,
            )

        # Convert to set if needed
        if not isinstance(war_targets, set):
            war_targets = set(war_targets)

        # Check victim
        if kill.victim_corporation_id in war_targets:
            return RuleMatch(
                rule_id=self._name,
                matched=True,
                reason="Victim corp is a war target",
            )
        if kill.victim_alliance_id and kill.victim_alliance_id in war_targets:
            return RuleMatch(
                rule_id=self._name,
                matched=True,
                reason="Victim alliance is a war target",
            )

        # Check attackers
        for corp_id in kill.attacker_corps:
            if corp_id in war_targets:
                return RuleMatch(
                    rule_id=self._name,
                    matched=True,
                    reason="Attacker corp is a war target",
                )
        for alliance_id in kill.attacker_alliances:
            if alliance_id in war_targets:
                return RuleMatch(
                    rule_id=self._name,
                    matched=True,
                    reason="Attacker alliance is a war target",
                )

        return RuleMatch(
            rule_id=self._name,
            matched=False,
            reason="No war target involvement",
        )


class WatchlistMatchRule(BaseRuleProvider):
    """
    Detect when the victim is on the global watchlist.

    Victim-only for prefetch capability. For attacker matching,
    use politics.groups with prefetch.mode: conservative.

    Prefetch capable: YES (victim corp/alliance in RedisQ)
    """

    _name = "watchlist_match"
    _prefetch_capable = True

    def evaluate(
        self,
        kill: ProcessedKill | None,
        system_id: int,
        config: dict[str, Any],
    ) -> RuleMatch:
        """Check if victim is on global watchlist."""
        watched_corps = config.get("watched_corps", set())
        watched_alliances = config.get("watched_alliances", set())

        if not watched_corps and not watched_alliances:
            return RuleMatch(
                rule_id=self._name,
                matched=False,
                reason="Watchlist is empty",
            )

        if kill is None:
            return RuleMatch(
                rule_id=self._name,
                matched=False,
                reason="No kill data",
                prefetch_capable=True,
            )

        # Convert to sets if needed
        if not isinstance(watched_corps, set):
            watched_corps = set(watched_corps)
        if not isinstance(watched_alliances, set):
            watched_alliances = set(watched_alliances)

        # Check victim only (for prefetch capability)
        if kill.victim_corporation_id in watched_corps:
            return RuleMatch(
                rule_id=self._name,
                matched=True,
                reason="Victim corp is on watchlist",
            )
        if kill.victim_alliance_id and kill.victim_alliance_id in watched_alliances:
            return RuleMatch(
                rule_id=self._name,
                matched=True,
                reason="Victim alliance is on watchlist",
            )

        return RuleMatch(
            rule_id=self._name,
            matched=False,
            reason="Victim not on watchlist",
        )


class HighValueRule(BaseRuleProvider):
    """
    Detect kills exceeding a value threshold.

    Requires signals.value.min to be configured for threshold.
    Falls back to config.high_value_threshold or 1B ISK.

    Prefetch capable: YES (zkb.totalValue in RedisQ)
    """

    _name = "high_value"
    _prefetch_capable = True

    def evaluate(
        self,
        kill: ProcessedKill | None,
        system_id: int,
        config: dict[str, Any],
    ) -> RuleMatch:
        """Check if kill exceeds value threshold."""
        # Get threshold from config
        threshold = config.get("high_value_threshold", 1_000_000_000.0)  # 1B default

        # Override with signals.value.min if present
        signals_config = config.get("signals", {})
        value_config = signals_config.get("value", {})
        if "min" in value_config:
            threshold = value_config["min"]

        if kill is None:
            return RuleMatch(
                rule_id=self._name,
                matched=False,
                reason="No kill data",
                prefetch_capable=True,
            )

        if kill.total_value >= threshold:
            value_str = _format_isk(kill.total_value)
            threshold_str = _format_isk(threshold)
            return RuleMatch(
                rule_id=self._name,
                matched=True,
                reason=f"Value {value_str} >= threshold {threshold_str}",
            )

        return RuleMatch(
            rule_id=self._name,
            matched=False,
            reason=f"Value below threshold ({_format_isk(threshold)})",
        )


class GatecampDetectedRule(BaseRuleProvider):
    """
    Detect gatecamp activity patterns.

    Requires activity analysis context (kill patterns, timing, etc.)

    Prefetch capable: NO (requires pattern analysis)
    """

    _name = "gatecamp_detected"
    _prefetch_capable = False

    def evaluate(
        self,
        kill: ProcessedKill | None,
        system_id: int,
        config: dict[str, Any],
    ) -> RuleMatch:
        """Check if gatecamp pattern detected."""
        # Gatecamp status should be passed in config context
        gatecamp_status = config.get("gatecamp_status")

        if gatecamp_status is None:
            return RuleMatch(
                rule_id=self._name,
                matched=False,
                reason="No gatecamp analysis available",
                prefetch_capable=False,
            )

        # Check confidence level
        confidence = getattr(gatecamp_status, "confidence", None)
        if confidence in ("medium", "high"):
            return RuleMatch(
                rule_id=self._name,
                matched=True,
                reason=f"Gatecamp detected ({confidence} confidence)",
            )

        return RuleMatch(
            rule_id=self._name,
            matched=False,
            reason="No gatecamp pattern detected",
        )


class StructureKillRule(BaseRuleProvider):
    """
    Detect structure destruction.

    Matches citadels, engineering complexes, refineries, POCOs, etc.

    Prefetch capable: YES (victim ship_type_id / group in RedisQ)
    """

    _name = "structure_kill"
    _prefetch_capable = True

    def evaluate(
        self,
        kill: ProcessedKill | None,
        system_id: int,
        config: dict[str, Any],
    ) -> RuleMatch:
        """Check if victim is a structure."""
        if kill is None:
            return RuleMatch(
                rule_id=self._name,
                matched=False,
                reason="No kill data",
                prefetch_capable=True,
            )

        # Check if victim ship group is a structure
        # This requires group ID lookup which may need SDE
        victim_group_id = config.get("victim_group_id")

        if victim_group_id and victim_group_id in STRUCTURE_GROUP_IDS:
            return RuleMatch(
                rule_id=self._name,
                matched=True,
                reason=f"Structure destroyed (group {victim_group_id})",
            )

        # Fallback: check ship type name if available
        ship_name = config.get("victim_ship_name", "").lower()
        structure_keywords = [
            "citadel",
            "astrahus",
            "fortizar",
            "keepstar",
            "raitaru",
            "azbel",
            "sotiyo",
            "athanor",
            "tatara",
            "ansiblex",
            "pharolux",
            "tenebrex",
            "metenox",
        ]
        if any(kw in ship_name for kw in structure_keywords):
            return RuleMatch(
                rule_id=self._name,
                matched=True,
                reason=f"Structure destroyed ({ship_name})",
            )

        return RuleMatch(
            rule_id=self._name,
            matched=False,
            reason="Victim is not a structure",
        )


# =============================================================================
# Helpers
# =============================================================================


def _format_isk(value: float) -> str:
    """Format ISK value for display."""
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{value:.0f}"
