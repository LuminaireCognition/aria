"""
Navigation Service Errors.

Domain-specific exceptions for route calculation operations.
These errors are independent of the transport layer (MCP, CLI, etc.).
"""

from __future__ import annotations

from aria_esi.core.exceptions import AriaError


class NavigationError(AriaError):
    """Base exception for navigation operations."""

    pass


class RouteNotFoundError(NavigationError):
    """Raised when no route exists between systems."""

    def __init__(self, origin: str, destination: str, reason: str | None = None):
        self.origin = origin
        self.destination = destination
        self.reason = reason
        msg = f"No route from {origin} to {destination}"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)


class SystemNotFoundError(NavigationError):
    """Raised when a system cannot be resolved."""

    def __init__(self, name: str, suggestions: list[str] | None = None):
        self.name = name
        self.suggestions = suggestions or []
        msg = f"Unknown system: {name}"
        if self.suggestions:
            msg += f". Did you mean: {', '.join(self.suggestions)}?"
        super().__init__(msg)
