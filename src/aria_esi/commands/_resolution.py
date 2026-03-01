"""
Batch name resolution for type IDs and station IDs.

Replaces sequential ESI HTTP calls with:
- SDE database lookups for type IDs (sub-millisecond for hundreds of IDs)
- ESI POST /universe/names/ for station IDs (one HTTP call for up to 1000 IDs)
"""

from __future__ import annotations

import sys
from typing import Any


def resolve_type_ids(
    type_ids: set[int],
    *,
    esi_client: Any = None,
) -> dict[int, dict]:
    """
    Resolve type IDs to name/group/market_group info.

    Phase 1: SDE batch lookup (fast, local SQLite)
    Phase 2: ESI POST /universe/names/ fallback for missing IDs
    Phase 3: Unknown-{id} for anything still unresolved

    Args:
        type_ids: Set of type IDs to resolve
        esi_client: Optional ESIClient instance for ESI fallback

    Returns:
        Dict mapping type_id to {"name": str, "group_id": int, "market_group_id": int|None}
    """
    if not type_ids:
        return {}

    result: dict[int, dict] = {}

    # Phase 1: SDE batch lookup
    try:
        from ..store.market.database import get_market_database

        db = get_market_database()
        sde_results = db.resolve_type_ids_batch(type_ids)
        for tid, info in sde_results.items():
            result[tid] = {
                "name": info.type_name,
                "group_id": info.group_id or 0,
                "market_group_id": info.market_group_id,
            }
    except Exception:  # noqa: BLE001
        pass

    # Phase 2: ESI fallback for missing IDs
    missing = type_ids - set(result)
    if missing and esi_client is not None:
        try:
            from ..core import ESIError

            batch_size = 1000
            missing_list = list(missing)
            for i in range(0, len(missing_list), batch_size):
                batch = missing_list[i : i + batch_size]
                try:
                    response = esi_client.post("/universe/names/", data=batch)
                    if isinstance(response, list):
                        for item in response:
                            if item.get("category") == "inventory_type":
                                result[item["id"]] = {
                                    "name": item["name"],
                                    "group_id": 0,
                                    "market_group_id": None,
                                }
                except ESIError as e:
                    print(
                        f"  Warning: ESI type name batch failed: {e}",
                        file=sys.stderr,
                    )
        except Exception:  # noqa: BLE001
            pass

    # Phase 3: Unknown fallback
    for tid in type_ids:
        if tid not in result:
            result[tid] = {
                "name": f"Unknown-{tid}",
                "group_id": 0,
                "market_group_id": None,
            }

    return result


def resolve_station_names(
    station_ids: set[int],
    *,
    esi_client: Any = None,
) -> dict[int, str]:
    """
    Resolve station/structure IDs to names.

    Uses ESI POST /universe/names/ (one HTTP call for up to 1000 IDs).
    Falls back to Structure-{id} or Station-{id} for unresolved IDs.

    Args:
        station_ids: Set of station/structure IDs to resolve
        esi_client: Optional ESIClient instance

    Returns:
        Dict mapping station_id to station name string
    """
    if not station_ids:
        return {}

    result: dict[int, str] = {}

    if esi_client is not None:
        try:
            from ..core import ESIError

            batch_size = 1000
            id_list = list(station_ids)
            for i in range(0, len(id_list), batch_size):
                batch = id_list[i : i + batch_size]
                try:
                    response = esi_client.post("/universe/names/", data=batch)
                    if isinstance(response, list):
                        for item in response:
                            result[item["id"]] = item["name"]
                except ESIError:
                    pass
        except Exception:  # noqa: BLE001
            pass

    # Fallback for unresolved IDs
    for sid in station_ids:
        if sid not in result:
            if sid >= 100_000_000:
                result[sid] = f"Structure-{sid}"
            else:
                result[sid] = f"Station-{sid}"

    return result
