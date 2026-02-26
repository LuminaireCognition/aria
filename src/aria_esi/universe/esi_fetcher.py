"""
Universe Cache Builder (ESI Fetcher)

Downloads static universe data from ESI and caches it locally as JSON.
This is step 1 of the graph build pipeline:
    esi_fetcher.py → universe_cache.json → builder.py → .universe binary

Run periodically (monthly or after expansions) to refresh.

Usage:
    uv run aria-esi cache-fetch [--output PATH]
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from aria_esi.core import ESIClient, get_utc_timestamp


def build_universe_cache(output_path: Path, verbose: bool = True) -> dict[str, Any]:
    """
    Build complete universe cache from ESI.

    Downloads:
    - All regions (name)
    - All constellations (name, region_id)
    - All systems (name, security, constellation_id, stargates)
    - All stargates (destination system)

    Args:
        output_path: Path to write cache JSON
        verbose: Print progress to stderr

    Returns:
        Cache dict with regions, constellations, systems, stargates
    """
    client = ESIClient()
    cache: dict[str, Any] = {
        "generated": get_utc_timestamp(),
        "regions": {},
        "constellations": {},
        "systems": {},
        "stargates": {},
    }

    def log(msg: str) -> None:
        if verbose:
            print(msg, file=sys.stderr)

    # Step 1: Fetch all region IDs
    log("Fetching region list...")
    region_ids = client.get("/universe/regions/")
    if not isinstance(region_ids, list):
        raise RuntimeError("Failed to fetch region list")
    log(f"  Found {len(region_ids)} regions")

    # Step 2: Fetch each region's details and constellations
    log("Fetching regions and constellations...")
    constellation_ids: list[int] = []

    for i, region_id in enumerate(region_ids):
        region = client.get_dict_safe(f"/universe/regions/{region_id}/")
        if region:
            cache["regions"][str(region_id)] = {
                "name": region.get("name", "Unknown"),
            }
            constellation_ids.extend(region.get("constellations", []))

        if verbose and (i + 1) % 10 == 0:
            print(f"  Regions: {i + 1}/{len(region_ids)}", file=sys.stderr, end="\r")

    log(f"  Fetched {len(cache['regions'])} regions, {len(constellation_ids)} constellations")

    # Step 3: Fetch each constellation's details
    log("Fetching constellation details...")
    system_ids: list[int] = []

    for i, const_id in enumerate(constellation_ids):
        const = client.get_dict_safe(f"/universe/constellations/{const_id}/")
        if const:
            cache["constellations"][str(const_id)] = {
                "name": const.get("name", "Unknown"),
                "region_id": const.get("region_id"),
            }
            system_ids.extend(const.get("systems", []))

        if verbose and (i + 1) % 50 == 0:
            print(
                f"  Constellations: {i + 1}/{len(constellation_ids)}",
                file=sys.stderr,
                end="\r",
            )

    log(f"  Fetched {len(cache['constellations'])} constellations, {len(system_ids)} systems")

    # Step 4: Fetch each system's details
    log("Fetching system details...")
    stargate_ids: list[int] = []

    for i, sys_id in enumerate(system_ids):
        system = client.get_dict_safe(f"/universe/systems/{sys_id}/")
        if system:
            gates = system.get("stargates", [])
            cache["systems"][str(sys_id)] = {
                "name": system.get("name", "Unknown"),
                "security": round(system.get("security_status", 0), 4),
                "constellation_id": system.get("constellation_id"),
                "stargates": gates,
            }
            stargate_ids.extend(gates)

        if verbose and (i + 1) % 100 == 0:
            print(f"  Systems: {i + 1}/{len(system_ids)}", file=sys.stderr, end="\r")

    log(f"  Fetched {len(cache['systems'])} systems, {len(stargate_ids)} stargates")

    # Step 5: Fetch stargate destinations
    log("Fetching stargate destinations...")
    for i, gate_id in enumerate(stargate_ids):
        gate = client.get_dict_safe(f"/universe/stargates/{gate_id}/")
        if gate:
            dest = gate.get("destination", {})
            cache["stargates"][str(gate_id)] = {
                "destination_system_id": dest.get("system_id"),
            }

        if verbose and (i + 1) % 200 == 0:
            print(f"  Stargates: {i + 1}/{len(stargate_ids)}", file=sys.stderr, end="\r")

    log(f"  Fetched {len(cache['stargates'])} stargates")

    # Write cache file
    log(f"Writing cache to {output_path}...")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(cache, f, separators=(",", ":"))  # Compact JSON

    # Calculate file size
    size_bytes = output_path.stat().st_size
    size_mb = size_bytes / (1024 * 1024)
    log(f"  Cache size: {size_mb:.2f} MB")

    log("Done!")
    return cache


def main() -> int:
    parser = argparse.ArgumentParser(description="Build universe cache from ESI")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path(__file__).parent.parent / "data" / "universe_cache.json",
        help="Output path for cache file",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress progress output",
    )
    args = parser.parse_args()

    start = time.time()
    try:
        cache = build_universe_cache(args.output, verbose=not args.quiet)
        elapsed = time.time() - start

        # Print summary
        print(
            json.dumps(
                {
                    "status": "success",
                    "generated": cache["generated"],
                    "output": str(args.output),
                    "counts": {
                        "regions": len(cache["regions"]),
                        "constellations": len(cache["constellations"]),
                        "systems": len(cache["systems"]),
                        "stargates": len(cache["stargates"]),
                    },
                    "elapsed_seconds": round(elapsed, 1),
                },
                indent=2,
            )
        )
        return 0

    except (json.JSONDecodeError, KeyError, ValueError) as e:
        print(json.dumps({"status": "error", "message": str(e)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
