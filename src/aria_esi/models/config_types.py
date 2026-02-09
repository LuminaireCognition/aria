"""
TypedDict definitions for common configuration and API response types.

These types enable stricter mypy checking by replacing dict[str, Any]
with typed dictionaries that have known keys.
"""

from __future__ import annotations

from typing import TypedDict

from typing_extensions import NotRequired

# =============================================================================
# ESI Universe Types
# =============================================================================


class UniverseTypeInfo(TypedDict):
    """ESI /universe/types/{type_id}/ response."""

    type_id: int
    name: str
    description: NotRequired[str]
    group_id: int
    market_group_id: NotRequired[int]
    mass: NotRequired[float]
    volume: NotRequired[float]
    capacity: NotRequired[float]
    portion_size: NotRequired[int]
    published: bool


class UniverseSystemInfo(TypedDict):
    """ESI /universe/systems/{system_id}/ response."""

    system_id: int
    name: str
    security_status: float
    constellation_id: int
    star_id: NotRequired[int]
    stargates: NotRequired[list[int]]
    stations: NotRequired[list[int]]


class UniverseCharacterInfo(TypedDict):
    """ESI /characters/{character_id}/ response (public subset)."""

    character_id: int
    name: str
    corporation_id: int
    alliance_id: NotRequired[int]
    faction_id: NotRequired[int]


class UniverseCorporationInfo(TypedDict):
    """ESI /corporations/{corporation_id}/ response (public subset)."""

    corporation_id: int
    name: str
    ticker: str
    alliance_id: NotRequired[int]


# =============================================================================
# Data Manifest Types
# =============================================================================


class DataSourceManifest(TypedDict):
    """Data source manifest from reference/data-sources.json."""

    sde: DataSourceEntry
    eos: EosSourceEntry


class DataSourceEntry(TypedDict):
    """SDE data source entry."""

    url: str
    checksum: NotRequired[str]
    version: NotRequired[str]


class EosSourceEntry(TypedDict):
    """EOS data source entry."""

    repository: str
    commit: str


# =============================================================================
# Persona Context Types
# =============================================================================


class PersonaContext(TypedDict):
    """Persona context from pilot profile.md."""

    branch: str  # "empire" or "pirate"
    persona: str  # persona directory name
    fallback: str | None  # for variants
    rp_level: str  # "off", "on", "full"
    files: list[str]  # files to load
    skill_overlay_path: str  # path to skill overlays
    overlay_fallback_path: str | None  # fallback for overlays


# =============================================================================
# Cache Types
# =============================================================================


class CacheEntryInfo(TypedDict):
    """Info about a cached entry."""

    key: str
    size: int
    expires: float
    created: float


class CacheStatus(TypedDict):
    """Cache status summary."""

    entry_count: int
    total_size: int
    oldest_entry: float | None
    newest_entry: float | None


# =============================================================================
# Killmail Types
# =============================================================================


class TypeCacheEntry(TypedDict):
    """Cached type name info."""

    name: str
    group_id: NotRequired[int]


class SystemCacheEntry(TypedDict):
    """Cached system info."""

    name: str
    security_status: float


class CharacterCacheEntry(TypedDict):
    """Cached character info."""

    name: str
    corporation_id: NotRequired[int]
