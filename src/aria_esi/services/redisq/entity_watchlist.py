"""
Entity Watchlist Management.

Manages watchlists for tracking corporations and alliances,
including automatic war target synchronization from ESI.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ...core.config import get_settings
from ...core.logging import get_logger

if TYPE_CHECKING:
    import httpx

logger = get_logger(__name__)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class EntityWatchlist:
    """Entity watchlist metadata."""

    watchlist_id: int
    name: str
    description: str | None
    watchlist_type: str  # 'manual', 'war_targets', 'contacts'
    owner_character_id: int | None
    created_at: int
    updated_at: int


@dataclass
class WatchedEntity:
    """Entity being tracked in a watchlist."""

    watchlist_id: int
    entity_id: int
    entity_type: str  # 'corporation', 'alliance'
    entity_name: str | None
    added_at: int
    added_reason: str | None


@dataclass
class SyncResult:
    """Result of a war target synchronization."""

    success: bool
    wars_checked: int = 0
    entities_added: int = 0
    entities_removed: int = 0
    error: str | None = None


# =============================================================================
# Entity Watchlist Manager
# =============================================================================


class EntityWatchlistManager:
    """
    Manages entity watchlists for tracking corps/alliances.

    Supports three watchlist types:
    - manual: User-created lists for tracking specific entities
    - war_targets: Automatically synced from ESI war data
    - contacts: Synced from character contacts (future)
    """

    def __init__(self, db_path: Path | str | None = None):
        """
        Initialize watchlist manager.

        Args:
            db_path: Path to SQLite database. Defaults to settings.db_path
        """
        if db_path is None:
            db_path = get_settings().db_path
        self.db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._conn is None:
            # Ensure schema via MarketDatabase
            from ...mcp.market.database import MarketDatabase

            market_db = MarketDatabase(self.db_path)
            market_db._get_connection()
            market_db.close()

            self._conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")

        return self._conn

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    # =========================================================================
    # Watchlist CRUD
    # =========================================================================

    def create_watchlist(
        self,
        name: str,
        watchlist_type: str = "manual",
        description: str | None = None,
        owner_character_id: int | None = None,
    ) -> EntityWatchlist:
        """
        Create a new entity watchlist.

        Args:
            name: Watchlist name
            watchlist_type: Type ('manual', 'war_targets', 'contacts')
            description: Optional description
            owner_character_id: Character ID for ownership (None = global)

        Returns:
            Created EntityWatchlist

        Raises:
            sqlite3.IntegrityError: If name already exists for this owner
        """
        conn = self._get_connection()
        now = int(time.time())

        cursor = conn.execute(
            """
            INSERT INTO entity_watchlists (
                name, description, watchlist_type, owner_character_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, description, watchlist_type, owner_character_id, now, now),
        )
        conn.commit()

        watchlist_id = cursor.lastrowid
        assert watchlist_id is not None

        return EntityWatchlist(
            watchlist_id=watchlist_id,
            name=name,
            description=description,
            watchlist_type=watchlist_type,
            owner_character_id=owner_character_id,
            created_at=now,
            updated_at=now,
        )

    def get_watchlist(
        self,
        name: str,
        owner_character_id: int | None = None,
    ) -> EntityWatchlist | None:
        """
        Get a watchlist by name and owner.

        Args:
            name: Watchlist name
            owner_character_id: Character ID (None = global)

        Returns:
            EntityWatchlist if found, None otherwise
        """
        conn = self._get_connection()

        if owner_character_id is None:
            row = conn.execute(
                """
                SELECT * FROM entity_watchlists
                WHERE name = ? AND owner_character_id IS NULL
                """,
                (name,),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT * FROM entity_watchlists
                WHERE name = ? AND owner_character_id = ?
                """,
                (name, owner_character_id),
            ).fetchone()

        return self._row_to_watchlist(row) if row else None

    def get_watchlist_by_id(self, watchlist_id: int) -> EntityWatchlist | None:
        """
        Get a watchlist by ID.

        Args:
            watchlist_id: Watchlist ID

        Returns:
            EntityWatchlist if found, None otherwise
        """
        conn = self._get_connection()
        row = conn.execute(
            "SELECT * FROM entity_watchlists WHERE watchlist_id = ?",
            (watchlist_id,),
        ).fetchone()

        return self._row_to_watchlist(row) if row else None

    def list_watchlists(
        self,
        owner_character_id: int | None = None,
        include_global: bool = True,
        watchlist_type: str | None = None,
    ) -> list[EntityWatchlist]:
        """
        List watchlists for an owner.

        Args:
            owner_character_id: Character ID (None = global only)
            include_global: Include global watchlists when owner is provided
            watchlist_type: Filter by type

        Returns:
            List of EntityWatchlist objects
        """
        conn = self._get_connection()

        query = "SELECT * FROM entity_watchlists WHERE 1=1"
        params: list = []

        if owner_character_id is None:
            query += " AND owner_character_id IS NULL"
        elif include_global:
            query += " AND (owner_character_id = ? OR owner_character_id IS NULL)"
            params.append(owner_character_id)
        else:
            query += " AND owner_character_id = ?"
            params.append(owner_character_id)

        if watchlist_type:
            query += " AND watchlist_type = ?"
            params.append(watchlist_type)

        query += " ORDER BY name"
        rows = conn.execute(query, params).fetchall()

        return [self._row_to_watchlist(row) for row in rows]

    def delete_watchlist(self, watchlist_id: int) -> bool:
        """
        Delete a watchlist and its items (cascade).

        Args:
            watchlist_id: Watchlist ID to delete

        Returns:
            True if deleted, False if not found
        """
        conn = self._get_connection()
        cursor = conn.execute(
            "DELETE FROM entity_watchlists WHERE watchlist_id = ?",
            (watchlist_id,),
        )
        conn.commit()
        return cursor.rowcount > 0

    def update_watchlist(
        self,
        watchlist_id: int,
        name: str | None = None,
        description: str | None = None,
    ) -> bool:
        """
        Update watchlist metadata.

        Args:
            watchlist_id: Watchlist ID
            name: New name (optional)
            description: New description (optional)

        Returns:
            True if updated, False if not found
        """
        conn = self._get_connection()
        now = int(time.time())

        updates = ["updated_at = ?"]
        params: list = [now]

        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if description is not None:
            updates.append("description = ?")
            params.append(description)

        params.append(watchlist_id)

        cursor = conn.execute(
            f"UPDATE entity_watchlists SET {', '.join(updates)} WHERE watchlist_id = ?",
            params,
        )
        conn.commit()
        return cursor.rowcount > 0

    # =========================================================================
    # Entity Management
    # =========================================================================

    def add_entity(
        self,
        watchlist_id: int,
        entity_id: int,
        entity_type: str,
        entity_name: str | None = None,
        added_reason: str | None = None,
    ) -> WatchedEntity:
        """
        Add an entity to a watchlist.

        Args:
            watchlist_id: Watchlist ID
            entity_id: Corporation or alliance ID
            entity_type: 'corporation' or 'alliance'
            entity_name: Optional entity name for display
            added_reason: Optional reason for adding

        Returns:
            Created WatchedEntity

        Raises:
            sqlite3.IntegrityError: If entity already in watchlist
        """
        conn = self._get_connection()
        now = int(time.time())

        conn.execute(
            """
            INSERT INTO entity_watchlist_items (
                watchlist_id, entity_id, entity_type, entity_name, added_at, added_reason
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (watchlist_id, entity_id, entity_type, entity_name, now, added_reason),
        )

        # Update watchlist timestamp
        conn.execute(
            "UPDATE entity_watchlists SET updated_at = ? WHERE watchlist_id = ?",
            (now, watchlist_id),
        )
        conn.commit()

        return WatchedEntity(
            watchlist_id=watchlist_id,
            entity_id=entity_id,
            entity_type=entity_type,
            entity_name=entity_name,
            added_at=now,
            added_reason=added_reason,
        )

    def remove_entity(
        self,
        watchlist_id: int,
        entity_id: int,
        entity_type: str,
    ) -> bool:
        """
        Remove an entity from a watchlist.

        Args:
            watchlist_id: Watchlist ID
            entity_id: Corporation or alliance ID
            entity_type: 'corporation' or 'alliance'

        Returns:
            True if removed, False if not found
        """
        conn = self._get_connection()
        cursor = conn.execute(
            """
            DELETE FROM entity_watchlist_items
            WHERE watchlist_id = ? AND entity_id = ? AND entity_type = ?
            """,
            (watchlist_id, entity_id, entity_type),
        )

        if cursor.rowcount > 0:
            # Update watchlist timestamp
            now = int(time.time())
            conn.execute(
                "UPDATE entity_watchlists SET updated_at = ? WHERE watchlist_id = ?",
                (now, watchlist_id),
            )

        conn.commit()
        return cursor.rowcount > 0

    def get_entities(self, watchlist_id: int) -> list[WatchedEntity]:
        """
        Get all entities in a watchlist.

        Args:
            watchlist_id: Watchlist ID

        Returns:
            List of WatchedEntity objects
        """
        conn = self._get_connection()
        rows = conn.execute(
            """
            SELECT * FROM entity_watchlist_items
            WHERE watchlist_id = ?
            ORDER BY entity_type, entity_name
            """,
            (watchlist_id,),
        ).fetchall()

        return [self._row_to_entity(row) for row in rows]

    def get_all_watched_entity_ids(
        self,
        owner_character_id: int | None = None,
    ) -> tuple[set[int], set[int]]:
        """
        Get all watched corporation and alliance IDs.

        Combines entities from all applicable watchlists (owner + global).

        Args:
            owner_character_id: Character ID for pilot-specific lists

        Returns:
            Tuple of (corporation_ids, alliance_ids)
        """
        conn = self._get_connection()

        if owner_character_id is None:
            rows = conn.execute(
                """
                SELECT DISTINCT entity_id, entity_type FROM entity_watchlist_items
                WHERE watchlist_id IN (
                    SELECT watchlist_id FROM entity_watchlists
                    WHERE owner_character_id IS NULL
                )
                """
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT DISTINCT entity_id, entity_type FROM entity_watchlist_items
                WHERE watchlist_id IN (
                    SELECT watchlist_id FROM entity_watchlists
                    WHERE owner_character_id = ? OR owner_character_id IS NULL
                )
                """,
                (owner_character_id,),
            ).fetchall()

        corp_ids: set[int] = set()
        alliance_ids: set[int] = set()

        for row in rows:
            if row["entity_type"] == "corporation":
                corp_ids.add(row["entity_id"])
            elif row["entity_type"] == "alliance":
                alliance_ids.add(row["entity_id"])

        return corp_ids, alliance_ids

    def is_entity_watched(
        self,
        entity_id: int,
        entity_type: str,
        owner_character_id: int | None = None,
    ) -> bool:
        """
        Check if an entity is in any applicable watchlist.

        Args:
            entity_id: Corporation or alliance ID
            entity_type: 'corporation' or 'alliance'
            owner_character_id: Character ID for pilot-specific lists

        Returns:
            True if entity is being watched
        """
        conn = self._get_connection()

        if owner_character_id is None:
            row = conn.execute(
                """
                SELECT 1 FROM entity_watchlist_items
                WHERE entity_id = ? AND entity_type = ?
                AND watchlist_id IN (
                    SELECT watchlist_id FROM entity_watchlists
                    WHERE owner_character_id IS NULL
                )
                LIMIT 1
                """,
                (entity_id, entity_type),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT 1 FROM entity_watchlist_items
                WHERE entity_id = ? AND entity_type = ?
                AND watchlist_id IN (
                    SELECT watchlist_id FROM entity_watchlists
                    WHERE owner_character_id = ? OR owner_character_id IS NULL
                )
                LIMIT 1
                """,
                (entity_id, entity_type, owner_character_id),
            ).fetchone()

        return row is not None

    def get_entity_count(self, watchlist_id: int) -> int:
        """
        Get count of entities in a watchlist.

        Args:
            watchlist_id: Watchlist ID

        Returns:
            Number of entities
        """
        conn = self._get_connection()
        row = conn.execute(
            "SELECT COUNT(*) FROM entity_watchlist_items WHERE watchlist_id = ?",
            (watchlist_id,),
        ).fetchone()
        return row[0] if row else 0

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _row_to_watchlist(self, row: sqlite3.Row) -> EntityWatchlist:
        """Convert database row to EntityWatchlist."""
        return EntityWatchlist(
            watchlist_id=row["watchlist_id"],
            name=row["name"],
            description=row["description"],
            watchlist_type=row["watchlist_type"],
            owner_character_id=row["owner_character_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_entity(self, row: sqlite3.Row) -> WatchedEntity:
        """Convert database row to WatchedEntity."""
        return WatchedEntity(
            watchlist_id=row["watchlist_id"],
            entity_id=row["entity_id"],
            entity_type=row["entity_type"],
            entity_name=row["entity_name"],
            added_at=row["added_at"],
            added_reason=row["added_reason"],
        )


# =============================================================================
# War Target Syncer
# =============================================================================


@dataclass
class WarInfo:
    """War information from ESI."""

    war_id: int
    aggressor_corp_id: int | None
    aggressor_alliance_id: int | None
    defender_corp_id: int | None
    defender_alliance_id: int | None
    is_mutual: bool
    is_finished: bool


class WarTargetSyncer:
    """
    Synchronizes war targets from ESI.

    Uses:
    - GET /corporations/{corporation_id}/wars/ - Get wars for pilot's corp
    - GET /wars/{war_id}/ - Get war details
    """

    def __init__(self, manager: EntityWatchlistManager):
        """
        Initialize war target syncer.

        Args:
            manager: EntityWatchlistManager instance
        """
        self.manager = manager

    async def sync_wars(self, character_id: int, corporation_id: int) -> SyncResult:
        """
        Sync war targets for a character's corporation.

        Creates or updates the "War Targets" watchlist with current enemies.

        Args:
            character_id: Character ID (for watchlist ownership)
            corporation_id: Corporation ID to get wars for

        Returns:
            SyncResult with sync statistics
        """
        import httpx

        # Get or create war targets watchlist
        watchlist = self.manager.get_watchlist(
            "War Targets",
            owner_character_id=character_id,
        )

        if watchlist is None:
            watchlist = self.manager.create_watchlist(
                name="War Targets",
                watchlist_type="war_targets",
                description="Automatically synced from ESI war data",
                owner_character_id=character_id,
            )

        # Fetch wars from ESI
        try:
            async with httpx.AsyncClient(
                timeout=30,
                headers={"User-Agent": "ARIA-ESI/1.0"},
            ) as client:
                # Get corporation wars
                wars_url = f"https://esi.evetech.net/latest/corporations/{corporation_id}/wars/"
                response = await client.get(wars_url)

                if response.status_code == 404:
                    # Corporation has no wars
                    return SyncResult(
                        success=True,
                        wars_checked=0,
                        entities_added=0,
                        entities_removed=0,
                    )

                if response.status_code != 200:
                    return SyncResult(
                        success=False,
                        error=f"ESI returned {response.status_code}",
                    )

                war_ids = response.json()
                logger.info("Found %d wars for corporation %d", len(war_ids), corporation_id)

                # Fetch details for each active war
                current_enemies: set[tuple[int, str]] = set()

                for war_id in war_ids:
                    war_info = await self._fetch_war_details(client, war_id)
                    if war_info is None or war_info.is_finished:
                        continue

                    # Determine which side is the enemy
                    enemies = self._get_enemies_from_war(war_info, corporation_id)
                    current_enemies.update(enemies)

                # Sync watchlist with current enemies
                existing = self.manager.get_entities(watchlist.watchlist_id)
                existing_set = {(e.entity_id, e.entity_type) for e in existing}

                # Add new enemies
                added = 0
                for entity_id, entity_type in current_enemies - existing_set:
                    try:
                        self.manager.add_entity(
                            watchlist_id=watchlist.watchlist_id,
                            entity_id=entity_id,
                            entity_type=entity_type,
                            added_reason="War target",
                        )
                        added += 1
                    except Exception as e:
                        logger.warning("Failed to add entity %d: %s", entity_id, e)

                # Remove old enemies (wars that ended)
                removed = 0
                for entity_id, entity_type in existing_set - current_enemies:
                    if self.manager.remove_entity(watchlist.watchlist_id, entity_id, entity_type):
                        removed += 1

                return SyncResult(
                    success=True,
                    wars_checked=len(war_ids),
                    entities_added=added,
                    entities_removed=removed,
                )

        except httpx.TimeoutException:
            return SyncResult(success=False, error="ESI request timed out")
        except Exception as e:
            logger.exception("War sync failed")
            return SyncResult(success=False, error=str(e))

    async def _fetch_war_details(
        self,
        client: httpx.AsyncClient,
        war_id: int,
    ) -> WarInfo | None:
        """
        Fetch war details from ESI.

        Args:
            client: HTTP client
            war_id: War ID

        Returns:
            WarInfo or None if not found
        """
        try:
            url = f"https://esi.evetech.net/latest/wars/{war_id}/"
            response = await client.get(url)

            if response.status_code != 200:
                return None

            data = response.json()

            aggressor = data.get("aggressor", {})
            defender = data.get("defender", {})

            return WarInfo(
                war_id=war_id,
                aggressor_corp_id=aggressor.get("corporation_id"),
                aggressor_alliance_id=aggressor.get("alliance_id"),
                defender_corp_id=defender.get("corporation_id"),
                defender_alliance_id=defender.get("alliance_id"),
                is_mutual=data.get("mutual", False),
                is_finished=data.get("finished") is not None,
            )
        except Exception as e:
            logger.warning("Failed to fetch war %d: %s", war_id, e)
            return None

    def _get_enemies_from_war(
        self,
        war: WarInfo,
        our_corp_id: int,
    ) -> list[tuple[int, str]]:
        """
        Determine enemy entities from war info.

        Args:
            war: War information
            our_corp_id: Our corporation ID

        Returns:
            List of (entity_id, entity_type) tuples
        """
        enemies: list[tuple[int, str]] = []

        # Determine which side we're on
        we_are_aggressor = war.aggressor_corp_id == our_corp_id
        we_are_defender = war.defender_corp_id == our_corp_id

        if we_are_aggressor:
            # We're aggressor, enemies are defenders
            if war.defender_alliance_id:
                enemies.append((war.defender_alliance_id, "alliance"))
            elif war.defender_corp_id:
                enemies.append((war.defender_corp_id, "corporation"))

        elif we_are_defender:
            # We're defender, enemies are aggressors
            if war.aggressor_alliance_id:
                enemies.append((war.aggressor_alliance_id, "alliance"))
            elif war.aggressor_corp_id:
                enemies.append((war.aggressor_corp_id, "corporation"))

        # If mutual war, both sides are enemies (unless we're one of them)
        if war.is_mutual:
            if not we_are_aggressor:
                if war.aggressor_alliance_id:
                    enemies.append((war.aggressor_alliance_id, "alliance"))
                elif war.aggressor_corp_id:
                    enemies.append((war.aggressor_corp_id, "corporation"))
            if not we_are_defender:
                if war.defender_alliance_id:
                    enemies.append((war.defender_alliance_id, "alliance"))
                elif war.defender_corp_id:
                    enemies.append((war.defender_corp_id, "corporation"))

        return enemies


# =============================================================================
# Module-level functions
# =============================================================================

_manager: EntityWatchlistManager | None = None


def get_entity_watchlist_manager() -> EntityWatchlistManager:
    """Get or create the entity watchlist manager singleton."""
    global _manager
    if _manager is None:
        _manager = EntityWatchlistManager()
    return _manager


def reset_entity_watchlist_manager() -> None:
    """Reset the entity watchlist manager singleton."""
    global _manager
    if _manager is not None:
        _manager.close()
        _manager = None
