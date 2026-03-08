"""
Coalition Service.

Provides coalition lookups and territory analysis.
Coalitions are player-defined groupings not tracked by ESI.
"""

from __future__ import annotations

from datetime import UTC

from ...core.logging import get_logger
from .database import CoalitionRecord, SovereigntyDatabase, get_sovereignty_database

logger = get_logger(__name__)


class CoalitionRegistry:
    """
    Lazy-loaded singleton for coalition lookups.

    Provides:
    - Coalition lookup by ID or alias
    - Alliance to coalition mapping
    - Territory statistics
    """

    def __init__(self):
        """Initialize the registry."""
        self._loaded = False
        self._auto_loaded = False

    def _ensure_loaded(self) -> None:
        """Ensure coalition data is loaded."""
        if self._loaded:
            return

        db = get_sovereignty_database()
        coalitions = db.get_all_coalitions()

        # If no coalitions in DB, attempt auto-load from YAML
        # This skips ESI validation (best-effort for MCP/runtime use)
        if not coalitions:
            self._auto_load_from_yaml(db)

        self._loaded = True

    def _auto_load_from_yaml(self, db: SovereigntyDatabase) -> None:
        """Auto-load coalition data from YAML when DB is empty.

        Best-effort: logs warnings on failure, never raises.
        Skips ESI validation — use 'uv run aria-esi sov-load-coalitions'
        for validated data.
        """
        try:
            import time
            from pathlib import Path

            import yaml

            yaml_path = (
                Path(__file__).parent.parent.parent / "data" / "sovereignty" / "coalitions.yaml"
            )
            if not yaml_path.exists():
                logger.warning(
                    "No coalition data in database and YAML not found at %s. "
                    "Run 'uv run aria-esi sov-load-coalitions' to load validated data.",
                    yaml_path,
                )
                return

            with open(yaml_path) as f:
                data = yaml.safe_load(f)

            now = int(time.time())
            coalitions_loaded = 0

            coalitions_data = data.get("coalitions", {})
            for coalition_id, coalition_info in coalitions_data.items():
                record = CoalitionRecord(
                    coalition_id=coalition_id,
                    display_name=coalition_info.get("display_name", coalition_id),
                    aliases=coalition_info.get("aliases", []),
                    updated_at=now,
                )
                db.save_coalition(record)
                coalitions_loaded += 1

                alliances = coalition_info.get("alliances", [])
                alliance_ids = [a["id"] for a in alliances if "id" in a]
                if alliance_ids:
                    db.save_coalition_members(coalition_id, alliance_ids)

            self._auto_loaded = True
            logger.info(
                "Auto-loaded %d coalitions from %s (unvalidated)",
                coalitions_loaded,
                yaml_path,
            )
        except Exception:  # noqa: BLE001 -- best-effort auto-load
            logger.warning(
                "Failed to auto-load coalitions from YAML. "
                "Run 'uv run aria-esi sov-load-coalitions' to load validated data.",
                exc_info=True,
            )

    def get_coalition(self, coalition_id: str) -> CoalitionRecord | None:
        """
        Get coalition by ID.

        Args:
            coalition_id: Coalition ID (e.g., "imperium")

        Returns:
            CoalitionRecord if found
        """
        self._ensure_loaded()
        db = get_sovereignty_database()
        return db.get_coalition(coalition_id)

    def resolve_coalition_alias(self, alias: str) -> CoalitionRecord | None:
        """
        Find coalition by alias (case-insensitive).

        Searches coalition IDs, display names, and aliases.

        Args:
            alias: Alias to search for (e.g., "goons", "bees")

        Returns:
            CoalitionRecord if found
        """
        self._ensure_loaded()
        db = get_sovereignty_database()
        return db.get_coalition_by_alias(alias)

    def get_coalition_for_alliance(self, alliance_id: int) -> CoalitionRecord | None:
        """
        Get coalition for an alliance.

        Args:
            alliance_id: Alliance ID

        Returns:
            CoalitionRecord if alliance is in a coalition
        """
        self._ensure_loaded()
        db = get_sovereignty_database()
        coalition_id = db.get_coalition_for_alliance(alliance_id)
        if coalition_id:
            return db.get_coalition(coalition_id)
        return None

    def get_all_coalitions(self) -> list[CoalitionRecord]:
        """Get all known coalitions."""
        self._ensure_loaded()
        db = get_sovereignty_database()
        return db.get_all_coalitions()

    def get_coalition_alliances(self, coalition_id: str) -> list[int]:
        """Get all alliance IDs in a coalition."""
        self._ensure_loaded()
        db = get_sovereignty_database()
        return db.get_coalition_alliances(coalition_id)


# Module-level singleton
_coalition_registry: CoalitionRegistry | None = None


def get_coalition_registry() -> CoalitionRegistry:
    """Get the coalition registry singleton."""
    global _coalition_registry
    if _coalition_registry is None:
        _coalition_registry = CoalitionRegistry()
    return _coalition_registry


def reset_coalition_registry() -> None:
    """Reset the coalition registry singleton (for testing)."""
    global _coalition_registry
    _coalition_registry = None


# =============================================================================
# Territory Analysis
# =============================================================================


def analyze_territory(
    coalition_id: str | None = None,
    alliance_id: int | None = None,
) -> dict:
    """
    Analyze territory for a coalition or alliance.

    Returns:
    - System count
    - Region breakdown
    - Ratting hotspots (via activity data if available)
    - Entry points (border systems)

    Args:
        coalition_id: Coalition ID to analyze
        alliance_id: Alliance ID to analyze

    Returns:
        Territory analysis dict
    """
    from ...universe.builder import load_universe_graph

    db = get_sovereignty_database()

    # Resolve coalition to alliance IDs
    if coalition_id:
        registry = get_coalition_registry()
        coalition = registry.get_coalition(coalition_id)
        if not coalition:
            # Try alias resolution
            coalition = registry.resolve_coalition_alias(coalition_id)
        if not coalition:
            return {
                "error": "coalition_not_found",
                "message": f"Unknown coalition: {coalition_id}",
            }
        alliance_ids = registry.get_coalition_alliances(coalition.coalition_id)
        entity_name = coalition.display_name
        entity_type = "coalition"
    elif alliance_id:
        alliance = db.get_alliance(alliance_id)
        if not alliance:
            return {
                "error": "alliance_not_found",
                "message": f"Unknown alliance: {alliance_id}",
            }
        alliance_ids = [alliance_id]
        entity_name = f"[{alliance.ticker}] {alliance.name}"
        entity_type = "alliance"
    else:
        return {
            "error": "missing_parameter",
            "message": "Must specify coalition_id or alliance_id",
        }

    # Get all systems held by these alliances
    system_ids: set[int] = set()
    for aid in alliance_ids:
        sids = db.get_systems_by_alliance(aid)
        system_ids.update(sids)

    if not system_ids:
        return {
            "entity_name": entity_name,
            "entity_type": entity_type,
            "system_count": 0,
            "regions": [],
            "message": "No sovereignty data found. Run 'aria-esi sov-update' to refresh.",
        }

    # Load universe for region mapping
    try:
        universe = load_universe_graph()
    except Exception as e:  # noqa: BLE001 -- service handler
        return {
            "entity_name": entity_name,
            "entity_type": entity_type,
            "system_count": len(system_ids),
            "regions": [],
            "error": f"Could not load universe: {e}",
        }

    # Analyze regions
    region_systems: dict[str, list[str]] = {}
    constellation_count = 0
    constellations_seen: set[int] = set()

    for system_id in system_ids:
        idx = universe.id_to_idx.get(system_id)
        if idx is None:
            continue

        region_name = universe.get_region_name(idx)
        system_name = universe.idx_to_name[idx]
        constellation_id = int(universe.constellation_ids[idx])

        if region_name not in region_systems:
            region_systems[region_name] = []
        region_systems[region_name].append(system_name)

        if constellation_id not in constellations_seen:
            constellations_seen.add(constellation_id)
            constellation_count += 1

    # Build region summary
    regions = [
        {
            "name": region,
            "system_count": len(systems),
        }
        for region, systems in sorted(region_systems.items(), key=lambda x: -len(x[1]))
    ]

    # Check for staleness warnings
    warnings: list[str] = []

    registry = get_coalition_registry()
    if registry._auto_loaded:
        warnings.append(
            "Coalition data loaded from YAML without ESI validation. "
            "Run 'uv run aria-esi sov-load-coalitions' for validated data."
        )

    # Check coalitions.yaml age
    try:
        from pathlib import Path

        import yaml

        yaml_path = Path(__file__).parent.parent / "data" / "sovereignty" / "coalitions.yaml"
        if yaml_path.exists():
            with open(yaml_path) as f:
                yaml_data = yaml.safe_load(f)
            last_updated = yaml_data.get("last_updated")
            if last_updated:
                from datetime import datetime

                updated_dt = datetime.strptime(last_updated, "%Y-%m-%d").replace(tzinfo=UTC)
                age_days = (datetime.now(tz=UTC) - updated_dt).days
                if age_days > 7:
                    warnings.append(
                        f"Coalition data is {age_days} days old (last updated: {last_updated}). "
                        "Coalition membership may have changed."
                    )
    except Exception:  # noqa: BLE001 -- best-effort staleness check
        pass

    result = {
        "entity_name": entity_name,
        "entity_type": entity_type,
        "alliance_count": len(alliance_ids) if entity_type == "coalition" else 1,
        "system_count": len(system_ids),
        "constellation_count": constellation_count,
        "region_count": len(regions),
        "regions": regions[:10],  # Top 10 regions
    }

    if warnings:
        result["warnings"] = warnings

    return result


def get_systems_by_coalition(coalition_id: str) -> list[int]:
    """
    Get all system IDs held by a coalition.

    Args:
        coalition_id: Coalition ID or alias

    Returns:
        List of system IDs
    """
    registry = get_coalition_registry()
    coalition = registry.get_coalition(coalition_id)
    if not coalition:
        coalition = registry.resolve_coalition_alias(coalition_id)
    if not coalition:
        return []

    alliance_ids = registry.get_coalition_alliances(coalition.coalition_id)

    db = get_sovereignty_database()
    system_ids: set[int] = set()
    for aid in alliance_ids:
        sids = db.get_systems_by_alliance(aid)
        system_ids.update(sids)

    return list(system_ids)
