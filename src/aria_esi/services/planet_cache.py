"""
ARIA Planet Cache Service.

Caches ESI planet type data for PI location planning.
Maps systems to their planets and planet types for resource availability lookup.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Planet type ID to name mapping from SDE
PLANET_TYPE_IDS = {
    11: "Temperate",
    12: "Ice",
    13: "Gas",
    2014: "Oceanic",
    2015: "Lava",
    2016: "Barren",
    2017: "Storm",
    2063: "Plasma",
}

# Reverse mapping
PLANET_TYPE_NAMES = {v: k for k, v in PLANET_TYPE_IDS.items()}

# Cache file location
DEFAULT_CACHE_PATH = Path("userdata/cache/planet_types.json")


class PlanetCacheService:
    """
    Service for caching and querying planet type data.

    Planet data is fetched from ESI and cached locally to avoid
    repeated API calls for static data (planet types don't change).
    """

    def __init__(self, cache_path: Optional[Path] = None):
        """
        Initialize planet cache service.

        Args:
            cache_path: Path to cache file (default: userdata/cache/planet_types.json)
        """
        self.cache_path = cache_path or DEFAULT_CACHE_PATH
        self._cache: Optional[dict[str, Any]] = None

    def _ensure_cache_dir(self) -> None:
        """Ensure cache directory exists."""
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

    def load_cache(self) -> dict[str, Any]:
        """
        Load cache from disk.

        Returns:
            Cache data dict with structure:
            {
                "systems": {
                    "system_name": {
                        "system_id": int,
                        "planets": [
                            {"planet_id": int, "type_id": int, "type_name": str}
                        ]
                    }
                },
                "metadata": {
                    "last_updated": str,
                    "systems_count": int,
                    "planets_count": int
                }
            }
        """
        if self._cache is not None:
            return self._cache

        if not self.cache_path.exists():
            self._cache = {"systems": {}, "metadata": {}}
            return self._cache

        try:
            with open(self.cache_path) as f:
                self._cache = json.load(f)
            return self._cache
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Could not load planet cache: {e}")
            self._cache = {"systems": {}, "metadata": {}}
            return self._cache

    def save_cache(self) -> None:
        """Save cache to disk."""
        if self._cache is None:
            return

        self._ensure_cache_dir()

        # Update metadata
        systems = self._cache.get("systems", {})
        total_planets = sum(
            len(s.get("planets", [])) for s in systems.values()
        )

        self._cache["metadata"] = {
            "last_updated": _get_timestamp(),
            "systems_count": len(systems),
            "planets_count": total_planets,
        }

        with open(self.cache_path, "w") as f:
            json.dump(self._cache, f, indent=2)

    def get_system_planets(self, system_name: str) -> Optional[list[dict[str, Any]]]:
        """
        Get planets for a system from cache.

        Args:
            system_name: System name (case-insensitive)

        Returns:
            List of planet dicts or None if not cached
        """
        cache = self.load_cache()
        systems = cache.get("systems", {})

        # Case-insensitive lookup
        for name, data in systems.items():
            if name.lower() == system_name.lower():
                return data.get("planets", [])

        return None

    def get_planet_types_in_system(self, system_name: str) -> Optional[set[str]]:
        """
        Get set of planet types in a system.

        Args:
            system_name: System name (case-insensitive)

        Returns:
            Set of planet type names or None if not cached
        """
        planets = self.get_system_planets(system_name)
        if planets is None:
            return None

        return {p["type_name"] for p in planets if "type_name" in p}

    def is_system_cached(self, system_name: str) -> bool:
        """Check if a system is in the cache."""
        cache = self.load_cache()
        systems = cache.get("systems", {})

        for name in systems:
            if name.lower() == system_name.lower():
                return True
        return False

    def add_system(
        self,
        system_name: str,
        system_id: int,
        planets: list[dict[str, Any]],
    ) -> None:
        """
        Add or update a system in the cache.

        Args:
            system_name: System name
            system_id: System ID
            planets: List of planet dicts with planet_id, type_id, type_name
        """
        cache = self.load_cache()

        if "systems" not in cache:
            cache["systems"] = {}

        cache["systems"][system_name] = {
            "system_id": system_id,
            "planets": planets,
        }

        self._cache = cache

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        cache = self.load_cache()
        return cache.get("metadata", {})

    def find_systems_with_planet_types(
        self,
        required_types: set[str],
    ) -> list[dict[str, Any]]:
        """
        Find systems that have all required planet types.

        Args:
            required_types: Set of planet type names (e.g., {"Barren", "Gas"})

        Returns:
            List of systems with their planet data
        """
        cache = self.load_cache()
        systems = cache.get("systems", {})
        matches = []

        required_lower = {t.lower() for t in required_types}

        for name, data in systems.items():
            planets = data.get("planets", [])
            types_in_system = {
                p.get("type_name", "").lower()
                for p in planets
                if p.get("type_name")
            }

            if required_lower.issubset(types_in_system):
                matches.append({
                    "system_name": name,
                    "system_id": data.get("system_id"),
                    "planet_types": list(types_in_system),
                    "planet_count": len(planets),
                })

        return matches

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._cache = {"systems": {}, "metadata": {}}
        if self.cache_path.exists():
            self.cache_path.unlink()


def _get_timestamp() -> str:
    """Get current UTC timestamp."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def get_planet_cache_service(cache_path: Optional[Path] = None) -> PlanetCacheService:
    """
    Factory function to create planet cache service.

    Args:
        cache_path: Optional custom cache path

    Returns:
        PlanetCacheService instance
    """
    return PlanetCacheService(cache_path)


async def fetch_system_planets(
    system_id: int,
    esi_client: Any,
) -> list[dict[str, Any]]:
    """
    Fetch planet data for a system from ESI.

    Args:
        system_id: System ID to fetch
        esi_client: ESI client with get method

    Returns:
        List of planet dicts with planet_id, type_id, type_name
    """
    # Fetch system info
    system_info = esi_client.get(f"/universe/systems/{system_id}/")
    if not system_info:
        return []

    planet_ids = system_info.get("planets", [])
    if not planet_ids:
        return []

    # Fetch each planet's type
    planets = []
    for planet_entry in planet_ids:
        planet_id = planet_entry.get("planet_id") if isinstance(planet_entry, dict) else planet_entry

        if not planet_id:
            continue

        planet_info = esi_client.get(f"/universe/planets/{planet_id}/")
        if not planet_info:
            continue

        type_id = planet_info.get("type_id")
        type_name = PLANET_TYPE_IDS.get(type_id, f"Unknown-{type_id}")

        planets.append({
            "planet_id": planet_id,
            "type_id": type_id,
            "type_name": type_name,
        })

    return planets


def fetch_system_planets_sync(
    system_id: int,
    esi_client: Any,
) -> list[dict[str, Any]]:
    """
    Synchronous version of fetch_system_planets.

    Args:
        system_id: System ID to fetch
        esi_client: ESI client with get method

    Returns:
        List of planet dicts with planet_id, type_id, type_name
    """
    # Fetch system info
    system_info = esi_client.get(f"/universe/systems/{system_id}/")
    if not system_info:
        return []

    planet_ids = system_info.get("planets", [])
    if not planet_ids:
        return []

    # Fetch each planet's type
    planets = []
    for planet_entry in planet_ids:
        planet_id = planet_entry.get("planet_id") if isinstance(planet_entry, dict) else planet_entry

        if not planet_id:
            continue

        planet_info = esi_client.get(f"/universe/planets/{planet_id}/")
        if not planet_info:
            continue

        type_id = planet_info.get("type_id")
        type_name = PLANET_TYPE_IDS.get(type_id, f"Unknown-{type_id}")

        planets.append({
            "planet_id": planet_id,
            "type_id": type_id,
            "type_name": type_name,
        })

    return planets


def get_resources_for_planet_type(planet_type: str) -> list[str]:
    """
    Get P0 resources available on a planet type.

    Args:
        planet_type: Planet type name (e.g., "Barren", "Gas")

    Returns:
        List of P0 resource names
    """
    # Load from reference data
    ref_path = Path("reference/mechanics/planetary-interaction.json")
    if not ref_path.exists():
        return []

    try:
        with open(ref_path) as f:
            pi_data = json.load(f)

        planet_resources = pi_data.get("planet_resources", {})
        return planet_resources.get(planet_type, [])
    except (json.JSONDecodeError, IOError):
        return []


def find_planets_for_resource(p0_resource: str) -> list[str]:
    """
    Find planet types that have a specific P0 resource.

    Args:
        p0_resource: P0 resource name (e.g., "Aqueous Liquids")

    Returns:
        List of planet type names
    """
    ref_path = Path("reference/mechanics/planetary-interaction.json")
    if not ref_path.exists():
        return []

    try:
        with open(ref_path) as f:
            pi_data = json.load(f)

        planet_resources = pi_data.get("planet_resources", {})
        matching = []

        for planet_type, resources in planet_resources.items():
            if p0_resource in resources:
                matching.append(planet_type)

        return matching
    except (json.JSONDecodeError, IOError):
        return []


def find_planets_for_product(product_name: str) -> dict[str, Any]:
    """
    Find planet types needed to produce a PI product.

    Args:
        product_name: PI product name (P1, P2, P3, or P4)

    Returns:
        Dict with:
        - product_tier: P1, P2, P3, or P4
        - required_p0: List of P0 resources needed
        - planet_types: Dict mapping each P0 to planet types
        - single_planet_options: Planet types that can do it all (if any)
    """
    ref_path = Path("reference/mechanics/planetary-interaction.json")
    if not ref_path.exists():
        return {"error": "Reference data not found"}

    try:
        with open(ref_path) as f:
            pi_data = json.load(f)

        # Find which tier the product is
        product_tier = None
        schematic = None

        for tier_key, tier_name in [
            ("p2_schematics", "P2"),
            ("p3_schematics", "P3"),
            ("p4_schematics", "P4"),
        ]:
            schematics = pi_data.get(tier_key, {})
            if product_name in schematics:
                product_tier = tier_name
                schematic = schematics[product_name]
                break

        if not product_tier:
            # Check if it's a P1 product
            p0_to_p1 = pi_data.get("p0_to_p1", {})
            for p0, p1 in p0_to_p1.items():
                if p1 == product_name:
                    return {
                        "product_tier": "P1",
                        "required_p0": [p0],
                        "planet_types": {p0: find_planets_for_resource(p0)},
                        "single_planet_options": find_planets_for_resource(p0),
                    }

            return {"error": f"Product '{product_name}' not found"}

        # Trace back to P0 resources
        required_p0 = _trace_to_p0(product_name, pi_data)
        planet_types = {p0: find_planets_for_resource(p0) for p0 in required_p0}

        # Find single-planet options (planets that have all required P0)
        single_planet = _find_single_planet_options(required_p0, pi_data)

        return {
            "product_tier": product_tier,
            "required_p0": required_p0,
            "planet_types": planet_types,
            "single_planet_options": single_planet,
        }

    except (json.JSONDecodeError, IOError):
        return {"error": "Could not load reference data"}


def _trace_to_p0(product_name: str, pi_data: dict) -> list[str]:
    """
    Trace a PI product back to its P0 inputs.

    Recursively traces through P4→P3→P2→P1→P0 chain.
    """
    p0_inputs = []

    # Get P0 to P1 mapping (inverted)
    p1_to_p0 = {v: k for k, v in pi_data.get("p0_to_p1", {}).items()}

    def trace(name: str, visited: set) -> None:
        if name in visited:
            return
        visited.add(name)

        # Check if this is a P1 (has P0 input)
        if name in p1_to_p0:
            p0 = p1_to_p0[name]
            if p0 not in p0_inputs:
                p0_inputs.append(p0)
            return

        # Check P2 schematics
        if name in pi_data.get("p2_schematics", {}):
            for input_name in pi_data["p2_schematics"][name].get("inputs", []):
                trace(input_name, visited)
            return

        # Check P3 schematics
        if name in pi_data.get("p3_schematics", {}):
            for input_name in pi_data["p3_schematics"][name].get("inputs", []):
                trace(input_name, visited)
            return

        # Check P4 schematics
        if name in pi_data.get("p4_schematics", {}):
            schematic = pi_data["p4_schematics"][name]
            for input_name in schematic.get("inputs", []):
                trace(input_name, visited)
            # P4 may also have P1 input
            if p1_input := schematic.get("p1_input"):
                trace(p1_input, visited)
            return

    trace(product_name, set())
    return p0_inputs


def _find_single_planet_options(required_p0: list[str], pi_data: dict) -> list[str]:
    """Find planet types that have all required P0 resources."""
    planet_resources = pi_data.get("planet_resources", {})
    options = []

    for planet_type, resources in planet_resources.items():
        if all(p0 in resources for p0 in required_p0):
            options.append(planet_type)

    return options
