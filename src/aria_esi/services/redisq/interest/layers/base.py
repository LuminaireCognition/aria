"""
Interest Layer Protocol.

Defines the interface for interest calculation layers.
Each layer independently scores systems/kills based on its criteria.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ...models import ProcessedKill
    from ..models import LayerScore


@runtime_checkable
class InterestLayer(Protocol):
    """
    Protocol for interest calculation layers.

    Each layer provides interest scores based on a specific criterion:
    - Geographic: Distance from operational systems
    - Entity: Corp/alliance involvement
    - Route: Named travel routes
    - Asset: Corp structure/office locations

    Layers implement two scoring methods:
    - score_system(): Quick check with system ID only (pre-fetch)
    - score_kill(): Full check with kill context (post-fetch)

    The calculator takes max(layer_scores) as the base interest.
    """

    @property
    def name(self) -> str:
        """
        Unique name for this layer.

        Used as key in InterestScore.layer_scores dict.

        Returns:
            Layer name (e.g., "geographic", "entity")
        """
        ...

    def score_system(self, system_id: int) -> LayerScore:
        """
        Score a system without kill context.

        Used for pre-fetch filtering when only system ID is available.
        Layers that require kill context should return score=0.0.

        Args:
            system_id: Solar system ID

        Returns:
            LayerScore with interest score and reason
        """
        ...

    def score_kill(self, system_id: int, kill: ProcessedKill | None) -> LayerScore:
        """
        Score a system with optional kill context.

        Used for post-fetch scoring when full kill data is available.
        If kill is None, behaves like score_system().

        Args:
            system_id: Solar system ID
            kill: ProcessedKill with full kill data, or None

        Returns:
            LayerScore with interest score and reason
        """
        ...


class BaseLayer:
    """
    Base implementation for interest layers.

    Provides common functionality and default implementations.
    Subclasses should override score_system() and optionally score_kill().
    """

    _name: str = "base"

    @property
    def name(self) -> str:
        """Get layer name."""
        return self._name

    def score_system(self, system_id: int) -> LayerScore:
        """
        Default implementation returns zero interest.

        Subclasses should override with their scoring logic.
        """
        from ..models import LayerScore

        return LayerScore(layer=self.name, score=0.0, reason=None)

    def score_kill(self, system_id: int, kill: ProcessedKill | None) -> LayerScore:
        """
        Default implementation delegates to score_system().

        Subclasses that need kill context should override.
        """
        if kill is None:
            return self.score_system(system_id)
        # Default: same as system-only scoring
        return self.score_system(system_id)
