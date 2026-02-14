"""
ARIA Freshness-Gated Auto-Sync Library

Checks if cached pilot data is fresh enough for eligibility decisions,
and optionally triggers a sync if data is stale and ESI is available.

Usage:
    from aria_esi.core.freshness import check_freshness, ensure_fresh

    result = check_freshness("standings", pilot_dir)
    result = ensure_fresh("standings", pilot_dir)
"""

import dataclasses
import importlib
import json
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

# =============================================================================
# Configuration
# =============================================================================


@dataclass(frozen=True)
class SectionConfig:
    """Configuration for a freshness-checked data section."""

    ttl_hours: float
    sync_fn: str  # dotted import path to adapter
    file_template: str  # "profile.md" or "skills.json"
    format: str  # "marker" or "json_meta"
    markers: list[str]  # marker patterns (empty for json_meta)


SECTION_REGISTRY: dict[str, SectionConfig] = {
    "standings": SectionConfig(
        ttl_hours=24,
        sync_fn="aria_esi.core.freshness_adapters.sync_standings",
        file_template="profile.md",
        format="marker",
        markers=[
            "ESI-SYNC:STANDINGS-EMPIRE:START",
            "ESI-SYNC:STANDINGS-CORPS:START",
            "ESI-SYNC:STANDINGS-PIRATES:START",
        ],
    ),
    "skills": SectionConfig(
        ttl_hours=12,
        sync_fn="aria_esi.core.freshness_adapters.sync_skills",
        file_template="skills.json",
        format="json_meta",
        markers=[],
    ),
}


# =============================================================================
# SyncResult
# =============================================================================


@dataclass(frozen=True)
class SyncResult:
    """Result of a freshness check or ensure-fresh operation."""

    section: str
    fresh: bool
    synced_at: Optional[str]  # ISO timestamp or None
    age_hours: Optional[float]  # hours since last sync or None
    ttl_hours: float
    refreshed: bool  # True if sync was performed and markers advanced
    esi_available: Optional[bool]  # None if ESI was not probed
    error: Optional[str]
    source: str  # "marker", "json_meta", "missing", "error"

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return dataclasses.asdict(self)


# =============================================================================
# Marker Parsing
# =============================================================================


def parse_sync_marker(content: str, pattern: str) -> Optional[dict[str, Any]]:
    """
    Parse ESI-SYNC marker to extract metadata.

    Markers look like:
    <!-- ESI-SYNC:STANDINGS-CORPS:START ttl_hours=24 synced_at=2026-01-25T04:59:00Z -->

    Legacy format:
    <!-- ESI-SYNC:STANDINGS-CORPS:START -->
    ...
    *Synced: 2026-01-25 04:59 UTC*

    Returns:
        Dict with parsed metadata, or None if marker not found.
    """
    # Try enhanced format with key=value pairs
    marker_match = re.search(rf"<!--\s*{pattern}\s+([^>]+)-->", content)
    if marker_match:
        metadata_str = marker_match.group(1)
        metadata: dict[str, Any] = {"format": "enhanced"}

        for match in re.finditer(r"(\w+)=([^\s]+)", metadata_str):
            key, value = match.groups()
            if key in ("ttl_hours",):
                try:
                    metadata[key] = float(value)
                except ValueError:
                    metadata[key] = value
            else:
                metadata[key] = value

        return metadata

    # Try legacy format without metadata
    legacy_match = re.search(rf"<!--\s*{pattern}\s*-->", content)
    if legacy_match:
        # Look for *Synced: timestamp* pattern within 500 chars after marker
        synced_match = re.search(
            r"\*Synced:\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s*UTC\*",
            content[legacy_match.end() : legacy_match.end() + 500],
        )
        if synced_match:
            try:
                synced_at = datetime.strptime(synced_match.group(1), "%Y-%m-%d %H:%M").replace(
                    tzinfo=UTC
                )
                return {
                    "synced_at": synced_at.isoformat(),
                    "format": "legacy",
                }
            except ValueError:
                pass

    return None


# =============================================================================
# Internal Helpers
# =============================================================================


def _resolve_pilot_dir(pilot_dir: Optional[Path]) -> Optional[Path]:
    """Resolve pilot directory, falling back to config-based resolution."""
    if pilot_dir is not None:
        return pilot_dir
    # Deferred import to avoid circular dependencies
    from .auth import get_pilot_directory

    return get_pilot_directory()


def _parse_iso_timestamp(ts: str) -> datetime:
    """Parse an ISO timestamp string, handling Z suffix."""
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _check_marker_freshness(pilot_dir: Path, config: SectionConfig) -> SyncResult:
    """Check freshness for marker-format sections (e.g., standings in profile.md)."""
    file_path = pilot_dir / config.file_template

    if not file_path.exists():
        return SyncResult(
            section="",  # Filled by caller
            fresh=False,
            synced_at=None,
            age_hours=None,
            ttl_hours=config.ttl_hours,
            refreshed=False,
            esi_available=None,
            error=None,
            source="missing",
        )

    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError as e:
        return SyncResult(
            section="",
            fresh=False,
            synced_at=None,
            age_hours=None,
            ttl_hours=config.ttl_hours,
            refreshed=False,
            esi_available=None,
            error=f"Cannot read file: {e}",
            source="error",
        )

    oldest_synced_at: Optional[datetime] = None
    now = datetime.now(UTC)

    for marker in config.markers:
        metadata = parse_sync_marker(content, marker)
        if metadata is None:
            # Any missing marker means data is incomplete
            return SyncResult(
                section="",
                fresh=False,
                synced_at=None,
                age_hours=None,
                ttl_hours=config.ttl_hours,
                refreshed=False,
                esi_available=None,
                error=None,
                source="missing",
            )

        if "synced_at" not in metadata:
            return SyncResult(
                section="",
                fresh=False,
                synced_at=None,
                age_hours=None,
                ttl_hours=config.ttl_hours,
                refreshed=False,
                esi_available=None,
                error=None,
                source="missing",
            )

        try:
            ts = _parse_iso_timestamp(metadata["synced_at"])
        except (ValueError, TypeError):
            return SyncResult(
                section="",
                fresh=False,
                synced_at=None,
                age_hours=None,
                ttl_hours=config.ttl_hours,
                refreshed=False,
                esi_available=None,
                error=None,
                source="missing",
            )

        if oldest_synced_at is None or ts < oldest_synced_at:
            oldest_synced_at = ts

    # All markers found — compute age from oldest
    assert oldest_synced_at is not None
    age_hours = (now - oldest_synced_at).total_seconds() / 3600
    is_fresh = age_hours < config.ttl_hours

    return SyncResult(
        section="",
        fresh=is_fresh,
        synced_at=oldest_synced_at.isoformat(),
        age_hours=round(age_hours, 2),
        ttl_hours=config.ttl_hours,
        refreshed=False,
        esi_available=None,
        error=None,
        source="marker",
    )


def _check_json_meta_freshness(pilot_dir: Path, config: SectionConfig) -> SyncResult:
    """Check freshness for json_meta format sections (e.g., skills.json)."""
    file_path = pilot_dir / config.file_template

    if not file_path.exists():
        return SyncResult(
            section="",
            fresh=False,
            synced_at=None,
            age_hours=None,
            ttl_hours=config.ttl_hours,
            refreshed=False,
            esi_available=None,
            error=None,
            source="missing",
        )

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return SyncResult(
            section="",
            fresh=False,
            synced_at=None,
            age_hours=None,
            ttl_hours=config.ttl_hours,
            refreshed=False,
            esi_available=None,
            error=f"Cannot read/parse file: {e}",
            source="error",
        )

    meta = data.get("_meta", {})
    synced_at_str = meta.get("synced_at")
    if not synced_at_str:
        return SyncResult(
            section="",
            fresh=False,
            synced_at=None,
            age_hours=None,
            ttl_hours=config.ttl_hours,
            refreshed=False,
            esi_available=None,
            error=None,
            source="missing",
        )

    try:
        synced_at = _parse_iso_timestamp(synced_at_str)
    except (ValueError, TypeError):
        return SyncResult(
            section="",
            fresh=False,
            synced_at=None,
            age_hours=None,
            ttl_hours=config.ttl_hours,
            refreshed=False,
            esi_available=None,
            error=None,
            source="missing",
        )

    now = datetime.now(UTC)
    age_hours = (now - synced_at).total_seconds() / 3600
    is_fresh = age_hours < config.ttl_hours

    return SyncResult(
        section="",
        fresh=is_fresh,
        synced_at=synced_at.isoformat(),
        age_hours=round(age_hours, 2),
        ttl_hours=config.ttl_hours,
        refreshed=False,
        esi_available=None,
        error=None,
        source="json_meta",
    )


# =============================================================================
# Public API
# =============================================================================


def check_freshness(section: str, pilot_dir: Optional[Path] = None) -> SyncResult:
    """
    Check if cached data for a section is fresh.

    Args:
        section: Registry key (e.g., "standings", "skills")
        pilot_dir: Pilot data directory. If None, resolved from config.

    Returns:
        SyncResult with freshness status.

    Raises:
        KeyError: If section is not in SECTION_REGISTRY.
    """
    config = SECTION_REGISTRY[section]  # Raises KeyError if invalid

    resolved_dir = _resolve_pilot_dir(pilot_dir)
    if resolved_dir is None:
        return SyncResult(
            section=section,
            fresh=False,
            synced_at=None,
            age_hours=None,
            ttl_hours=config.ttl_hours,
            refreshed=False,
            esi_available=None,
            error="Could not resolve pilot directory",
            source="error",
        )

    if config.format == "marker":
        result = _check_marker_freshness(resolved_dir, config)
    elif config.format == "json_meta":
        result = _check_json_meta_freshness(resolved_dir, config)
    else:
        return SyncResult(
            section=section,
            fresh=False,
            synced_at=None,
            age_hours=None,
            ttl_hours=config.ttl_hours,
            refreshed=False,
            esi_available=None,
            error=f"Unknown format: {config.format}",
            source="error",
        )

    # Replace the placeholder section field
    return dataclasses.replace(result, section=section)


def _resolve_sync_fn(dotted_path: str) -> Callable:
    """Resolve a dotted import path to a callable."""
    module_path, _, fn_name = dotted_path.rpartition(".")
    module = importlib.import_module(module_path)
    return getattr(module, fn_name)


def is_esi_available(timeout: float = 5.0) -> bool:
    """
    Check if ESI authentication is available.

    Runs get_authenticated_client() in a thread with a timeout to avoid
    blocking the caller. Returns False on any failure.
    """
    result_holder: list[bool] = [False]
    error_holder: list[Optional[Exception]] = [None]

    def _probe() -> None:
        try:
            from .auth import get_authenticated_client

            get_authenticated_client()
            result_holder[0] = True
        except Exception as e:
            error_holder[0] = e

    thread = threading.Thread(target=_probe, daemon=True)
    thread.start()
    thread.join(timeout=timeout)

    if thread.is_alive():
        return False

    return result_holder[0]


def ensure_fresh(
    section: str,
    pilot_dir: Optional[Path] = None,
    force: bool = False,
) -> SyncResult:
    """
    Ensure data for a section is fresh, syncing if needed.

    Decision tree:
    1. check_freshness() — if fresh and not force, return immediately
    2. If stale (or force) — probe ESI availability
    3. If ESI unavailable — return with esi_available=False
    4. If ESI available — resolve and call sync_fn
    5. Re-check freshness to verify markers advanced

    Args:
        section: Registry key (e.g., "standings", "skills")
        pilot_dir: Pilot data directory. If None, resolved from config.
        force: If True, sync even when data is fresh.

    Returns:
        SyncResult with freshness and sync status.

    Raises:
        KeyError: If section is not in SECTION_REGISTRY.
    """
    config = SECTION_REGISTRY[section]  # Raises KeyError if invalid
    resolved_dir = _resolve_pilot_dir(pilot_dir)

    # Step 1: Check current freshness
    result = check_freshness(section, resolved_dir)

    if result.fresh and not force:
        return result

    # Step 2: Probe ESI availability
    esi_up = is_esi_available()
    if not esi_up:
        # Re-check freshness to get final state (may have changed)
        final = check_freshness(section, resolved_dir)
        return dataclasses.replace(final, esi_available=False)

    # Step 3: Resolve and call sync function
    try:
        sync_fn = _resolve_sync_fn(config.sync_fn)
        sync_fn(resolved_dir)
    except Exception as e:
        # Sync failed — return with error
        final = check_freshness(section, resolved_dir)
        return dataclasses.replace(
            final,
            esi_available=True,
            refreshed=False,
            error=str(e),
        )

    # Step 4: Re-check freshness to verify markers advanced
    post_sync = check_freshness(section, resolved_dir)

    if not post_sync.fresh and result.synced_at == post_sync.synced_at:
        # Sync completed but markers didn't advance
        return dataclasses.replace(
            post_sync,
            esi_available=True,
            refreshed=False,
            error="sync completed but markers did not advance",
        )

    return dataclasses.replace(
        post_sync,
        esi_available=True,
        refreshed=True,
    )
