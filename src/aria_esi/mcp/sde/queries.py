"""
Dynamic SDE Query Functions.

Replaces hard-coded constants with database queries.
Used by both MCP tools and internal code.

Implements a cache-aside pattern with timestamp-based invalidation
to detect SDE re-imports automatically.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ...core.config import get_settings
from ...core.logging import get_logger

if TYPE_CHECKING:
    from aria_esi.mcp.market.database import MarketDatabase

logger = get_logger(__name__)


def _is_debug_timing_enabled() -> bool:
    """Check if timing debug is enabled via centralized config."""
    return get_settings().debug_timing


# =============================================================================
# Exceptions
# =============================================================================


class SDENotSeededError(Exception):
    """Raised when SDE tables are missing from database."""

    pass


# =============================================================================
# Data Classes
# =============================================================================


@dataclass(frozen=True)
class CorporationRegions:
    """
    Regions where a corporation has stations.

    Immutable to ensure cached values aren't accidentally mutated.
    Regions are sorted by station count descending (primary region first).
    """

    corporation_id: int
    corporation_name: str
    regions: tuple[tuple[int, str, int], ...]  # (region_id, region_name, station_count)

    @property
    def primary_region_id(self) -> int | None:
        """Region ID where corporation has most stations."""
        return self.regions[0][0] if self.regions else None

    @property
    def primary_region_name(self) -> str | None:
        """Region name where corporation has most stations."""
        return self.regions[0][1] if self.regions else None

    @property
    def total_stations(self) -> int:
        """Total stations across all regions."""
        return sum(r[2] for r in self.regions)


@dataclass(frozen=True)
class CorporationInfo:
    """
    Full NPC corporation information.

    Includes faction affiliation and seeding statistics.
    """

    corporation_id: int
    corporation_name: str
    faction_id: int | None
    station_count: int
    regions: tuple[tuple[int, str, int], ...]  # (region_id, region_name, station_count)
    seeds_items: bool
    seeded_item_count: int


@dataclass(frozen=True)
class StationInfo:
    """
    NPC station information for corporation attribution.

    Used to map station IDs from market orders back to owning corporations.
    """

    station_id: int
    station_name: str
    corporation_id: int
    corporation_name: str
    system_id: int
    region_id: int
    region_name: str


@dataclass(frozen=True)
class SkillAttributes:
    """
    Skill training attributes from SDE.

    Contains the data needed for training time calculations.
    """

    type_id: int
    type_name: str
    rank: int
    primary_attribute: str | None
    secondary_attribute: str | None


@dataclass(frozen=True)
class SkillPrereq:
    """A skill prerequisite."""

    skill_id: int
    skill_name: str
    required_level: int


@dataclass(frozen=True)
class TypeRequirement:
    """A skill requirement for using a type."""

    skill_id: int
    skill_name: str
    required_level: int


@dataclass(frozen=True)
class MetaGroup:
    """Meta group definition (Tech I, Tech II, Faction, etc.)."""

    meta_group_id: int
    meta_group_name: str


@dataclass(frozen=True)
class MetaVariant:
    """A variant of a base item (T2, Faction, etc.)."""

    type_id: int
    type_name: str
    meta_group_id: int
    meta_group_name: str


# =============================================================================
# Query Service
# =============================================================================


class SDEQueryService:
    """
    Cached SDE query layer.

    Separates connection management from data caching.
    Cache is invalidated when SDE import timestamp changes.
    """

    def __init__(self, db: MarketDatabase):
        self._db = db
        self._lock = threading.Lock()

        # Data caches (dict, not lru_cache - explicit control)
        self._corp_regions: dict[int, CorporationRegions | None] = {}
        self._seeding_corps: dict[int, tuple[tuple[int, str], ...]] = {}
        self._category_ids: dict[str, int | None] = {}
        self._corp_info: dict[int, CorporationInfo | None] = {}
        self._station_info: dict[int, StationInfo | None] = {}
        self._npc_station_regions: tuple[tuple[int, str], ...] | None = None

        # Skill-related caches
        self._skill_attrs: dict[int, SkillAttributes | None] = {}
        self._skill_prereqs: dict[int, tuple[SkillPrereq, ...]] = {}
        self._type_requirements: dict[int, tuple[TypeRequirement, ...]] = {}

        # Meta type caches
        self._meta_groups: dict[int, MetaGroup | None] = {}
        self._meta_variants_by_parent: dict[int, tuple[MetaVariant, ...]] = {}
        self._parent_type: dict[int, int | None] = {}  # type_id → parent_type_id

        # Cache metadata
        self._cache_import_timestamp: str | None = None

    def _check_cache_validity(self) -> None:
        """Invalidate caches if SDE was re-imported."""
        start = time.perf_counter() if _is_debug_timing_enabled() else None

        conn = self._db._get_connection()
        cursor = conn.execute("SELECT value FROM metadata WHERE key = 'sde_import_timestamp'")
        row = cursor.fetchone()
        current_timestamp = row[0] if row else None

        if current_timestamp != self._cache_import_timestamp:
            with self._lock:
                # Double-check after acquiring lock
                if current_timestamp != self._cache_import_timestamp:
                    self._corp_regions.clear()
                    self._seeding_corps.clear()
                    self._category_ids.clear()
                    self._corp_info.clear()
                    self._station_info.clear()
                    self._npc_station_regions = None
                    self._skill_attrs.clear()
                    self._skill_prereqs.clear()
                    self._type_requirements.clear()
                    self._meta_groups.clear()
                    self._meta_variants_by_parent.clear()
                    self._parent_type.clear()
                    self._cache_import_timestamp = current_timestamp
                    logger.debug(
                        "SDE cache invalidated, new timestamp: %s",
                        current_timestamp,
                    )

        if _is_debug_timing_enabled() and start:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.debug("_check_cache_validity: %.2fms", elapsed_ms)

    def ensure_sde_seeded(self) -> None:
        """
        Verify SDE tables exist in database.

        Raises:
            SDENotSeededError: If required SDE tables are missing

        Note:
            Distinguishes "data not found" (returns None) from
            "database not seeded" (raises exception).
        """
        conn = self._db._get_connection()
        required_tables = ["npc_corporations", "npc_seeding", "stations", "regions"]
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ({})".format(
                ",".join("?" * len(required_tables))
            ),
            required_tables,
        )
        found = {row[0] for row in cursor.fetchall()}
        missing = set(required_tables) - found
        if missing:
            raise SDENotSeededError(
                f"SDE tables missing: {missing}. Run 'uv run aria-esi sde-seed' first."
            )

    def get_corporation_regions(self, corporation_id: int) -> CorporationRegions | None:
        """
        Get all regions where a corporation has stations.

        Replaces FACTION_REGIONS lookup with dynamic query.

        Args:
            corporation_id: NPC corporation ID

        Returns:
            CorporationRegions with all regions, or None if corporation not found

        Raises:
            SDENotSeededError: If SDE tables are missing
        """
        start = time.perf_counter() if _is_debug_timing_enabled() else None
        self._check_cache_validity()

        if corporation_id in self._corp_regions:
            result = self._corp_regions[corporation_id]
            if _is_debug_timing_enabled() and start:
                elapsed_ms = (time.perf_counter() - start) * 1000
                logger.debug(
                    "get_corporation_regions(%d) cache hit: %.2fms",
                    corporation_id,
                    elapsed_ms,
                )
            return result

        # Cache miss - verify SDE is seeded first
        self.ensure_sde_seeded()

        # Query database
        conn = self._db._get_connection()
        result = self._query_corporation_regions(conn, corporation_id)

        with self._lock:
            self._corp_regions[corporation_id] = result

        if _is_debug_timing_enabled() and start:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.debug(
                "get_corporation_regions(%d) cache miss: %.2fms",
                corporation_id,
                elapsed_ms,
            )

        return result

    def _query_corporation_regions(self, conn, corporation_id: int) -> CorporationRegions | None:
        """Execute corporation regions query."""
        cursor = conn.execute(
            """
            SELECT
                nc.corporation_name,
                r.region_id,
                r.region_name,
                COUNT(*) as station_count
            FROM npc_corporations nc
            JOIN stations s ON nc.corporation_id = s.corporation_id
            JOIN regions r ON s.region_id = r.region_id
            WHERE nc.corporation_id = ?
            GROUP BY r.region_id
            ORDER BY station_count DESC
            """,
            (corporation_id,),
        )

        rows = cursor.fetchall()
        if not rows:
            return None

        corp_name = rows[0][0]
        regions = tuple((row[1], row[2], row[3]) for row in rows)

        return CorporationRegions(
            corporation_id=corporation_id,
            corporation_name=corp_name,
            regions=regions,
        )

    def get_npc_seeding_corporations(self, type_id: int) -> tuple[tuple[int, str], ...]:
        """
        Get corporations that seed an item.

        Args:
            type_id: Item type ID

        Returns:
            Tuple of (corporation_id, corporation_name) pairs

        Raises:
            SDENotSeededError: If SDE tables are missing
        """
        self._check_cache_validity()

        if type_id in self._seeding_corps:
            return self._seeding_corps[type_id]

        # Cache miss - verify SDE is seeded first
        self.ensure_sde_seeded()

        conn = self._db._get_connection()
        cursor = conn.execute(
            """
            SELECT
                nc.corporation_id,
                nc.corporation_name
            FROM npc_seeding ns
            JOIN npc_corporations nc ON ns.corporation_id = nc.corporation_id
            WHERE ns.type_id = ?
            """,
            (type_id,),
        )

        result = tuple((row[0], row[1]) for row in cursor.fetchall())

        with self._lock:
            self._seeding_corps[type_id] = result

        return result

    def get_category_id(self, category_name: str) -> int | None:
        """
        Look up category ID by name.

        Args:
            category_name: Category name (case-insensitive)

        Returns:
            Category ID or None if not found
        """
        self._check_cache_validity()
        category_lower = category_name.lower()

        if category_lower in self._category_ids:
            return self._category_ids[category_lower]

        conn = self._db._get_connection()
        cursor = conn.execute(
            "SELECT category_id FROM categories WHERE category_name_lower = ?",
            (category_lower,),
        )
        row = cursor.fetchone()
        result = row[0] if row else None

        with self._lock:
            self._category_ids[category_lower] = result

        return result

    def get_corporation_info(self, corporation_id: int) -> CorporationInfo | None:
        """
        Get full corporation information including seeding stats.

        Args:
            corporation_id: NPC corporation ID

        Returns:
            CorporationInfo or None if not found
        """
        self._check_cache_validity()

        if corporation_id in self._corp_info:
            return self._corp_info[corporation_id]

        # Cache miss - verify SDE is seeded first
        self.ensure_sde_seeded()

        conn = self._db._get_connection()

        # Get basic corporation info
        cursor = conn.execute(
            """
            SELECT corporation_name, faction_id
            FROM npc_corporations
            WHERE corporation_id = ?
            """,
            (corporation_id,),
        )
        row = cursor.fetchone()
        if not row:
            with self._lock:
                self._corp_info[corporation_id] = None
            return None

        corp_name, faction_id = row

        # Get regions and station count
        corp_regions = self.get_corporation_regions(corporation_id)
        regions = corp_regions.regions if corp_regions else ()
        station_count = corp_regions.total_stations if corp_regions else 0

        # Get seeding stats
        cursor = conn.execute(
            "SELECT COUNT(*) FROM npc_seeding WHERE corporation_id = ?",
            (corporation_id,),
        )
        seeded_count = cursor.fetchone()[0]

        result = CorporationInfo(
            corporation_id=corporation_id,
            corporation_name=corp_name,
            faction_id=faction_id,
            station_count=station_count,
            regions=regions,
            seeds_items=seeded_count > 0,
            seeded_item_count=seeded_count,
        )

        with self._lock:
            self._corp_info[corporation_id] = result

        return result

    def get_npc_station_regions(self) -> tuple[tuple[int, str], ...]:
        """
        Get all regions that have NPC stations.

        Used for ESI fallback scans when SDE seeding data is incomplete.
        Returns regions sorted by station count (most stations first).

        Returns:
            Tuple of (region_id, region_name) pairs

        Raises:
            SDENotSeededError: If SDE tables are missing
        """
        self._check_cache_validity()

        if self._npc_station_regions is not None:
            return self._npc_station_regions

        # Cache miss - verify SDE is seeded first
        self.ensure_sde_seeded()

        conn = self._db._get_connection()
        cursor = conn.execute(
            """
            SELECT
                r.region_id,
                r.region_name,
                COUNT(DISTINCT s.station_id) as station_count
            FROM stations s
            JOIN regions r ON s.region_id = r.region_id
            WHERE r.region_id < 11000000  -- Exclude wormhole regions
            GROUP BY r.region_id
            ORDER BY station_count DESC
            """
        )

        result = tuple((row[0], row[1]) for row in cursor.fetchall())

        with self._lock:
            self._npc_station_regions = result

        logger.debug("Loaded %d NPC station regions", len(result))
        return result

    def get_station_info(self, station_id: int) -> StationInfo | None:
        """
        Get station information for corporation attribution.

        Used to map station IDs from market orders back to owning corporations.
        Only works for NPC stations (not player structures).

        Args:
            station_id: NPC station ID (typically 6xxxxxxxx range)

        Returns:
            StationInfo or None if station not found in SDE

        Raises:
            SDENotSeededError: If SDE tables are missing
        """
        self._check_cache_validity()

        if station_id in self._station_info:
            return self._station_info[station_id]

        # Cache miss - verify SDE is seeded first
        self.ensure_sde_seeded()

        conn = self._db._get_connection()
        cursor = conn.execute(
            """
            SELECT
                s.station_id,
                s.station_name,
                s.corporation_id,
                nc.corporation_name,
                s.system_id,
                s.region_id,
                r.region_name
            FROM stations s
            JOIN npc_corporations nc ON s.corporation_id = nc.corporation_id
            JOIN regions r ON s.region_id = r.region_id
            WHERE s.station_id = ?
            """,
            (station_id,),
        )

        row = cursor.fetchone()
        if not row:
            with self._lock:
                self._station_info[station_id] = None
            return None

        result = StationInfo(
            station_id=row[0],
            station_name=row[1],
            corporation_id=row[2],
            corporation_name=row[3],
            system_id=row[4],
            region_id=row[5],
            region_name=row[6],
        )

        with self._lock:
            self._station_info[station_id] = result

        return result

    def get_stations_bulk(self, station_ids: list[int]) -> dict[int, StationInfo]:
        """
        Get station information for multiple stations efficiently.

        Batch lookup for multiple stations - more efficient than individual calls.

        Args:
            station_ids: List of station IDs to look up

        Returns:
            Dict mapping station_id to StationInfo (missing stations omitted)

        Raises:
            SDENotSeededError: If SDE tables are missing
        """
        if not station_ids:
            return {}

        self._check_cache_validity()

        # Check cache first
        result: dict[int, StationInfo] = {}
        missing: list[int] = []

        for station_id in station_ids:
            if station_id in self._station_info:
                cached = self._station_info[station_id]
                if cached is not None:
                    result[station_id] = cached
            else:
                missing.append(station_id)

        if not missing:
            return result

        # Query missing stations
        self.ensure_sde_seeded()
        conn = self._db._get_connection()

        # Use placeholders for IN clause
        placeholders = ",".join("?" * len(missing))
        cursor = conn.execute(
            f"""
            SELECT
                s.station_id,
                s.station_name,
                s.corporation_id,
                nc.corporation_name,
                s.system_id,
                s.region_id,
                r.region_name
            FROM stations s
            JOIN npc_corporations nc ON s.corporation_id = nc.corporation_id
            JOIN regions r ON s.region_id = r.region_id
            WHERE s.station_id IN ({placeholders})
            """,
            missing,
        )

        rows = cursor.fetchall()
        found_station_ids: set[int] = set()

        with self._lock:
            for row in rows:
                info = StationInfo(
                    station_id=row[0],
                    station_name=row[1],
                    corporation_id=row[2],
                    corporation_name=row[3],
                    system_id=row[4],
                    region_id=row[5],
                    region_name=row[6],
                )
                self._station_info[row[0]] = info
                result[row[0]] = info
                found_station_ids.add(row[0])

            # Mark missing stations as None in cache
            for station_id in missing:
                if station_id not in found_station_ids and station_id not in self._station_info:
                    self._station_info[station_id] = None

        return result

    def get_skill_attributes(self, type_id: int) -> SkillAttributes | None:
        """
        Get skill training attributes (rank, primary/secondary attribute).

        Args:
            type_id: Skill type ID

        Returns:
            SkillAttributes or None if not found
        """
        self._check_cache_validity()

        if type_id in self._skill_attrs:
            return self._skill_attrs[type_id]

        conn = self._db._get_connection()

        # Check if skill_attributes table exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='skill_attributes'"
        )
        if not cursor.fetchone():
            return None

        cursor = conn.execute(
            """
            SELECT sa.type_id, t.type_name, sa.rank, sa.primary_attribute, sa.secondary_attribute
            FROM skill_attributes sa
            JOIN types t ON sa.type_id = t.type_id
            WHERE sa.type_id = ?
            """,
            (type_id,),
        )

        row = cursor.fetchone()
        if not row:
            with self._lock:
                self._skill_attrs[type_id] = None
            return None

        result = SkillAttributes(
            type_id=row[0],
            type_name=row[1],
            rank=row[2],
            primary_attribute=row[3],
            secondary_attribute=row[4],
        )

        with self._lock:
            self._skill_attrs[type_id] = result

        return result

    def get_skill_prerequisites(self, skill_type_id: int) -> tuple[SkillPrereq, ...]:
        """
        Get direct prerequisites for a skill.

        Args:
            skill_type_id: Skill type ID

        Returns:
            Tuple of SkillPrereq (empty if no prerequisites)
        """
        self._check_cache_validity()

        if skill_type_id in self._skill_prereqs:
            return self._skill_prereqs[skill_type_id]

        conn = self._db._get_connection()

        # Check if skill_prerequisites table exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='skill_prerequisites'"
        )
        if not cursor.fetchone():
            return ()

        cursor = conn.execute(
            """
            SELECT sp.prerequisite_skill_id, t.type_name, sp.prerequisite_level
            FROM skill_prerequisites sp
            JOIN types t ON sp.prerequisite_skill_id = t.type_id
            WHERE sp.skill_type_id = ?
            ORDER BY sp.prerequisite_level DESC
            """,
            (skill_type_id,),
        )

        result = tuple(
            SkillPrereq(skill_id=row[0], skill_name=row[1], required_level=row[2])
            for row in cursor.fetchall()
        )

        with self._lock:
            self._skill_prereqs[skill_type_id] = result

        return result

    def get_type_skill_requirements(self, type_id: int) -> tuple[TypeRequirement, ...]:
        """
        Get skills required to use a type (ship, module, etc.).

        Args:
            type_id: Item type ID

        Returns:
            Tuple of TypeRequirement (empty if no requirements)
        """
        self._check_cache_validity()

        if type_id in self._type_requirements:
            return self._type_requirements[type_id]

        conn = self._db._get_connection()

        # Check if type_skill_requirements table exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='type_skill_requirements'"
        )
        if not cursor.fetchone():
            return ()

        cursor = conn.execute(
            """
            SELECT tsr.required_skill_id, t.type_name, tsr.required_level
            FROM type_skill_requirements tsr
            JOIN types t ON tsr.required_skill_id = t.type_id
            WHERE tsr.type_id = ?
            ORDER BY tsr.required_level DESC
            """,
            (type_id,),
        )

        result = tuple(
            TypeRequirement(skill_id=row[0], skill_name=row[1], required_level=row[2])
            for row in cursor.fetchall()
        )

        with self._lock:
            self._type_requirements[type_id] = result

        return result

    def get_full_skill_tree(
        self, type_id: int, max_depth: int = 10
    ) -> list[tuple[int, str, int, int]]:
        """
        Get the full skill prerequisite tree for a type.

        Recursively resolves all skill prerequisites, returning a flat list
        of unique skills with the maximum level required at each point.

        Args:
            type_id: Item type ID (can be skill, ship, module, etc.)
            max_depth: Maximum recursion depth to prevent infinite loops

        Returns:
            List of (skill_id, skill_name, required_level, rank) tuples
            sorted by rank (ascending), then skill_id for reproducibility
        """
        # First get direct requirements for this type
        direct_reqs = self.get_type_skill_requirements(type_id)

        # Track all skills needed and their maximum required levels
        # Key: skill_id, Value: (skill_name, max_level, rank)
        skill_tree: dict[int, tuple[str, int, int]] = {}

        def add_skill_with_prereqs(skill_id: int, level: int, depth: int) -> None:
            """Recursively add a skill and its prerequisites."""
            if depth > max_depth:
                return

            # Get skill attributes for rank
            attrs = self.get_skill_attributes(skill_id)
            rank = attrs.rank if attrs else 1
            name = attrs.type_name if attrs else f"Skill {skill_id}"

            # Track maximum level needed for this skill
            if skill_id in skill_tree:
                existing_name, existing_level, existing_rank = skill_tree[skill_id]
                if level > existing_level:
                    skill_tree[skill_id] = (name, level, rank)
            else:
                skill_tree[skill_id] = (name, level, rank)

            # Get prerequisites for this skill and recurse
            prereqs = self.get_skill_prerequisites(skill_id)
            for prereq in prereqs:
                add_skill_with_prereqs(prereq.skill_id, prereq.required_level, depth + 1)

        # Start with direct requirements
        for req in direct_reqs:
            add_skill_with_prereqs(req.skill_id, req.required_level, 0)

        # If type_id is itself a skill, add its prerequisites too
        skill_prereqs = self.get_skill_prerequisites(type_id)
        for prereq in skill_prereqs:
            add_skill_with_prereqs(prereq.skill_id, prereq.required_level, 0)

        # Convert to list and sort (stable sort by skill_id for reproducibility)
        result = [
            (skill_id, name, level, rank) for skill_id, (name, level, rank) in skill_tree.items()
        ]
        result.sort(key=lambda x: (x[3], x[0]))  # Sort by rank, then skill_id

        return result

    def get_meta_group(self, meta_group_id: int) -> MetaGroup | None:
        """Get meta group by ID."""
        self._check_cache_validity()

        if meta_group_id in self._meta_groups:
            return self._meta_groups[meta_group_id]

        conn = self._db._get_connection()

        # Check if table exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='meta_groups'"
        )
        if not cursor.fetchone():
            return None

        cursor = conn.execute(
            "SELECT meta_group_id, meta_group_name FROM meta_groups WHERE meta_group_id = ?",
            (meta_group_id,),
        )
        row = cursor.fetchone()

        if not row:
            with self._lock:
                self._meta_groups[meta_group_id] = None
            return None

        result = MetaGroup(meta_group_id=row[0], meta_group_name=row[1])

        with self._lock:
            self._meta_groups[meta_group_id] = result

        return result

    def get_meta_variants(self, type_id: int) -> tuple[MetaVariant, ...]:
        """
        Get all meta variants for an item.

        If type_id is a variant (T2/Faction/etc), finds siblings via parent.
        If type_id is a base item (T1), finds all variants directly.

        Args:
            type_id: Any item type ID (base or variant)

        Returns:
            Tuple of MetaVariant for all variants (including the queried item)
        """
        self._check_cache_validity()

        # First, resolve to parent type if this is a variant
        parent_id = self._get_parent_type_id(type_id)
        if parent_id is None:
            # This might BE the parent, check if it has variants
            parent_id = type_id

        # Check cache for parent
        if parent_id in self._meta_variants_by_parent:
            return self._meta_variants_by_parent[parent_id]

        conn = self._db._get_connection()

        # Check if table exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='meta_types'"
        )
        if not cursor.fetchone():
            return ()

        # Query all variants for this parent
        cursor = conn.execute(
            """
            SELECT
                mt.type_id,
                t.type_name,
                mt.meta_group_id,
                mg.meta_group_name
            FROM meta_types mt
            JOIN types t ON mt.type_id = t.type_id
            JOIN meta_groups mg ON mt.meta_group_id = mg.meta_group_id
            WHERE mt.parent_type_id = ?
            ORDER BY mt.meta_group_id, t.type_name
            """,
            (parent_id,),
        )

        result = tuple(
            MetaVariant(
                type_id=row[0],
                type_name=row[1],
                meta_group_id=row[2],
                meta_group_name=row[3],
            )
            for row in cursor.fetchall()
        )

        with self._lock:
            self._meta_variants_by_parent[parent_id] = result

        return result

    def _get_parent_type_id(self, type_id: int) -> int | None:
        """Get the parent (base) type for a meta variant."""
        if type_id in self._parent_type:
            return self._parent_type[type_id]

        conn = self._db._get_connection()

        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='meta_types'"
        )
        if not cursor.fetchone():
            return None

        cursor = conn.execute(
            "SELECT parent_type_id FROM meta_types WHERE type_id = ?",
            (type_id,),
        )
        row = cursor.fetchone()
        result = row[0] if row else None

        with self._lock:
            self._parent_type[type_id] = result

        return result

    def get_all_meta_groups(self) -> tuple[MetaGroup, ...]:
        """Get all meta groups."""
        conn = self._db._get_connection()

        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='meta_groups'"
        )
        if not cursor.fetchone():
            return ()

        cursor = conn.execute(
            "SELECT meta_group_id, meta_group_name FROM meta_groups ORDER BY meta_group_id"
        )

        return tuple(
            MetaGroup(meta_group_id=row[0], meta_group_name=row[1])
            for row in cursor.fetchall()
        )

    def _get_top_seeding_corps(self, limit: int = 15) -> list[int]:
        """
        Get corporation IDs with most seeded items.

        Queries the SDE to find corporations that seed the most items,
        used for cache warming instead of a hardcoded list.

        Args:
            limit: Maximum corporations to return (default 15)

        Returns:
            List of corporation IDs, ordered by seeded item count descending
        """
        conn = self._db._get_connection()
        cursor = conn.execute(
            """
            SELECT corporation_id
            FROM npc_seeding
            GROUP BY corporation_id
            ORDER BY COUNT(*) DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [row[0] for row in cursor.fetchall()]

    def warm_caches(self) -> dict[str, int]:
        """
        Pre-populate caches with commonly-accessed data.

        Call at MCP server startup to avoid cold-cache latency.
        Silently skips if SDE not seeded (allows server to start).

        Returns:
            Statistics dict with counts of warmed entries
        """
        stats = {"corporations": 0, "categories": 0, "errors": 0}

        try:
            self.ensure_sde_seeded()
        except SDENotSeededError:
            # SDE not imported yet - that's OK, skip warming
            return stats

        # Warm corporation regions cache with top seeding corps from SDE
        top_seeding_corps = self._get_top_seeding_corps(limit=15)
        for corp_id in top_seeding_corps:
            try:
                self.get_corporation_regions(corp_id)
                stats["corporations"] += 1
            except Exception as e:
                logger.debug("Failed to warm cache for corp %d: %s", corp_id, e)
                stats["errors"] += 1

        # Warm category cache
        for category_name in ["Ship", "Module", "Blueprint", "Skill", "Drone"]:
            try:
                self.get_category_id(category_name)
                stats["categories"] += 1
            except Exception as e:
                logger.debug("Failed to warm cache for category %s: %s", category_name, e)
                stats["errors"] += 1

        return stats

    def invalidate_all(self) -> None:
        """Explicitly clear all caches. Call after SDE re-import."""
        with self._lock:
            self._corp_regions.clear()
            self._seeding_corps.clear()
            self._category_ids.clear()
            self._corp_info.clear()
            self._station_info.clear()
            self._npc_station_regions = None
            self._skill_attrs.clear()
            self._skill_prereqs.clear()
            self._type_requirements.clear()
            self._meta_groups.clear()
            self._meta_variants_by_parent.clear()
            self._parent_type.clear()
            self._cache_import_timestamp = None
        logger.debug("SDE query caches explicitly invalidated")


# =============================================================================
# Singleton Accessor
# =============================================================================

_sde_query_service: SDEQueryService | None = None
_service_lock = threading.Lock()


def get_sde_query_service() -> SDEQueryService:
    """Get the singleton SDE query service."""
    global _sde_query_service
    if _sde_query_service is None:
        with _service_lock:
            # Double-check after acquiring lock
            if _sde_query_service is None:
                from aria_esi.mcp.market.database import get_market_database

                _sde_query_service = SDEQueryService(get_market_database())
    return _sde_query_service


def reset_sde_query_service() -> None:
    """Reset the singleton (for testing)."""
    global _sde_query_service
    with _service_lock:
        _sde_query_service = None
