"""
SDE (Static Data Export) Module for ARIA.

Provides EVE Online static game data including:
- Item classification (categories, groups, types)
- Blueprint information (products, materials, times)
- NPC seeding data (where to buy BPOs)

This module extends the market database with authoritative game data
from the Fuzzwork SDE SQLite conversion.
"""

from .importer import SDEImporter, SDEImportResult, SDEStatus, seed_sde
from .schema import SDE_SCHEMA_VERSION

__all__ = [
    "SDEImporter",
    "SDEImportResult",
    "SDEStatus",
    "seed_sde",
    "SDE_SCHEMA_VERSION",
]
