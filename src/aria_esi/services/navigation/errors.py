"""
Navigation Service Errors.

Domain-specific exceptions for route calculation operations.
These errors are independent of the transport layer (MCP, CLI, etc.).
"""

from __future__ import annotations


class NavigationError(Exception):
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

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Unknown system: {name}")
