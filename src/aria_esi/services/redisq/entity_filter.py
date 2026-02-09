"""
Entity-Aware Kill Filtering.

Checks kills against watched entity watchlists and flags matches.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ...core.logging import get_logger

if TYPE_CHECKING:
    from .models import ProcessedKill

logger = get_logger(__name__)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class EntityMatchResult:
    """
    Result of checking a kill against watched entities.

    Flags which entities matched and in what role.
    """

    has_match: bool = False

    # Matched entity IDs by role
    victim_corp_match: int | None = None
    victim_alliance_match: int | None = None
    attacker_corp_matches: list[int] = field(default_factory=list)
    attacker_alliance_matches: list[int] = field(default_factory=list)

    @property
    def all_matched_ids(self) -> list[int]:
        """Get all matched entity IDs as a flat list."""
        ids: list[int] = []
        if self.victim_corp_match:
            ids.append(self.victim_corp_match)
        if self.victim_alliance_match:
            ids.append(self.victim_alliance_match)
        ids.extend(self.attacker_corp_matches)
        ids.extend(self.attacker_alliance_matches)
        return ids

    @property
    def match_types(self) -> list[str]:
        """Get list of match type descriptions."""
        types: list[str] = []
        if self.victim_corp_match:
            types.append("victim_corp")
        if self.victim_alliance_match:
            types.append("victim_alliance")
        if self.attacker_corp_matches:
            types.append("attacker_corp")
        if self.attacker_alliance_matches:
            types.append("attacker_alliance")
        return types

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "has_match": self.has_match,
            "victim_corp_match": self.victim_corp_match,
            "victim_alliance_match": self.victim_alliance_match,
            "attacker_corp_matches": self.attacker_corp_matches,
            "attacker_alliance_matches": self.attacker_alliance_matches,
            "all_matched_ids": self.all_matched_ids,
            "match_types": self.match_types,
        }


# =============================================================================
# Entity-Aware Filter
# =============================================================================


class EntityAwareFilter:
    """
    Filters kills based on watched entity watchlists.

    Maintains an in-memory cache of watched entities for fast
    kill processing. Call refresh_cache() to reload from database.
    """

    def __init__(self, owner_character_id: int | None = None):
        """
        Initialize entity filter.

        Args:
            owner_character_id: Character ID for pilot-specific watchlists
        """
        self.owner_character_id = owner_character_id

        # Cached entity IDs for fast lookup
        self._watched_corps: set[int] = set()
        self._watched_alliances: set[int] = set()
        self._cache_loaded = False

    def refresh_cache(self) -> None:
        """
        Reload watched entity IDs from database.

        Should be called:
        - On startup
        - After watchlist modifications
        - Periodically (e.g., every 5 minutes)
        """
        from .entity_watchlist import get_entity_watchlist_manager

        manager = get_entity_watchlist_manager()
        self._watched_corps, self._watched_alliances = manager.get_all_watched_entity_ids(
            self.owner_character_id
        )
        self._cache_loaded = True

        logger.debug(
            "Entity filter cache refreshed: %d corps, %d alliances",
            len(self._watched_corps),
            len(self._watched_alliances),
        )

    def _ensure_cache(self) -> None:
        """Ensure cache is loaded before use."""
        if not self._cache_loaded:
            self.refresh_cache()

    @property
    def watched_corp_count(self) -> int:
        """Get count of watched corporations."""
        self._ensure_cache()
        return len(self._watched_corps)

    @property
    def watched_alliance_count(self) -> int:
        """Get count of watched alliances."""
        self._ensure_cache()
        return len(self._watched_alliances)

    @property
    def is_active(self) -> bool:
        """Check if there are any watched entities."""
        self._ensure_cache()
        return bool(self._watched_corps or self._watched_alliances)

    def check_kill(self, kill: ProcessedKill) -> EntityMatchResult:
        """
        Check a kill against watched entities.

        Args:
            kill: ProcessedKill to check

        Returns:
            EntityMatchResult with match details
        """
        self._ensure_cache()

        result = EntityMatchResult()

        # Check victim corporation
        if kill.victim_corporation_id and kill.victim_corporation_id in self._watched_corps:
            result.victim_corp_match = kill.victim_corporation_id
            result.has_match = True

        # Check victim alliance
        if kill.victim_alliance_id and kill.victim_alliance_id in self._watched_alliances:
            result.victim_alliance_match = kill.victim_alliance_id
            result.has_match = True

        # Check attacker corporations
        for corp_id in kill.attacker_corps:
            if corp_id in self._watched_corps:
                result.attacker_corp_matches.append(corp_id)
                result.has_match = True

        # Check attacker alliances
        for alliance_id in kill.attacker_alliances:
            if alliance_id in self._watched_alliances:
                result.attacker_alliance_matches.append(alliance_id)
                result.has_match = True

        return result

    def is_entity_watched(self, entity_id: int, entity_type: str) -> bool:
        """
        Quick check if a specific entity is watched.

        Args:
            entity_id: Corporation or alliance ID
            entity_type: 'corporation' or 'alliance'

        Returns:
            True if entity is in any watchlist
        """
        self._ensure_cache()

        if entity_type == "corporation":
            return entity_id in self._watched_corps
        elif entity_type == "alliance":
            return entity_id in self._watched_alliances
        return False


# =============================================================================
# Module-level singleton
# =============================================================================

_entity_filter: EntityAwareFilter | None = None


def get_entity_filter(owner_character_id: int | None = None) -> EntityAwareFilter:
    """
    Get or create the entity filter singleton.

    Args:
        owner_character_id: Character ID for pilot-specific watchlists

    Returns:
        EntityAwareFilter instance
    """
    global _entity_filter

    if _entity_filter is None:
        _entity_filter = EntityAwareFilter(owner_character_id)

    return _entity_filter


def reset_entity_filter() -> None:
    """Reset the entity filter singleton."""
    global _entity_filter
    _entity_filter = None
