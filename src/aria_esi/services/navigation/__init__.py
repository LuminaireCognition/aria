"""
Navigation Service.

Unified route calculation service shared between MCP tools and CLI commands.
Provides a single source of truth for routing algorithms, weight constants,
and result construction utilities.

Usage:
    from aria_esi.services.navigation import NavigationService

    service = NavigationService(universe)
    path = service.calculate_route(origin_idx, dest_idx, "safe")
"""

from __future__ import annotations

__all__ = [
    # Core service
    "NavigationService",
    "RouteMode",
    "VALID_MODES",
    # Errors
    "NavigationError",
    "RouteNotFoundError",
    "SystemNotFoundError",
    # Weight computation
    "compute_avoid_weights",
    "compute_safe_weights",
    "compute_unsafe_weights",
    # Weight constants
    "HIGHSEC_THRESHOLD",
    "LOWSEC_THRESHOLD",
    "WEIGHT_NORMAL",
    "WEIGHT_LOWSEC_ENTRY",
    "WEIGHT_LOWSEC_STAY",
    "WEIGHT_NULLSEC",
    "WEIGHT_UNSAFE_NULLSEC",
    "WEIGHT_UNSAFE_LOWSEC",
    "WEIGHT_UNSAFE_HIGHSEC",
    "WEIGHT_AVOID",
    # Result utilities
    "SecuritySummary",
    "compute_security_summary",
    "generate_warnings",
    "get_threat_level",
]


def __getattr__(name: str):
    """Lazy import to avoid circular dependencies."""
    # Router
    if name == "NavigationService":
        from .router import NavigationService

        return NavigationService
    if name in ("RouteMode", "VALID_MODES"):
        from . import router

        return getattr(router, name)

    # Errors
    if name in ("NavigationError", "RouteNotFoundError", "SystemNotFoundError"):
        from . import errors

        return getattr(errors, name)

    # Weights
    if name in (
        "compute_avoid_weights",
        "compute_safe_weights",
        "compute_unsafe_weights",
        "HIGHSEC_THRESHOLD",
        "LOWSEC_THRESHOLD",
        "WEIGHT_NORMAL",
        "WEIGHT_LOWSEC_ENTRY",
        "WEIGHT_LOWSEC_STAY",
        "WEIGHT_NULLSEC",
        "WEIGHT_UNSAFE_NULLSEC",
        "WEIGHT_UNSAFE_LOWSEC",
        "WEIGHT_UNSAFE_HIGHSEC",
        "WEIGHT_AVOID",
    ):
        from . import weights

        return getattr(weights, name)

    # Result utilities
    if name in (
        "SecuritySummary",
        "compute_security_summary",
        "generate_warnings",
        "get_threat_level",
    ):
        from . import result_builder

        return getattr(result_builder, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
