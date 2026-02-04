"""
Entity Interest Layer.

Calculates interest based on who is involved in a kill:
- Corp member victims always get 1.0 (highest priority)
- Alliance members, war targets, and watched entities get high interest
- Requires kill context to provide meaningful scores
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .....core.logging import get_logger
from ..models import LayerScore
from .base import BaseLayer

if TYPE_CHECKING:
    from ...entity_filter import EntityAwareFilter
    from ...models import ProcessedKill

logger = get_logger(__name__)


# =============================================================================
# Default Interest Scores
# =============================================================================

# Corp member deaths are always maximum priority
CORP_MEMBER_VICTIM_INTEREST = 1.0

# Corp member kills (we scored) are high priority
CORP_MEMBER_ATTACKER_INTEREST = 0.9

# Alliance member involvement
ALLIANCE_MEMBER_VICTIM_INTEREST = 0.8
ALLIANCE_MEMBER_ATTACKER_INTEREST = 0.75

# War targets are almost as important as corp members
WAR_TARGET_INTEREST = 0.95

# Manually watched entities
WATCHLIST_ENTITY_INTEREST = 0.9


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class EntityConfig:
    """Configuration for the entity layer."""

    # Our corp/alliance IDs
    corp_id: int | None = None
    alliance_id: int | None = None

    # Entities to watch
    watched_corps: set[int] = field(default_factory=set)
    watched_alliances: set[int] = field(default_factory=set)
    war_targets: set[int] = field(default_factory=set)

    # Configurable interest scores
    corp_member_victim: float = CORP_MEMBER_VICTIM_INTEREST
    corp_member_attacker: float = CORP_MEMBER_ATTACKER_INTEREST
    alliance_member_victim: float = ALLIANCE_MEMBER_VICTIM_INTEREST
    alliance_member_attacker: float = ALLIANCE_MEMBER_ATTACKER_INTEREST
    war_target: float = WAR_TARGET_INTEREST
    watchlist_entity: float = WATCHLIST_ENTITY_INTEREST

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> EntityConfig:
        """Create from config dict."""
        if not data:
            return cls()

        return cls(
            corp_id=data.get("corp_id"),
            alliance_id=data.get("alliance_id"),
            watched_corps=set(data.get("watched_corps", [])),
            watched_alliances=set(data.get("watched_alliances", [])),
            war_targets=set(data.get("war_targets", [])),
            corp_member_victim=data.get("corp_member_victim", CORP_MEMBER_VICTIM_INTEREST),
            corp_member_attacker=data.get("corp_member_attacker", CORP_MEMBER_ATTACKER_INTEREST),
            alliance_member_victim=data.get(
                "alliance_member_victim", ALLIANCE_MEMBER_VICTIM_INTEREST
            ),
            alliance_member_attacker=data.get(
                "alliance_member_attacker", ALLIANCE_MEMBER_ATTACKER_INTEREST
            ),
            war_target=data.get("war_target", WAR_TARGET_INTEREST),
            watchlist_entity=data.get("watchlist_entity", WATCHLIST_ENTITY_INTEREST),
        )

    @property
    def is_configured(self) -> bool:
        """Check if entity tracking is meaningfully configured."""
        return bool(
            self.corp_id
            or self.alliance_id
            or self.watched_corps
            or self.watched_alliances
            or self.war_targets
        )


# =============================================================================
# Entity Layer
# =============================================================================


@dataclass
class EntityLayer(BaseLayer):
    """
    Entity-based interest layer.

    Calculates interest based on who is involved in a kill:
    - Corp member victim: 1.0 (ALWAYS notify, regardless of location)
    - Corp member attacker: 0.9 (we got a kill)
    - Alliance member: 0.8 (coalition activity)
    - War target: 0.95 (strategic importance)
    - Watchlist entity: 0.9 (manually tracked)

    This layer requires kill context to provide meaningful scores.
    score_system() always returns 0.0 since we don't know who's involved
    until we fetch the kill.

    CRITICAL: This layer ensures corp member losses are NEVER missed,
    regardless of geographic location. A corp member dying 50 jumps away
    still gets interest 1.0.
    """

    _name: str = "entity"
    config: EntityConfig = field(default_factory=EntityConfig)

    @property
    def name(self) -> str:
        return self._name

    def score_system(self, system_id: int) -> LayerScore:
        """
        Score a system without kill context.

        Entity layer requires kill context to determine involvement.
        Always returns 0.0 - actual scoring happens in score_kill().

        Args:
            system_id: Solar system ID (unused)

        Returns:
            LayerScore with 0.0 score
        """
        return LayerScore(
            layer=self.name,
            score=0.0,
            reason=None,
        )

    def score_kill(self, system_id: int, kill: ProcessedKill | None) -> LayerScore:
        """
        Score a kill based on entity involvement.

        Checks victim and attackers against configured entities.
        Returns the highest matching interest score.

        Args:
            system_id: Solar system ID (unused - entity interest is location-independent)
            kill: ProcessedKill with victim and attacker data

        Returns:
            LayerScore with interest based on entity matches
        """
        if kill is None:
            return self.score_system(system_id)

        scores: list[tuple[float, str]] = []

        # =================================================================
        # Check victim
        # =================================================================

        # Corp member victim - ALWAYS MAX PRIORITY
        if self.config.corp_id and kill.victim_corporation_id == self.config.corp_id:
            scores.append((self.config.corp_member_victim, "corp member loss"))

        # Alliance member victim
        elif self.config.alliance_id and kill.victim_alliance_id == self.config.alliance_id:
            scores.append((self.config.alliance_member_victim, "alliance member loss"))

        # War target as victim
        if kill.victim_corporation_id and kill.victim_corporation_id in self.config.war_targets:
            scores.append((self.config.war_target, "war target killed"))

        # Watched corp as victim
        if kill.victim_corporation_id and kill.victim_corporation_id in self.config.watched_corps:
            scores.append((self.config.watchlist_entity, "watched corp victim"))

        # Watched alliance as victim
        if kill.victim_alliance_id and kill.victim_alliance_id in self.config.watched_alliances:
            scores.append((self.config.watchlist_entity, "watched alliance victim"))

        # =================================================================
        # Check attackers
        # =================================================================

        # Corp member attacker (we got a kill)
        if self.config.corp_id and self.config.corp_id in kill.attacker_corps:
            scores.append((self.config.corp_member_attacker, "corp member kill"))

        # Alliance member attacker
        if self.config.alliance_id and self.config.alliance_id in kill.attacker_alliances:
            scores.append((self.config.alliance_member_attacker, "alliance member kill"))

        # War target as attacker
        for corp_id in kill.attacker_corps:
            if corp_id in self.config.war_targets:
                scores.append((self.config.war_target, "war target activity"))
                break  # Only count once

        # Watched corp as attacker
        for corp_id in kill.attacker_corps:
            if corp_id in self.config.watched_corps:
                scores.append((self.config.watchlist_entity, "watched corp attacker"))
                break

        # Watched alliance as attacker
        for alliance_id in kill.attacker_alliances:
            if alliance_id in self.config.watched_alliances:
                scores.append((self.config.watchlist_entity, "watched alliance attacker"))
                break

        # =================================================================
        # Return highest score
        # =================================================================

        if scores:
            best_score, best_reason = max(scores, key=lambda x: x[0])
            return LayerScore(
                layer=self.name,
                score=best_score,
                reason=best_reason,
            )

        return LayerScore(layer=self.name, score=0.0, reason=None)

    def refresh_from_filter(self, entity_filter: EntityAwareFilter) -> None:
        """
        Sync watched entities from existing EntityAwareFilter.

        The EntityAwareFilter maintains cached entity IDs from the database.
        This method allows the entity layer to stay in sync with watchlist
        changes.

        Args:
            entity_filter: EntityAwareFilter with cached entity IDs
        """
        entity_filter._ensure_cache()
        self.config.watched_corps = entity_filter._watched_corps.copy()
        self.config.watched_alliances = entity_filter._watched_alliances.copy()
        logger.debug(
            "Synced entity layer from filter: %d corps, %d alliances",
            len(self.config.watched_corps),
            len(self.config.watched_alliances),
        )

    def add_war_target(self, corp_or_alliance_id: int) -> None:
        """Add a war target to track."""
        self.config.war_targets.add(corp_or_alliance_id)
        logger.debug("Added war target: %d", corp_or_alliance_id)

    def remove_war_target(self, corp_or_alliance_id: int) -> None:
        """Remove a war target."""
        self.config.war_targets.discard(corp_or_alliance_id)
        logger.debug("Removed war target: %d", corp_or_alliance_id)

    def to_dict(self) -> dict[str, Any]:
        """Serialize configuration to dict."""
        return {
            "name": self.name,
            "config": {
                "corp_id": self.config.corp_id,
                "alliance_id": self.config.alliance_id,
                "watched_corps": list(self.config.watched_corps),
                "watched_alliances": list(self.config.watched_alliances),
                "war_targets": list(self.config.war_targets),
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EntityLayer:
        """Deserialize from dict."""
        config = EntityConfig.from_dict(data.get("config"))
        return cls(config=config)

    @classmethod
    def from_config(cls, config: EntityConfig) -> EntityLayer:
        """Create layer from configuration."""
        return cls(config=config)
