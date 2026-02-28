#!/usr/bin/env python3
"""
Exercise output validator for ARIA skill exercises.

Validates exercise outputs against _index.json required_tools and known
quality patterns. Three validation passes:

1. Spec Dump Detection — did the agent reproduce SKILL.md instead of executing?
2. Required Tool Evidence — does output show signs of actual tool calls?
3. System Security Spot-Check — are system security values factually correct?

Usage:
    uv run python dev/scripts/exercise-validate.py --run-dir dev/reviews/exercise-outputs/20260227-142840
    uv run python dev/scripts/exercise-validate.py --run-dir ... --check spec-dump --verbose
    uv run python dev/scripts/exercise-validate.py --run-dir ... --json
    uv run python dev/scripts/exercise-validate.py --generate-reference
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
INDEX_PATH = PROJECT_ROOT / ".claude" / "skills" / "_index.json"
SKILLS_DIR = PROJECT_ROOT / ".claude" / "skills"
REFERENCE_PATH = PROJECT_ROOT / "dev" / "data" / "system_security_reference.json"

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

COLORS = {
    "FAIL": "\033[91m",
    "WARN": "\033[93m",
    "PASS": "\033[92m",
    "SKIP": "\033[90m",
    "RESET": "\033[0m",
    "BOLD": "\033[1m",
    "DIM": "\033[2m",
}


def colored(text: str, style: str) -> str:
    """Apply terminal colour if stdout is a tty."""
    if not sys.stdout.isatty():
        return text
    return f"{COLORS.get(style, '')}{text}{COLORS['RESET']}"


# ---------------------------------------------------------------------------
# Output file parser
# ---------------------------------------------------------------------------

FILENAME_RE = re.compile(r"^(\d+)-(.+)-q(\d+)\.md$")


def parse_output_file(path: Path) -> dict | None:
    """Parse an exercise output file, extracting metadata and content."""
    m = FILENAME_RE.match(path.name)
    if not m:
        return None
    seq, skill_name, query_num = m.group(1), m.group(2), m.group(3)
    text = path.read_text(errors="replace")

    # Split header from body at first ---
    parts = text.split("---", 1)
    header = parts[0] if len(parts) > 1 else ""
    body = parts[1] if len(parts) > 1 else text

    return {
        "path": path,
        "filename": path.name,
        "seq": int(seq),
        "skill": skill_name,
        "query_num": int(query_num),
        "header": header,
        "body": body,
        "text": text,
        "lines": text.splitlines(),
    }


# ---------------------------------------------------------------------------
# Pass 1: Spec Dump Detection
# ---------------------------------------------------------------------------

SPEC_DUMP_PATTERNS = [
    # Direct SKILL.md instruction markers
    re.compile(r"## Step \d+:", re.IGNORECASE),
    re.compile(r"## Execution Flow", re.IGNORECASE),
    re.compile(r"This skill generates.*at runtime", re.IGNORECASE),
    re.compile(r"Do not hardcode", re.IGNORECASE),
    re.compile(r"NEVER.*(?:from )?training data", re.IGNORECASE),
    re.compile(r"returned its base documentation", re.IGNORECASE),
    re.compile(r"returned (?:its |the )?documentation rather than", re.IGNORECASE),
    re.compile(r"## Command Syntax", re.IGNORECASE),
    re.compile(r"## ESI Failure Handling", re.IGNORECASE),
    re.compile(r"## Output Format", re.IGNORECASE),
    re.compile(r"## (?:When|If) (?:ESI|the pilot)", re.IGNORECASE),
    # Tool call documentation blocks (showing syntax, not results)
    re.compile(
        r"^\s*(?:sde|market|universe|fitting|killmails|pilot|skills|status)"
        r"\(action=",
        re.MULTILINE,
    ),
    # Authentication setup instructions (failed to execute)
    re.compile(r"Authentication Required", re.IGNORECASE),
    re.compile(r"uv run (?:python )?\.claude/scripts/aria-oauth", re.IGNORECASE),
    re.compile(r"uv run aria-oauth-setup", re.IGNORECASE),
    # "What This Skill Does" / "What This Query Does" (explaining instead of executing)
    re.compile(r"What This (?:Skill|Query) Does", re.IGNORECASE),
    # Calculation steps shown but not executed
    re.compile(r"Calculation Steps Required", re.IGNORECASE),
    re.compile(r"skill invocation (?:demonstrates|requires)", re.IGNORECASE),
    # Returning documentation instead of executing
    re.compile(r"returning the skill definition", re.IGNORECASE),
    # Frontmatter references (SKILL.md structure leaked)
    re.compile(r"frontmatter", re.IGNORECASE),
]


def compute_skill_overlap(output_lines: list[str], skill_name: str) -> float:
    """Compute line-level overlap between output and the actual SKILL.md."""
    skill_md_path = SKILLS_DIR / skill_name / "SKILL.md"
    if not skill_md_path.exists():
        return 0.0

    skill_lines = set()
    for line in skill_md_path.read_text().splitlines():
        stripped = line.strip()
        if stripped and len(stripped) > 10:  # Ignore trivial lines
            skill_lines.add(stripped)

    if not skill_lines:
        return 0.0

    # Skip header lines (metadata)
    content_lines = []
    past_header = False
    for line in output_lines:
        if line.strip() == "---":
            past_header = True
            continue
        if past_header:
            content_lines.append(line.strip())

    if not content_lines:
        return 0.0

    matches = sum(1 for line in content_lines if line in skill_lines and len(line) > 10)
    return matches / len(content_lines) if content_lines else 0.0


def check_spec_dump(entry: dict) -> tuple[str, list[str]]:
    """
    Check for spec dump patterns.

    Returns (verdict, reasons) where verdict is FAIL/WARN/PASS.
    """
    text = entry["text"]
    reasons = []

    # Count pattern matches
    matched_patterns = []
    for pattern in SPEC_DUMP_PATTERNS:
        if pattern.search(text):
            matched_patterns.append(pattern.pattern[:60])

    # Compute SKILL.md overlap
    overlap = compute_skill_overlap(entry["lines"], entry["skill"])

    if overlap > 0.4 and len(matched_patterns) >= 2:
        reasons.append(f"High SKILL.md overlap ({overlap:.0%}) + {len(matched_patterns)} spec patterns")
        return "FAIL", reasons

    if len(matched_patterns) >= 2:
        reasons.extend(matched_patterns[:5])
        return "FAIL", reasons

    if len(matched_patterns) == 1:
        reasons.extend(matched_patterns[:3])
        return "WARN", reasons

    return "PASS", []


# ---------------------------------------------------------------------------
# Pass 2: Required Tool Evidence
# ---------------------------------------------------------------------------

# Evidence patterns: what output should contain if a tool was actually called
TOOL_EVIDENCE = {
    "market.prices": [
        re.compile(r"\d[\d,.]*\s*ISK", re.IGNORECASE),
        re.compile(r"sell|buy|spread", re.IGNORECASE),
        re.compile(r"jita|amarr|dodixie|rens|hek", re.IGNORECASE),
    ],
    "market.valuation": [
        re.compile(r"\d[\d,.]*\s*ISK", re.IGNORECASE),
        re.compile(r"total.*value|valuation|worth", re.IGNORECASE),
    ],
    "market.arbitrage_scan": [
        re.compile(r"arbitrage|margin|profit", re.IGNORECASE),
        re.compile(r"\d[\d,.]*\s*(?:ISK|%)", re.IGNORECASE),
    ],
    "market.find_nearby": [
        re.compile(r"\d[\d,.]*\s*ISK", re.IGNORECASE),
        re.compile(r"jumps?\s*(?:away|from)", re.IGNORECASE),
    ],
    "sde.blueprint_info": [
        re.compile(r"(?:tritanium|pyerite|mexallon|isogen|nocxium|zydrine|megacyte|morphite)", re.IGNORECASE),
        re.compile(r"material|component|manufacture|blueprint", re.IGNORECASE),
    ],
    "sde.item_info": [
        re.compile(r"(?:type_id|group|category|slot|cpu|powergrid|volume)", re.IGNORECASE),
        re.compile(r"(?:cruiser|battleship|frigate|destroyer|battlecruiser|industrial)", re.IGNORECASE),
    ],
    "sde.agent_search": [
        re.compile(r"agent|level\s*[1-5]|division", re.IGNORECASE),
        re.compile(r"standing|security|distribution|mining", re.IGNORECASE),
    ],
    "sde.meta_variants": [
        re.compile(r"(?:T2|Tech II|faction|officer|deadspace|storyline)", re.IGNORECASE),
        re.compile(r"variant|meta|upgrade|downgrade", re.IGNORECASE),
    ],
    "sde.resolve_names": [
        re.compile(r"(?:alliance|corporation).*(?:id|ID|\d{5,})", re.IGNORECASE),
        re.compile(r"resolved|entity|name", re.IGNORECASE),
    ],
    "fitting.calculate_stats": [
        re.compile(r"\d[\d,.]*\s*(?:DPS|dps)", re.IGNORECASE),
        re.compile(r"\d[\d,.]*\s*(?:EHP|ehp|HP|hp)", re.IGNORECASE),
        re.compile(r"(?:CPU|powergrid|PG|capacitor)", re.IGNORECASE),
    ],
    "fitting.extract_requirements": [
        re.compile(r"skill.*(?:level|requirement|prerequisite)", re.IGNORECASE),
    ],
    "universe.route": [
        re.compile(r"\d+\s*jumps?", re.IGNORECASE),
        re.compile(r"(?:route|path|waypoint)", re.IGNORECASE),
    ],
    "universe.activity": [
        re.compile(r"\d+\s*(?:kills?|pods?|ships?)", re.IGNORECASE),
        re.compile(r"activity|traffic|dangerous", re.IGNORECASE),
    ],
    "universe.hotspots": [
        re.compile(r"\d+\s*(?:kills?|pods?)", re.IGNORECASE),
        re.compile(r"hotspot|activity|active", re.IGNORECASE),
    ],
    "universe.local_area": [
        re.compile(r"(?:THREAT|threat).*(?:LEVEL|level|LOW|MODERATE|HIGH|CRITICAL)", re.IGNORECASE),
        re.compile(r"\d+\s*(?:kills?|jumps?)", re.IGNORECASE),
    ],
    "killmails.analyze": [
        re.compile(r"victim|attacker|final.blow", re.IGNORECASE),
        re.compile(r"zkillboard|damage.*taken|killmail", re.IGNORECASE),
    ],
    "pilot.mail_list": [
        re.compile(r"(?:mail|message|inbox|unread)", re.IGNORECASE),
        re.compile(r"(?:from|sender|subject|timestamp)", re.IGNORECASE),
    ],
    "pilot.mining_ledger": [
        re.compile(r"(?:mining|mined|ore|extracted)", re.IGNORECASE),
        re.compile(r"(?:veldspar|scordite|pyroxeres|plagioclase|quantity)", re.IGNORECASE),
    ],
    "skills.easy_80_plan": [
        re.compile(r"(?:skill|training).*(?:time|plan|queue)", re.IGNORECASE),
        re.compile(r"(?:level\s*[IVX1-5]|days?|hours?)", re.IGNORECASE),
    ],
}


def check_tool_evidence(entry: dict, index_data: dict) -> tuple[str, list[str]]:
    """
    Check if output shows evidence of required tool calls.

    Returns (verdict, reasons).
    """
    skill_name = entry["skill"]
    skills_by_name = {s["name"]: s for s in index_data["skills"]}

    if skill_name not in skills_by_name:
        return "SKIP", [f"Skill '{skill_name}' not in index"]

    required = skills_by_name[skill_name].get("required_tools", [])
    if not required:
        return "PASS", ["No required tools"]

    text = entry["text"]
    missing = []
    found = []

    for tool_ref in required:
        evidence_patterns = TOOL_EVIDENCE.get(tool_ref, [])
        if not evidence_patterns:
            # No evidence patterns defined for this tool — skip
            found.append(tool_ref)
            continue

        # Require at least 1 of the evidence patterns to match
        tool_found = any(p.search(text) for p in evidence_patterns)
        if tool_found:
            found.append(tool_ref)
        else:
            missing.append(tool_ref)

    if not missing:
        return "PASS", [f"All {len(required)} tools evidenced"]

    if len(missing) == len(required):
        return "FAIL", [f"No evidence for any required tool: {', '.join(missing)}"]

    return "WARN", [f"Missing evidence for: {', '.join(missing)}"]


# ---------------------------------------------------------------------------
# Pass 3: System Security Spot-Check
# ---------------------------------------------------------------------------

SEC_STATUS_PATTERNS = [
    # "Tama (0.3)" or "Tama — 0.3 security"
    re.compile(
        r"(?P<system>[A-Z][A-Za-z0-9-]+(?:-[A-Z0-9]+)*)"
        r"\s*[\(—–-]\s*"
        r"(?P<sec>-?\d+\.\d+)"
        r"\s*(?:security|sec)?\s*\)?",
    ),
    # "| Tama | 0.3 |" table format
    re.compile(
        r"\|\s*(?P<system>[A-Z][A-Za-z0-9-]+(?:-[A-Z0-9]+)*)\s*\|"
        r"\s*(?P<sec>-?\d+\.\d+)\s*\|",
    ),
    # "Tama (sec: 0.3)" or "Tama [0.3]"
    re.compile(
        r"(?P<system>[A-Z][A-Za-z0-9-]+(?:-[A-Z0-9]+)*)"
        r"\s*[\[\(](?:sec:?\s*)?(?P<sec>-?\d+\.\d+)\s*[\]\)]",
    ),
]


def extract_system_security_pairs(text: str) -> list[tuple[str, float]]:
    """Extract (system_name, security_value) pairs from text."""
    pairs = []
    seen = set()
    for pattern in SEC_STATUS_PATTERNS:
        for m in pattern.finditer(text):
            system = m.group("system")
            sec = float(m.group("sec"))
            key = (system, sec)
            if key not in seen:
                seen.add(key)
                pairs.append((system, sec))
    return pairs


def check_system_security(entry: dict, reference: dict) -> tuple[str, list[str]]:
    """
    Spot-check system security values against reference data.

    Returns (verdict, reasons).
    """
    if not reference:
        return "SKIP", ["No reference data"]

    pairs = extract_system_security_pairs(entry["text"])
    if not pairs:
        return "PASS", ["No security values to check"]

    mismatches = []
    checked = 0
    for system, claimed_sec in pairs:
        if system in reference:
            checked += 1
            actual_sec = reference[system]
            if abs(claimed_sec - actual_sec) > 0.05:
                mismatches.append(
                    f"{system}: claimed {claimed_sec:.1f}, actual {actual_sec:.1f}"
                )

    if not checked:
        return "PASS", ["No known systems to verify"]

    if len(mismatches) >= 2:
        return "FAIL", mismatches
    if len(mismatches) == 1:
        return "WARN", mismatches
    return "PASS", [f"Verified {checked} system(s)"]


# ---------------------------------------------------------------------------
# Verdict aggregation
# ---------------------------------------------------------------------------


def aggregate_verdict(
    spec_dump: tuple[str, list[str]],
    tool_evidence: tuple[str, list[str]],
    security: tuple[str, list[str]],
) -> str:
    """Aggregate pass verdicts into a final verdict."""
    verdicts = [spec_dump[0], tool_evidence[0], security[0]]

    # FAIL if any pass FAILs
    if "FAIL" in verdicts:
        return "FAIL"

    # Also FAIL if spec dump + tool evidence both WARN (strong correlation)
    if spec_dump[0] == "WARN" and tool_evidence[0] == "WARN":
        return "FAIL"

    if "WARN" in verdicts:
        return "WARN"

    return "PASS"


# ---------------------------------------------------------------------------
# Reference data generation
# ---------------------------------------------------------------------------


def generate_reference():
    """Generate system_security_reference.json from universe MCP data."""
    # Import here to avoid hard dependency
    try:
        import subprocess

        # Use a python script that calls the universe tool
        # We'll query common systems used in exercises
        systems = [
            "Jita", "Amarr", "Dodixie", "Rens", "Hek",
            "Tama", "Amamake", "Rancer", "Niarja", "Uedama",
            "Perimeter", "Sivala", "1DQ1-A", "Masalle",
            "EC-P8R", "M-OEE8", "HED-GP", "D-PNP9",
        ]

        print(f"Generating reference for {len(systems)} systems...")
        print("Using universe MCP via aria-esi...")

        result = subprocess.run(
            ["uv", "run", "aria-esi", "sysinfo"] + systems,
            capture_output=True, text=True, cwd=str(PROJECT_ROOT),
        )

        if result.returncode != 0:
            print(f"Error running aria-esi: {result.stderr}", file=sys.stderr)
            sys.exit(1)

        # Parse output for security values
        reference = {}
        for line in result.stdout.splitlines():
            # Expected format: "System: sec_status"
            m = re.match(r"(\S+):\s*(-?\d+\.\d+)", line)
            if m:
                reference[m.group(1)] = float(m.group(2))

        if not reference:
            print("Warning: Could not parse system security from CLI output.")
            print("Falling back to manual reference data.")
            reference = _get_fallback_reference()

        out_path = REFERENCE_PATH
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(reference, indent=2, sort_keys=True) + "\n")
        print(f"Wrote {len(reference)} systems to {out_path}")

    except Exception as e:
        print(f"Error generating reference: {e}", file=sys.stderr)
        print("Using fallback reference data.")
        reference = _get_fallback_reference()
        out_path = REFERENCE_PATH
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(reference, indent=2, sort_keys=True) + "\n")
        print(f"Wrote {len(reference)} systems to {out_path}")


def _get_fallback_reference() -> dict:
    """Hardcoded reference for common systems (verified via MCP 2026-02-27).

    Values use EVE client truncation convention (towards zero).
    """
    return {
        "1DQ1-A": -0.3,
        "Amarr": 1.0,
        "Amamake": 0.4,
        "D-PNP9": -0.5,
        "Dodixie": 0.8,
        "EC-P8R": -0.4,
        "HED-GP": -0.1,
        "Hek": 0.8,
        "Jita": 0.9,
        "M-OEE8": -0.2,
        "Masalle": 0.7,
        "Niarja": -1.0,
        "Perimeter": 0.9,
        "Rancer": 0.3,
        "Rens": 0.8,
        "Sivala": 0.5,
        "Tama": 0.2,
        "Uedama": 0.5,
    }


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


def load_index() -> dict:
    """Load the skill index."""
    return json.loads(INDEX_PATH.read_text())


def load_reference() -> dict:
    """Load the system security reference, if available."""
    if REFERENCE_PATH.exists():
        return json.loads(REFERENCE_PATH.read_text())
    return _get_fallback_reference()


def validate_run(
    run_dir: Path,
    checks: list[str] | None = None,
    verbose: bool = False,
) -> list[dict]:
    """Validate all output files in a run directory."""
    index_data = load_index()
    reference = load_reference()

    all_checks = {"spec-dump", "tool-evidence", "security"}
    active_checks = set(checks) if checks else all_checks

    results = []
    for path in sorted(run_dir.glob("*.md")):
        if path.name == "MANIFEST.md":
            continue

        entry = parse_output_file(path)
        if not entry:
            continue

        result = {
            "filename": path.name,
            "skill": entry["skill"],
            "query_num": entry["query_num"],
            "passes": {},
        }

        if "spec-dump" in active_checks:
            verdict, reasons = check_spec_dump(entry)
            result["passes"]["spec-dump"] = {"verdict": verdict, "reasons": reasons}

        if "tool-evidence" in active_checks:
            verdict, reasons = check_tool_evidence(entry, index_data)
            result["passes"]["tool-evidence"] = {"verdict": verdict, "reasons": reasons}

        if "security" in active_checks:
            verdict, reasons = check_system_security(entry, reference)
            result["passes"]["security"] = {"verdict": verdict, "reasons": reasons}

        # Compute final verdict
        spec = result["passes"].get("spec-dump", {"verdict": "PASS", "reasons": []})
        tool = result["passes"].get("tool-evidence", {"verdict": "PASS", "reasons": []})
        sec = result["passes"].get("security", {"verdict": "PASS", "reasons": []})

        result["verdict"] = aggregate_verdict(
            (spec["verdict"], spec["reasons"]),
            (tool["verdict"], tool["reasons"]),
            (sec["verdict"], sec["reasons"]),
        )

        results.append(result)

    return results


def print_results(results: list[dict], verbose: bool = False) -> None:
    """Print a formatted report to stdout."""
    # Per-file results
    for r in results:
        verdict = r["verdict"]
        tag = colored(f"[{verdict}]", verdict)
        print(f"  {tag} {r['filename']}")

        if verbose or verdict in ("FAIL", "WARN"):
            for pass_name, pass_data in r["passes"].items():
                pv = pass_data["verdict"]
                if pv in ("FAIL", "WARN") or verbose:
                    reasons = "; ".join(pass_data["reasons"][:3])
                    ptag = colored(pv, pv)
                    print(f"       {pass_name}: {ptag} — {reasons}")

    # Summary
    total = len(results)
    fails = sum(1 for r in results if r["verdict"] == "FAIL")
    warns = sum(1 for r in results if r["verdict"] == "WARN")
    passes = sum(1 for r in results if r["verdict"] == "PASS")
    skips = sum(1 for r in results if r["verdict"] == "SKIP")

    print()
    print(colored("=" * 60, "BOLD"))
    print(f"  Total: {total}  |  "
          f"{colored(f'PASS: {passes}', 'PASS')}  |  "
          f"{colored(f'WARN: {warns}', 'WARN')}  |  "
          f"{colored(f'FAIL: {fails}', 'FAIL')}"
          + (f"  |  {colored(f'SKIP: {skips}', 'SKIP')}" if skips else ""))
    print(colored("=" * 60, "BOLD"))

    # Per-skill summary for failures
    if fails or warns:
        print()
        fail_skills: dict[str, list[str]] = {}
        for r in results:
            if r["verdict"] in ("FAIL", "WARN"):
                fail_skills.setdefault(r["skill"], []).append(
                    f"{r['filename']} ({r['verdict']})"
                )
        for skill, files in sorted(fail_skills.items()):
            print(f"  {colored(skill, 'BOLD')}: {', '.join(files)}")


def print_json(results: list[dict]) -> None:
    """Print results as JSON."""
    output = {
        "total": len(results),
        "pass": sum(1 for r in results if r["verdict"] == "PASS"),
        "warn": sum(1 for r in results if r["verdict"] == "WARN"),
        "fail": sum(1 for r in results if r["verdict"] == "FAIL"),
        "results": results,
    }
    # Convert Path objects to strings
    print(json.dumps(output, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser(
        description="Validate ARIA exercise outputs",
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        help="Path to exercise output directory",
    )
    parser.add_argument(
        "--check",
        choices=["spec-dump", "tool-evidence", "security"],
        action="append",
        help="Run only specific check(s). Can be repeated.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show all pass results, not just failures",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--generate-reference",
        action="store_true",
        help="Generate system_security_reference.json and exit",
    )

    args = parser.parse_args()

    if args.generate_reference:
        generate_reference()
        return

    if not args.run_dir:
        parser.error("--run-dir is required (or use --generate-reference)")

    if not args.run_dir.is_dir():
        print(f"Error: {args.run_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    results = validate_run(args.run_dir, checks=args.check, verbose=args.verbose)

    if args.json_output:
        print_json(results)
    else:
        print()
        print(colored(f"  Validating: {args.run_dir}", "BOLD"))
        print()
        print_results(results, verbose=args.verbose)

    # Exit code: 1 if any FAILs
    if any(r["verdict"] == "FAIL" for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
