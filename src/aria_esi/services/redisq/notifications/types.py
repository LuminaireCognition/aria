"""
Shared Type Definitions for Notification Commentary.

This module contains enums and types shared between commentary.py and prompts.py
to avoid circular import issues.
"""

from __future__ import annotations

from enum import Enum


class CommentaryStyle(Enum):
    """Style presets for commentary generation."""

    CONVERSATIONAL = "conversational"  # Default: natural prose
    RADIO = "radio"  # Tactical brevity, operator cadence


class StressLevel(Enum):
    """
    Stress level for style conditioning.

    CRITICAL: Stress level has a COUNTERINTUITIVE relationship to output tone.
    This implements "Yeager voice" panic suppression (see research document §2.2.2):

    - HIGH stress → *calmer* linguistic output (minimization engaged, no fillers)
    - LOW stress  → personality can breathe (fillers permitted, more expressive)

    The operator who says "taking a little rattle" while their engine is on fire
    is demonstrating supreme confidence. Panic in the voice destroys that signal.
    """

    LOW = "low"  # Routine intel, market updates → expressive, fillers OK
    MODERATE = "moderate"  # Watchlist activity, system changes → balanced
    HIGH = "high"  # Active combat, gatecamps, losses → calm understatement


class PatternSeverity(Enum):
    """
    Severity level for detected patterns.

    Used to derive stress level automatically, ensuring new pattern types
    receive correct stress handling based on their declared severity rather
    than requiring exhaustive map maintenance.
    """

    INFO = "info"  # Routine intel (NPC activity, market updates)
    WARNING = "warning"  # Elevated concern (watchlist hits, repeat attackers)
    CRITICAL = "critical"  # Active threat (gatecamps, gank rotations, losses)


# Severity → Stress level mapping (derived from pattern metadata)
SEVERITY_STRESS_MAP: dict[PatternSeverity, StressLevel] = {
    PatternSeverity.INFO: StressLevel.LOW,
    PatternSeverity.WARNING: StressLevel.MODERATE,
    PatternSeverity.CRITICAL: StressLevel.HIGH,
}

# Stress level severity ordering (higher index = higher severity)
STRESS_SEVERITY_ORDER: dict[StressLevel, int] = {
    StressLevel.LOW: 0,
    StressLevel.MODERATE: 1,
    StressLevel.HIGH: 2,
}

# Default character limit for radio-style commentary
DEFAULT_MAX_CHARS = 200
