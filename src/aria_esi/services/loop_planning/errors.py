"""
Loop Planning Service Errors.

Domain-specific exceptions for loop planning operations.
These errors are independent of the transport layer (MCP, CLI, etc.).
"""

from __future__ import annotations


class LoopPlanningError(Exception):
    """Base exception for loop planning operations."""

    pass


class InsufficientBordersError(LoopPlanningError):
    """Raised when loop planning cannot find enough border systems."""

    def __init__(
        self,
        found: int,
        required: int,
        search_radius: int,
        suggestion: str | None = None,
    ):
        self.found = found
        self.required = required
        self.search_radius = search_radius
        self.suggestion = (
            suggestion
            or "Try increasing target_jumps, decreasing min_borders, or relaxing security_filter"
        )
        super().__init__(
            f"Only found {found} border systems within {search_radius} jumps, "
            f"but {required} required"
        )
