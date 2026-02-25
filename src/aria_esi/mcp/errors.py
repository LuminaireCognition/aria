"""
MCP Error Classes for Universe Server.

Provides structured exceptions that serialize to MCP-compliant error responses.

STP-004: MCP Server Core
"""

from __future__ import annotations

from typing import Any

from ..core.exceptions import AriaError
from ..services.loop_planning.errors import (
    InsufficientBordersError as _ServiceInsufficientBordersError,
)
from ..services.navigation.errors import (
    RouteNotFoundError as _ServiceRouteNotFoundError,
)
from ..services.navigation.errors import (
    SystemNotFoundError as _ServiceSystemNotFoundError,
)


class UniverseError(AriaError):
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


class SystemNotFoundError(UniverseError, _ServiceSystemNotFoundError):
    """
    Raised when a system name cannot be resolved.

    Inherits from both UniverseError (for MCP error formatting)
    and the service-level SystemNotFoundError (for attribute compatibility).
    """

    code = "SYSTEM_NOT_FOUND"

    def __init__(self, name: str, suggestions: list[str] | None = None):
        _ServiceSystemNotFoundError.__init__(self, name, suggestions)

    def _error_data(self) -> dict[str, Any]:
        return {"suggestions": self.suggestions}


class RouteNotFoundError(UniverseError, _ServiceRouteNotFoundError):
    """
    Raised when no route exists between systems.

    Inherits from both UniverseError (for MCP error formatting)
    and the service-level RouteNotFoundError (for attribute compatibility).
    """

    code = "ROUTE_NOT_FOUND"

    def __init__(self, origin: str, destination: str, reason: str | None = None):
        _ServiceRouteNotFoundError.__init__(self, origin, destination, reason)

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
