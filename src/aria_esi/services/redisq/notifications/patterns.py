"""
Pattern Detection for Commentary Warrant.

Detects tactical patterns in killmail data to determine when LLM-generated
commentary would add value to Discord notifications.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ....core.logging import get_logger
from .types import PatternSeverity

if TYPE_CHECKING:
    from ..entity_filter import EntityMatchResult
    from ..models import ProcessedKill
    from ..threat_cache import ThreatCache
    from .npc_factions import NPCFactionTriggerResult

logger = get_logger(__name__)


# =============================================================================
# Known Gank Corps
# =============================================================================

# Corporation IDs of known ganking groups
KNOWN_GANK_CORPS = {
    98506879,  # SAFETY.
    98326526,  # CODE.
}

# Minimum kills for gank rotation detection
GANK_ROTATION_MIN_KILLS = 2


# =============================================================================
# Pattern Configuration
# =============================================================================

# Pattern weights for warrant score calculation
PATTERN_WEIGHTS = {
    "repeat_attacker": 0.4,
    "gank_rotation": 0.5,
    "unusual_victim": 0.3,
    "war_target_activity": 0.5,
    "npc_faction_activity": 0.4,
}

# Thresholds
REPEAT_ATTACKER_MIN_KILLS = 3
HIGH_VALUE_THRESHOLD_ISK = 1_000_000_000  # 1B ISK
WAR_TARGET_MIN_KILLS = 2
NPC_FACTION_MIN_KILLS = 2  # Minimum kills for NPC faction activity pattern


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class DetectedPattern:
    """
    A single detected tactical pattern.

    Each pattern type contributes a weight to the overall warrant score.
    The severity field enables automatic stress-level derivation without
    requiring exhaustive pattern-type maps.
    """

    pattern_type: str  # "repeat_attacker", "gank_rotation", "unusual_victim", etc.
    description: str  # Human-readable for LLM context
    weight: float  # Contribution to warrant score (0.0-0.5)
    context: dict = field(default_factory=dict)  # Pattern-specific data
    severity: PatternSeverity | None = None  # Severity for stress-level derivation

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        result = {
            "pattern_type": self.pattern_type,
            "description": self.description,
            "weight": self.weight,
            "context": self.context,
        }
        if self.severity is not None:
            result["severity"] = self.severity.value
        return result


@dataclass
class PatternContext:
    """
    Aggregated pattern detection results for a kill.

    Used to decide whether to generate commentary and what context
    to provide to the LLM.
    """

    kill: ProcessedKill
    patterns: list[DetectedPattern] = field(default_factory=list)
    same_attacker_kills_1h: int = 0
    same_system_kills_1h: int = 0
    is_watched_entity: bool = False
    watched_entity_kills_1h: int = 0

    def warrant_score(self) -> float:
        """
        Calculate aggregate warrant score from detected patterns.

        Returns:
            Float between 0.0 and 1.0 indicating commentary value
        """
        if not self.patterns:
            return 0.0

        # Sum pattern weights, capped at 1.0
        total = sum(p.weight for p in self.patterns)
        return min(total, 1.0)

    @property
    def has_patterns(self) -> bool:
        """Check if any patterns were detected."""
        return len(self.patterns) > 0

    def get_pattern_descriptions(self) -> list[str]:
        """Get human-readable descriptions of all patterns."""
        return [p.description for p in self.patterns]

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "kill_id": self.kill.kill_id,
            "patterns": [p.to_dict() for p in self.patterns],
            "same_attacker_kills_1h": self.same_attacker_kills_1h,
            "same_system_kills_1h": self.same_system_kills_1h,
            "is_watched_entity": self.is_watched_entity,
            "watched_entity_kills_1h": self.watched_entity_kills_1h,
            "warrant_score": self.warrant_score(),
        }


# =============================================================================
# Pattern Detector
# =============================================================================


class PatternDetector:
    """
    Detects tactical patterns in killmail data.

    Uses ThreatCache to query recent kills and identify patterns that
    warrant LLM-generated commentary.
    """

    def __init__(self, threat_cache: ThreatCache):
        """
        Initialize pattern detector.

        Args:
            threat_cache: ThreatCache instance for querying kills
        """
        self._threat_cache = threat_cache

    async def detect_patterns(
        self,
        kill: ProcessedKill,
        entity_match: EntityMatchResult | None = None,
        npc_faction_result: NPCFactionTriggerResult | None = None,
    ) -> PatternContext:
        """
        Detect patterns for a kill.

        Checks for:
        - repeat_attacker: Same corp with 3+ kills in 1 hour
        - gank_rotation: Known gank corp (SAFETY., CODE.) with 2+ kills
        - unusual_victim: 1B+ ISK loss
        - war_target_activity: Watched entity with 2+ kills
        - npc_faction_activity: NPC faction with 2+ kills in system

        Args:
            kill: The processed killmail to analyze
            entity_match: Entity match result from watchlist filter
            npc_faction_result: NPC faction trigger result (if this is a faction kill)

        Returns:
            PatternContext with detected patterns and context
        """
        patterns: list[DetectedPattern] = []

        # Get recent kills in same system for context
        system_kills = self._threat_cache.get_recent_kills(
            system_id=kill.solar_system_id,
            since_minutes=60,
            limit=100,
        )
        same_system_kills_1h = len(system_kills)

        # Analyze attacker patterns
        same_attacker_kills_1h = 0
        attacker_corp_ids = set(kill.attacker_corps)

        if attacker_corp_ids:
            # Count kills by same attacker corps in last hour
            for recent_kill in system_kills:
                if recent_kill.kill_id == kill.kill_id:
                    continue
                if set(recent_kill.attacker_corps) & attacker_corp_ids:
                    same_attacker_kills_1h += 1

            # Check for repeat attacker pattern
            if (
                same_attacker_kills_1h >= REPEAT_ATTACKER_MIN_KILLS - 1
            ):  # -1 because current kill counts
                total_kills = same_attacker_kills_1h + 1
                patterns.append(
                    DetectedPattern(
                        pattern_type="repeat_attacker",
                        description=f"Same attackers responsible for {total_kills} kills in this system in the last hour",
                        weight=PATTERN_WEIGHTS["repeat_attacker"],
                        context={
                            "attacker_corp_ids": list(attacker_corp_ids),
                            "kills_count": total_kills,
                        },
                        severity=PatternSeverity.WARNING,
                    )
                )

            # Check for gank rotation pattern (known gank corps)
            known_gank_matches = attacker_corp_ids & KNOWN_GANK_CORPS
            if known_gank_matches and same_attacker_kills_1h >= GANK_ROTATION_MIN_KILLS - 1:
                total_kills = same_attacker_kills_1h + 1
                patterns.append(
                    DetectedPattern(
                        pattern_type="gank_rotation",
                        description=f"Known ganking group with {total_kills} kills in this system - active gank rotation",
                        weight=PATTERN_WEIGHTS["gank_rotation"],
                        context={
                            "gank_corp_ids": list(known_gank_matches),
                            "kills_count": total_kills,
                        },
                        severity=PatternSeverity.CRITICAL,
                    )
                )

        # Check for unusual victim (high value)
        if kill.total_value >= HIGH_VALUE_THRESHOLD_ISK:
            value_display = f"{kill.total_value / 1_000_000_000:.1f}B"
            patterns.append(
                DetectedPattern(
                    pattern_type="unusual_victim",
                    description=f"High-value loss: {value_display} ISK",
                    weight=PATTERN_WEIGHTS["unusual_victim"],
                    context={
                        "total_value": kill.total_value,
                        "value_display": value_display,
                    },
                    severity=PatternSeverity.WARNING,
                )
            )

        # Check for war target activity
        is_watched = entity_match is not None and entity_match.has_match
        watched_entity_kills_1h = 0

        if is_watched:
            # Get watched entity kills in last hour
            watched_kills = self._threat_cache._get_db().get_watched_entity_kills(
                since_minutes=60,
                limit=100,
            )
            watched_entity_kills_1h = len(watched_kills)

            if watched_entity_kills_1h >= WAR_TARGET_MIN_KILLS:
                patterns.append(
                    DetectedPattern(
                        pattern_type="war_target_activity",
                        description=f"Watched entity involved in {watched_entity_kills_1h} kills in the last hour",
                        weight=PATTERN_WEIGHTS["war_target_activity"],
                        context={
                            "matched_entity_ids": entity_match.all_matched_ids
                            if entity_match
                            else [],
                            "kills_count": watched_entity_kills_1h,
                            "match_types": entity_match.match_types if entity_match else [],
                        },
                        severity=PatternSeverity.CRITICAL,
                    )
                )

        # Check for NPC faction activity pattern
        npc_faction_pattern = self._detect_npc_faction_activity(
            kill=kill,
            npc_result=npc_faction_result,
            system_kills=system_kills,
        )
        if npc_faction_pattern:
            patterns.append(npc_faction_pattern)

        return PatternContext(
            kill=kill,
            patterns=patterns,
            same_attacker_kills_1h=same_attacker_kills_1h,
            same_system_kills_1h=same_system_kills_1h,
            is_watched_entity=is_watched,
            watched_entity_kills_1h=watched_entity_kills_1h,
        )

    def _detect_npc_faction_activity(
        self,
        kill: ProcessedKill,
        npc_result: NPCFactionTriggerResult | None,
        system_kills: list[ProcessedKill],
    ) -> DetectedPattern | None:
        """
        Detect sustained NPC faction activity pattern.

        Triggers when an NPC faction has 2+ kills in the same system within the
        last hour. This enables LLM commentary for "faction operations in progress".

        Args:
            kill: The current kill
            npc_result: NPC faction trigger result (None if not a faction kill)
            system_kills: Recent kills in the same system

        Returns:
            DetectedPattern if faction activity detected, None otherwise
        """
        if not npc_result or not npc_result.matched:
            return None

        # Get faction mapper to check for same-faction kills
        from .npc_factions import get_npc_faction_mapper

        mapper = get_npc_faction_mapper()
        faction_corps = mapper.get_corps_for_faction(npc_result.faction)

        if not faction_corps:
            return None

        # Count recent kills by same NPC faction
        faction_kills_count = 0
        for recent_kill in system_kills:
            if recent_kill.kill_id == kill.kill_id:
                continue

            # Check if any attacker is from the same faction
            for attacker_corp_id in recent_kill.attacker_corps:
                if attacker_corp_id in faction_corps:
                    faction_kills_count += 1
                    break  # Count once per kill

        # Only trigger pattern if there are 2+ kills (including current)
        total_faction_kills = faction_kills_count + 1  # +1 for current kill

        if total_faction_kills >= NPC_FACTION_MIN_KILLS:
            faction_display = mapper.get_faction_display_name(npc_result.faction)
            return DetectedPattern(
                pattern_type="npc_faction_activity",
                description=f"{faction_display} operations active: {total_faction_kills} kills in this system",
                weight=PATTERN_WEIGHTS["npc_faction_activity"],
                context={
                    "faction": npc_result.faction,
                    "faction_display": faction_display,
                    "corporation_id": npc_result.corporation_id,
                    "corporation_name": npc_result.corporation_name,
                    "kill_count": total_faction_kills,
                    "role": npc_result.role,
                },
                severity=PatternSeverity.INFO,
            )

        return None
