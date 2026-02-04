"""
Pattern Escalation Layer.

Provides interest multipliers based on activity patterns.
Integrates with existing gatecamp detection and activity tracking.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .....core.logging import get_logger
from ..models import LayerScore, PatternEscalation
from .base import BaseLayer

if TYPE_CHECKING:
    from ...threat_cache import ThreatCache

logger = get_logger(__name__)


# =============================================================================
# Pattern Constants
# =============================================================================

# Multipliers applied to base interest
GATECAMP_MULTIPLIER = 1.5  # Active gatecamp detected
SPIKE_MULTIPLIER = 1.3  # Activity spike above normal
SUSTAINED_MULTIPLIER = 1.2  # Sustained elevated activity

# Escalation time-to-live (seconds)
ESCALATION_TTL_SECONDS = 300  # 5 minutes


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class PatternConfig:
    """Configuration for pattern detection."""

    gatecamp_detection: bool = True
    spike_detection: bool = True

    gatecamp_multiplier: float = GATECAMP_MULTIPLIER
    spike_multiplier: float = SPIKE_MULTIPLIER
    sustained_multiplier: float = SUSTAINED_MULTIPLIER
    spike_threshold: float = 2.0  # Current > baseline * threshold = spike

    escalation_ttl_seconds: int = ESCALATION_TTL_SECONDS

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> PatternConfig:
        """Create from config dict."""
        if not data:
            return cls()

        return cls(
            gatecamp_detection=data.get("gatecamp_detection", True),
            spike_detection=data.get("spike_detection", True),
            gatecamp_multiplier=data.get("gatecamp_multiplier", GATECAMP_MULTIPLIER),
            spike_multiplier=data.get("spike_multiplier", SPIKE_MULTIPLIER),
            sustained_multiplier=data.get("sustained_multiplier", SUSTAINED_MULTIPLIER),
            spike_threshold=data.get("spike_threshold", 2.0),
            escalation_ttl_seconds=data.get("escalation_ttl_seconds", ESCALATION_TTL_SECONDS),
        )


# =============================================================================
# Pattern Layer
# =============================================================================


@dataclass
class PatternLayer(BaseLayer):
    """
    Pattern-based escalation layer.

    Unlike other layers that provide base interest scores (0.0-1.0),
    the pattern layer provides MULTIPLIERS that boost the final interest.

    score_system() returns the multiplier in the score field:
    - 1.0 = no escalation
    - 1.5 = gatecamp detected
    - 1.3 = activity spike

    The calculator applies this as: final = min(base * multiplier, 1.0)

    Integration with ThreatCache:
        The pattern layer can use the existing ThreatCache for gatecamp
        detection and activity analysis.

    Usage:
        pattern_layer = PatternLayer(threat_cache=get_threat_cache())
        calculator.set_pattern_layer(pattern_layer)
    """

    _name: str = "pattern"
    config: PatternConfig = field(default_factory=PatternConfig)

    # Optional ThreatCache for real-time detection
    threat_cache: ThreatCache | None = None

    # Manual escalations: system_id -> PatternEscalation
    _escalations: dict[int, PatternEscalation] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self._name

    def score_system(self, system_id: int) -> LayerScore:
        """
        Get escalation multiplier for a system.

        Returns multiplier as the score value:
        - 1.0 = no escalation
        - >1.0 = escalation active

        Args:
            system_id: Solar system ID

        Returns:
            LayerScore with multiplier in score field
        """
        escalation = self.get_escalation(system_id)
        return LayerScore(
            layer=self.name,
            score=escalation.multiplier,
            reason=escalation.reason,
        )

    def get_escalation(self, system_id: int) -> PatternEscalation:
        """
        Get current escalation state for a system.

        Checks cached escalation first, then recalculates if expired
        or missing.

        Args:
            system_id: Solar system ID

        Returns:
            PatternEscalation with multiplier and reason
        """
        now = time.time()

        # Check cached escalation
        cached = self._escalations.get(system_id)
        if cached is not None and not cached.is_expired(now):
            return cached

        # Recalculate escalation
        return self._calculate_escalation(system_id)

    def _calculate_escalation(self, system_id: int) -> PatternEscalation:
        """
        Calculate escalation based on activity patterns.

        Uses ThreatCache for gatecamp detection and activity spike detection.

        Args:
            system_id: Solar system ID

        Returns:
            PatternEscalation (may be cached)
        """
        now = time.time()

        # Check for gatecamp using ThreatCache (highest priority)
        if self.config.gatecamp_detection and self.threat_cache is not None:
            try:
                gatecamp = self.threat_cache.get_gatecamp_status(system_id)
                if gatecamp is not None:
                    escalation = PatternEscalation(
                        multiplier=self.config.gatecamp_multiplier,
                        reason=f"Active gatecamp ({gatecamp.confidence} confidence)",
                        expires_at=now + self.config.escalation_ttl_seconds,
                    )
                    self._escalations[system_id] = escalation
                    return escalation
            except Exception as e:
                logger.debug("Gatecamp detection failed for %d: %s", system_id, e)

        # Check for activity spike (lower priority than gatecamp)
        if self.config.spike_detection and self.threat_cache is not None:
            try:
                spike_result = self.threat_cache.detect_activity_spike(
                    system_id,
                    spike_threshold=self.config.spike_threshold,
                )
                if spike_result is not None:
                    is_spike, current_rate, baseline_rate = spike_result
                    if is_spike:
                        escalation = PatternEscalation(
                            multiplier=self.config.spike_multiplier,
                            reason=f"Activity spike ({current_rate:.0f}/h vs {baseline_rate:.1f} baseline)",
                            expires_at=now + self.config.escalation_ttl_seconds,
                        )
                        self._escalations[system_id] = escalation
                        return escalation
            except Exception as e:
                logger.debug("Spike detection failed for %d: %s", system_id, e)

        # No escalation detected
        return PatternEscalation(multiplier=1.0)

    def set_escalation(
        self,
        system_id: int,
        multiplier: float,
        reason: str,
        ttl_seconds: int | None = None,
    ) -> None:
        """
        Manually set an escalation for a system.

        Args:
            system_id: Solar system ID
            multiplier: Escalation multiplier
            reason: Human-readable reason
            ttl_seconds: Time-to-live (defaults to config value)
        """
        if ttl_seconds is None:
            ttl_seconds = self.config.escalation_ttl_seconds

        self._escalations[system_id] = PatternEscalation(
            multiplier=multiplier,
            reason=reason,
            expires_at=time.time() + ttl_seconds,
        )
        logger.debug(
            "Set escalation for %d: %.1fx (%s, %ds TTL)",
            system_id,
            multiplier,
            reason,
            ttl_seconds,
        )

    def clear_escalation(self, system_id: int) -> None:
        """Clear escalation for a system."""
        self._escalations.pop(system_id, None)
        logger.debug("Cleared escalation for %d", system_id)

    def clear_expired_escalations(self) -> int:
        """
        Clear all expired escalations.

        Returns:
            Number of escalations cleared
        """
        now = time.time()
        expired = [sid for sid, esc in self._escalations.items() if esc.is_expired(now)]
        for sid in expired:
            del self._escalations[sid]

        if expired:
            logger.debug("Cleared %d expired escalations", len(expired))
        return len(expired)

    @property
    def active_escalation_count(self) -> int:
        """Get count of active (non-expired) escalations."""
        now = time.time()
        return sum(1 for esc in self._escalations.values() if not esc.is_expired(now))

    def get_all_escalations(self) -> dict[int, PatternEscalation]:
        """Get all active escalations."""
        now = time.time()
        return {sid: esc for sid, esc in self._escalations.items() if not esc.is_expired(now)}

    @classmethod
    def from_config(
        cls,
        config: PatternConfig,
        threat_cache: ThreatCache | None = None,
    ) -> PatternLayer:
        """Create layer from configuration."""
        return cls(config=config, threat_cache=threat_cache)

    def to_dict(self) -> dict[str, Any]:
        """Serialize configuration to dict."""
        return {
            "name": self.name,
            "config": {
                "gatecamp_detection": self.config.gatecamp_detection,
                "spike_detection": self.config.spike_detection,
                "gatecamp_multiplier": self.config.gatecamp_multiplier,
                "spike_multiplier": self.config.spike_multiplier,
                "spike_threshold": self.config.spike_threshold,
                "escalation_ttl_seconds": self.config.escalation_ttl_seconds,
            },
            "active_escalations": self.active_escalation_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PatternLayer:
        """Deserialize from dict."""
        config = PatternConfig.from_dict(data.get("config"))
        return cls(config=config)
