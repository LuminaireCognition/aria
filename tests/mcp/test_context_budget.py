"""
Tests for context budget tracking functionality.

Tracks cumulative output size across tool calls and warns at soft limits (50KB)
and flags at hard limit (100KB).
"""

from __future__ import annotations

import pytest

from aria_esi.mcp.context_budget import (
    ContextBudget,
    get_context_budget,
    reset_context_budget,
)
from aria_esi.mcp.context_policy import GLOBAL


class TestContextBudgetBasic:
    """Basic ContextBudget functionality tests."""

    def test_budget_starts_at_zero(self):
        """New budget should start with 0 bytes and 0 tool calls."""
        budget = ContextBudget()

        assert budget.bytes_used == 0
        assert budget.tool_count == 0

    def test_add_output_increments_bytes(self):
        """add_output should increment bytes_used."""
        budget = ContextBudget()

        budget.add_output(1000)

        assert budget.bytes_used == 1000

    def test_add_output_increments_tool_count(self):
        """add_output should increment tool_count."""
        budget = ContextBudget()

        budget.add_output(1000)

        assert budget.tool_count == 1

    def test_multiple_outputs_accumulate(self):
        """Multiple outputs should accumulate correctly."""
        budget = ContextBudget()

        budget.add_output(1000)
        budget.add_output(2000)
        budget.add_output(500)

        assert budget.bytes_used == 3500
        assert budget.tool_count == 3

    def test_zero_byte_output(self):
        """Zero-byte output should still increment tool count."""
        budget = ContextBudget()

        budget.add_output(0)

        assert budget.bytes_used == 0
        assert budget.tool_count == 1


class TestContextBudgetLimits:
    """Tests for limit checking functionality."""

    def test_under_soft_limit_no_warning(self):
        """Should not warn when under soft limit."""
        budget = ContextBudget()
        budget.add_output(10000)  # 10KB, well under 50KB soft limit

        limits = budget.check_limits()

        assert limits["soft_limit_exceeded"] is False
        assert limits["hard_limit_exceeded"] is False
        assert "warning" not in limits

    def test_soft_limit_warning(self):
        """Should warn when exceeding soft limit (50KB)."""
        budget = ContextBudget()
        budget.add_output(55000)  # 55KB, over 50KB soft limit

        limits = budget.check_limits()

        assert limits["soft_limit_exceeded"] is True
        assert limits["hard_limit_exceeded"] is False
        assert "warning" in limits
        assert "55,000 bytes" in limits["warning"]

    def test_hard_limit_warning(self):
        """Should warn with different message when exceeding hard limit (100KB)."""
        budget = ContextBudget()
        budget.add_output(110000)  # 110KB, over 100KB hard limit

        limits = budget.check_limits()

        assert limits["soft_limit_exceeded"] is True
        assert limits["hard_limit_exceeded"] is True
        assert "warning" in limits
        assert "hard limit" in limits["warning"].lower()

    def test_exactly_at_soft_limit(self):
        """At exactly soft limit should not warn (uses > not >=)."""
        budget = ContextBudget()
        budget.add_output(GLOBAL.MAX_TOTAL_OUTPUT_BYTES)  # Exactly 50KB

        limits = budget.check_limits()

        assert limits["soft_limit_exceeded"] is False
        assert "warning" not in limits

    def test_exactly_at_hard_limit(self):
        """At exactly hard limit should not warn (uses > not >=)."""
        budget = ContextBudget()
        budget.add_output(GLOBAL.HARD_LIMIT_BYTES)  # Exactly 100KB

        limits = budget.check_limits()

        assert limits["hard_limit_exceeded"] is False


class TestRemainingBudget:
    """Tests for remaining_budget calculation."""

    def test_remaining_budget_calculation(self):
        """Should calculate remaining budget correctly."""
        budget = ContextBudget()
        budget.add_output(30000)  # 30KB

        remaining = budget.remaining_budget()

        expected = GLOBAL.HARD_LIMIT_BYTES - 30000
        assert remaining == expected

    def test_remaining_budget_never_negative(self):
        """Remaining budget should never go negative."""
        budget = ContextBudget()
        budget.add_output(200000)  # Way over limit

        remaining = budget.remaining_budget()

        assert remaining == 0

    def test_remaining_budget_at_zero(self):
        """Starting budget should show full remaining."""
        budget = ContextBudget()

        remaining = budget.remaining_budget()

        assert remaining == GLOBAL.HARD_LIMIT_BYTES


class TestContextBudgetCheckLimitsFields:
    """Tests for check_limits return value fields."""

    def test_check_limits_returns_bytes_used(self):
        """check_limits should return bytes_used."""
        budget = ContextBudget()
        budget.add_output(5000)

        limits = budget.check_limits()

        assert limits["bytes_used"] == 5000

    def test_check_limits_returns_tool_count(self):
        """check_limits should return tool_count."""
        budget = ContextBudget()
        budget.add_output(1000)
        budget.add_output(1000)

        limits = budget.check_limits()

        assert limits["tool_count"] == 2

    def test_check_limits_returns_remaining_bytes(self):
        """check_limits should return remaining_bytes."""
        budget = ContextBudget()
        budget.add_output(10000)

        limits = budget.check_limits()

        expected = GLOBAL.HARD_LIMIT_BYTES - 10000
        assert limits["remaining_bytes"] == expected


class TestContextVariable:
    """Tests for context variable management."""

    def test_get_context_budget_creates_new(self):
        """get_context_budget should create new budget if none exists."""
        reset_context_budget()

        budget = get_context_budget()

        assert budget is not None
        assert budget.bytes_used == 0
        assert budget.tool_count == 0

    def test_get_context_budget_returns_same(self):
        """get_context_budget should return same budget on subsequent calls."""
        reset_context_budget()

        budget1 = get_context_budget()
        budget1.add_output(1000)

        budget2 = get_context_budget()

        assert budget1 is budget2
        assert budget2.bytes_used == 1000

    def test_reset_clears_state(self):
        """reset_context_budget should clear accumulated state."""
        reset_context_budget()

        budget1 = get_context_budget()
        budget1.add_output(50000)

        reset_context_budget()

        budget2 = get_context_budget()

        assert budget2.bytes_used == 0
        assert budget2.tool_count == 0

    def test_reset_creates_new_instance(self):
        """reset_context_budget should create new instance."""
        reset_context_budget()

        budget1 = get_context_budget()

        reset_context_budget()

        budget2 = get_context_budget()

        assert budget1 is not budget2


class TestPolicyConstants:
    """Tests for policy constant integration."""

    def test_soft_limit_constant(self):
        """Soft limit should be 50KB."""
        assert GLOBAL.MAX_TOTAL_OUTPUT_BYTES == 51200  # 50 * 1024

    def test_hard_limit_constant(self):
        """Hard limit should be 100KB."""
        assert GLOBAL.HARD_LIMIT_BYTES == 102400  # 100 * 1024

    def test_limits_relationship(self):
        """Soft limit should be less than hard limit."""
        assert GLOBAL.MAX_TOTAL_OUTPUT_BYTES < GLOBAL.HARD_LIMIT_BYTES


class TestWarningMessages:
    """Tests for warning message content."""

    def test_soft_limit_warning_includes_remaining(self):
        """Soft limit warning should include remaining bytes."""
        budget = ContextBudget()
        budget.add_output(55000)

        limits = budget.check_limits()

        assert "remaining" in limits["warning"].lower()

    def test_hard_limit_warning_suggests_action(self):
        """Hard limit warning should suggest reducing scope."""
        budget = ContextBudget()
        budget.add_output(110000)

        limits = budget.check_limits()

        assert "summarizing" in limits["warning"].lower() or "reducing" in limits["warning"].lower()


class TestEdgeCases:
    """Edge case tests."""

    def test_large_single_output(self):
        """Should handle large single output."""
        budget = ContextBudget()
        budget.add_output(1_000_000)  # 1MB

        limits = budget.check_limits()

        assert limits["hard_limit_exceeded"] is True
        assert budget.remaining_budget() == 0

    def test_many_small_outputs(self):
        """Should handle many small outputs accumulating."""
        budget = ContextBudget()

        for _ in range(1000):
            budget.add_output(100)

        assert budget.bytes_used == 100_000
        assert budget.tool_count == 1000
        limits = budget.check_limits()
        assert limits["hard_limit_exceeded"] is False  # Exactly at 100KB

    def test_output_just_over_soft_limit(self):
        """Should warn at soft limit + 1."""
        budget = ContextBudget()
        budget.add_output(GLOBAL.MAX_TOTAL_OUTPUT_BYTES + 1)

        limits = budget.check_limits()

        assert limits["soft_limit_exceeded"] is True
        assert "warning" in limits


class TestLogContextIntegration:
    """Integration tests for log_context decorator with budget tracking."""

    @pytest.mark.asyncio
    async def test_log_context_tracks_budget(self):
        """log_context should track output in budget."""
        from aria_esi.mcp.context import log_context

        reset_context_budget()

        @log_context("test")
        async def mock_tool(action: str = "test") -> dict:
            return {"data": "x" * 1000, "_meta": {"count": 1}}

        await mock_tool()

        budget = get_context_budget()
        assert budget.bytes_used > 0
        assert budget.tool_count == 1

    @pytest.mark.asyncio
    async def test_log_context_adds_warning_at_limit(self):
        """log_context should add budget_warning to _meta when limit exceeded."""
        from aria_esi.mcp.context import log_context

        reset_context_budget()

        # Pre-fill budget near soft limit
        budget = get_context_budget()
        budget.add_output(GLOBAL.MAX_TOTAL_OUTPUT_BYTES)

        @log_context("test")
        async def mock_tool(action: str = "test") -> dict:
            return {"data": "more data", "_meta": {"count": 1}}

        result = await mock_tool()

        # Should have warning in meta
        assert "budget_warning" in result["_meta"]
        assert "budget_bytes_used" in result["_meta"]

    @pytest.mark.asyncio
    async def test_log_context_accumulates_across_calls(self):
        """Multiple tool calls should accumulate in budget."""
        from aria_esi.mcp.context import log_context

        reset_context_budget()

        @log_context("test")
        async def mock_tool(action: str = "test") -> dict:
            return {"data": "x" * 100, "_meta": {"count": 1}}

        await mock_tool()
        await mock_tool()
        await mock_tool()

        budget = get_context_budget()
        assert budget.tool_count == 3
        assert budget.bytes_used > 300  # At least 3 x 100 bytes
