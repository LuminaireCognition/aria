#!/usr/bin/env python3
"""
Exercise runner for ARIA skill exercises.

Parses SKILL_EXERCISE_QUERIES.md, runs each query via `claude -p`,
and captures stdout per output file.

Usage:
    uv run python dev/scripts/exercise-runner.py --filter NONE,LOW
    uv run python dev/scripts/exercise-runner.py --skills help,price --dry-run
    uv run python dev/scripts/exercise-runner.py --filter NONE --parallel 4 --timeout 180
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
QUERIES_PATH = PROJECT_ROOT / "dev" / "reviews" / "SKILL_EXERCISE_QUERIES.md"
OUTPUT_BASE = PROJECT_ROOT / "dev" / "reviews" / "exercise-outputs"

# ---------------------------------------------------------------------------
# Query parser
# ---------------------------------------------------------------------------

# Matches: ### skill-name
SKILL_RE = re.compile(r"^###\s+(\S+)")
# Matches: - **ESI:** LEVEL
ESI_RE = re.compile(r"^\s*-\s*\*\*ESI:\*\*\s*(\w+)")
# Matches: N. "query text"
QUERY_RE = re.compile(r'^\s*(\d+)\.\s*"(.+)"$')


def parse_queries(md_path: Path) -> list[dict]:
    """
    Parse SKILL_EXERCISE_QUERIES.md into a list of query dicts.

    Each dict: {skill, esi_level, query_num, query_text}
    Multi-line queries use literal \\n in the markdown (on one line).
    """
    text = md_path.read_text()
    lines = text.splitlines()

    queries = []
    current_skill = None
    current_esi = None

    for line in lines:
        # Skill header
        m = SKILL_RE.match(line)
        if m:
            raw = m.group(1)
            # Strip trailing markup like *(persona-exclusive: paria)*
            current_skill = raw.split("*")[0].rstrip()
            current_esi = None
            continue

        # ESI level
        m = ESI_RE.match(line)
        if m:
            current_esi = m.group(1)
            continue

        # Query line
        m = QUERY_RE.match(line)
        if m and current_skill:
            query_num = int(m.group(1))
            query_text = m.group(2)
            # Convert literal \n to actual newlines (for EFT blocks etc.)
            query_text = query_text.replace("\\n", "\n")
            queries.append({
                "skill": current_skill,
                "esi_level": current_esi or "UKN",
                "query_num": query_num,
                "query_text": query_text,
            })

    return queries


# ---------------------------------------------------------------------------
# Query filter
# ---------------------------------------------------------------------------


def filter_queries(
    queries: list[dict],
    esi_levels: list[str] | None = None,
    skill_names: list[str] | None = None,
) -> list[dict]:
    """Filter queries by ESI level and/or skill name."""
    result = queries
    if esi_levels:
        levels = {l.upper() for l in esi_levels}
        result = [q for q in result if q["esi_level"] in levels]
    if skill_names:
        names = {n.lower() for n in skill_names}
        result = [q for q in result if q["skill"].lower() in names]
    return result


# ---------------------------------------------------------------------------
# Query runner
# ---------------------------------------------------------------------------


def run_query(
    query: dict,
    output_dir: Path,
    seq: int,
    timeout: int = 120,
    model: str | None = None,
) -> dict:
    """
    Run a single query via `claude -p` and capture output.

    Returns a result dict with status, output_path, duration, etc.
    """
    filename = f"{seq:02d}-{query['skill']}-q{query['query_num']}.md"
    output_path = output_dir / filename

    # Build header
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    header = (
        f"# Skill: {query['skill']}\n"
        f"# Query: \"{query['query_text'][:200]}\"\n"
        f"# ESI Level: {query['esi_level']}\n"
        f"# Timestamp: {timestamp}\n"
        f"---\n\n"
    )

    # Build command
    cmd = ["claude", "-p"]
    if model:
        cmd.extend(["--model", model])

    start = time.monotonic()

    try:
        result = subprocess.run(
            cmd,
            input=query["query_text"],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(PROJECT_ROOT),
        )
        duration = time.monotonic() - start

        if result.returncode != 0 and not result.stdout.strip():
            body = f"# ERROR (exit {result.returncode})\n\n{result.stderr[:500]}"
        elif not result.stdout.strip():
            body = "# EMPTY RESPONSE"
        else:
            body = result.stdout

        output_path.write_text(header + body)

        return {
            "seq": seq,
            "filename": filename,
            "skill": query["skill"],
            "query_num": query["query_num"],
            "status": "ok" if result.returncode == 0 else f"error:{result.returncode}",
            "duration": round(duration, 1),
            "lines": len(body.splitlines()),
        }

    except subprocess.TimeoutExpired:
        duration = time.monotonic() - start
        body = f"# TIMEOUT after {timeout}s"
        output_path.write_text(header + body)
        return {
            "seq": seq,
            "filename": filename,
            "skill": query["skill"],
            "query_num": query["query_num"],
            "status": "timeout",
            "duration": round(duration, 1),
            "lines": 1,
        }


# ---------------------------------------------------------------------------
# Manifest generation
# ---------------------------------------------------------------------------


def generate_manifest(
    output_dir: Path,
    queries: list[dict],
    results: list[dict],
    filter_desc: str,
    model: str | None,
    timeout: int,
    parallel: int,
) -> None:
    """Generate MANIFEST.md with run metadata."""
    run_id = output_dir.name
    total_lines = sum(r["lines"] for r in results)
    total_files = len(results)
    ok = sum(1 for r in results if r["status"] == "ok")
    errors = sum(1 for r in results if r["status"].startswith("error"))
    timeouts = sum(1 for r in results if r["status"] == "timeout")

    lines = [
        "# Exercise Run Manifest\n",
        f"- **Run ID:** {run_id}",
        f"- **Date:** {datetime.now().strftime('%Y-%m-%d')}",
        f"- **Filter:** {filter_desc}",
        f"- **Model:** {model or 'default'}",
        f"- **Timeout:** {timeout}s",
        f"- **Parallel workers:** {parallel}",
        f"- **Queries executed:** {total_files}",
        f"- **Results:** {ok} ok, {errors} errors, {timeouts} timeouts",
        f"- **Total output:** {total_files} files, {total_lines} lines",
        "",
        "## File Index",
        "",
        "| # | Skill | Query | ESI | Status | Duration |",
        "|---|-------|-------|-----|--------|----------|",
    ]

    for r, q in zip(results, queries):
        query_short = q["query_text"][:60].replace("\n", " ").replace("|", "\\|")
        lines.append(
            f"| {r['seq']:02d} | {r['skill']} | {query_short} | "
            f"{q['esi_level']} | {r['status']} | {r['duration']}s |"
        )

    manifest = output_dir / "MANIFEST.md"
    manifest.write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Run ARIA skill exercise queries",
    )
    parser.add_argument(
        "--filter",
        help="Comma-separated ESI levels to include (e.g., NONE,LOW)",
    )
    parser.add_argument(
        "--skills",
        help="Comma-separated skill names to include (e.g., help,price)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Timeout per query in seconds (default: 120)",
    )
    parser.add_argument(
        "--model",
        help="Claude model to use (passed to claude -p --model)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and filter queries without executing",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="Number of parallel workers (default: 1)",
    )
    parser.add_argument(
        "--queries-file",
        type=Path,
        default=QUERIES_PATH,
        help="Path to queries markdown file",
    )

    args = parser.parse_args()

    # Fail fast: check for claude CLI
    if not args.dry_run:
        if not shutil.which("claude"):
            print("Error: 'claude' CLI not found in PATH", file=sys.stderr)
            sys.exit(1)

    # Parse queries
    queries = parse_queries(args.queries_file)
    print(f"Parsed {len(queries)} queries from {args.queries_file.name}")

    # Filter
    esi_levels = args.filter.split(",") if args.filter else None
    skill_names = args.skills.split(",") if args.skills else None
    filtered = filter_queries(queries, esi_levels, skill_names)

    filter_desc_parts = []
    if esi_levels:
        filter_desc_parts.append(f"ESI:{','.join(esi_levels)}")
    if skill_names:
        filter_desc_parts.append(f"skills:{','.join(skill_names)}")
    filter_desc = " + ".join(filter_desc_parts) if filter_desc_parts else "ALL"

    print(f"After filtering ({filter_desc}): {len(filtered)} queries")

    if args.dry_run:
        print()
        print("Dry run — queries that would execute:")
        print()
        for i, q in enumerate(filtered, 1):
            query_short = q["query_text"][:80].replace("\n", "\\n")
            print(f"  {i:02d}. [{q['skill']}] (ESI:{q['esi_level']}) \"{query_short}\"")
        print()
        print(f"Total: {len(filtered)} queries")
        return

    if not filtered:
        print("No queries match the filter. Nothing to do.")
        return

    # Create output directory
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir = OUTPUT_BASE / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {output_dir}")

    # Run queries
    results = []
    if args.parallel <= 1:
        # Sequential execution
        for seq, query in enumerate(filtered, 1):
            query_short = query["query_text"][:60].replace("\n", "\\n")
            print(f"  [{seq:02d}/{len(filtered)}] {query['skill']} q{query['query_num']}: \"{query_short}\"")
            result = run_query(query, output_dir, seq, args.timeout, args.model)
            print(f"          → {result['status']} ({result['duration']}s, {result['lines']} lines)")
            results.append(result)
    else:
        # Parallel execution
        futures = {}
        with ThreadPoolExecutor(max_workers=args.parallel) as executor:
            for seq, query in enumerate(filtered, 1):
                future = executor.submit(
                    run_query, query, output_dir, seq, args.timeout, args.model,
                )
                futures[future] = (seq, query)

            for future in as_completed(futures):
                seq, query = futures[future]
                result = future.result()
                query_short = query["query_text"][:60].replace("\n", "\\n")
                print(f"  [{seq:02d}/{len(filtered)}] {query['skill']} q{query['query_num']}: "
                      f"{result['status']} ({result['duration']}s)")
                results.append(result)

        # Sort results by sequence number
        results.sort(key=lambda r: r["seq"])

    # Generate manifest
    generate_manifest(
        output_dir, filtered, results,
        filter_desc, args.model, args.timeout, args.parallel,
    )

    # Summary
    ok = sum(1 for r in results if r["status"] == "ok")
    errors = sum(1 for r in results if r["status"].startswith("error"))
    timeouts = sum(1 for r in results if r["status"] == "timeout")
    print()
    print(f"Done: {ok} ok, {errors} errors, {timeouts} timeouts")
    print(f"Output: {output_dir}")


if __name__ == "__main__":
    main()
