"""
Provider Framework for Interest Engine v2.

Providers are pluggable modules that implement specific functionality:
- SignalProvider: Score computation for a signal category
- RuleProvider: Custom rule evaluation
- ScalingProvider: Value normalization curves
- DeliveryProvider: Notification output handling
"""

from .base import (
    DeliveryProvider,
    Provider,
    RuleProvider,
    ScalingProvider,
    SignalProvider,
)
from .registry import ProviderRegistry, get_provider_registry

__all__ = [
    "DeliveryProvider",
    "Provider",
    "ProviderRegistry",
    "RuleProvider",
    "ScalingProvider",
    "SignalProvider",
    "get_provider_registry",
]
