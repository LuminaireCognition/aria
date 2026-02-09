"""
NPC Faction Mapping for Kill Notifications.

Maps NPC corporation IDs to faction names for the npc_faction_kill trigger.
Uses static reference data extracted from EVE SDE.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ....core.logging import get_logger

logger = get_logger(__name__)


# Default path to NPC corporation reference data
DEFAULT_REFERENCE_PATH = Path("reference/factions/npc_corporations.json")


@dataclass
class NPCFactionTriggerResult:
    """
    Result of NPC faction trigger evaluation.

    Returned when a kill involves an NPC corporation from a watched faction.
    """

    matched: bool
    faction: str  # Faction key (e.g., "serpentis", "angel_cartel")
    corporation_id: int
    corporation_name: str
    role: str  # "attacker" or "victim"

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "matched": self.matched,
            "faction": self.faction,
            "corporation_id": self.corporation_id,
            "corporation_name": self.corporation_name,
            "role": self.role,
        }


class NPCFactionMapper:
    """
    Maps NPC corporation IDs to faction names.

    Uses static reference data to resolve NPC corporation IDs to their
    parent faction. Supports both corp → faction and faction → corps lookups.
    """

    def __init__(self, reference_path: Path | None = None):
        """
        Initialize the faction mapper.

        Args:
            reference_path: Path to npc_corporations.json reference file.
                          Defaults to reference/factions/npc_corporations.json
        """
        self._reference_path = reference_path or DEFAULT_REFERENCE_PATH
        self._corp_to_faction: dict[int, str] = {}
        self._corp_to_name: dict[int, str] = {}
        self._faction_corps: dict[str, set[int]] = {}
        self._faction_names: dict[str, str] = {}  # key -> display name
        self._faction_id_to_name: dict[int, str] = {}  # faction_id -> display name
        self._loaded = False

        self._load_mapping()

    def _load_mapping(self) -> None:
        """Load NPC corporation mapping from reference file."""
        if not self._reference_path.exists():
            logger.warning(
                "NPC corporation reference file not found: %s",
                self._reference_path,
            )
            return

        try:
            with open(self._reference_path) as f:
                data = json.load(f)

            for faction_key, faction_data in data.items():
                faction_key_lower = faction_key.lower()
                faction_display_name = faction_data.get("name", faction_key)
                self._faction_names[faction_key_lower] = faction_display_name
                self._faction_corps[faction_key_lower] = set()

                # Map faction_id -> display name for direct lookups
                faction_id = faction_data.get("faction_id")
                if faction_id:
                    self._faction_id_to_name[faction_id] = faction_display_name

                for corp in faction_data.get("corporations", []):
                    corp_id = corp.get("id")
                    corp_name = corp.get("name", f"Corporation {corp_id}")

                    if corp_id:
                        self._corp_to_faction[corp_id] = faction_key_lower
                        self._corp_to_name[corp_id] = corp_name
                        self._faction_corps[faction_key_lower].add(corp_id)

            self._loaded = True
            logger.debug(
                "Loaded NPC faction mapping: %d factions, %d corporations",
                len(self._faction_corps),
                len(self._corp_to_faction),
            )

        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to load NPC corporation mapping: %s", e)

    def get_faction_for_corp(self, corp_id: int) -> str | None:
        """
        Get faction key for an NPC corporation ID.

        Args:
            corp_id: NPC corporation ID

        Returns:
            Faction key (e.g., "serpentis") or None if not found
        """
        return self._corp_to_faction.get(corp_id)

    def get_corp_name(self, corp_id: int) -> str | None:
        """
        Get corporation name for an NPC corporation ID.

        Args:
            corp_id: NPC corporation ID

        Returns:
            Corporation name or None if not found
        """
        return self._corp_to_name.get(corp_id)

    def get_corps_for_faction(self, faction_key: str) -> set[int]:
        """
        Get all corporation IDs for a faction.

        Args:
            faction_key: Faction key (e.g., "serpentis", "angel_cartel")

        Returns:
            Set of corporation IDs (empty if faction not found)
        """
        return self._faction_corps.get(faction_key.lower(), set())

    def get_faction_display_name(self, faction_key: str) -> str:
        """
        Get display name for a faction.

        Args:
            faction_key: Faction key

        Returns:
            Display name (e.g., "Serpentis", "Angel Cartel")
        """
        return self._faction_names.get(faction_key.lower(), faction_key.title())

    def get_faction_name_by_id(self, faction_id: int) -> str | None:
        """
        Get faction display name by faction ID.

        Args:
            faction_id: EVE faction ID (e.g., 500010 for Guristas)

        Returns:
            Faction display name or None if not found
        """
        return self._faction_id_to_name.get(faction_id)

    def get_all_faction_keys(self) -> list[str]:
        """
        Get all available faction keys.

        Returns:
            List of faction keys (e.g., ["serpentis", "angel_cartel", ...])
        """
        return list(self._faction_corps.keys())

    def is_valid_faction(self, faction_key: str) -> bool:
        """
        Check if a faction key is valid.

        Args:
            faction_key: Faction key to validate

        Returns:
            True if faction exists in mapping
        """
        return faction_key.lower() in self._faction_corps

    def is_npc_corp(self, corp_id: int) -> bool:
        """
        Check if a corporation ID is a known NPC faction corporation.

        Args:
            corp_id: Corporation ID to check

        Returns:
            True if corporation is a known NPC faction corp
        """
        return corp_id in self._corp_to_faction

    @property
    def is_loaded(self) -> bool:
        """Check if mapping was successfully loaded."""
        return self._loaded

    @property
    def corporation_count(self) -> int:
        """Get total number of mapped corporations."""
        return len(self._corp_to_faction)

    @property
    def faction_count(self) -> int:
        """Get total number of factions."""
        return len(self._faction_corps)


# Module-level singleton
_mapper: NPCFactionMapper | None = None


def get_npc_faction_mapper(reference_path: Path | None = None) -> NPCFactionMapper:
    """
    Get or create the NPC faction mapper singleton.

    Args:
        reference_path: Optional path to reference file

    Returns:
        NPCFactionMapper instance
    """
    global _mapper

    if _mapper is None:
        _mapper = NPCFactionMapper(reference_path)

    return _mapper


def reset_npc_faction_mapper() -> None:
    """Reset the NPC faction mapper singleton."""
    global _mapper
    _mapper = None
