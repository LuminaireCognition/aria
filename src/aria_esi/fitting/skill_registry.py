"""
Skill Registry — SDE-backed name-to-ID resolution.

Replaces hardcoded skill ID lists with names resolved from the SDE
at startup. A typo in a skill name fails at boot instead of silently
mapping to the wrong type ID in production.
"""

from __future__ import annotations

import threading

from aria_esi.core.logging import get_logger

logger = get_logger(__name__)


class SkillRegistry:
    """
    Registry of skill name-to-ID mappings resolved from the SDE.

    Usage:
        registry = get_skill_registry()
        drone_interfacing_id = registry.id("Drone Interfacing")  # 3442
        drone_ids = registry.ids(DRONE_SKILL_NAMES)  # [3436, 24241, ...]
    """

    def __init__(self, resolved: dict[str, int]):
        self._by_name = resolved
        self._by_id = {v: k for k, v in resolved.items()}

    def id(self, name: str) -> int:
        """Get type ID for a skill name. Raises KeyError if not registered."""
        return self._by_name[name]

    def ids(self, names: list[str]) -> list[int]:
        """Get type IDs for a list of skill names, in input order.

        All names must be registered (present in ALL_SKILL_NAMES).
        Raises KeyError on the first name missing from the registry,
        consistent with ``id()`` behavior.
        """
        return [self._by_name[n] for n in names]

    def name(self, type_id: int) -> str | None:
        """Reverse lookup: type ID to name."""
        return self._by_id.get(type_id)

    def contains(self, name: str) -> bool:
        return name in self._by_name


# Skill names that the fitting module needs — the ONLY source of truth
# is the name string. The integer ID comes from the SDE at startup.

DRONE_SKILL_NAMES = [
    "Drones",
    "Light Drone Operation",
    "Medium Drone Operation",
    "Heavy Drone Operation",
    "Drone Avionics",
    "Drone Interfacing",
    "Drone Navigation",
    "Drone Sharpshooting",
    "Drone Durability",
]

FITTING_SKILL_NAMES = [
    "Weapon Upgrades",
    "Advanced Weapon Upgrades",
    "Capacitor Systems Operation",
    "Capacitor Management",
    "Capacitor Emission Systems",
]

TANK_SKILL_NAMES = [
    "Mechanics",
    "Hull Upgrades",
    "Repair Systems",
    "Shield Operation",
    "Shield Management",
    "Shield Compensation",
    "Shield Upgrades",
    "Tactical Shield Manipulation",
    "Armor Rigging",
    "Shield Rigging",
]

NAVIGATION_SKILL_NAMES = [
    "Navigation",
    "Afterburner",
    "Warp Drive Operation",
    "Evasive Maneuvering",
    "Fuel Conservation",
    "Acceleration Control",
]

BONUS_DRONE_SKILL_NAMES = [
    "Drone Interfacing",
    "Drone Sharpshooting",
    "Drone Navigation",
    "Drone Durability",
]

BONUS_CORE_SKILL_NAMES = [
    # Fitting skills
    "Weapon Upgrades",
    "Advanced Weapon Upgrades",
    # Capacitor skills
    "Capacitor Systems Operation",
    "Capacitor Management",
    # Tank skills
    "Mechanics",
    "Hull Upgrades",
    "Shield Operation",
    "Shield Management",
    # Navigation skills
    "Navigation",
    "Evasive Maneuvering",
    "Acceleration Control",
    # Engineering skills
    "Power Grid Management",
]

# All skill names the registry must resolve at startup
ALL_SKILL_NAMES = sorted(
    set(
        DRONE_SKILL_NAMES
        + FITTING_SKILL_NAMES
        + TANK_SKILL_NAMES
        + NAVIGATION_SKILL_NAMES
        + BONUS_DRONE_SKILL_NAMES
        + BONUS_CORE_SKILL_NAMES
    )
)


_skill_registry: SkillRegistry | None = None
_registry_lock = threading.Lock()
_registry_attempted = False


def get_skill_registry() -> SkillRegistry | None:
    """
    Get or create the skill registry (thread-safe, singleton).

    On first call, resolves all skill names from the SDE.
    Returns None if SDE is unavailable (logs warning).
    After a failed attempt, returns None immediately on subsequent calls
    to avoid retry storms — SDE unavailability requires process restart.

    The lazy import of ``get_sde_query_service`` inside the function body
    is deliberate: it prevents circular imports between ``fitting/`` and
    ``mcp/sde/``. Do not move it to module level.
    """
    global _skill_registry, _registry_attempted

    if _skill_registry is not None:
        return _skill_registry

    with _registry_lock:
        # Double-checked locking: another thread may have initialized
        if _skill_registry is not None:
            return _skill_registry
        if _registry_attempted:
            return None  # already failed, don't retry until restart

        try:
            from aria_esi.mcp.sde.queries import (
                SDEResolutionError,
                get_sde_query_service,
            )

            sde = get_sde_query_service()
            resolved = sde.resolve_skill_ids(ALL_SKILL_NAMES)
            _skill_registry = SkillRegistry(resolved)
            logger.info("Skill registry initialized: %d skills resolved", len(resolved))
            return _skill_registry
        except SDEResolutionError as e:
            _registry_attempted = True
            logger.error(
                "Skill registry failed — %d names not found in SDE: %s",
                len(e.missing_names),
                e.missing_names,
            )
            return None
        except (ImportError, RuntimeError) as e:
            _registry_attempted = True
            logger.warning("Skill registry unavailable (SDE infrastructure): %s", e)
            return None


def reset_skill_registry() -> None:
    """Reset registry state for testing. Not for production use."""
    global _skill_registry, _registry_attempted
    with _registry_lock:
        _skill_registry = None
        _registry_attempted = False
