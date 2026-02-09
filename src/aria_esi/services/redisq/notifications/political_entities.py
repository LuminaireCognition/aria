"""
Political Entity Tracking for Notifications.

Provides support for tracking player corporations and alliances in killmails.
Used by the political_entity trigger type.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PoliticalEntityTriggerResult:
    """
    Result of political entity trigger evaluation.

    Contains information about which entity matched and their role in the kill.
    """

    matched: bool = False
    entity_type: str = ""  # "corporation" or "alliance"
    entity_id: int = 0
    entity_name: str = ""
    role: str = ""  # "attacker" or "victim"

    @property
    def is_attacker(self) -> bool:
        """Check if matched entity was an attacker."""
        return self.role == "attacker"

    @property
    def is_victim(self) -> bool:
        """Check if matched entity was the victim."""
        return self.role == "victim"

    @property
    def is_corporation(self) -> bool:
        """Check if matched entity is a corporation."""
        return self.entity_type == "corporation"

    @property
    def is_alliance(self) -> bool:
        """Check if matched entity is an alliance."""
        return self.entity_type == "alliance"

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "matched": self.matched,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "role": self.role,
        }


def resolve_entity_names(
    corporations: list[int | str],
    alliances: list[int | str],
) -> tuple[set[int], set[int]]:
    """
    Resolve entity names to IDs using ESI search.

    Args:
        corporations: List of corporation IDs or names
        alliances: List of alliance IDs or names

    Returns:
        Tuple of (resolved_corp_ids, resolved_alliance_ids)
    """

    resolved_corps: set[int] = set()
    resolved_alliances: set[int] = set()

    # Process corporations
    for corp in corporations:
        if isinstance(corp, int):
            resolved_corps.add(corp)
        elif isinstance(corp, str):
            # Try to resolve via ESI search
            corp_id = _search_entity(corp, "corporation")
            if corp_id:
                resolved_corps.add(corp_id)

    # Process alliances
    for alliance in alliances:
        if isinstance(alliance, int):
            resolved_alliances.add(alliance)
        elif isinstance(alliance, str):
            # Try to resolve via ESI search
            alliance_id = _search_entity(alliance, "alliance")
            if alliance_id:
                resolved_alliances.add(alliance_id)

    return resolved_corps, resolved_alliances


def _search_entity(name: str, category: str) -> int | None:
    """
    Search for an entity by name using ESI.

    Args:
        name: Entity name to search for
        category: "corporation" or "alliance"

    Returns:
        Entity ID if found, None otherwise
    """
    import requests  # type: ignore[import-untyped]

    try:
        # ESI search endpoint
        resp = requests.get(
            "https://esi.evetech.net/latest/search/",
            params={
                "categories": category,
                "search": name,
                "strict": "true",
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        # Get the matching ID
        if category == "corporation" and "corporation" in data:
            ids = data["corporation"]
            if ids:
                return ids[0]
        elif category == "alliance" and "alliance" in data:
            ids = data["alliance"]
            if ids:
                return ids[0]

    except requests.RequestException as e:
        logger.warning("ESI request failed resolving %s '%s': %s", category, name, e)
    except (ValueError, KeyError) as e:
        logger.warning("Failed to parse ESI response for %s '%s': %s", category, name, e)

    return None
