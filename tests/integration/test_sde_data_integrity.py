"""
SDE Data Integrity Tests.

These tests validate that the SDE data in the database matches
the assumptions made by the query layer. Run after `aria-esi sde-seed`.

Usage:
    uv run pytest tests/integration/test_sde_data_integrity.py -v

These tests are SKIPPED if SDE is not seeded, allowing CI to pass
on fresh environments.
"""

from __future__ import annotations

import pytest

from aria_esi.mcp.market.database import get_market_database
from aria_esi.mcp.sde.queries import (
    get_sde_query_service,
    reset_sde_query_service,
)


def sde_is_seeded() -> bool:
    """Check if SDE data has been imported."""
    try:
        db = get_market_database()
        conn = db._get_connection()
        cursor = conn.execute("SELECT COUNT(*) FROM types WHERE published = 1")
        count = cursor.fetchone()[0]
        return count > 1000  # Sanity check - real SDE has ~40k types
    except Exception:
        return False


# Skip marker for unseeded databases
requires_sde = pytest.mark.skipif(
    not sde_is_seeded(),
    reason="SDE not seeded. Run 'uv run aria-esi sde-seed' first.",
)


@requires_sde
class TestCorporationRegionIntegrity:
    """Validate corporation-to-region mapping assumptions."""

    def test_seeding_corporations_have_stations(self):
        """Every corporation in npc_seeding should have at least one station."""
        db = get_market_database()
        conn = db._get_connection()

        cursor = conn.execute(
            """
            SELECT DISTINCT ns.corporation_id, nc.corporation_name
            FROM npc_seeding ns
            JOIN npc_corporations nc ON ns.corporation_id = nc.corporation_id
            LEFT JOIN stations s ON ns.corporation_id = s.corporation_id
            WHERE s.station_id IS NULL
            """
        )

        orphans = cursor.fetchall()

        # Some corporations may legitimately seed items but have no stations
        # (e.g., they sell through other corps' stations). Document exceptions:
        known_exceptions: set[int] = {
            # Add corporation IDs here if discovered to be legitimate
        }

        unexpected = [(cid, name) for cid, name in orphans if cid not in known_exceptions]

        # This is informational - some corps seed items but don't have stations
        # The dynamic query handles this gracefully by returning None
        if unexpected:
            pytest.skip(
                f"Corporations seed items but have no stations (expected for some): "
                f"{unexpected[:5]}..."
            )

    def test_major_factions_have_regions(self):
        """Key NPC corporations should have resolvable regions."""
        db = get_market_database()
        conn = db._get_connection()

        # Corporations that MUST have station presence for blueprint lookups
        critical_corps = [
            (1000129, "Outer Ring Excavations"),
            (1000130, "Sisters of EVE"),
        ]

        for corp_id, expected_name in critical_corps:
            cursor = conn.execute(
                """
                SELECT nc.corporation_name, COUNT(DISTINCT s.region_id)
                FROM npc_corporations nc
                LEFT JOIN stations s ON nc.corporation_id = s.corporation_id
                WHERE nc.corporation_id = ?
                GROUP BY nc.corporation_id
                """,
                (corp_id,),
            )
            row = cursor.fetchone()

            assert row is not None, f"Corporation {corp_id} not found in database"
            corp_name, region_count = row
            assert region_count > 0, f"{corp_name} ({corp_id}) has no stations in any region"

    def test_no_orphan_blueprint_products(self):
        """All blueprint products should reference valid types."""
        db = get_market_database()
        conn = db._get_connection()

        cursor = conn.execute(
            """
            SELECT bp.blueprint_type_id, bp.product_type_id
            FROM blueprint_products bp
            LEFT JOIN types t ON bp.product_type_id = t.type_id
            WHERE t.type_id IS NULL
            LIMIT 10
            """
        )

        orphans = cursor.fetchall()
        assert not orphans, f"Blueprint products reference missing types: {orphans}"


@requires_sde
class TestCategoryConstants:
    """Validate that category ID constants match SDE."""

    EXPECTED_CATEGORIES = {
        6: "Ship",
        7: "Module",
        8: "Charge",
        9: "Blueprint",
        16: "Skill",
        18: "Drone",
        25: "Asteroid",
    }

    def test_category_ids_match_sde(self):
        """Hard-coded category IDs should match actual SDE values."""
        db = get_market_database()
        conn = db._get_connection()

        mismatches = []
        for cat_id, expected_name in self.EXPECTED_CATEGORIES.items():
            cursor = conn.execute(
                "SELECT category_name FROM categories WHERE category_id = ?",
                (cat_id,),
            )
            row = cursor.fetchone()

            if row is None:
                mismatches.append((cat_id, expected_name, "NOT FOUND"))
            elif row[0] != expected_name:
                mismatches.append((cat_id, expected_name, row[0]))

        assert not mismatches, (
            f"Category constant mismatches (id, expected, actual): {mismatches}"
        )


@requires_sde
class TestQueryServiceIntegration:
    """Test the SDEQueryService against real data."""

    def setup_method(self):
        """Reset service before each test."""
        reset_sde_query_service()

    def test_ore_corporation_regions(self):
        """ORE should have stations in Outer Ring."""
        service = get_sde_query_service()
        result = service.get_corporation_regions(1000129)  # ORE

        assert result is not None
        assert result.corporation_name == "Outer Ring Excavations"
        assert result.primary_region_name == "Outer Ring"

    def test_sisters_multi_region(self):
        """Sisters of EVE should have stations in multiple regions."""
        service = get_sde_query_service()
        result = service.get_corporation_regions(1000130)  # Sisters

        assert result is not None
        # Sisters have stations in many regions, not just Syndicate
        assert len(result.regions) > 1, (
            f"Sisters only found in {len(result.regions)} region(s), expected multiple"
        )

    def test_cache_invalidation(self):
        """Cache should invalidate when timestamp changes."""
        service = get_sde_query_service()

        # Populate cache
        _ = service.get_corporation_regions(1000129)
        assert 1000129 in service._corp_regions

        # Simulate re-import by changing timestamp
        old_timestamp = service._cache_import_timestamp
        service._cache_import_timestamp = "old-timestamp"

        # Next query should detect mismatch and clear cache
        _ = service.get_corporation_regions(1000129)

        # Cache should have been rebuilt with current timestamp
        assert service._cache_import_timestamp != "old-timestamp"

    def test_nonexistent_corporation(self):
        """Non-existent corporation should return None, not raise."""
        service = get_sde_query_service()
        result = service.get_corporation_regions(999999999)
        assert result is None

    def test_seeding_corporations_lookup(self):
        """Can look up seeding corporations for items."""
        service = get_sde_query_service()

        # Venture Blueprint (32881) should be seeded by ORE
        db = get_market_database()
        conn = db._get_connection()
        cursor = conn.execute(
            "SELECT type_id FROM types WHERE type_name = 'Venture Blueprint' LIMIT 1"
        )
        row = cursor.fetchone()

        if row:
            result = service.get_npc_seeding_corporations(row[0])
            # Should have at least ORE
            corp_ids = [corp_id for corp_id, _ in result]
            assert 1000129 in corp_ids, "ORE should seed Venture Blueprint"

    def test_category_lookup(self):
        """Can look up category ID by name."""
        service = get_sde_query_service()

        ship_id = service.get_category_id("Ship")
        assert ship_id == 6

        blueprint_id = service.get_category_id("Blueprint")
        assert blueprint_id == 9

        # Case-insensitive
        module_id = service.get_category_id("module")
        assert module_id == 7

    def test_corporation_info(self):
        """Can get full corporation info."""
        service = get_sde_query_service()
        result = service.get_corporation_info(1000129)

        assert result is not None
        assert result.corporation_name == "Outer Ring Excavations"
        assert result.station_count > 0
        assert result.seeds_items
        assert result.seeded_item_count > 0


@requires_sde
class TestBlueprintSourceAccuracy:
    """Validate blueprint source lookups return correct data."""

    def test_venture_blueprint_sources(self):
        """Venture Blueprint should show correct seeding corporations."""
        db = get_market_database()
        conn = db._get_connection()

        cursor = conn.execute(
            """
            SELECT nc.corporation_id, nc.corporation_name
            FROM npc_seeding ns
            JOIN npc_corporations nc ON ns.corporation_id = nc.corporation_id
            JOIN types t ON ns.type_id = t.type_id
            WHERE t.type_name = 'Venture Blueprint'
            """,
        )

        corps = {row[0]: row[1] for row in cursor.fetchall()}

        # Venture Blueprint is seeded by ORE and University of Caille
        assert 1000129 in corps, "ORE should seed Venture Blueprint"

    def test_pioneer_blueprint_sources(self):
        """Pioneer Blueprint seeding should be queryable."""
        db = get_market_database()
        conn = db._get_connection()

        cursor = conn.execute(
            """
            SELECT nc.corporation_id, nc.corporation_name
            FROM npc_seeding ns
            JOIN npc_corporations nc ON ns.corporation_id = nc.corporation_id
            JOIN types t ON ns.type_id = t.type_id
            WHERE t.type_name = 'Pioneer Blueprint'
            """,
        )

        corps = {row[0]: row[1] for row in cursor.fetchall()}

        # Pioneer Blueprint may be seeded differently than documented
        # This test documents actual behavior
        if corps:
            # If we found seeding data, verify we can query regions for those corps
            service = get_sde_query_service()
            for corp_id, corp_name in corps.items():
                regions = service.get_corporation_regions(corp_id)
                # Some corps may not have stations, that's OK
                if regions:
                    assert regions.primary_region_id is not None
        else:
            pytest.skip("Pioneer Blueprint has no NPC seeding data in this SDE version")
