"""
Tier-based Delivery Routing for Interest Engine v2.

Routes notifications to different delivery providers based on tier.
Supports multiple destinations per tier with fallback chains.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..models import InterestResultV2

logger = logging.getLogger(__name__)


@dataclass
class TierRouting:
    """
    Routing configuration for a notification tier.

    Attributes:
        tier: Notification tier this applies to
        destinations: List of destination configs
        fallback_on_failure: Try next destination if current fails
        require_all: All destinations must succeed
    """

    tier: str
    destinations: list[dict[str, Any]] = field(default_factory=list)
    fallback_on_failure: bool = True
    require_all: bool = False

    @classmethod
    def from_dict(cls, tier: str, data: dict[str, Any]) -> TierRouting:
        """Create from dictionary."""
        return cls(
            tier=tier,
            destinations=data.get("destinations", []),
            fallback_on_failure=data.get("fallback_on_failure", True),
            require_all=data.get("require_all", False),
        )


class DeliveryRouter:
    """
    Routes notifications to delivery providers based on tier.

    Each tier can have multiple destinations. The router handles:
    - Provider lookup from registry
    - Fallback chains on failure
    - Parallel delivery when require_all is set

    Usage:
        router = DeliveryRouter(routing_config)
        success = await router.deliver(result, payload)
    """

    def __init__(
        self,
        routing: dict[str, TierRouting] | None = None,
    ) -> None:
        """
        Initialize delivery router.

        Args:
            routing: Dict of tier name -> TierRouting config
        """
        self._routing = routing or {}

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> DeliveryRouter:
        """
        Create router from configuration dict.

        Args:
            config: Delivery configuration with tier routing

        Returns:
            Configured DeliveryRouter
        """
        routing = {}
        for tier_name, tier_config in config.items():
            if isinstance(tier_config, dict):
                routing[tier_name] = TierRouting.from_dict(tier_name, tier_config)
        return cls(routing)

    async def deliver(
        self,
        result: InterestResultV2,
        payload: dict[str, Any],
    ) -> bool:
        """
        Deliver notification based on tier routing.

        Args:
            result: Interest result with tier
            payload: Notification payload

        Returns:
            True if delivery succeeded (or no routing configured)
        """
        tier_name = result.tier.value
        tier_routing = self._routing.get(tier_name)

        if not tier_routing or not tier_routing.destinations:
            logger.debug(f"No routing for tier {tier_name}")
            return True

        return await self._deliver_tier(result, payload, tier_routing)

    async def _deliver_tier(
        self,
        result: InterestResultV2,
        payload: dict[str, Any],
        routing: TierRouting,
    ) -> bool:
        """
        Deliver to tier destinations.

        Handles fallback chains and require_all semantics.
        """
        from ..providers.registry import get_provider_registry

        registry = get_provider_registry()
        successes = []
        failures = []

        for dest_config in routing.destinations:
            provider_name = dest_config.get("provider", "log")
            provider = registry.get_delivery(provider_name)

            if not provider:
                logger.warning(f"Unknown delivery provider: {provider_name}")
                failures.append(provider_name)
                if not routing.fallback_on_failure:
                    break
                continue

            try:
                success = await provider.deliver(result, payload, dest_config)
                if success:
                    successes.append(provider_name)
                    if not routing.require_all:
                        # First success is enough
                        return True
                else:
                    failures.append(provider_name)
                    if not routing.fallback_on_failure:
                        break
            except Exception as e:
                logger.error(f"Delivery provider {provider_name} raised: {e}")
                failures.append(provider_name)
                if not routing.fallback_on_failure:
                    break

        if routing.require_all:
            # All must succeed
            return len(failures) == 0 and len(successes) > 0
        else:
            # At least one must succeed
            return len(successes) > 0

    def get_routing_for_tier(self, tier: str) -> TierRouting | None:
        """Get routing config for a tier."""
        return self._routing.get(tier)

    def add_routing(self, routing: TierRouting) -> None:
        """Add or update routing for a tier."""
        self._routing[routing.tier] = routing

    def list_configured_tiers(self) -> list[str]:
        """List tiers with routing configured."""
        return list(self._routing.keys())


def create_default_router() -> DeliveryRouter:
    """
    Create a router with default log-only delivery.

    Returns:
        DeliveryRouter with log delivery for all tiers
    """
    routing = {}
    for tier in ("priority", "notify", "digest", "log_only"):
        routing[tier] = TierRouting(
            tier=tier,
            destinations=[{"provider": "log"}],
        )
    return DeliveryRouter(routing)
