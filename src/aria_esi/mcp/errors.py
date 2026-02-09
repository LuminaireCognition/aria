"""
MCP Error Classes for Universe Server.

Provides structured exceptions that serialize to MCP-compliant error responses.

STP-004: MCP Server Core
"""

from __future__ import annotations

from typing import Any

from ..services.loop_planning.errors import (
    InsufficientBordersError as _ServiceInsufficientBordersError,
)


class UniverseError(Exception):
    """Base exception for universe queries."""

    code: str = "UNIVERSE_ERROR"

    def to_mcp_error(self) -> dict[str, Any]:
        """Convert to MCP error response format."""
        return {
            "error": {
                "code": self.code,
                "message": str(self),
                "data": self._error_data(),
            }
        }

    def _error_data(self) -> dict[str, Any]:
        """Override to provide error-specific data."""
        return {}


class SystemNotFoundError(UniverseError):
    """Raised when a system name cannot be resolved."""

    code = "SYSTEM_NOT_FOUND"

    def __init__(self, name: str, suggestions: list[str] | None = None):
        self.name = name
        self.suggestions = suggestions or []
        msg = f"Unknown system: {name}"
        if self.suggestions:
            msg += f". Did you mean: {', '.join(self.suggestions)}?"
        super().__init__(msg)

    def _error_data(self) -> dict[str, Any]:
        return {"suggestions": self.suggestions}


class RouteNotFoundError(UniverseError):
    """Raised when no route exists between systems."""

    code = "ROUTE_NOT_FOUND"

    def __init__(self, origin: str, destination: str, reason: str | None = None):
        self.origin = origin
        self.destination = destination
        self.reason = reason
        msg = f"No route from {origin} to {destination}"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)

    def _error_data(self) -> dict[str, Any]:
        return {
            "origin": self.origin,
            "destination": self.destination,
            "reason": self.reason,
        }


class InvalidParameterError(UniverseError):
    """Raised for invalid tool parameters."""

    code = "INVALID_PARAMETER"

    def __init__(self, param: str, value: Any, reason: str):
        self.param = param
        self.value = value
        self.reason = reason
        super().__init__(f"Invalid {param}: {reason}")

    def _error_data(self) -> dict[str, Any]:
        return {
            "parameter": self.param,
            "value": str(self.value),
            "reason": self.reason,
        }


class InsufficientBordersError(UniverseError, _ServiceInsufficientBordersError):
    """
    Raised when loop planning cannot find enough border systems.

    This class inherits from both UniverseError (for MCP error formatting)
    and the service-level InsufficientBordersError (for attribute compatibility).
    """

    code = "INSUFFICIENT_BORDERS"

    def __init__(
        self,
        found: int,
        required: int,
        search_radius: int,
        suggestion: str | None = None,
    ):
        # Initialize the service error (sets attributes and message)
        _ServiceInsufficientBordersError.__init__(self, found, required, search_radius, suggestion)
        # UniverseError.__init__ is implicitly called via MRO

    def _error_data(self) -> dict[str, Any]:
        return {
            "found": self.found,
            "required": self.required,
            "search_radius": self.search_radius,
            "suggestion": self.suggestion,
        }
