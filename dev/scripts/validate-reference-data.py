#!/usr/bin/env python3
"""
Validate internal consistency across ARIA reference data files.

Checks that damage profiles, hardener modules, drone/missile recommendations,
and mission intel all agree with the primary source of truth (npc_damage_types.md).

Usage:
    uv run python dev/scripts/validate-reference-data.py
    uv run python dev/scripts/validate-reference-data.py --verbose

Exit codes:
    0 = all checks pass (warnings are OK)
    1 = at least one FAIL
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# ---------------------------------------------------------------------------
# File paths
# ---------------------------------------------------------------------------

NPC_DAMAGE_PATH = PROJECT_ROOT / "reference" / "mechanics" / "npc_damage_types.md"
FACTION_TUNING_PATH = (
    PROJECT_ROOT / "reference" / "archetypes" / "_shared" / "faction_tuning.yaml"
)
PVE_INDEX_PATH = PROJECT_ROOT / "reference" / "pve-intel" / "INDEX.md"
MISSIONS_DIR = PROJECT_ROOT / "reference" / "pve-intel" / "missions"
DRONES_PATH = PROJECT_ROOT / "reference" / "mechanics" / "drones.json"
MISSILES_PATH = PROJECT_ROOT / "reference" / "mechanics" / "missiles.json"

# ---------------------------------------------------------------------------
# Colour helpers (from exercise-validate.py pattern)
# ---------------------------------------------------------------------------

COLORS = {
    "FAIL": "\033[91m",
    "WARN": "\033[93m",
    "PASS": "\033[92m",
    "SKIP": "\033[90m",
    "RESET": "\033[0m",
    "BOLD": "\033[1m",
}


def colored(text: str, style: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"{COLORS.get(style, '')}{text}{COLORS['RESET']}"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class FactionDamage:
    they_deal: list[str]  # ["Kinetic", "Thermal"] — canonical form
    you_deal: list[str]  # ["Thermal", "Kinetic"] — primary first
    is_omni: bool = False
    is_mixed: bool = False


@dataclass
class CheckResult:
    check: str  # e.g. "hardener_consistency"
    subject: str  # e.g. "serpentis (armor_active)"
    verdict: str  # PASS / FAIL / WARN / SKIP
    detail: str = ""  # human-readable explanation (empty for PASS)


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

ABBREV_MAP = {
    "therm": "Thermal",
    "thermal": "Thermal",
    "kin": "Kinetic",
    "kinetic": "Kinetic",
    "exp": "Explosive",
    "explosive": "Explosive",
    "em": "EM",
}

FACTION_NAME_MAP = {
    "serpentis": "serpentis",
    "angel cartel": "angel_cartel",
    "blood raiders": "blood_raiders",
    "guristas": "guristas",
    "guristas pirates": "guristas",
    "sansha's nation": "sansha",
    "sansha": "sansha",
    "mordu's legion": "mordus_legion",
    "rogue drones": "rogue_drones",
    "equilibrium of mankind": "equilibrium_of_mankind",
    "eom": "equilibrium_of_mankind",
    "mercenaries": "mercenaries",
    "sleepers": "sleepers",
    "triglavians": "triglavian",
    "triglavian": "triglavian",
    "amarr empire": "amarr_empire",
    "caldari state": "caldari_state",
    "gallente federation": "gallente_federation",
    "minmatar republic": "minmatar_republic",
}


def normalize_damage_types(raw: str) -> list[str]:
    """Parse a damage type string into canonical sorted list.

    Handles: "55% Therm / 45% Kin", "Kin/Therm", "EM > Therm",
    "Kinetic, Thermal", "Omni", "Mixed".
    """
    if not raw or raw.strip().lower() in ("omni", "omni (varies)", "mixed"):
        return []
    # Strip percentages
    cleaned = re.sub(r"\d+%\s*", "", raw)
    # Split on / , > or comma
    parts = re.split(r"\s*[/,>]\s*", cleaned)
    result = []
    for p in parts:
        p = p.strip().lower()
        if p and p in ABBREV_MAP:
            result.append(ABBREV_MAP[p])
    return sorted(set(result))


def normalize_damage_types_ordered(raw: str) -> list[str]:
    """Like normalize_damage_types but preserves primary-first ordering."""
    if not raw or raw.strip().lower() in ("omni", "omni (varies)", "mixed"):
        return []
    cleaned = re.sub(r"\d+%\s*", "", raw)
    parts = re.split(r"\s*[/,>]\s*", cleaned)
    result = []
    seen: set[str] = set()
    for p in parts:
        p = p.strip().lower()
        if p and p in ABBREV_MAP:
            canonical = ABBREV_MAP[p]
            if canonical not in seen:
                result.append(canonical)
                seen.add(canonical)
    return result


def normalize_faction_name(display: str) -> str:
    """Convert display faction name to snake_case key."""
    cleaned = display.strip().strip("*").strip().lower()
    return FACTION_NAME_MAP.get(cleaned, cleaned.replace(" ", "_").replace("'", ""))


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def parse_npc_damage_types() -> dict[str, FactionDamage]:
    """Parse npc_damage_types.md into {snake_case_key: FactionDamage}.

    Only parses tables that have "They Deal" and "You Deal" columns
    (Pirate, Empire, Special faction tables). Stops at other tables.
    """
    text = NPC_DAMAGE_PATH.read_text()
    result: dict[str, FactionDamage] = {}

    row_re = re.compile(
        r"\|\s*\*\*(.+?)\*\*\s*\|"  # faction name (bold)
        r"\s*(.+?)\s*\|"  # they deal
        r"\s*(.+?)\s*\|"  # you deal
    )

    in_faction_table = False
    for line in text.splitlines():
        # Detect faction tables by header row
        if "They Deal" in line and "You Deal" in line:
            in_faction_table = True
            continue
        # Any other table header (e.g. EWAR Types) ends faction table
        if line.strip().startswith("##"):
            in_faction_table = False
            continue
        if not in_faction_table:
            continue
        if line.strip().startswith("|---"):
            continue

        m = row_re.match(line.strip())
        if not m:
            continue

        display_name = m.group(1).strip()
        they_deal_raw = m.group(2).strip()
        you_deal_raw = m.group(3).strip()

        key = normalize_faction_name(display_name)
        is_omni = "omni" in they_deal_raw.lower()
        is_mixed = "mixed" in they_deal_raw.lower()

        result[key] = FactionDamage(
            they_deal=normalize_damage_types(they_deal_raw),
            you_deal=normalize_damage_types_ordered(you_deal_raw),
            is_omni=is_omni,
            is_mixed=is_mixed,
        )

    return result


def parse_faction_tuning() -> dict[str, dict[str, dict]]:
    """Parse faction_tuning.yaml into {profile: {faction: entry}}."""
    import yaml

    data = yaml.safe_load(FACTION_TUNING_PATH.read_text())

    profiles: dict[str, dict[str, dict]] = {}
    profile_keys = [
        "armor_active",
        "shield_passive",
        "shield_active",
        "shield_buffer",
    ]

    for pkey in profile_keys:
        if pkey in data and isinstance(data[pkey], dict):
            profiles[pkey] = data[pkey]

    return profiles


def resolve_inherit(
    profiles: dict[str, dict[str, dict]], profile: str, faction: str
) -> dict | None:
    """Resolve a faction entry, following inherit chains."""
    if profile not in profiles or faction not in profiles[profile]:
        return None
    entry = profiles[profile][faction]
    if "inherit" in entry:
        parent = entry["inherit"]
        return resolve_inherit(profiles, profile, parent)
    return entry


def extract_hardener_types(module_list: list[str]) -> tuple[list[str], bool]:
    """Extract damage types from hardener module names.

    Returns (sorted damage types, has_multispectrum).
    """
    types: list[str] = []
    has_multi = False

    for mod in module_list:
        mod_lower = mod.lower()
        if "multispectrum" in mod_lower or "adaptive" in mod_lower:
            has_multi = True
            continue
        for dtype in ["EM", "Thermal", "Kinetic", "Explosive"]:
            if dtype.lower() in mod_lower:
                if dtype not in types:
                    types.append(dtype)
                break

    return sorted(types), has_multi


def parse_index_damage_table() -> dict[str, FactionDamage]:
    """Parse INDEX.md Damage Quick Reference table."""
    text = PVE_INDEX_PATH.read_text()
    result: dict[str, FactionDamage] = {}

    # Match rows: | Faction | They Deal | You Deal |
    row_re = re.compile(
        r"\|\s*(.+?)\s*\|"  # faction
        r"\s*(.+?)\s*\|"  # they deal
        r"\s*(.+?)\s*\|"  # you deal
    )

    in_table = False
    for line in text.splitlines():
        if "They Deal" in line and "You Deal" in line:
            in_table = True
            continue
        if in_table and line.strip().startswith("|---"):
            continue
        if in_table and line.strip().startswith("|"):
            m = row_re.match(line.strip())
            if m:
                faction_display = m.group(1).strip()
                they_raw = m.group(2).strip()
                you_raw = m.group(3).strip()

                key = normalize_faction_name(faction_display)
                is_omni = "omni" in they_raw.lower()
                is_mixed = "mixed" in they_raw.lower()

                result[key] = FactionDamage(
                    they_deal=normalize_damage_types(they_raw),
                    you_deal=normalize_damage_types_ordered(you_raw),
                    is_omni=is_omni,
                    is_mixed=is_mixed,
                )
        elif in_table and not line.strip().startswith("|"):
            in_table = False

    return result


def parse_mission_quick_ref(path: Path) -> dict[str, str]:
    """Parse a mission file's Quick Reference table into {field: value}."""
    text = path.read_text()
    result: dict[str, str] = {}

    row_re = re.compile(r"\|\s*(.+?)\s*\|\s*(.+?)\s*\|")
    in_qr = False
    for line in text.splitlines():
        if "Quick Reference" in line:
            in_qr = True
            continue
        if in_qr and line.strip().startswith("|---"):
            continue
        if in_qr and line.strip().startswith("| Field"):
            continue
        if in_qr and line.strip().startswith("|"):
            m = row_re.match(line.strip())
            if m:
                field_name = m.group(1).strip()
                value = m.group(2).strip()
                result[field_name.lower()] = value
        elif in_qr and not line.strip().startswith("|"):
            break

    return result


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

# Factions to skip in hardener/completeness checks
SKIP_FACTIONS = {"sleepers"}
EMPIRE_FACTIONS = {"amarr_empire", "caldari_state", "gallente_federation", "minmatar_republic"}

# Common factions that should appear in all tank profiles
COMMON_FACTIONS = {
    "serpentis", "angel_cartel", "blood_raiders", "guristas", "sansha",
    "equilibrium_of_mankind", "rogue_drones", "mercenaries", "triglavian",
}


def check_hardener_consistency(
    npc_damage: dict[str, FactionDamage],
    profiles: dict[str, dict[str, dict]],
) -> list[CheckResult]:
    """Check 1: Hardener modules match 'They Deal' damage types."""
    results: list[CheckResult] = []

    for faction, fd in npc_damage.items():
        if faction in SKIP_FACTIONS or faction in EMPIRE_FACTIONS:
            continue

        for profile_name in profiles:
            subject = f"{faction} ({profile_name})"

            if fd.is_omni or fd.is_mixed:
                results.append(CheckResult(
                    "hardener_consistency", subject, "SKIP",
                    "Omni/Mixed damage — hardener check not applicable",
                ))
                continue

            entry = resolve_inherit(profiles, profile_name, faction)
            if entry is None:
                # Handled by completeness check
                continue

            modules = entry.get("modules", [])
            resist_mods: list[str] = []
            for mod_entry in modules:
                if mod_entry.get("slot") == "resist":
                    resist_mods = mod_entry.get("to", [])
                    break

            if not resist_mods:
                results.append(CheckResult(
                    "hardener_consistency", subject, "WARN",
                    "No resist modules found in tuning entry",
                ))
                continue

            hardener_types, has_multi = extract_hardener_types(resist_mods)

            if has_multi:
                if fd.is_mixed:
                    results.append(CheckResult(
                        "hardener_consistency", subject, "PASS",
                    ))
                else:
                    results.append(CheckResult(
                        "hardener_consistency", subject, "WARN",
                        f"Multispectrum module used — mods: {resist_mods}",
                    ))
                continue

            if hardener_types == sorted(fd.they_deal):
                results.append(CheckResult(
                    "hardener_consistency", subject, "PASS",
                ))
            else:
                results.append(CheckResult(
                    "hardener_consistency", subject, "FAIL",
                    f"npc_damage_types.md: {fd.they_deal}, "
                    f"faction_tuning.yaml: {resist_mods}",
                ))

    return results


def check_index_consistency(
    npc_damage: dict[str, FactionDamage],
    index_damage: dict[str, FactionDamage],
) -> list[CheckResult]:
    """Check 2: INDEX.md must match npc_damage_types.md."""
    results: list[CheckResult] = []

    for faction, idx_fd in index_damage.items():
        subject = faction
        if faction not in npc_damage:
            results.append(CheckResult(
                "index_consistency", subject, "WARN",
                f"Faction '{faction}' in INDEX.md but not in npc_damage_types.md",
            ))
            continue

        npc_fd = npc_damage[faction]

        # Compare they_deal
        if idx_fd.they_deal != npc_fd.they_deal:
            if idx_fd.is_omni == npc_fd.is_omni and idx_fd.is_mixed == npc_fd.is_mixed:
                # Both omni/mixed — fine
                if idx_fd.is_omni or idx_fd.is_mixed:
                    results.append(CheckResult(
                        "index_consistency", subject, "PASS",
                    ))
                    continue
            results.append(CheckResult(
                "index_consistency", subject, "FAIL",
                f"They Deal — INDEX: {idx_fd.they_deal}, NPC: {npc_fd.they_deal}",
            ))
            continue

        # Compare you_deal (ordered)
        if idx_fd.you_deal != npc_fd.you_deal:
            results.append(CheckResult(
                "index_consistency", subject, "FAIL",
                f"You Deal — INDEX: {idx_fd.you_deal}, NPC: {npc_fd.you_deal}",
            ))
            continue

        results.append(CheckResult("index_consistency", subject, "PASS"))

    return results


def check_mission_consistency(
    npc_damage: dict[str, FactionDamage],
) -> list[CheckResult]:
    """Check 3: Mission files' Tank field vs general faction profile."""
    results: list[CheckResult] = []

    if not MISSIONS_DIR.exists():
        return [CheckResult(
            "mission_consistency", "missions/", "SKIP",
            "Missions directory not found",
        )]

    for path in sorted(MISSIONS_DIR.glob("*.md")):
        if path.name == "INDEX.md":
            continue

        subject = path.name
        qr = parse_mission_quick_ref(path)

        if not qr:
            results.append(CheckResult(
                "mission_consistency", subject, "SKIP",
                "No Quick Reference table found",
            ))
            continue

        faction_raw = qr.get("faction", "")

        # Multi-faction missions: skip if complex format
        if "/" in faction_raw and "(" not in faction_raw:
            results.append(CheckResult(
                "mission_consistency", subject, "SKIP",
                f"Multi-faction mission: {faction_raw}",
            ))
            continue

        # Multi-part missions with different factions per part
        if "Parts" in faction_raw or "Part" in faction_raw:
            results.append(CheckResult(
                "mission_consistency", subject, "SKIP",
                f"Multi-part mission with varying factions: {faction_raw}",
            ))
            continue

        # Resolve faction — take first faction if multi-faction
        faction_key = normalize_faction_name(
            faction_raw.split("(")[0].strip()
            if "(" in faction_raw
            else faction_raw
        )

        tank_raw = qr.get("tank", "")
        if not tank_raw:
            results.append(CheckResult(
                "mission_consistency", subject, "WARN",
                "No Tank field in Quick Reference",
            ))
            continue

        # Parse multi-segment tank fields like "Kin/Therm (Parts 1-4), Exp/Kin (Part 5)"
        mission_tank = normalize_damage_types(tank_raw.split("(")[0].strip())

        if faction_key not in npc_damage:
            results.append(CheckResult(
                "mission_consistency", subject, "WARN",
                f"Faction '{faction_key}' not in npc_damage_types.md",
            ))
            continue

        npc_fd = npc_damage[faction_key]
        if npc_fd.is_omni or npc_fd.is_mixed:
            results.append(CheckResult(
                "mission_consistency", subject, "PASS",
            ))
            continue

        # Compare — differences are WARNs, not FAILs
        if mission_tank == sorted(npc_fd.they_deal):
            results.append(CheckResult(
                "mission_consistency", subject, "PASS",
            ))
        else:
            results.append(CheckResult(
                "mission_consistency", subject, "WARN",
                f"Tank: {mission_tank}, general profile: {sorted(npc_fd.they_deal)} "
                f"(mission-specific differences may be legitimate)",
            ))

    return results


def check_faction_completeness(
    npc_damage: dict[str, FactionDamage],
    profiles: dict[str, dict[str, dict]],
) -> list[CheckResult]:
    """Check 4: Every non-Omni faction should appear in all tank profiles."""
    results: list[CheckResult] = []

    for faction in npc_damage:
        if faction in SKIP_FACTIONS or faction in EMPIRE_FACTIONS:
            continue

        fd = npc_damage[faction]
        if fd.is_omni:
            continue

        for profile_name in profiles:
            subject = f"{faction} ({profile_name})"
            if faction in profiles[profile_name]:
                results.append(CheckResult(
                    "faction_completeness", subject, "PASS",
                ))
            else:
                verdict = "WARN" if faction == "mordus_legion" else "FAIL"
                results.append(CheckResult(
                    "faction_completeness", subject, verdict,
                    f"Missing from {profile_name} in faction_tuning.yaml",
                ))

    return results


def check_drone_missile_weakness(
    npc_damage: dict[str, FactionDamage],
) -> list[CheckResult]:
    """Check 5: Drone/missile weakness must match 'You Deal' primary type."""
    results: list[CheckResult] = []

    for file_path, label in [(DRONES_PATH, "drones"), (MISSILES_PATH, "missiles")]:
        if not file_path.exists():
            results.append(CheckResult(
                "weapon_weakness", f"{label}.json", "SKIP",
                f"{file_path.name} not found",
            ))
            continue

        data = json.loads(file_path.read_text())
        recs = data.get("enemy_recommendations", {})

        for faction, fd in npc_damage.items():
            if faction in SKIP_FACTIONS:
                continue

            subject = f"{faction} ({label})"

            if not fd.you_deal:
                results.append(CheckResult(
                    "weapon_weakness", subject, "SKIP",
                    "No 'You Deal' types (Omni/Mixed)",
                ))
                continue

            primary_you_deal = fd.you_deal[0].lower()

            if faction not in recs:
                results.append(CheckResult(
                    "weapon_weakness", subject, "SKIP",
                    f"Not in {label}.json enemy_recommendations",
                ))
                continue

            rec_weakness = recs[faction].get("weakness", "").lower()
            if rec_weakness == primary_you_deal:
                results.append(CheckResult(
                    "weapon_weakness", subject, "PASS",
                ))
            else:
                results.append(CheckResult(
                    "weapon_weakness", subject, "FAIL",
                    f"npc_damage_types.md You Deal primary: {fd.you_deal[0]}, "
                    f"{label}.json weakness: {rec_weakness}",
                ))

    return results


def check_staleness() -> list[CheckResult]:
    """Check 6: JSON files with _meta.last_verified > 90 days old."""
    results: list[CheckResult] = []
    now = datetime.now(timezone.utc)

    for file_path in [DRONES_PATH, MISSILES_PATH]:
        subject = file_path.name
        if not file_path.exists():
            results.append(CheckResult(
                "staleness", subject, "SKIP", "File not found",
            ))
            continue

        data = json.loads(file_path.read_text())
        meta = data.get("_meta", {})
        last_verified = meta.get("last_verified")

        if not last_verified:
            results.append(CheckResult(
                "staleness", subject, "WARN", "No _meta.last_verified date",
            ))
            continue

        try:
            verified_date = datetime.strptime(last_verified, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
            days_ago = (now - verified_date).days
            if days_ago > 90:
                results.append(CheckResult(
                    "staleness", subject, "WARN",
                    f"last_verified: {last_verified} ({days_ago} days ago)",
                ))
            else:
                results.append(CheckResult(
                    "staleness", subject, "PASS",
                    f"last_verified: {last_verified} ({days_ago} days ago)",
                ))
        except ValueError:
            results.append(CheckResult(
                "staleness", subject, "WARN",
                f"Invalid date format: {last_verified}",
            ))

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run_all_checks() -> list[CheckResult]:
    """Run all validation checks and return results."""
    npc_damage = parse_npc_damage_types()
    profiles = parse_faction_tuning()
    index_damage = parse_index_damage_table()

    results: list[CheckResult] = []
    results.extend(check_hardener_consistency(npc_damage, profiles))
    results.extend(check_index_consistency(npc_damage, index_damage))
    results.extend(check_mission_consistency(npc_damage))
    results.extend(check_faction_completeness(npc_damage, profiles))
    results.extend(check_drone_missile_weakness(npc_damage))
    results.extend(check_staleness())
    return results


def print_results(results: list[CheckResult], verbose: bool = False) -> None:
    """Print formatted validation report."""
    print()
    print(colored("=== Reference Data Validation ===", "BOLD"))
    print()

    current_check = ""
    for r in results:
        if r.check != current_check:
            current_check = r.check
            label = current_check.replace("_", " ").title()
            print(f"  {colored(label, 'BOLD')}")

        if r.verdict == "PASS" and not verbose:
            continue

        tag = colored(r.verdict, r.verdict)
        print(f"  {tag}  {r.subject}")
        if r.detail:
            print(f"        {r.detail}")

    # Summary
    total = len(results)
    counts = {"PASS": 0, "FAIL": 0, "WARN": 0, "SKIP": 0}
    for r in results:
        counts[r.verdict] = counts.get(r.verdict, 0) + 1

    print()
    print(colored("  --- Summary ---", "BOLD"))
    print(
        f"  Checks: {colored(str(counts['PASS']), 'PASS')} passed, "
        f"{colored(str(counts['FAIL']), 'FAIL')} failed, "
        f"{colored(str(counts['WARN']), 'WARN')} warnings, "
        f"{colored(str(counts['SKIP']), 'SKIP')} skipped"
    )
    print()


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate ARIA reference data internal consistency",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show PASS results too",
    )
    args = parser.parse_args()

    results = run_all_checks()
    print_results(results, verbose=args.verbose)

    if any(r.verdict == "FAIL" for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
