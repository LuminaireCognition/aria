"""
Interest Engine v2 CLI Tools.

Provides commands for:
- explain: Signal breakdown for a kill
- simulate: Historical replay with v2 scoring
- migrate: Convert v1 profiles to v2
- tune: Interactive weight tuning
"""

from .explain import explain_kill, format_explanation
from .migrate import MigrationStrategy, migrate_profile
from .simulate import simulate_profile

__all__ = [
    "MigrationStrategy",
    "explain_kill",
    "format_explanation",
    "migrate_profile",
    "simulate_profile",
]
