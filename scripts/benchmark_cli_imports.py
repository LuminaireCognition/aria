#!/usr/bin/env python3
"""
Benchmark CLI command module import times.

Measures how long each command module takes to import individually,
helping identify heavy transitive dependencies that slow CLI startup.

Usage:
    uv run python scripts/benchmark_cli_imports.py
"""

import importlib
import sys
import time

COMMAND_MODULES = [
    "navigation", "market", "pilot",
    "character", "wallet", "skills", "industry", "assets",
    "corporation", "loyalty", "clones",
    "killmails", "killmail", "contracts", "agents_research",
    "mining", "orders", "fittings", "mail",
    "universe", "persona", "sync_profile", "sde",
    "validation", "fitting", "redisq", "notifications",
    "pi", "sovereignty", "freshness",
]


def benchmark_module(name: str) -> tuple[str, float, str | None]:
    """Import a single module in a clean state and measure time."""
    # Remove cached module and its children to get fresh import time
    keys_to_remove = [
        k for k in sys.modules
        if k.startswith(f"aria_esi.commands.{name}")
    ]
    for k in keys_to_remove:
        del sys.modules[k]

    error = None
    start = time.perf_counter()
    try:
        importlib.import_module(f"aria_esi.commands.{name}")
    except Exception as e:  # noqa: BLE001
        error = str(e)
    elapsed = time.perf_counter() - start
    return name, elapsed, error


def benchmark_register_parsers() -> float:
    """Measure the full build_parser() time (all modules + register_parsers)."""
    # Clear all command modules
    keys_to_remove = [
        k for k in sys.modules
        if k.startswith("aria_esi.commands.")
    ]
    for k in keys_to_remove:
        del sys.modules[k]

    start = time.perf_counter()
    from aria_esi.__main__ import build_parser
    build_parser()
    elapsed = time.perf_counter() - start
    return elapsed


def main() -> None:
    print("=" * 60)
    print("ARIA CLI Import Benchmark")
    print("=" * 60)

    # First, ensure base modules are loaded
    importlib.import_module("aria_esi")
    importlib.import_module("aria_esi.core")

    # Benchmark individual imports
    results = []
    print(f"\n{'Module':<25} {'Time (ms)':>10}  Status")
    print("-" * 50)

    for name in COMMAND_MODULES:
        module_name, elapsed, error = benchmark_module(name)
        ms = elapsed * 1000
        status = f"ERROR: {error}" if error else "ok"
        print(f"  {module_name:<23} {ms:>8.1f}  {status}")
        results.append((module_name, elapsed, error))

    # Summary
    total = sum(r[1] for r in results)
    errors = [r for r in results if r[2]]
    slowest = sorted(results, key=lambda r: r[1], reverse=True)[:5]

    print(f"\n{'Total':<25} {total * 1000:>8.1f} ms")
    print(f"{'Modules':<25} {len(results):>8}")
    if errors:
        print(f"{'Errors':<25} {len(errors):>8}")

    print(f"\nSlowest 5 modules:")
    for name, elapsed, _ in slowest:
        print(f"  {name:<23} {elapsed * 1000:>8.1f} ms")

    # Benchmark full build_parser
    print(f"\n{'build_parser()':<25} ", end="", flush=True)
    bp_time = benchmark_register_parsers()
    print(f"{bp_time * 1000:>8.1f} ms")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
