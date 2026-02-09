"""
Signal Providers for Interest Engine v2.

Signals compute interest scores for specific categories:
- location: GeographicSignal, SecuritySignal
- value: ValueSignal
- politics: PoliticsSignal
- activity: ActivitySignal
- time: TimeSignal
- routes: RouteSignal
- assets: AssetSignal
- war: WarSignal
- ship: ShipSignal
"""

from .activity import ActivitySignal
from .assets import AssetSignal
from .location import GeographicSignal, SecuritySignal
from .politics import PoliticsSignal
from .routes import RouteSignal
from .ship import ShipSignal
from .time import TimeSignal
from .value import ValueSignal
from .war import WarSignal

__all__ = [
    "ActivitySignal",
    "AssetSignal",
    "GeographicSignal",
    "PoliticsSignal",
    "RouteSignal",
    "SecuritySignal",
    "ShipSignal",
    "TimeSignal",
    "ValueSignal",
    "WarSignal",
]


def register_builtin_signals() -> None:
    """Register all built-in signal providers with the global registry."""
    from ..providers.registry import get_provider_registry

    registry = get_provider_registry()

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
