"""Navigation action implementations: route, systems, borders, search, nearest."""

from __future__ import annotations

from ....services.navigation import VALID_MODES
from ...context import summarize_route, wrap_output
from ...context_policy import UNIVERSE
from ...errors import InvalidParameterError, RouteNotFoundError
from ...models import RouteResult, SystemInfo
from ...tools import ResolvedSystem, collect_corrections, get_universe, resolve_system_name
from ...utils import build_system_info
from ._helpers_route import _build_route_result, _calculate_route, _generate_fw_route_warnings
from ._helpers_search import (
    _build_predicate,
    _find_border_systems,
    _find_nearest,
    _resolve_region,
    _search_systems,
    _summarize_filters,
    _summarize_predicates,
)


async def _route(
    origin: str | None,
    destination: str | None,
    mode: str,
    avoid_systems: list[str] | None,
    prefer_territory: str | None = None,
    avoid_territory: str | None = None,
) -> dict:
    """Route action."""
    if not origin:
        raise InvalidParameterError("origin", origin, "Required for action='route'")
    if not destination:
        raise InvalidParameterError("destination", destination, "Required for action='route'")

    universe = get_universe()

    if mode not in VALID_MODES:
        raise InvalidParameterError(
            "mode", mode, f"Must be one of: {', '.join(sorted(VALID_MODES))}"
        )

    origin_resolved = resolve_system_name(origin)
    dest_resolved = resolve_system_name(destination)
    corrections = collect_corrections(origin_resolved, dest_resolved)

    avoid_indices: set[int] | None = None
    unresolved_avoids: list[str] = []
    if avoid_systems:
        avoid_indices = set()
        for name in avoid_systems:
            idx = universe.resolve_name(name)
            if idx is not None:
                avoid_indices.add(idx)
            else:
                unresolved_avoids.append(name)

    # Expand territory params to system indices
    territory_warnings: list[str] = []
    if avoid_territory or prefer_territory:
        from ....services.sovereignty.coalition_service import get_systems_by_coalition

    if avoid_territory:
        territory_system_ids = get_systems_by_coalition(avoid_territory)
        if territory_system_ids:
            if avoid_indices is None:
                avoid_indices = set()
            for sys_id in territory_system_ids:
                idx = universe.id_to_idx.get(sys_id)
                if idx is not None:
                    avoid_indices.add(idx)
            territory_warnings.append(
                f"Avoiding {avoid_territory} territory ({len(territory_system_ids)} systems)"
            )
        else:
            territory_warnings.append(
                f"Unknown coalition '{avoid_territory}' — territory avoidance not applied"
            )

    # Expand prefer_territory to system indices
    preferred_indices: set[int] | None = None
    if prefer_territory:
        territory_system_ids = get_systems_by_coalition(prefer_territory)
        if territory_system_ids:
            preferred_indices = set()
            for sys_id in territory_system_ids:
                idx = universe.id_to_idx.get(sys_id)
                if idx is not None:
                    preferred_indices.add(idx)
            territory_warnings.append(
                f"Preferring {prefer_territory} territory ({len(territory_system_ids)} systems)"
            )
        else:
            territory_warnings.append(
                f"Unknown coalition '{prefer_territory}' — territory preference not applied"
            )

    path = _calculate_route(
        universe,
        origin_resolved.idx,
        dest_resolved.idx,
        mode,
        avoid_indices,
        preferred_indices,
    )

    if not path:
        raise RouteNotFoundError(origin_resolved.canonical_name, dest_resolved.canonical_name)

    result = _build_route_result(
        universe,
        path,
        origin_resolved.canonical_name,
        dest_resolved.canonical_name,
        mode,
        corrections,
    )

    if unresolved_avoids:
        result = RouteResult(
            **{
                **result.model_dump(),
                "warnings": result.warnings
                + [f"Unknown systems in avoid_systems: {', '.join(unresolved_avoids)}"],
            }
        )

    # Add territory warnings
    if territory_warnings:
        result = RouteResult(
            **{
                **result.model_dump(),
                "warnings": result.warnings + territory_warnings,
            }
        )

    # Add FW warzone warnings
    fw_warnings = await _generate_fw_route_warnings(universe, path)
    if fw_warnings:
        result = RouteResult(
            **{
                **result.model_dump(),
                "warnings": result.warnings + fw_warnings,
            }
        )

    return summarize_route(
        result.model_dump(),
        systems_key="systems",
        threshold=UNIVERSE.ROUTE_SUMMARIZE_THRESHOLD,
        head=UNIVERSE.ROUTE_SHOW_HEAD,
        tail=UNIVERSE.ROUTE_SHOW_TAIL,
    )


async def _systems(systems: list[str] | None) -> dict:
    """Systems action."""
    if not systems:
        raise InvalidParameterError("systems", systems, "Required for action='systems'")

    universe = get_universe()
    results: list[SystemInfo | None] = []
    corrections: dict[str, str] = {}

    for name in systems:
        try:
            resolved: ResolvedSystem = resolve_system_name(name)
            results.append(build_system_info(universe, resolved.idx))
            if resolved.was_corrected and resolved.corrected_from:
                corrections[resolved.corrected_from] = resolved.canonical_name
        except Exception:  # noqa: BLE001 -- MCP handler
            results.append(None)

    return wrap_output(
        {
            "systems": [s.model_dump() if s else None for s in results],
            "found": sum(1 for s in results if s is not None),
            "not_found": sum(1 for s in results if s is None),
            "corrections": corrections,
        },
        "systems",
        max_items=UNIVERSE.OUTPUT_MAX_SYSTEMS,
    )


async def _borders(
    origin: str | None,
    limit: int,
    max_jumps: int | None,
) -> dict:
    """Borders action."""
    if not origin:
        raise InvalidParameterError("origin", origin, "Required for action='borders'")

    effective_limit = min(limit, UNIVERSE.BORDERS_MAX_LIMIT) if limit else 10
    effective_max_jumps = min(max_jumps or 15, UNIVERSE.BORDERS_MAX_JUMPS)

    if effective_limit < 1:
        raise InvalidParameterError(
            "limit", limit, f"Must be between 1 and {UNIVERSE.BORDERS_MAX_LIMIT}"
        )
    if effective_max_jumps < 1:
        raise InvalidParameterError(
            "max_jumps", max_jumps, f"Must be between 1 and {UNIVERSE.BORDERS_MAX_JUMPS}"
        )

    universe = get_universe()
    origin_resolved = resolve_system_name(origin)
    corrections = collect_corrections(origin_resolved)

    borders = _find_border_systems(
        universe, origin_resolved.idx, effective_limit, effective_max_jumps
    )

    return wrap_output(
        {
            "origin": origin_resolved.canonical_name,
            "borders": [b.model_dump() for b in borders],
            "total_found": len(borders),
            "search_radius": effective_max_jumps,
            "corrections": corrections,
        },
        "borders",
        max_items=UNIVERSE.OUTPUT_MAX_SYSTEMS,
    )


async def _search(
    origin: str | None,
    max_jumps: int | None,
    security_min: float | None,
    security_max: float | None,
    region: str | None,
    is_border: bool | None,
    limit: int,
    coalition: str | None = None,
) -> dict:
    """Search action."""
    universe = get_universe()

    if limit < 1 or limit > UNIVERSE.SEARCH_MAX_LIMIT:
        raise InvalidParameterError(
            "limit", limit, f"Must be between 1 and {UNIVERSE.SEARCH_MAX_LIMIT}"
        )

    if max_jumps is not None and origin is None:
        raise InvalidParameterError(
            "origin", None, "origin is required when max_jumps is specified"
        )

    if max_jumps is not None and (max_jumps < 1 or max_jumps > UNIVERSE.SEARCH_MAX_JUMPS):
        raise InvalidParameterError(
            "max_jumps", max_jumps, f"Must be between 1 and {UNIVERSE.SEARCH_MAX_JUMPS}"
        )

    origin_idx: int | None = None
    origin_canonical: str | None = None
    corrections: dict[str, str] = {}
    if origin:
        origin_resolved = resolve_system_name(origin)
        origin_idx = origin_resolved.idx
        origin_canonical = origin_resolved.canonical_name
        corrections = collect_corrections(origin_resolved)

    region_id = None
    region_not_found = False
    if region:
        region_id = _resolve_region(universe, region)
        if region_id is None:
            region_not_found = True

    if region_not_found:
        return {
            "systems": [],
            "total_found": 0,
            "filters_applied": _summarize_filters(
                origin_canonical or origin,
                max_jumps,
                security_min,
                security_max,
                region,
                is_border,
                coalition,
            ),
            "warning": f"Unknown region: '{region}'",
            "corrections": corrections,
        }

    # Resolve coalition filter to system IDs
    coalition_system_ids: set[int] | None = None
    coalition_warning: str | None = None
    if coalition:
        from aria_esi.services.sovereignty import get_systems_by_coalition

        coalition_systems = get_systems_by_coalition(coalition)
        if coalition_systems:
            coalition_system_ids = set(coalition_systems)
        else:
            coalition_warning = f"Unknown or empty coalition: '{coalition}'"

    if coalition_warning and coalition_system_ids is None:
        return {
            "systems": [],
            "total_found": 0,
            "filters_applied": _summarize_filters(
                origin_canonical or origin,
                max_jumps,
                security_min,
                security_max,
                region,
                is_border,
                coalition,
            ),
            "warning": coalition_warning,
            "corrections": corrections,
        }

    results = _search_systems(
        universe=universe,
        origin_idx=origin_idx,
        max_jumps=max_jumps,
        security_min=security_min,
        security_max=security_max,
        region_id=region_id,
        is_border=is_border,
        limit=limit,
        coalition_system_ids=coalition_system_ids,
    )

    return wrap_output(
        {
            "systems": [r.model_dump() for r in results],
            "total_found": len(results),
            "filters_applied": _summarize_filters(
                origin_canonical or origin,
                max_jumps,
                security_min,
                security_max,
                region,
                is_border,
                coalition,
            ),
            "corrections": corrections,
        },
        "systems",
        max_items=UNIVERSE.OUTPUT_MAX_SYSTEMS,
    )


async def _nearest(
    origin: str | None,
    is_border: bool | None,
    min_adjacent_lowsec: int | None,
    security_min: float | None,
    security_max: float | None,
    region: str | None,
    limit: int,
    max_jumps: int | None,
) -> dict:
    """Nearest action."""
    if not origin:
        raise InvalidParameterError("origin", origin, "Required for action='nearest'")

    universe = get_universe()

    effective_limit = min(limit, UNIVERSE.NEAREST_MAX_LIMIT) if limit else 5
    # Lower default for NPC null searches — rare features found within ~12 jumps
    # from typical lowsec starting points. Full 30 causes 95s+ BFS traversals.
    default_jumps = 30
    if not max_jumps and security_max is not None and security_max < 0.0:
        default_jumps = 15
    effective_max_jumps = min(max_jumps or default_jumps, UNIVERSE.NEAREST_MAX_JUMPS)

    if effective_limit < 1:
        raise InvalidParameterError(
            "limit", limit, f"Must be between 1 and {UNIVERSE.NEAREST_MAX_LIMIT}"
        )
    if effective_max_jumps < 1:
        raise InvalidParameterError(
            "max_jumps", max_jumps, f"Must be between 1 and {UNIVERSE.NEAREST_MAX_JUMPS}"
        )
    if security_min is not None and (security_min < -1.0 or security_min > 1.0):
        raise InvalidParameterError("security_min", security_min, "Must be between -1.0 and 1.0")
    if security_max is not None and (security_max < -1.0 or security_max > 1.0):
        raise InvalidParameterError("security_max", security_max, "Must be between -1.0 and 1.0")
    if min_adjacent_lowsec is not None and min_adjacent_lowsec < 1:
        raise InvalidParameterError(
            "min_adjacent_lowsec", min_adjacent_lowsec, "Must be at least 1"
        )

    origin_resolved = resolve_system_name(origin)
    corrections = collect_corrections(origin_resolved)

    region_id = None
    if region:
        region_id = universe.resolve_region(region)
        if region_id is None:
            return {
                "origin": origin_resolved.canonical_name,
                "systems": [],
                "total_found": 0,
                "search_radius": effective_max_jumps,
                "predicates": _summarize_predicates(
                    is_border, min_adjacent_lowsec, security_min, security_max, region
                ),
                "warning": f"Unknown region: '{region}'",
                "corrections": corrections,
            }

    predicate = _build_predicate(
        universe=universe,
        is_border=is_border,
        min_adjacent_lowsec=min_adjacent_lowsec,
        security_min=security_min,
        security_max=security_max,
        region_id=region_id,
    )

    results = _find_nearest(
        universe=universe,
        origin_idx=origin_resolved.idx,
        predicate=predicate,
        limit=effective_limit,
        max_jumps=effective_max_jumps,
    )

    return wrap_output(
        {
            "origin": origin_resolved.canonical_name,
            "systems": [r.model_dump() for r in results],
            "total_found": len(results),
            "search_radius": effective_max_jumps,
            "predicates": _summarize_predicates(
                is_border, min_adjacent_lowsec, security_min, security_max, region
            ),
            "corrections": corrections,
        },
        "systems",
        max_items=UNIVERSE.OUTPUT_MAX_SYSTEMS,
    )
