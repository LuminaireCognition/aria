"""
Context budget tracking for MCP tool outputs.

Tracks cumulative output size across tool calls within a conversation turn
and provides warnings when approaching context limits.

Usage:
    from aria_esi.mcp.context_budget import get_context_budget, reset_context_budget

    # Get/create budget for current turn
    budget = get_context_budget()

    # Track output
    budget.add_output(len(json.dumps(result)))

    # Check limits
    limits = budget.check_limits()
    if limits.get("warning"):
        result["_meta"]["budget_warning"] = limits["warning"]

    # Reset for new turn
    reset_context_budget()
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass

from .context_policy import GLOBAL


@dataclass
class ContextBudget:
    """
    Tracks cumulative output size within a conversation turn.

    Provides soft limit warnings at 50KB and hard limit flags at 100KB
    to help manage context window usage across multiple MCP tool calls.

    Attributes:
        bytes_used: Total bytes output so far in this turn
        tool_count: Number of tool calls made in this turn
    """

    bytes_used: int = 0
    tool_count: int = 0

    def add_output(self, size_bytes: int) -> None:
        """
        Record output from a tool call.

        Args:
            size_bytes: Size of the output in bytes
        """
        self.bytes_used += size_bytes
        self.tool_count += 1

    def check_limits(self) -> dict:
        """
        Check if output has exceeded soft or hard limits.

        Returns:
            Dictionary with limit status:
            - bytes_used: Current total bytes
            - tool_count: Number of tool calls
            - soft_limit_exceeded: True if > 50KB
            - hard_limit_exceeded: True if > 100KB
            - warning: Human-readable warning message (if any)
            - remaining_bytes: Bytes remaining before hard limit
        """
        soft_exceeded = self.bytes_used > GLOBAL.MAX_TOTAL_OUTPUT_BYTES
        hard_exceeded = self.bytes_used > GLOBAL.HARD_LIMIT_BYTES
        remaining = max(0, GLOBAL.HARD_LIMIT_BYTES - self.bytes_used)

        result: dict[str, int | bool | str] = {
            "bytes_used": self.bytes_used,
            "tool_count": self.tool_count,
            "soft_limit_exceeded": soft_exceeded,
            "hard_limit_exceeded": hard_exceeded,
            "remaining_bytes": remaining,
        }

        if hard_exceeded:
            result["warning"] = (
                f"Context budget exceeded hard limit ({self.bytes_used:,} bytes). "
                "Consider summarizing results or reducing scope."
            )
        elif soft_exceeded:
            result["warning"] = (
                f"Context budget at {self.bytes_used:,} bytes "
                f"({remaining:,} bytes remaining before hard limit). "
                "Consider limiting further queries."
            )

        return result

    def remaining_budget(self) -> int:
        """
        Get remaining bytes before hard limit.

        Returns:
            Remaining bytes available (minimum 0)
        """
        return max(0, GLOBAL.HARD_LIMIT_BYTES - self.bytes_used)


# Context variable for async tracking across tool calls
_budget_var: ContextVar[ContextBudget | None] = ContextVar("context_budget", default=None)


def get_context_budget() -> ContextBudget:
    """
    Get or create budget for current conversation turn.

    Uses a context variable so each async context has its own budget.
    Creates a new budget if one doesn't exist for the current context.

    Returns:
        ContextBudget instance for current turn
    """
    budget = _budget_var.get()
    if budget is None:
        budget = ContextBudget()
        _budget_var.set(budget)
    return budget


def reset_context_budget() -> None:
    """
    Reset budget for new conversation turn.

    Call this at the start of a new conversation turn to clear
    accumulated output tracking.
    """
    _budget_var.set(None)
