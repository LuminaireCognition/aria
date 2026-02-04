"""
Tests for Loop Planning Result Builder.

Tests the LoopSummary dataclass and compute_loop_summary function.
"""

from __future__ import annotations

import pytest


# =============================================================================
# LoopSummary Tests
# =============================================================================


class TestLoopSummary:
    """Test LoopSummary dataclass."""

    def test_dataclass_fields(self):
        """LoopSummary has all required fields."""
        from aria_esi.services.loop_planning.result_builder import LoopSummary

        summary = LoopSummary(
            full_route=[0, 1, 2, 1, 0],
            borders_visited=[(2, 2)],
            total_jumps=4,
            unique_systems=3,
            backtrack_jumps=2,
            efficiency=0.6,
        )

        assert summary.full_route == [0, 1, 2, 1, 0]
        assert summary.borders_visited == [(2, 2)]
        assert summary.total_jumps == 4
        assert summary.unique_systems == 3
        assert summary.backtrack_jumps == 2
        assert summary.efficiency == 0.6

    def test_frozen(self):
        """LoopSummary is immutable."""
        from aria_esi.services.loop_planning.result_builder import LoopSummary

        summary = LoopSummary(
            full_route=[0, 1, 0],
            borders_visited=[],
            total_jumps=2,
            unique_systems=2,
            backtrack_jumps=1,
            efficiency=0.67,
        )

        with pytest.raises((TypeError, AttributeError)):
            summary.total_jumps = 5  # type: ignore


# =============================================================================
# compute_loop_summary Tests
# =============================================================================


class TestComputeLoopSummary:
    """Test compute_loop_summary function."""

    def test_basic_calculation(self):
        """Computes summary for simple route."""
        from aria_esi.services.loop_planning.result_builder import compute_loop_summary

        # Route: A -> B -> C -> B -> A (return trip)
        full_route = [0, 1, 2, 1, 0]
        borders_visited = [(2, 2)]

        summary = compute_loop_summary(full_route, borders_visited)

        assert summary.total_jumps == 4
        assert summary.unique_systems == 3  # A, B, C
        assert summary.backtrack_jumps == 2  # B->A revisits
        assert summary.full_route == full_route
        assert summary.borders_visited == borders_visited

    def test_no_backtrack(self):
        """Computes summary for route with no backtracking."""
        from aria_esi.services.loop_planning.result_builder import compute_loop_summary

        # Route: A -> B -> C (linear)
        full_route = [0, 1, 2]
        borders_visited = []

        summary = compute_loop_summary(full_route, borders_visited)

        assert summary.total_jumps == 2
        assert summary.unique_systems == 3
        assert summary.backtrack_jumps == 0
        assert summary.efficiency == 1.0

    def test_empty_route(self):
        """Handles empty route gracefully."""
        from aria_esi.services.loop_planning.result_builder import compute_loop_summary

        summary = compute_loop_summary([], [])

        assert summary.total_jumps == 0
        assert summary.unique_systems == 0
        assert summary.backtrack_jumps == 0
        assert summary.efficiency == 0.0

    def test_single_system(self):
        """Handles single system route."""
        from aria_esi.services.loop_planning.result_builder import compute_loop_summary

        summary = compute_loop_summary([0], [])

        assert summary.total_jumps == 0
        assert summary.unique_systems == 1
        assert summary.backtrack_jumps == 0
        assert summary.efficiency == 1.0

    def test_efficiency_calculation(self):
        """Efficiency is unique_systems / total_length."""
        from aria_esi.services.loop_planning.result_builder import compute_loop_summary

        # Route visits 5 systems total, only 3 unique
        full_route = [0, 1, 2, 1, 0]  # 5 total, 3 unique

        summary = compute_loop_summary(full_route, [])

        assert summary.efficiency == 3 / 5  # 0.6

    def test_efficiency_capped_at_one(self):
        """Efficiency is capped at 1.0."""
        from aria_esi.services.loop_planning.result_builder import compute_loop_summary

        # Perfectly efficient route
        full_route = [0, 1, 2, 3]

        summary = compute_loop_summary(full_route, [])

        assert summary.efficiency <= 1.0

    def test_backtrack_not_negative(self):
        """Backtrack jumps is never negative."""
        from aria_esi.services.loop_planning.result_builder import compute_loop_summary

        # No backtracking possible
        full_route = [0, 1, 2]

        summary = compute_loop_summary(full_route, [])

        assert summary.backtrack_jumps >= 0
