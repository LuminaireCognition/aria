"""
Interest Calculator.

Orchestrates multi-layer interest calculation for context-aware topology.
Interest = max(layer_scores) * escalation_multiplier
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ....core.logging import get_logger

if TYPE_CHECKING:
    from ..models import ProcessedKill
    from .layers.base import InterestLayer

from .models import InterestScore, LayerScore, PatternEscalation

logger = get_logger(__name__)


@dataclass
class InterestCalculator:
    """
    Multi-layer interest calculator.

    Coordinates multiple interest layers to produce a unified interest score.
    The final score is: min(max(layer_scores) * escalation_multiplier, 1.0)

    Usage:
        calculator = InterestCalculator(layers=[geo_layer, entity_layer])

        # Pre-fetch check (system only)
        if calculator.should_fetch(system_id):
            kill = fetch_from_esi(kill_id)

            # Post-fetch with full context
            score = calculator.calculate_kill_interest(system_id, kill)
            if score.should_notify:
                send_notification(kill, score)
    """

    layers: list[InterestLayer] = field(default_factory=list)
    pattern_layer: InterestLayer | None = None  # Optional pattern escalation layer
    fetch_threshold: float = 0.0  # Minimum interest to fetch from ESI

    # Configurable thresholds
    log_threshold: float = 0.3
    digest_threshold: float = 0.6
    priority_threshold: float = 0.8

    def calculate_system_interest(self, system_id: int) -> InterestScore:
        """
        Calculate interest for a system without kill context.

        Used for pre-fetch filtering when only system ID is available.
        Layers that require kill context will return 0.0.

        Args:
            system_id: Solar system ID

        Returns:
            InterestScore with breakdown by layer
        """
        return self._calculate(system_id, kill=None)

    def calculate_kill_interest(
        self,
        system_id: int,
        kill: ProcessedKill,
    ) -> InterestScore:
        """
        Calculate interest for a kill with full context.

        Used after ESI fetch when complete kill data is available.
        All layers can contribute based on kill details.

        Args:
            system_id: Solar system ID
            kill: ProcessedKill with full kill data

        Returns:
            InterestScore with breakdown by layer
        """
        return self._calculate(system_id, kill=kill)

    def should_fetch(self, system_id: int) -> bool:
        """
        Quick check if a kill should be fetched from ESI.

        Uses system-only scoring for efficiency.

        Args:
            system_id: Solar system ID

        Returns:
            True if kill should be fetched
        """
        score = self.calculate_system_interest(system_id)
        return score.interest > self.fetch_threshold

    def _calculate(
        self,
        system_id: int,
        kill: ProcessedKill | None,
    ) -> InterestScore:
        """
        Internal calculation logic shared by both methods.

        Args:
            system_id: Solar system ID
            kill: Optional ProcessedKill for full context

        Returns:
            InterestScore with complete breakdown
        """
        layer_scores: dict[str, LayerScore] = {}

        # Score from each layer
        for layer in self.layers:
            try:
                if kill is not None:
                    score = layer.score_kill(system_id, kill)
                else:
                    score = layer.score_system(system_id)
                layer_scores[layer.name] = score
            except Exception as e:
                logger.warning(
                    "Layer %s failed to score system %d: %s",
                    layer.name,
                    system_id,
                    e,
                )
                # Add zero score for failed layer
                layer_scores[layer.name] = LayerScore(
                    layer=layer.name,
                    score=0.0,
                    reason=f"Error: {e}",
                )

        # Base interest = max of all layer scores
        if layer_scores:
            max_layer = max(layer_scores.values(), key=lambda ls: ls.score)
            base_interest = max_layer.score
            dominant_layer = max_layer.layer
        else:
            base_interest = 0.0
            dominant_layer = "none"

        # Pattern escalation (multiplier)
        escalation: PatternEscalation | None = None
        if self.pattern_layer is not None:
            try:
                pattern_score = (
                    self.pattern_layer.score_kill(system_id, kill)
                    if kill
                    else self.pattern_layer.score_system(system_id)
                )
                # Pattern layer returns multiplier as score, reason explains why
                if pattern_score.score > 1.0:
                    escalation = PatternEscalation(
                        multiplier=pattern_score.score,
                        reason=pattern_score.reason,
                    )
            except Exception as e:
                logger.warning(
                    "Pattern layer failed for system %d: %s",
                    system_id,
                    e,
                )

        # Final interest = base * escalation, capped at 1.0
        multiplier = escalation.multiplier if escalation else 1.0
        final_interest = min(base_interest * multiplier, 1.0)

        return InterestScore(
            system_id=system_id,
            interest=final_interest,
            base_interest=base_interest,
            dominant_layer=dominant_layer,
            layer_scores=layer_scores,
            escalation=escalation,
        )

    def add_layer(self, layer: InterestLayer) -> None:
        """
        Add an interest layer.

        Args:
            layer: Layer to add
        """
        self.layers.append(layer)
        logger.debug("Added interest layer: %s", layer.name)

    def set_pattern_layer(self, layer: InterestLayer) -> None:
        """
        Set the pattern escalation layer.

        Args:
            layer: Pattern layer providing escalation multipliers
        """
        self.pattern_layer = layer
        logger.debug("Set pattern layer: %s", layer.name)

    def get_layer(self, name: str) -> InterestLayer | None:
        """
        Get a layer by name.

        Args:
            name: Layer name

        Returns:
            Layer instance or None if not found
        """
        for layer in self.layers:
            if layer.name == name:
                return layer
        return None

    @property
    def layer_names(self) -> list[str]:
        """Get list of configured layer names."""
        names = [layer.name for layer in self.layers]
        if self.pattern_layer:
            names.append(f"{self.pattern_layer.name} (escalation)")
        return names

    def explain_system(self, system_id: int) -> str:
        """
        Generate human-readable explanation of interest calculation.

        Args:
            system_id: Solar system ID

        Returns:
            Multi-line explanation string
        """
        score = self.calculate_system_interest(system_id)
        lines = [
            f"Interest Breakdown for System {system_id}",
            "=" * 40,
            f"Final Interest: {score.interest:.3f} ({score.tier})",
            f"Base Interest: {score.base_interest:.3f}",
            f"Dominant Layer: {score.dominant_layer}",
            "",
            "Layer Scores:",
        ]

        for name, layer_score in score.layer_scores.items():
            reason = f" ({layer_score.reason})" if layer_score.reason else ""
            marker = " *" if name == score.dominant_layer else "  "
            lines.append(f"{marker}{name}: {layer_score.score:.3f}{reason}")

        if score.escalation and score.escalation.multiplier != 1.0:
            lines.append("")
            lines.append(f"Escalation: {score.escalation.multiplier}x")
            if score.escalation.reason:
                lines.append(f"  Reason: {score.escalation.reason}")

        return "\n".join(lines)
