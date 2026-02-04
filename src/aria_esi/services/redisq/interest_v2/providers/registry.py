"""
Provider Registry for Interest Engine v2.

Central registry for lazy-loading and managing providers.
Providers are registered by type and name, loaded on demand.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from .base import (
        DeliveryProvider,
        Provider,
        RuleProvider,
        ScalingProvider,
        SignalProvider,
    )

logger = logging.getLogger(__name__)

P = TypeVar("P", bound="Provider")


class ProviderRegistry:
    """
    Central registry for all provider types.

    Providers are registered as factories (callables) and instantiated
    on first access. This enables lazy loading and reduces startup cost.

    Usage:
        registry = ProviderRegistry()

        # Register a signal provider factory
        registry.register_signal("geographic", lambda: GeographicSignal())

        # Get provider instance (lazy-loaded)
        provider = registry.get_signal("geographic")
    """

    def __init__(self) -> None:
        """Initialize empty registries."""
        # Signal providers by category -> name -> factory
        self._signals: dict[str, dict[str, Callable[[], SignalProvider]]] = {}
        self._signal_instances: dict[str, dict[str, SignalProvider]] = {}

        # Rule providers by name -> factory
        self._rules: dict[str, Callable[[], RuleProvider]] = {}
        self._rule_instances: dict[str, RuleProvider] = {}

        # Scaling providers by name -> factory
        self._scaling: dict[str, Callable[[], ScalingProvider]] = {}
        self._scaling_instances: dict[str, ScalingProvider] = {}

        # Delivery providers by name -> factory
        self._delivery: dict[str, Callable[[], DeliveryProvider]] = {}
        self._delivery_instances: dict[str, DeliveryProvider] = {}

    # =========================================================================
    # Signal Providers
    # =========================================================================

    def register_signal(
        self,
        category: str,
        name: str,
        factory: Callable[[], SignalProvider],
    ) -> None:
        """
        Register a signal provider factory.

        Args:
            category: Signal category (location, value, etc.)
            name: Signal name within category
            factory: Callable that returns SignalProvider instance
        """
        if category not in self._signals:
            self._signals[category] = {}
            self._signal_instances[category] = {}
        self._signals[category][name] = factory
        logger.debug(f"Registered signal provider: {category}.{name}")

    def get_signal(self, category: str, name: str) -> SignalProvider | None:
        """
        Get a signal provider instance (lazy-loaded).

        Args:
            category: Signal category
            name: Signal name

        Returns:
            SignalProvider instance or None if not registered
        """
        # Check cache first
        if category in self._signal_instances:
            if name in self._signal_instances[category]:
                return self._signal_instances[category][name]

        # Look up factory
        if category not in self._signals:
            return None
        if name not in self._signals[category]:
            return None

        # Instantiate and cache
        factory = self._signals[category][name]
        try:
            instance = factory()
            if category not in self._signal_instances:
                self._signal_instances[category] = {}
            self._signal_instances[category][name] = instance
            logger.debug(f"Instantiated signal provider: {category}.{name}")
            return instance
        except Exception as e:
            logger.error(f"Failed to instantiate signal {category}.{name}: {e}")
            return None

    def get_signals_for_category(self, category: str) -> dict[str, SignalProvider]:
        """
        Get all signal providers for a category.

        Args:
            category: Signal category

        Returns:
            Dict of name -> SignalProvider
        """
        if category not in self._signals:
            return {}

        result = {}
        for name in self._signals[category]:
            provider = self.get_signal(category, name)
            if provider:
                result[name] = provider
        return result

    def list_signals(self) -> dict[str, list[str]]:
        """
        List all registered signals by category.

        Returns:
            Dict of category -> list of signal names
        """
        return {cat: list(signals.keys()) for cat, signals in self._signals.items()}

    # =========================================================================
    # Rule Providers
    # =========================================================================

    def register_rule(
        self,
        name: str,
        factory: Callable[[], RuleProvider],
    ) -> None:
        """Register a rule provider factory."""
        self._rules[name] = factory
        logger.debug(f"Registered rule provider: {name}")

    def get_rule(self, name: str) -> RuleProvider | None:
        """Get a rule provider instance (lazy-loaded)."""
        if name in self._rule_instances:
            return self._rule_instances[name]

        if name not in self._rules:
            return None

        try:
            instance = self._rules[name]()
            self._rule_instances[name] = instance
            logger.debug(f"Instantiated rule provider: {name}")
            return instance
        except Exception as e:
            logger.error(f"Failed to instantiate rule {name}: {e}")
            return None

    def list_rules(self) -> list[str]:
        """List all registered rule names."""
        return list(self._rules.keys())

    # =========================================================================
    # Scaling Providers
    # =========================================================================

    def register_scaling(
        self,
        name: str,
        factory: Callable[[], ScalingProvider],
    ) -> None:
        """Register a scaling provider factory."""
        self._scaling[name] = factory
        logger.debug(f"Registered scaling provider: {name}")

    def get_scaling(self, name: str) -> ScalingProvider | None:
        """Get a scaling provider instance (lazy-loaded)."""
        if name in self._scaling_instances:
            return self._scaling_instances[name]

        if name not in self._scaling:
            return None

        try:
            instance = self._scaling[name]()
            self._scaling_instances[name] = instance
            logger.debug(f"Instantiated scaling provider: {name}")
            return instance
        except Exception as e:
            logger.error(f"Failed to instantiate scaling {name}: {e}")
            return None

    def list_scaling(self) -> list[str]:
        """List all registered scaling function names."""
        return list(self._scaling.keys())

    # =========================================================================
    # Delivery Providers
    # =========================================================================

    def register_delivery(
        self,
        name: str,
        factory: Callable[[], DeliveryProvider],
    ) -> None:
        """Register a delivery provider factory."""
        self._delivery[name] = factory
        logger.debug(f"Registered delivery provider: {name}")

    def get_delivery(self, name: str) -> DeliveryProvider | None:
        """Get a delivery provider instance (lazy-loaded)."""
        if name in self._delivery_instances:
            return self._delivery_instances[name]

        if name not in self._delivery:
            return None

        try:
            instance = self._delivery[name]()
            self._delivery_instances[name] = instance
            logger.debug(f"Instantiated delivery provider: {name}")
            return instance
        except Exception as e:
            logger.error(f"Failed to instantiate delivery {name}: {e}")
            return None

    def list_delivery(self) -> list[str]:
        """List all registered delivery provider names."""
        return list(self._delivery.keys())

    # =========================================================================
    # Validation
    # =========================================================================

    def validate_signal_config(
        self,
        category: str,
        name: str,
        config: dict[str, Any],
    ) -> list[str]:
        """
        Validate signal configuration.

        Args:
            category: Signal category
            name: Signal name
            config: Signal configuration

        Returns:
            List of validation errors
        """
        provider = self.get_signal(category, name)
        if not provider:
            return [f"Unknown signal: {category}.{name}"]
        return provider.validate(config)

    def validate_rule_config(
        self,
        name: str,
        config: dict[str, Any],
    ) -> list[str]:
        """Validate rule configuration."""
        provider = self.get_rule(name)
        if not provider:
            return [f"Unknown rule: {name}"]
        return provider.validate(config)

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get registry statistics."""
        return {
            "signals": {
                "registered": sum(len(s) for s in self._signals.values()),
                "instantiated": sum(len(s) for s in self._signal_instances.values()),
                "categories": list(self._signals.keys()),
            },
            "rules": {
                "registered": len(self._rules),
                "instantiated": len(self._rule_instances),
            },
            "scaling": {
                "registered": len(self._scaling),
                "instantiated": len(self._scaling_instances),
            },
            "delivery": {
                "registered": len(self._delivery),
                "instantiated": len(self._delivery_instances),
            },
        }


# =============================================================================
# Global Registry
# =============================================================================

_global_registry: ProviderRegistry | None = None


def get_provider_registry() -> ProviderRegistry:
    """
    Get the global provider registry.

    Returns a lazily-initialized registry with built-in providers registered.
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = ProviderRegistry()
        _register_builtin_providers(_global_registry)
    return _global_registry


def _register_builtin_providers(registry: ProviderRegistry) -> None:
    """
    Register all built-in providers.

    Called once when the global registry is created.
    """
    # Register built-in scaling functions
    _register_builtin_scaling(registry)

    # Register built-in rules
    _register_builtin_rules(registry)

    # Register built-in signals
    _register_builtin_signals(registry)

    # Register built-in delivery providers
    _register_builtin_delivery(registry)


def _register_builtin_scaling(registry: ProviderRegistry) -> None:
    """Register built-in scaling functions."""
    # Import here to avoid circular imports
    from ..scaling.builtin import (
        InverseScaling,
        LinearScaling,
        LogScaling,
        SigmoidScaling,
        StepScaling,
    )

    registry.register_scaling("sigmoid", lambda: SigmoidScaling())
    registry.register_scaling("linear", lambda: LinearScaling())
    registry.register_scaling("log", lambda: LogScaling())
    registry.register_scaling("logarithmic", lambda: LogScaling())  # Alias
    registry.register_scaling("step", lambda: StepScaling())
    registry.register_scaling("inverse", lambda: InverseScaling())


def _register_builtin_rules(registry: ProviderRegistry) -> None:
    """Register built-in rules."""
    # Import here to avoid circular imports
    from ..rules.builtin import (
        AllianceMemberVictimRule,
        CorpMemberVictimRule,
        GatecampDetectedRule,
        HighValueRule,
        NpcOnlyRule,
        PodOnlyRule,
        StructureKillRule,
        WarTargetActivityRule,
        WatchlistMatchRule,
    )

    registry.register_rule("npc_only", lambda: NpcOnlyRule())
    registry.register_rule("pod_only", lambda: PodOnlyRule())
    registry.register_rule("corp_member_victim", lambda: CorpMemberVictimRule())
    registry.register_rule("alliance_member_victim", lambda: AllianceMemberVictimRule())
    registry.register_rule("war_target_activity", lambda: WarTargetActivityRule())
    registry.register_rule("watchlist_match", lambda: WatchlistMatchRule())
    registry.register_rule("high_value", lambda: HighValueRule())
    registry.register_rule("gatecamp_detected", lambda: GatecampDetectedRule())
    registry.register_rule("structure_kill", lambda: StructureKillRule())


def _register_builtin_signals(registry: ProviderRegistry) -> None:
    """Register built-in signal providers."""
    from ..signals import (
        ActivitySignal,
        AssetSignal,
        GeographicSignal,
        PoliticsSignal,
        RouteSignal,
        SecuritySignal,
        ShipSignal,
        TimeSignal,
        ValueSignal,
        WarSignal,
    )

    # Location category
    registry.register_signal("location", "geographic", lambda: GeographicSignal())
    registry.register_signal("location", "security", lambda: SecuritySignal())

    # Value category
    registry.register_signal("value", "value", lambda: ValueSignal())

    # Politics category
    registry.register_signal("politics", "politics", lambda: PoliticsSignal())

    # Activity category
    registry.register_signal("activity", "activity", lambda: ActivitySignal())

    # Time category
    registry.register_signal("time", "time", lambda: TimeSignal())

    # Routes category
    registry.register_signal("routes", "routes", lambda: RouteSignal())

    # Assets category
    registry.register_signal("assets", "assets", lambda: AssetSignal())

    # War category
    registry.register_signal("war", "war", lambda: WarSignal())

    # Ship category
    registry.register_signal("ship", "ship", lambda: ShipSignal())


def _register_builtin_delivery(registry: ProviderRegistry) -> None:
    """Register built-in delivery providers."""
    from ..delivery.builtin import DiscordDelivery, LogDelivery, WebhookDelivery

    registry.register_delivery("discord", lambda: DiscordDelivery())
    registry.register_delivery("webhook", lambda: WebhookDelivery())
    registry.register_delivery("log", lambda: LogDelivery())


def reset_registry() -> None:
    """
    Reset the global registry.

    Useful for testing to ensure clean state.
    """
    global _global_registry
    _global_registry = None
