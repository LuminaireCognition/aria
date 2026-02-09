"""
Tests for entity watchlist management.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from aria_esi.services.redisq.entity_watchlist import (
    EntityWatchlistManager,
)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Create test database path."""
    return tmp_path / "test.db"


@pytest.fixture
def manager(db_path: Path) -> EntityWatchlistManager:
    """Create a test watchlist manager."""
    # Pre-create the schema
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS entity_watchlists (
            watchlist_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            watchlist_type TEXT NOT NULL CHECK(watchlist_type IN ('manual', 'war_targets', 'contacts')),
            owner_character_id INTEGER,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_entity_watchlists_owner
            ON entity_watchlists(name, owner_character_id) WHERE owner_character_id IS NOT NULL;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_entity_watchlists_global
            ON entity_watchlists(name) WHERE owner_character_id IS NULL;

        CREATE TABLE IF NOT EXISTS entity_watchlist_items (
            watchlist_id INTEGER NOT NULL,
            entity_id INTEGER NOT NULL,
            entity_type TEXT NOT NULL CHECK(entity_type IN ('corporation', 'alliance')),
            entity_name TEXT,
            added_at INTEGER NOT NULL,
            added_reason TEXT,
            PRIMARY KEY (watchlist_id, entity_id, entity_type),
            FOREIGN KEY (watchlist_id) REFERENCES entity_watchlists(watchlist_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_entity_items_entity ON entity_watchlist_items(entity_id, entity_type);

        INSERT OR REPLACE INTO metadata (key, value) VALUES ('schema_version', '7');
    """)
    conn.commit()
    conn.close()

    mgr = EntityWatchlistManager(db_path)
    yield mgr
    mgr.close()


class TestWatchlistCRUD:
    """Tests for watchlist CRUD operations."""

    def test_create_watchlist(self, manager: EntityWatchlistManager):
        """Test creating a watchlist."""
        watchlist = manager.create_watchlist(
            name="Test Watchlist",
            description="A test watchlist",
            watchlist_type="manual",
        )

        assert watchlist.watchlist_id is not None
        assert watchlist.name == "Test Watchlist"
        assert watchlist.description == "A test watchlist"
        assert watchlist.watchlist_type == "manual"
        assert watchlist.owner_character_id is None

    def test_create_watchlist_with_owner(self, manager: EntityWatchlistManager):
        """Test creating a pilot-specific watchlist."""
        watchlist = manager.create_watchlist(
            name="War Targets",
            watchlist_type="war_targets",
            owner_character_id=123456,
        )

        assert watchlist.owner_character_id == 123456

    def test_get_watchlist(self, manager: EntityWatchlistManager):
        """Test retrieving a watchlist by name."""
        manager.create_watchlist(name="Hostiles", watchlist_type="manual")

        retrieved = manager.get_watchlist("Hostiles")

        assert retrieved is not None
        assert retrieved.name == "Hostiles"

    def test_get_watchlist_not_found(self, manager: EntityWatchlistManager):
        """Test retrieving non-existent watchlist."""
        retrieved = manager.get_watchlist("Does Not Exist")

        assert retrieved is None

    def test_list_watchlists(self, manager: EntityWatchlistManager):
        """Test listing all global watchlists."""
        manager.create_watchlist(name="List1", watchlist_type="manual")
        manager.create_watchlist(name="List2", watchlist_type="manual")

        watchlists = manager.list_watchlists()

        assert len(watchlists) == 2
        names = [w.name for w in watchlists]
        assert "List1" in names
        assert "List2" in names

    def test_list_watchlists_by_type(self, manager: EntityWatchlistManager):
        """Test filtering watchlists by type."""
        manager.create_watchlist(name="Manual1", watchlist_type="manual")
        manager.create_watchlist(name="Wars", watchlist_type="war_targets")

        manual_lists = manager.list_watchlists(watchlist_type="manual")

        assert len(manual_lists) == 1
        assert manual_lists[0].name == "Manual1"

    def test_delete_watchlist(self, manager: EntityWatchlistManager):
        """Test deleting a watchlist."""
        watchlist = manager.create_watchlist(name="ToDelete", watchlist_type="manual")

        deleted = manager.delete_watchlist(watchlist.watchlist_id)

        assert deleted is True
        assert manager.get_watchlist("ToDelete") is None

    def test_update_watchlist(self, manager: EntityWatchlistManager):
        """Test updating watchlist metadata."""
        watchlist = manager.create_watchlist(name="Original", watchlist_type="manual")

        updated = manager.update_watchlist(
            watchlist.watchlist_id,
            description="Updated description",
        )

        assert updated is True
        retrieved = manager.get_watchlist_by_id(watchlist.watchlist_id)
        assert retrieved.description == "Updated description"


class TestEntityManagement:
    """Tests for entity management within watchlists."""

    def test_add_entity(self, manager: EntityWatchlistManager):
        """Test adding an entity to a watchlist."""
        watchlist = manager.create_watchlist(name="Test", watchlist_type="manual")

        entity = manager.add_entity(
            watchlist_id=watchlist.watchlist_id,
            entity_id=98000001,
            entity_type="corporation",
            entity_name="Test Corp",
            added_reason="Known hostile",
        )

        assert entity.entity_id == 98000001
        assert entity.entity_type == "corporation"
        assert entity.entity_name == "Test Corp"
        assert entity.added_reason == "Known hostile"

    def test_add_alliance(self, manager: EntityWatchlistManager):
        """Test adding an alliance to a watchlist."""
        watchlist = manager.create_watchlist(name="Test", watchlist_type="manual")

        entity = manager.add_entity(
            watchlist_id=watchlist.watchlist_id,
            entity_id=99000001,
            entity_type="alliance",
        )

        assert entity.entity_type == "alliance"

    def test_get_entities(self, manager: EntityWatchlistManager):
        """Test getting all entities in a watchlist."""
        watchlist = manager.create_watchlist(name="Test", watchlist_type="manual")
        manager.add_entity(watchlist.watchlist_id, 98000001, "corporation")
        manager.add_entity(watchlist.watchlist_id, 99000001, "alliance")

        entities = manager.get_entities(watchlist.watchlist_id)

        assert len(entities) == 2

    def test_remove_entity(self, manager: EntityWatchlistManager):
        """Test removing an entity from a watchlist."""
        watchlist = manager.create_watchlist(name="Test", watchlist_type="manual")
        manager.add_entity(watchlist.watchlist_id, 98000001, "corporation")

        removed = manager.remove_entity(
            watchlist.watchlist_id,
            98000001,
            "corporation",
        )

        assert removed is True
        entities = manager.get_entities(watchlist.watchlist_id)
        assert len(entities) == 0

    def test_get_entity_count(self, manager: EntityWatchlistManager):
        """Test getting entity count for a watchlist."""
        watchlist = manager.create_watchlist(name="Test", watchlist_type="manual")
        manager.add_entity(watchlist.watchlist_id, 98000001, "corporation")
        manager.add_entity(watchlist.watchlist_id, 98000002, "corporation")

        count = manager.get_entity_count(watchlist.watchlist_id)

        assert count == 2


class TestEntityLookup:
    """Tests for entity lookup methods."""

    def test_get_all_watched_entity_ids(self, manager: EntityWatchlistManager):
        """Test getting all watched entity IDs."""
        wl1 = manager.create_watchlist(name="List1", watchlist_type="manual")
        wl2 = manager.create_watchlist(name="List2", watchlist_type="manual")
        manager.add_entity(wl1.watchlist_id, 98000001, "corporation")
        manager.add_entity(wl1.watchlist_id, 99000001, "alliance")
        manager.add_entity(wl2.watchlist_id, 98000002, "corporation")

        corp_ids, alliance_ids = manager.get_all_watched_entity_ids()

        assert 98000001 in corp_ids
        assert 98000002 in corp_ids
        assert 99000001 in alliance_ids

    def test_is_entity_watched(self, manager: EntityWatchlistManager):
        """Test checking if an entity is watched."""
        watchlist = manager.create_watchlist(name="Test", watchlist_type="manual")
        manager.add_entity(watchlist.watchlist_id, 98000001, "corporation")

        assert manager.is_entity_watched(98000001, "corporation") is True
        assert manager.is_entity_watched(98000002, "corporation") is False
        assert manager.is_entity_watched(98000001, "alliance") is False


class TestCascadeDelete:
    """Tests for cascade delete behavior."""

    def test_delete_watchlist_cascades_entities(self, manager: EntityWatchlistManager):
        """Test that deleting a watchlist removes its entities."""
        watchlist = manager.create_watchlist(name="Test", watchlist_type="manual")
        manager.add_entity(watchlist.watchlist_id, 98000001, "corporation")
        manager.add_entity(watchlist.watchlist_id, 98000002, "corporation")

        manager.delete_watchlist(watchlist.watchlist_id)

        # Entities should no longer be watched
        assert manager.is_entity_watched(98000001, "corporation") is False
        assert manager.is_entity_watched(98000002, "corporation") is False
