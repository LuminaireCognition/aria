"""
War Signal for Interest Engine v2.

Scores kills involving war targets based on standings and war status.

Prefetch capable: NO (requires war data from ESI)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..models import SignalScore
from ..providers.base import BaseSignalProvider

if TYPE_CHECKING:
    from ...models import ProcessedKill


class WarSignal(BaseSignalProvider):
    """
    War and standings-based scoring signal.

    Scores kills involving war targets or entities with negative standings.

    Config:
        war_targets: Set of corp/alliance IDs we're at war with
        standings: Dict of entity_id -> standing (-10 to +10)
        hostile_threshold: Standing below which entities are considered hostile
        war_score: Score for war target involvement
        hostile_score: Score for hostile (negative standing) involvement

    Prefetch capable: NO (requires war data lookup)
    """

    _name = "war"
    _category = "war"
    _prefetch_capable = False

    DEFAULT_WAR_SCORE = 0.95
    DEFAULT_HOSTILE_SCORE = 0.7
    DEFAULT_HOSTILE_THRESHOLD = -5.0

    def score(
        self,
        kill: ProcessedKill | None,
        system_id: int,
        config: dict[str, Any],
    ) -> SignalScore:
        """Score based on war/standings."""
        war_targets = set(config.get("war_targets", []))
        standings = config.get("standings", {})

        if not war_targets and not standings:
            return SignalScore(
                signal=self._name,
                score=0.0,
                reason="No war targets or standings configured",
                prefetch_capable=False,
            )

        if kill is None:
            return SignalScore(
                signal=self._name,
                score=0.0,
                reason="No kill data",
                prefetch_capable=False,
            )

        war_score = config.get("war_score", self.DEFAULT_WAR_SCORE)
        hostile_score = config.get("hostile_score", self.DEFAULT_HOSTILE_SCORE)
        hostile_threshold = config.get("hostile_threshold", self.DEFAULT_HOSTILE_THRESHOLD)

        # Check victim for war target
        victim_entities = []
        if kill.victim_corporation_id:
            victim_entities.append(kill.victim_corporation_id)
        if kill.victim_alliance_id:
            victim_entities.append(kill.victim_alliance_id)

        for entity_id in victim_entities:
            if entity_id in war_targets:
                return SignalScore(
                    signal=self._name,
                    score=war_score,
                    reason="War target died",
                    prefetch_capable=False,
                    raw_value={"match_type": "war_target", "role": "victim"},
                )

        # Check attackers for war target
        attacker_entities = list(kill.attacker_corps) + list(kill.attacker_alliances)
        for entity_id in attacker_entities:
            if entity_id in war_targets:
                return SignalScore(
                    signal=self._name,
                    score=war_score,
                    reason="War target scored a kill",
                    prefetch_capable=False,
                    raw_value={"match_type": "war_target", "role": "attacker"},
                )

        # Check standings
        if standings:
            # Check victim standings
            for entity_id in victim_entities:
                standing = standings.get(str(entity_id)) or standings.get(entity_id)
                if standing is not None and standing <= hostile_threshold:
                    return SignalScore(
                        signal=self._name,
                        score=hostile_score,
                        reason=f"Hostile entity died (standing: {standing})",
                        prefetch_capable=False,
                        raw_value={"match_type": "hostile", "standing": standing},
                    )

            # Check attacker standings
            for entity_id in attacker_entities:
                standing = standings.get(str(entity_id)) or standings.get(entity_id)
                if standing is not None and standing <= hostile_threshold:
                    return SignalScore(
                        signal=self._name,
                        score=hostile_score * 0.8,  # Slightly lower for attacker
                        reason=f"Hostile entity active (standing: {standing})",
                        prefetch_capable=False,
                        raw_value={"match_type": "hostile", "standing": standing},
                    )

        return SignalScore(
            signal=self._name,
            score=0.0,
            reason="No war target or hostile involvement",
            prefetch_capable=False,
        )

    def validate(self, config: dict[str, Any]) -> list[str]:
        """Validate war signal config."""
        errors = []

        # Validate scores
        for score_field in ("war_score", "hostile_score"):
            if score_field in config:
                score = config[score_field]
                if not isinstance(score, (int, float)) or not (0 <= score <= 1):
                    errors.append(f"'{score_field}' must be between 0 and 1")

        # Validate threshold
        if "hostile_threshold" in config:
            threshold = config["hostile_threshold"]
            if not isinstance(threshold, (int, float)) or not (-10 <= threshold <= 10):
                errors.append("'hostile_threshold' must be between -10 and 10")

        return errors
