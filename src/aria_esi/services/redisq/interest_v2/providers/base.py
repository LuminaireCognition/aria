"""
Provider Protocols for Interest Engine v2.

Defines the interfaces that all providers must implement.
Providers are lazy-loaded when referenced and validated on registration.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ...models import ProcessedKill
    from ..models import RuleMatch, SignalScore


# =============================================================================
# Base Provider Protocol
# =============================================================================


@runtime_checkable
class Provider(Protocol):
    """
    Base protocol for all providers.

    All providers must have a name and validate() method.
    """

    @property
    def name(self) -> str:
        """
        Unique provider name.

        Used for registration and configuration reference.
        """
        ...

    def validate(self, config: dict[str, Any]) -> list[str]:
        """
        Validate provider configuration.

        Args:
            config: Provider-specific configuration dictionary

        Returns:
            List of validation error messages (empty if valid)
        """
        ...


# =============================================================================
# Signal Provider
# =============================================================================


@runtime_checkable
class SignalProvider(Protocol):
    """
    Protocol for signal scoring providers.

    Signal providers compute interest scores for a specific category.
    They must declare prefetch capability and support two-stage scoring.
    """

    @property
    def name(self) -> str:
        """Unique signal name within its category."""
        ...

    @property
    def category(self) -> str:
        """
        Category this signal belongs to.

        Must be one of the 9 canonical categories:
        location, value, politics, activity, time, routes, assets, war, ship
        """
        ...

    @property
    def prefetch_capable(self) -> bool:
        """
        Whether this signal can score with RedisQ data only.

        Prefetch-capable signals can use:
        - system_id
        - zkb.totalValue
        - victim corp/alliance/ship_type_id
        - attacker count (but not details)
        - kill timestamp
        """
        ...

    def score(
        self,
        kill: ProcessedKill | None,
        system_id: int,
        config: dict[str, Any],
    ) -> SignalScore:
        """
        Compute interest score for this signal.

        Args:
            kill: ProcessedKill with full data, or None for prefetch
            system_id: Solar system ID
            config: Signal-specific configuration

        Returns:
            SignalScore with normalized score [0, 1] and metadata
        """
        ...

    def validate(self, config: dict[str, Any]) -> list[str]:
        """
        Validate signal configuration.

        Args:
            config: Signal-specific configuration

        Returns:
            List of validation error messages
        """
        ...


class BaseSignalProvider(ABC):
    """
    Base implementation for signal providers.

    Provides common functionality and enforces the protocol contract.
    Subclasses must implement score() and may override validate().
    """

    _name: str = "base"
    _category: str = "location"
    _prefetch_capable: bool = True

    @property
    def name(self) -> str:
        """Get signal name."""
        return self._name

    @property
    def category(self) -> str:
        """Get signal category."""
        return self._category

    @property
    def prefetch_capable(self) -> bool:
        """Get prefetch capability."""
        return self._prefetch_capable

    @abstractmethod
    def score(
        self,
        kill: ProcessedKill | None,
        system_id: int,
        config: dict[str, Any],
    ) -> SignalScore:
        """Compute interest score. Must be implemented by subclass."""
        ...

    def validate(self, config: dict[str, Any]) -> list[str]:
        """
        Validate configuration.

        Default implementation accepts any config.
        Override to add validation logic.
        """
        return []


# =============================================================================
# Rule Provider
# =============================================================================


@runtime_checkable
class RuleProvider(Protocol):
    """
    Protocol for rule evaluation providers.

    Rule providers evaluate hard rules (always_notify, always_ignore, gates).
    They must declare prefetch capability for optimization.
    """

    @property
    def name(self) -> str:
        """Unique rule identifier."""
        ...

    @property
    def prefetch_capable(self) -> bool:
        """Whether this rule can evaluate with RedisQ data only."""
        ...

    def evaluate(
        self,
        kill: ProcessedKill | None,
        system_id: int,
        config: dict[str, Any],
    ) -> RuleMatch:
        """
        Evaluate the rule against a kill.

        Args:
            kill: ProcessedKill with full data, or None for prefetch
            system_id: Solar system ID
            config: Rule-specific configuration

        Returns:
            RuleMatch with match result and reason
        """
        ...

    def validate(self, config: dict[str, Any]) -> list[str]:
        """Validate rule configuration."""
        ...


class BaseRuleProvider(ABC):
    """
    Base implementation for rule providers.
    """

    _name: str = "base"
    _prefetch_capable: bool = True

    @property
    def name(self) -> str:
        return self._name

    @property
    def prefetch_capable(self) -> bool:
        return self._prefetch_capable

    @abstractmethod
    def evaluate(
        self,
        kill: ProcessedKill | None,
        system_id: int,
        config: dict[str, Any],
    ) -> RuleMatch:
        """Evaluate the rule. Must be implemented by subclass."""
        ...

    def validate(self, config: dict[str, Any]) -> list[str]:
        """Default validation accepts any config."""
        return []


# =============================================================================
# Scaling Provider
# =============================================================================


@runtime_checkable
class ScalingProvider(Protocol):
    """
    Protocol for value scaling/normalization providers.

    Scaling providers convert raw values (ISK, distance, time) to
    normalized scores [0, 1] using various curves.
    """

    @property
    def name(self) -> str:
        """Scaling function name (sigmoid, linear, log, step, inverse)."""
        ...

    def scale(
        self,
        value: float,
        config: dict[str, Any],
    ) -> float:
        """
        Scale a raw value to [0, 1].

        Args:
            value: Raw value to scale
            config: Scaling parameters (min, max, pivot, etc.)

        Returns:
            Normalized score in [0, 1]
        """
        ...

    def validate(self, config: dict[str, Any]) -> list[str]:
        """Validate scaling configuration."""
        ...


class BaseScalingProvider(ABC):
    """
    Base implementation for scaling providers.
    """

    _name: str = "linear"

    @property
    def name(self) -> str:
        return self._name

    @abstractmethod
    def scale(self, value: float, config: dict[str, Any]) -> float:
        """Scale value. Must be implemented by subclass."""
        ...

    def validate(self, config: dict[str, Any]) -> list[str]:
        """Default validation accepts any config."""
        return []


# =============================================================================
# Delivery Provider
# =============================================================================


@runtime_checkable
class DeliveryProvider(Protocol):
    """
    Protocol for notification delivery providers.

    Delivery providers handle output formatting and transport
    (Discord, webhook, Slack, email, etc.).
    """

    @property
    def name(self) -> str:
        """Provider name (discord, webhook, slack, etc.)."""
        ...

    async def deliver(
        self,
        result: Any,  # InterestResultV2
        payload: dict[str, Any],
        config: dict[str, Any],
    ) -> bool:
        """
        Deliver a notification.

        Args:
            result: InterestResultV2 with scoring details
            payload: Formatted notification payload
            config: Provider-specific configuration (webhook URL, etc.)

        Returns:
            True if delivered successfully
        """
        ...

    def validate(self, config: dict[str, Any]) -> list[str]:
        """Validate delivery configuration."""
        ...

    def format(
        self,
        notification: dict[str, Any],
        config: dict[str, Any],
    ) -> Any:
        """
        Format notification for this provider.

        Args:
            notification: Raw notification data
            config: Formatting options

        Returns:
            Provider-specific formatted payload
        """
        ...


class BaseDeliveryProvider(ABC):
    """
    Base implementation for delivery providers.
    """

    _name: str = "log"

    @property
    def name(self) -> str:
        return self._name

    @abstractmethod
    async def deliver(
        self,
        result: Any,  # InterestResultV2
        payload: dict[str, Any],
        config: dict[str, Any],
    ) -> bool:
        """Deliver notification. Must be implemented by subclass."""
        ...

    def validate(self, config: dict[str, Any]) -> list[str]:
        """Default validation accepts any config."""
        return []

    def format(
        self,
        notification: dict[str, Any],
        config: dict[str, Any],
    ) -> Any:
        """Default formatting returns notification as-is."""
        return notification
