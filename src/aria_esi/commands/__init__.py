"""
ARIA ESI Commands

Command implementations for ESI API operations.
Each module handles a logical group of related commands.
"""

import importlib as _importlib

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


def __getattr__(name: str):
    """Lazy import command modules on first access."""
    if name in __all__:
        return _importlib.import_module(f".{name}", __name__)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
