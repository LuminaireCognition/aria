"""Local area classification and escape route helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aria_esi.universe.graph import UniverseGraph

    from ...models import BorderType, EscapeRoute, ThreatLevel


def _classify_border(sec: float, neighbor_sec: float) -> BorderType | None:
    """Classify the type of security border between two systems."""

    # Determine security classes
    def sec_class(s: float) -> str:
        if s >= 0.45:
            return "high"
        elif s > 0.0:
            return "low"
        else:
            return "null"

    from_class = sec_class(sec)
    to_class = sec_class(neighbor_sec)

    if from_class == to_class:
        return None

    border_map: dict[tuple[str, str], BorderType] = {
        ("null", "low"): "null_to_low",
        ("low", "high"): "low_to_high",
        ("high", "low"): "high_to_low",
        ("low", "null"): "low_to_null",
    }

    return border_map.get((from_class, to_class))


def _classify_threat_level(total_kills: int, hotspot_count: int, camp_count: int) -> ThreatLevel:
    """Classify overall threat level for the local area."""
    # Active camps are high priority
    if camp_count >= 3:
        return "EXTREME"
    if camp_count >= 1:
        return "HIGH"

    # High activity
    if total_kills >= 50 or hotspot_count >= 5:
        return "HIGH"
    if total_kills >= 20 or hotspot_count >= 2:
        return "MEDIUM"

    return "LOW"


async def _find_escape_routes(
    universe: UniverseGraph,
    origin_idx: int,
    origin_sec: float,
    visited: dict[int, int],
    max_jumps: int,
) -> list[EscapeRoute]:
    """Find escape routes to safer space."""
    from ...models import EscapeRoute as EscapeRouteModel

    escape_routes: list[EscapeRouteModel] = []

    # Determine what we're looking for based on origin security
    origin_class = "null" if origin_sec <= 0.0 else ("low" if origin_sec < 0.45 else "high")

    # Find nearest low-sec (if in null)
    if origin_class == "null":
        for idx, distance in sorted(visited.items(), key=lambda x: x[1]):
            if idx == origin_idx:
                continue
            sec = float(universe.security[idx])
            if 0.0 < sec < 0.45:
                escape_routes.append(
                    EscapeRouteModel(
                        destination=universe.idx_to_name[idx],
                        destination_type="lowsec",
                        jumps=distance,
                        via_system=None,  # Could trace path if needed
                        route_security="lowsec",
                    )
                )
                break

    # Find nearest high-sec (if in low or null)
    if origin_class in ("null", "low"):
        for idx, distance in sorted(visited.items(), key=lambda x: x[1]):
            if idx == origin_idx:
                continue
            sec = float(universe.security[idx])
            if sec >= 0.45:
                escape_routes.append(
                    EscapeRouteModel(
                        destination=universe.idx_to_name[idx],
                        destination_type="highsec",
                        jumps=distance,
                        via_system=None,
                        route_security="mixed" if origin_class == "null" else "lowsec",
                    )
                )
                break

    # Note: NPC station lookup would require SDE enhancement
    # For now, we identify security transitions which often have stations

    return escape_routes
