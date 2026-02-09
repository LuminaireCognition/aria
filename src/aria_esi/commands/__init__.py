"""
ARIA ESI Commands

Command implementations for ESI API operations.
Each module handles a logical group of related commands.
"""

# Phase 2: Public commands (no authentication required)
# Phase 3: Personal commands (authentication required)
# Phase 4: Corporation commands
# Phase 5: Loyalty Points
# Phase 6: Clones
# Phase 7: Killmails
# Phase 8: Contracts
# Phase 9: Research Agents
# Phase 10: Mining Ledger
# Phase 11: Market Orders
# Phase 12: Saved Fittings
# Phase 13: Mail
# Phase 14: Universe Cache
# Phase 15: Killmail Analysis (zKillboard integration)
from . import (
    agents_research,
    assets,
    character,
    clones,
    contracts,
    corporation,
    fittings,
    industry,
    killmail,
    killmails,
    loyalty,
    mail,
    market,
    mining,
    navigation,
    orders,
    pilot,
    skills,
    universe,
    wallet,
)

__all__ = [
    # Phase 2
    "navigation",
    "market",
    "pilot",
    # Phase 3
    "character",
    "wallet",
    "skills",
    "industry",
    "assets",
    # Phase 4
    "corporation",
    # Phase 5
    "loyalty",
    # Phase 6
    "clones",
    # Phase 7
    "killmails",
    # Phase 8
    "contracts",
    # Phase 9
    "agents_research",
    # Phase 10
    "mining",
    # Phase 11
    "orders",
    # Phase 12
    "fittings",
    # Phase 13
    "mail",
    # Phase 14
    "universe",
    # Phase 15
    "killmail",
]
