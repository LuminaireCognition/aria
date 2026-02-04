"""
Arbitrage Freshness and Utility Module.

Pure functions for data freshness classification, confidence scoring,
and volume calculations. Extracted from arbitrage_engine.py for testability.
"""

from __future__ import annotations

import time

from aria_esi.models.market import (
    DEFAULT_VOLUME_M3,
    ConfidenceLevel,
    FreshnessLevel,
)

# =============================================================================
# Freshness Thresholds (seconds)
# =============================================================================

# Hub data thresholds
FRESH_THRESHOLD = 300  # 5 minutes
RECENT_THRESHOLD = 1800  # 30 minutes

# Scope data thresholds (more lenient)
SCOPE_FRESH_THRESHOLD = 600  # 10 minutes
SCOPE_RECENT_THRESHOLD = 3600  # 1 hour


# =============================================================================
# Freshness Classification
# =============================================================================


def get_freshness(timestamp: int) -> FreshnessLevel:
    """
    Classify freshness based on timestamp (hub data thresholds).

    Args:
        timestamp: Unix timestamp of the data

    Returns:
        FreshnessLevel: "fresh" (<5 min), "recent" (5-30 min), or "stale" (>30 min)
    """
    age = time.time() - timestamp
    if age < FRESH_THRESHOLD:
        return "fresh"
    elif age < RECENT_THRESHOLD:
        return "recent"
    return "stale"


def get_scope_freshness(timestamp: int) -> FreshnessLevel:
    """
    Classify freshness based on timestamp (scope data - more lenient thresholds).

    Args:
        timestamp: Unix timestamp of the data

    Returns:
        FreshnessLevel: "fresh" (<10 min), "recent" (10-60 min), or "stale" (>60 min)
    """
    age = time.time() - timestamp
    if age < SCOPE_FRESH_THRESHOLD:
        return "fresh"
    elif age < SCOPE_RECENT_THRESHOLD:
        return "recent"
    return "stale"


def get_confidence(
    buy_freshness: FreshnessLevel,
    sell_freshness: FreshnessLevel,
) -> ConfidenceLevel:
    """
    Calculate V1 confidence level based on data freshness.

    V1 confidence is purely freshness-based:
    - high: Both sides fresh (<5 min)
    - medium: At least one side recent (5-30 min)
    - low: Any side stale (>30 min)

    Args:
        buy_freshness: Freshness of buy-side data
        sell_freshness: Freshness of sell-side data

    Returns:
        ConfidenceLevel: "high", "medium", or "low"
    """
    if buy_freshness == "fresh" and sell_freshness == "fresh":
        return "high"
    elif buy_freshness == "stale" or sell_freshness == "stale":
        return "low"
    return "medium"


def get_combined_freshness(
    buy_freshness: FreshnessLevel,
    sell_freshness: FreshnessLevel,
) -> FreshnessLevel:
    """
    Combine buy and sell freshness levels into overall freshness.

    Overall freshness is the worse of the two sides.

    Args:
        buy_freshness: Freshness of buy-side data
        sell_freshness: Freshness of sell-side data

    Returns:
        FreshnessLevel: The worst of the two freshness levels
    """
    if buy_freshness == "stale" or sell_freshness == "stale":
        return "stale"
    elif buy_freshness == "recent" or sell_freshness == "recent":
        return "recent"
    return "fresh"


# =============================================================================
# Volume Utilities
# =============================================================================


def get_effective_volume(
    volume: float | None,
    packaged_volume: float | None,
) -> tuple[float, str]:
    """
    Get effective item volume, preferring packaged volume.

    Preference order: packaged_volume -> volume -> DEFAULT_VOLUME_M3

    Args:
        volume: Item volume from SDE
        packaged_volume: Packaged volume from SDE (for ships/modules)

    Returns:
        Tuple of (effective_volume, volume_source)
        volume_source is "sde_packaged" | "sde_volume" | "fallback"
    """
    if packaged_volume is not None and packaged_volume > 0:
        return packaged_volume, "sde_packaged"
    if volume is not None and volume > 0:
        return volume, "sde_volume"
    return DEFAULT_VOLUME_M3, "fallback"
