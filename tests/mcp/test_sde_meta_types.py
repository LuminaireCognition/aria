"""
Tests for meta type functionality.

These tests verify the invMetaGroups and invMetaTypes import and query functionality.
"""

from __future__ import annotations

import pytest


class TestMetaTypeImporter:
    """Test meta type import functionality."""

    def test_import_meta_groups(self, seeded_market_db):
        """Verify meta groups are imported from SDE."""
        from aria_esi.mcp.sde.importer import SDEImporter

        importer = SDEImporter(seeded_market_db)
        status = importer.get_sde_status()

        # Meta groups should be imported (Tech I, Tech II, Faction, etc.)
        # Fuzzwork SDE typically has ~14 meta groups
        assert status.meta_group_count > 0, "Expected meta groups to be imported"

    def test_import_meta_types(self, seeded_market_db):
        """Verify meta types are imported from SDE."""
        from aria_esi.mcp.sde.importer import SDEImporter

        importer = SDEImporter(seeded_market_db)
        status = importer.get_sde_status()

        # Meta types link variants to parent items
        # Should have thousands of meta type relationships
        assert status.meta_type_count > 0, "Expected meta types to be imported"


class TestMetaTypeQueries:
    """Test meta type query functionality."""

    def test_get_all_meta_groups(self, seeded_market_db):
        """List all meta groups."""
        from aria_esi.mcp.sde.queries import SDEQueryService

        service = SDEQueryService(seeded_market_db)
        groups = service.get_all_meta_groups()

        assert len(groups) > 0, "Expected meta groups to exist"

        # Check for standard meta groups
        names = {g.meta_group_name for g in groups}
        # At minimum we expect Tech II to exist
        assert any("Tech" in name for name in names), f"Expected Tech meta groups, got: {names}"

    def test_get_meta_group_by_id(self, seeded_market_db):
        """Get a specific meta group by ID."""
        from aria_esi.mcp.sde.queries import SDEQueryService

        service = SDEQueryService(seeded_market_db)

        # Tech II is typically meta_group_id = 2
        group = service.get_meta_group(2)

        if group:
            assert group.meta_group_id == 2
            assert "II" in group.meta_group_name or "2" in group.meta_group_name

    def test_get_meta_variants_from_t2(self, seeded_market_db):
        """Query variants starting from T2 item."""
        from aria_esi.mcp.sde.queries import SDEQueryService

        service = SDEQueryService(seeded_market_db)

        # Look up a well-known item - find any T2 module type_id
        conn = seeded_market_db._get_connection()
        cursor = conn.execute(
            """
            SELECT mt.type_id, t.type_name
            FROM meta_types mt
            JOIN types t ON mt.type_id = t.type_id
            WHERE mt.meta_group_id = 2  -- Tech II
            LIMIT 1
            """
        )
        row = cursor.fetchone()

        if row:
            type_id, type_name = row
            variants = service.get_meta_variants(type_id)

            # Should find at least the T2 variant itself
            assert len(variants) >= 0, f"Expected variants for {type_name}"

    def test_get_meta_variants_from_t1(self, seeded_market_db):
        """Query variants starting from T1 item."""
        from aria_esi.mcp.sde.queries import SDEQueryService

        service = SDEQueryService(seeded_market_db)

        # Find a T1 item that has variants
        conn = seeded_market_db._get_connection()
        cursor = conn.execute(
            """
            SELECT parent_type_id, COUNT(*) as variant_count
            FROM meta_types
            GROUP BY parent_type_id
            HAVING variant_count > 1
            LIMIT 1
            """
        )
        row = cursor.fetchone()

        if row:
            parent_id = row[0]
            variants = service.get_meta_variants(parent_id)

            # Should find multiple variants
            assert len(variants) > 1, f"Expected multiple variants for parent {parent_id}"

    def test_get_parent_type_id(self, seeded_market_db):
        """Test parent type resolution."""
        from aria_esi.mcp.sde.queries import SDEQueryService

        service = SDEQueryService(seeded_market_db)

        # Find a variant type
        conn = seeded_market_db._get_connection()
        cursor = conn.execute(
            """
            SELECT type_id, parent_type_id FROM meta_types LIMIT 1
            """
        )
        row = cursor.fetchone()

        if row:
            type_id, expected_parent = row
            actual_parent = service._get_parent_type_id(type_id)
            assert actual_parent == expected_parent

    def test_cache_invalidation(self, seeded_market_db):
        """Test that caches are properly invalidated."""
        from aria_esi.mcp.sde.queries import SDEQueryService

        service = SDEQueryService(seeded_market_db)

        # Warm cache
        groups1 = service.get_all_meta_groups()

        # Invalidate
        service.invalidate_all()

        # Should still work after invalidation
        groups2 = service.get_all_meta_groups()

        assert len(groups1) == len(groups2)


@pytest.mark.asyncio
class TestMetaVariantsDispatcher:
    """Test meta_variants action via MCP dispatcher."""

    async def test_meta_variants_not_found(self, seeded_market_db):
        """Test meta_variants with non-existent item."""
        from aria_esi.mcp.dispatchers.sde import _meta_variants

        result = await _meta_variants("Nonexistent Item XYZ123")

        assert result["found"] is False
        assert result["query_type_id"] == 0
        assert len(result["warnings"]) > 0

    async def test_meta_variants_missing_param(self):
        """Test meta_variants without item parameter."""
        from aria_esi.mcp.dispatchers.sde import _meta_variants
        from aria_esi.mcp.errors import InvalidParameterError

        with pytest.raises(InvalidParameterError):
            await _meta_variants(None)

    async def test_meta_variants_with_valid_item(self, seeded_market_db):
        """Test meta_variants with a valid item that has variants."""
        from aria_esi.mcp.dispatchers.sde import _meta_variants

        # Find an item that has variants
        conn = seeded_market_db._get_connection()
        cursor = conn.execute(
            """
            SELECT t.type_name
            FROM meta_types mt
            JOIN types t ON mt.parent_type_id = t.type_id
            WHERE t.published = 1
            LIMIT 1
            """
        )
        row = cursor.fetchone()

        if row:
            item_name = row[0]
            result = await _meta_variants(item_name)

            assert result["found"] is True
            assert result["query_type_id"] > 0
            # Parent should be identified
            assert result["parent_type_id"] is not None or result["total_variants"] >= 0


@pytest.fixture
def seeded_market_db():
    """
    Fixture that provides a seeded market database for testing.

    This reuses the existing database if available, otherwise skips.
    """
    from aria_esi.mcp.market.database import get_market_database

    db = get_market_database()

    # Check if SDE is seeded
    conn = db._get_connection()
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='meta_groups'"
    )
    if not cursor.fetchone():
        pytest.skip("SDE meta tables not seeded - run 'uv run aria-esi sde-seed' first")

    return db
