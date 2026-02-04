"""
Commentary Warrant Checker.

Decides when LLM-generated commentary adds value to Discord notifications
based on detected patterns and warrant scores.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ....core.logging import get_logger

if TYPE_CHECKING:
    from .patterns import PatternContext

logger = get_logger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Default thresholds
DEFAULT_THRESHOLD_SKIP = 0.3
DEFAULT_THRESHOLD_OPPORTUNISTIC = 0.5

# Default timeouts in milliseconds
DEFAULT_TIMEOUT_OPPORTUNISTIC_MS = 1500
DEFAULT_TIMEOUT_GENERATE_MS = 3000


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class CommentaryDecision:
    """
    Decision about whether to generate LLM commentary.

    Actions:
    - skip: Don't generate commentary, patterns don't warrant it
    - opportunistic: Generate with short timeout, nice to have but not critical
    - generate: Generate with full timeout, patterns are interesting
    """

    action: str  # "skip", "opportunistic", "generate"
    reason: str  # Human-readable explanation
    timeout_ms: int  # Timeout for LLM call
    warrant_score: float = 0.0  # Score that led to this decision

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "action": self.action,
            "reason": self.reason,
            "timeout_ms": self.timeout_ms,
            "warrant_score": self.warrant_score,
        }


# =============================================================================
# Warrant Checker
# =============================================================================


class WarrantChecker:
    """
    Decides when LLM commentary should be generated.

    Uses pattern detection results to determine:
    - Whether to skip commentary entirely
    - Whether to try with a short timeout (opportunistic)
    - Whether to try with full timeout (generate)
    """

    def __init__(
        self,
        threshold_skip: float = DEFAULT_THRESHOLD_SKIP,
        threshold_opportunistic: float = DEFAULT_THRESHOLD_OPPORTUNISTIC,
        timeout_opportunistic_ms: int = DEFAULT_TIMEOUT_OPPORTUNISTIC_MS,
        timeout_generate_ms: int = DEFAULT_TIMEOUT_GENERATE_MS,
    ):
        """
        Initialize warrant checker.

        Args:
            threshold_skip: Warrant score below this = skip commentary
            threshold_opportunistic: Score between skip and this = opportunistic
            timeout_opportunistic_ms: Timeout for opportunistic commentary
            timeout_generate_ms: Timeout for full commentary generation
        """
        self.threshold_skip = threshold_skip
        self.threshold_opportunistic = threshold_opportunistic
        self.timeout_opportunistic_ms = timeout_opportunistic_ms
        self.timeout_generate_ms = timeout_generate_ms

    def should_generate_commentary(
        self,
        pattern_context: PatternContext,
    ) -> CommentaryDecision:
        """
        Decide whether to generate commentary for a kill.

        Decision logic:
        - score < threshold_skip: Skip entirely
        - threshold_skip <= score < threshold_opportunistic: Opportunistic (short timeout)
        - score >= threshold_opportunistic: Generate (full timeout)

        Args:
            pattern_context: Pattern detection results for the kill

        Returns:
            CommentaryDecision with action, reason, and timeout
        """
        score = pattern_context.warrant_score()

        if score < self.threshold_skip:
            return CommentaryDecision(
                action="skip",
                reason=f"Warrant score {score:.2f} below skip threshold {self.threshold_skip}",
                timeout_ms=0,
                warrant_score=score,
            )

        if score < self.threshold_opportunistic:
            # Build reason from patterns
            pattern_names = [p.pattern_type for p in pattern_context.patterns]
            reason = (
                f"Patterns detected ({', '.join(pattern_names)}), trying opportunistic commentary"
            )

            return CommentaryDecision(
                action="opportunistic",
                reason=reason,
                timeout_ms=self.timeout_opportunistic_ms,
                warrant_score=score,
            )

        # High warrant score - generate with full timeout
        pattern_names = [p.pattern_type for p in pattern_context.patterns]
        reason = f"High-value patterns detected ({', '.join(pattern_names)}), generating commentary"

        return CommentaryDecision(
            action="generate",
            reason=reason,
            timeout_ms=self.timeout_generate_ms,
            warrant_score=score,
        )

    @classmethod
    def from_config(cls, config: dict) -> WarrantChecker:
        """
        Create WarrantChecker from config dict.

        Args:
            config: Dict with optional threshold and timeout overrides

        Returns:
            WarrantChecker instance
        """
        return cls(
            threshold_skip=config.get("threshold_skip", DEFAULT_THRESHOLD_SKIP),
            threshold_opportunistic=config.get(
                "threshold_opportunistic", DEFAULT_THRESHOLD_OPPORTUNISTIC
            ),
            timeout_opportunistic_ms=config.get(
                "timeout_opportunistic_ms", DEFAULT_TIMEOUT_OPPORTUNISTIC_MS
            ),
            timeout_generate_ms=config.get("timeout_generate_ms", DEFAULT_TIMEOUT_GENERATE_MS),
        )
