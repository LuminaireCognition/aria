"""
SDE Query Performance Benchmarks.

These tests validate that the query layer meets latency requirements.
Run after SDE is seeded: uv run pytest tests/integration/test_sde_performance.py -v

Performance targets:
- Cached lookups: <10ms (p99)
- Uncached lookups: <250ms
- Cache warming: <500ms
"""

from __future__ import annotations

import statistics
import time

import pytest

from aria_esi.mcp.sde.queries import (
    SDENotSeededError,
    get_sde_query_service,
    reset_sde_query_service,
)


def sde_is_seeded() -> bool:
    """Check if SDE data has been imported."""
    try:
        reset_sde_query_service()
        service = get_sde_query_service()
        service.get_corporation_regions(1000129)  # ORE
        return True
    except (SDENotSeededError, Exception):
        return False


requires_sde = pytest.mark.skipif(
    not sde_is_seeded(),
    reason="SDE not seeded. Run 'uv run aria-esi sde-seed' first.",
)


@requires_sde
class TestCachedLookupPerformance:
    """Validate cached lookup latency requirements."""

    def setup_method(self):
        """Reset service before each test."""
        reset_sde_query_service()

    def test_cached_corporation_lookup_p99(self):
        """Cached corporation lookups should complete in <10ms (p99)."""
        service = get_sde_query_service()

        # Warm the cache
        service.get_corporation_regions(1000129)

        # Measure 100 cached lookups
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            service.get_corporation_regions(1000129)
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)

        p99 = sorted(latencies)[98]  # 99th percentile
        avg = statistics.mean(latencies)

        assert p99 < 10.0, (
            f"Cached lookup p99={p99:.2f}ms exceeds 10ms target (avg={avg:.2f}ms)"
        )

    def test_cached_lookup_consistency(self):
        """Multiple cached lookups should return identical results."""
        service = get_sde_query_service()

        results = [service.get_corporation_regions(1000129) for _ in range(10)]

        # All results should be the same object (cached)
        assert all(r is results[0] for r in results), (
            "Cached lookups returned different objects"
        )


@requires_sde
class TestUncachedLookupPerformance:
    """Validate cold-cache lookup latency requirements."""

    def setup_method(self):
        """Reset service before each test."""
        reset_sde_query_service()

    def test_uncached_corporation_lookup(self):
        """Uncached corporation lookup should complete in <250ms."""
        service = get_sde_query_service()

        # Clear cache to force cold lookup
        service.invalidate_all()

        start = time.perf_counter()
        result = service.get_corporation_regions(1000129)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert result is not None, "ORE should exist in SDE"
        assert elapsed_ms < 250.0, (
            f"Uncached lookup took {elapsed_ms:.2f}ms, exceeds 250ms target"
        )

    def test_uncached_unknown_corporation(self):
        """Lookup of non-existent corporation should also be fast."""
        service = get_sde_query_service()
        service.invalidate_all()

        start = time.perf_counter()
        result = service.get_corporation_regions(999999999)  # Non-existent
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert result is None, "Non-existent corp should return None"
        assert elapsed_ms < 250.0, (
            f"Negative lookup took {elapsed_ms:.2f}ms, exceeds 250ms target"
        )


@requires_sde
class TestCacheWarmingPerformance:
    """Validate cache warming latency requirements."""

    def setup_method(self):
        """Reset service before each test."""
        reset_sde_query_service()

    def test_full_cache_warming(self):
        """Full cache warming should complete in <500ms."""
        service = get_sde_query_service()

        # Clear caches first
        service.invalidate_all()

        start = time.perf_counter()
        stats = service.warm_caches()
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 500.0, (
            f"Cache warming took {elapsed_ms:.2f}ms, exceeds 500ms target"
        )
        assert stats["corporations"] >= 5, (
            f"Only {stats['corporations']} corporations warmed, expected >=5"
        )

    def test_cache_validity_check_overhead(self):
        """Cache validity check should add <5ms overhead."""
        service = get_sde_query_service()

        # Warm cache
        service.get_corporation_regions(1000129)

        # Measure validity check overhead (happens on every lookup)
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            service._check_cache_validity()
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)

        p99 = sorted(latencies)[98]

        assert p99 < 5.0, f"Cache validity check p99={p99:.2f}ms exceeds 5ms target"


@requires_sde
class TestQueryPlanEfficiency:
    """Validate that queries use indexes effectively."""

    def test_corporation_regions_query_is_efficient(self):
        """Corporation regions query should be efficient."""
        from aria_esi.mcp.market.database import get_market_database

        db = get_market_database()
        conn = db._get_connection()

        # Get query plan for the corporation regions query
        cursor = conn.execute(
            """
            EXPLAIN QUERY PLAN
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
            (1000129,),
        )

        plan = "\n".join(str(row) for row in cursor.fetchall())

        # The query should use indexes, not full table scans
        # This is informational - print the plan for debugging
        print(f"\nQuery plan:\n{plan}")

        # Basic sanity check: the query should complete quickly
        start = time.perf_counter()
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
            (1000129,),
        )
        _ = cursor.fetchall()
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 50.0, f"Raw query took {elapsed_ms:.2f}ms, may need index"
