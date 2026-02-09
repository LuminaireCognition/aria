"""
Politics Signal for Interest Engine v2.

Scores based on entity group involvement with role weighting.
Implements the deterministic politics aggregation algorithm from the proposal.

Prefetch capable: PARTIAL (victim only - attacker details require ESI)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..models import SignalScore
from ..providers.base import BaseSignalProvider

if TYPE_CHECKING:
    from ...models import ProcessedKill


# Default role weights
DEFAULT_ROLE_WEIGHTS = {
    "victim": 1.0,
    "final_blow": 0.8,
    "attacker": 0.6,
    "solo": 1.0,  # Multiplier applied when single attacker
}


class PoliticsSignal(BaseSignalProvider):
    """
    Entity group-based political involvement scoring.

    Implements the deterministic algorithm from the proposal:
    1. Match entities to groups by role
    2. Calculate per-group scores with role weights
    3. Aggregate across groups (max for require_any, min for require_all)
    4. Apply penalties

    Config:
        groups: Dict of group_name -> {corporations: [], alliances: [], factions: []}
        role_weights: Optional dict overriding DEFAULT_ROLE_WEIGHTS
        require_any: List of group names (at least one must match)
        require_all: List of group names (all must match)
        penalties: List of {condition: str, penalty: float}

    Prefetch capable: PARTIAL (victim corp/alliance in RedisQ, attackers require ESI)
    """

    _name = "politics"
    _category = "politics"
    _prefetch_capable = False  # Conservative - attacker details need ESI

    def score(
        self,
        kill: ProcessedKill | None,
        system_id: int,
        config: dict[str, Any],
    ) -> SignalScore:
        """Score based on political entity involvement."""
        groups = config.get("groups", {})

        if not groups:
            return SignalScore(
                signal=self._name,
                score=0.0,
                reason="No political groups configured",
                prefetch_capable=True,
            )

        if kill is None:
            return SignalScore(
                signal=self._name,
                score=0.0,
                reason="No kill data",
                prefetch_capable=True,
            )

        role_weights = {**DEFAULT_ROLE_WEIGHTS, **config.get("role_weights", {})}

        # Step 1 & 2: Calculate per-group scores
        group_scores = {}
        group_reasons = {}

        for group_name, group_config in groups.items():
            score, reason = self._calculate_group_score(kill, group_config, role_weights)
            if score > 0:
                group_scores[group_name] = score
                group_reasons[group_name] = reason

        if not group_scores:
            return SignalScore(
                signal=self._name,
                score=0.0,
                reason="No group matches",
                prefetch_capable=False,
            )

        # Step 3: Aggregate across groups
        require_any = config.get("require_any", [])
        require_all = config.get("require_all", [])

        if require_all:
            # All listed groups must match
            missing = [g for g in require_all if g not in group_scores]
            if missing:
                return SignalScore(
                    signal=self._name,
                    score=0.0,
                    reason=f"require_all not met: missing {missing}",
                    prefetch_capable=False,
                )
            # Take minimum score of required groups
            final_score = min(group_scores[g] for g in require_all)
            matched_groups = require_all
        elif require_any:
            # At least one listed group must match
            matched = [g for g in require_any if g in group_scores]
            if not matched:
                return SignalScore(
                    signal=self._name,
                    score=0.0,
                    reason=f"require_any not met: none of {require_any} matched",
                    prefetch_capable=False,
                )
            # Take maximum score of matched groups
            final_score = max(group_scores[g] for g in matched)
            matched_groups = matched
        else:
            # No gates - take maximum of all matched groups
            final_score = max(group_scores.values())
            matched_groups = list(group_scores.keys())

        # Step 4: Apply penalties
        penalties = config.get("penalties", [])
        penalty_factor = 1.0
        penalty_reasons = []

        for penalty_config in penalties:
            penalty_value = penalty_config.get("penalty", 0)
            condition = penalty_config.get("condition", "")

            # Evaluate simple conditions
            if self._evaluate_penalty_condition(condition, kill, config):
                penalty_factor -= penalty_value
                penalty_reasons.append(f"{condition}: -{penalty_value:.0%}")

        # Clamp penalty factor
        penalty_factor = max(0.0, min(1.0, penalty_factor))
        final_score = final_score * penalty_factor

        # Build reason
        if len(matched_groups) == 1:
            reason = group_reasons.get(matched_groups[0], f"Group '{matched_groups[0]}' matched")
        else:
            reason = f"Groups matched: {', '.join(matched_groups)}"

        if penalty_reasons:
            reason += f" (penalties: {', '.join(penalty_reasons)})"

        return SignalScore(
            signal=self._name,
            score=final_score,
            reason=reason,
            prefetch_capable=False,
            raw_value={"groups": list(group_scores.keys()), "penalty_factor": penalty_factor},
        )

    def _calculate_group_score(
        self,
        kill: ProcessedKill,
        group_config: dict[str, Any],
        role_weights: dict[str, float],
    ) -> tuple[float, str]:
        """
        Calculate score for a single entity group.

        Returns (score, reason)
        """
        corporations = set(group_config.get("corporations", []))
        alliances = set(group_config.get("alliances", []))
        _factions = set(group_config.get("factions", []))  # Reserved for faction matching

        # Check victim
        victim_match = (
            (kill.victim_corporation_id and kill.victim_corporation_id in corporations)
            or (kill.victim_alliance_id and kill.victim_alliance_id in alliances)
            # Faction matching would require additional victim data
        )
        victim_score = role_weights["victim"] if victim_match else 0.0

        # Check attackers (requires full kill data)
        final_blow_match = False
        attacker_match = False

        # For now, check against attacker corps/alliances
        for corp_id in kill.attacker_corps:
            if corp_id in corporations:
                attacker_match = True
                break
        for alliance_id in kill.attacker_alliances:
            if alliance_id in alliances:
                attacker_match = True
                break

        # Solo modifier
        solo_modifier = role_weights["solo"] if kill.attacker_count == 1 else 1.0

        # Calculate scores
        final_blow_score = role_weights["final_blow"] * solo_modifier if final_blow_match else 0.0
        attacker_score = role_weights["attacker"] * solo_modifier if attacker_match else 0.0

        # Take maximum
        max_score = max(victim_score, final_blow_score, attacker_score)

        # Build reason
        if victim_score == max_score and victim_match:
            reason = "Victim matches group"
        elif final_blow_score == max_score and final_blow_match:
            reason = "Final blow matches group"
        elif attacker_score == max_score and attacker_match:
            reason = "Attacker matches group"
        else:
            reason = "Group matched"

        return max_score, reason

    def _evaluate_penalty_condition(
        self,
        condition: str,
        kill: ProcessedKill,
        config: dict[str, Any],
    ) -> bool:
        """Evaluate a simple penalty condition."""
        # Simple condition evaluation
        condition = condition.lower().strip()

        if condition == "is_pod":
            return kill.is_pod_kill

        if condition == "is_solo":
            return kill.attacker_count == 1

        if condition == "is_npc_only":
            # Check if all attackers are NPCs (corp ID < 2M)
            return all(corp < 2_000_000 for corp in kill.attacker_corps if corp)

        # Unknown condition - don't apply penalty
        return False

    def validate(self, config: dict[str, Any]) -> list[str]:
        """Validate politics signal config."""
        errors = []
        groups = config.get("groups", {})

        if not groups:
            errors.append("At least one political group must be configured")
            return errors

        for group_name, group_config in groups.items():
            if not isinstance(group_config, dict):
                errors.append(f"Group '{group_name}' must be a dictionary")
                continue

            corporations = group_config.get("corporations", [])
            alliances = group_config.get("alliances", [])
            factions = group_config.get("factions", [])

            if not corporations and not alliances and not factions:
                errors.append(
                    f"Group '{group_name}' must have at least one corporation, alliance, or faction"
                )

        # Validate require_any/require_all reference existing groups
        for gate_name in ("require_any", "require_all"):
            gate_groups = config.get(gate_name, [])
            for group_name in gate_groups:
                if group_name not in groups:
                    errors.append(f"{gate_name} references unknown group: '{group_name}'")

        # Validate role weights
        role_weights = config.get("role_weights", {})
        valid_roles = {"victim", "final_blow", "attacker", "solo"}
        for role, weight in role_weights.items():
            if role not in valid_roles:
                errors.append(f"Unknown role weight: '{role}'. Valid: {valid_roles}")
            if not isinstance(weight, (int, float)) or weight < 0:
                errors.append(f"Role weight '{role}' must be a non-negative number")

        return errors
