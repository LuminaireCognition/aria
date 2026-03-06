"""
Archetype Library Integrity Tests.

Validates that reference/archetypes/ YAML files are structurally sound,
INDEX.md paths resolve to real files, and archetype schemas are consistent.

These tests run in CI to catch drift between INDEX.md and actual files,
broken YAML, or missing required fields in archetype definitions.
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path

import pytest
import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent
ARCHETYPES_DIR = PROJECT_ROOT / "reference" / "archetypes"
INDEX_PATH = ARCHETYPES_DIR / "INDEX.md"
SHARED_DIR = ARCHETYPES_DIR / "_shared"

VALID_SKILL_TIERS = {"t1", "meta", "t2_budget", "t2_optimal"}

# NOTE: keep in sync with VALID_ROLES in src/aria_esi/mcp/dispatchers/fitting.py
VALID_ROLES: set[str] = {
    "missions-l1",
    "missions-l2",
    "missions-l3",
    "missions-l4",
    "exploration-data",
    "exploration-relic",
    "exploration-combat",
    "mining-ore",
    "mining-gas",
    "mining-ice",
    "hauling-hisec",
    "hauling-lowsec",
    "pvp-solo",
    "pvp-fleet-dps",
    "pvp-fleet-logi",
    "pvp-fleet-tackle",
    "abyssal",
    "ratting-anomaly",
    "salvaging",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def index_entries() -> list[dict[str, str]]:
    """Parse INDEX.md table into a list of {hull, activity, level, tier, roles, path} dicts."""
    text = INDEX_PATH.read_text()
    rows = []
    for line in text.splitlines():
        # Match 6-column table rows: | Hull | Activity | Level | Tier | Roles | `path` |
        # Roles column may be empty (for archetypes not yet backfilled)
        m = re.match(
            r"\|\s*(\w[\w\s]*?)\s*\|\s*(\w+)\s*\|\s*(\S+)\s*\|\s*(\w+)\s*\|\s*([^|]*?)\s*\|\s*`([^`]+)`\s*\|",
            line,
        )
        if m and m.group(1).strip() not in ("Hull",):  # skip header
            rows.append({
                "hull": m.group(1).strip(),
                "activity": m.group(2).strip(),
                "level": m.group(3).strip(),
                "tier": m.group(4).strip(),
                "roles": m.group(5).strip(),
                "path": m.group(6).strip(),
            })
    return rows


@pytest.fixture(scope="module")
def archetype_yamls(index_entries) -> dict[str, dict]:
    """Load every archetype YAML referenced by INDEX.md."""
    loaded = {}
    for entry in index_entries:
        full_path = ARCHETYPES_DIR / entry["path"]
        if full_path.exists():
            loaded[entry["path"]] = yaml.safe_load(full_path.read_text())
    return loaded


@pytest.fixture(scope="module")
def shared_configs() -> dict[str, dict]:
    """Load all shared config YAMLs."""
    loaded = {}
    for f in sorted(SHARED_DIR.glob("*.yaml")):
        loaded[f.name] = yaml.safe_load(f.read_text())
    return loaded


@pytest.fixture(scope="module")
def all_hull_yamls() -> dict[str, dict]:
    """Load every YAML under hulls/ (archetypes + meta files)."""
    loaded = {}
    hulls_dir = ARCHETYPES_DIR / "hulls"
    for f in sorted(hulls_dir.rglob("*.yaml")):
        loaded[str(f.relative_to(ARCHETYPES_DIR))] = yaml.safe_load(f.read_text())
    return loaded


# ===========================================================================
# 1. INDEX.md ↔ Disk Sync
# ===========================================================================


class TestIndexDiskSync:
    """Validate INDEX.md paths resolve to actual files."""

    def test_index_has_entries(self, index_entries):
        """INDEX.md contains at least one archetype entry."""
        assert len(index_entries) > 0

    def test_all_index_paths_exist(self, index_entries):
        """Every path in INDEX.md exists on disk."""
        missing = []
        for entry in index_entries:
            full_path = ARCHETYPES_DIR / entry["path"]
            if not full_path.exists():
                missing.append(entry["path"])
        assert not missing, f"INDEX.md references missing files: {missing}"

    def test_no_orphan_archetypes(self, index_entries, all_hull_yamls):
        """Every archetype YAML (has archetype+eft) is listed in INDEX.md."""
        indexed_paths = {e["path"] for e in index_entries}
        orphans = []
        for path, data in all_hull_yamls.items():
            if "archetype" in data and "eft" in data and path not in indexed_paths:
                orphans.append(path)
        assert not orphans, f"Archetype files not in INDEX.md: {orphans}"


# ===========================================================================
# 2. Archetype YAML Schema
# ===========================================================================


class TestArchetypeSchema:
    """Validate required fields in archetype YAML files."""

    def test_archetype_section_present(self, archetype_yamls):
        """Every indexed archetype has an 'archetype' section."""
        missing = [p for p, d in archetype_yamls.items() if "archetype" not in d]
        assert not missing, f"Missing 'archetype' section: {missing}"

    def test_eft_section_present(self, archetype_yamls):
        """Every indexed archetype has an 'eft' section."""
        missing = [p for p, d in archetype_yamls.items() if "eft" not in d]
        assert not missing, f"Missing 'eft' section: {missing}"

    def test_archetype_has_hull(self, archetype_yamls):
        """Every archetype declares a hull name."""
        missing = []
        for path, data in archetype_yamls.items():
            arch = data.get("archetype", {})
            if not arch.get("hull"):
                missing.append(path)
        assert not missing, f"Missing archetype.hull: {missing}"

    def test_archetype_has_valid_skill_tier(self, archetype_yamls):
        """Every archetype declares a recognized skill_tier."""
        bad = []
        for path, data in archetype_yamls.items():
            tier = data.get("archetype", {}).get("skill_tier")
            if tier not in VALID_SKILL_TIERS:
                bad.append(f"{path}: {tier!r}")
        assert not bad, f"Invalid skill_tier values: {bad}"

    def test_eft_has_ship_header(self, archetype_yamls):
        """Every EFT block starts with [ShipName, FitName]."""
        bad = []
        for path, data in archetype_yamls.items():
            eft = data.get("eft", "").strip()
            if not re.match(r"\[.+,.+\]", eft):
                bad.append(path)
        assert not bad, f"EFT blocks missing [Ship, Name] header: {bad}"

    def test_skill_requirements_present(self, archetype_yamls):
        """Every archetype has skill_requirements with at least 'required'."""
        bad = []
        for path, data in archetype_yamls.items():
            reqs = data.get("skill_requirements", {})
            if not reqs.get("required"):
                bad.append(path)
        assert not bad, f"Missing skill_requirements.required: {bad}"

    def test_stats_present(self, archetype_yamls):
        """Every archetype has a stats section with ehp."""
        bad = []
        for path, data in archetype_yamls.items():
            stats = data.get("stats", {})
            if "ehp" not in stats:
                bad.append(path)
        assert not bad, f"Missing stats.ehp: {bad}"

    def test_combat_archetypes_have_dps(self, archetype_yamls):
        """Combat archetypes (missions) have dps in stats."""
        bad = []
        for path, data in archetype_yamls.items():
            if "missions" in path:
                if "dps" not in data.get("stats", {}):
                    bad.append(path)
        assert not bad, f"Mission archetypes missing stats.dps: {bad}"

    def test_combat_archetypes_have_damage_tuning(self, archetype_yamls):
        """Combat archetypes (missions) have damage_tuning."""
        bad = []
        for path, data in archetype_yamls.items():
            if "missions" in path:
                if "damage_tuning" not in data:
                    bad.append(path)
        assert not bad, f"Mission archetypes missing damage_tuning: {bad}"


# ===========================================================================
# 3. EFT Hull ↔ Index Consistency
# ===========================================================================


class TestArchetypeConsistency:
    """Cross-check archetype data against INDEX.md entries."""

    def test_eft_hull_matches_index(self, index_entries, archetype_yamls):
        """EFT [Ship, ...] header matches the hull declared in INDEX.md."""
        mismatches = []
        for entry in index_entries:
            data = archetype_yamls.get(entry["path"])
            if not data:
                continue
            eft = data.get("eft", "").strip()
            m = re.match(r"\[(\w[\w\s]*?),", eft)
            if m:
                eft_hull = m.group(1).strip()
                if eft_hull != entry["hull"]:
                    mismatches.append(
                        f"{entry['path']}: INDEX says {entry['hull']!r}, "
                        f"EFT says {eft_hull!r}"
                    )
        assert not mismatches, f"Hull mismatches: {mismatches}"

    def test_archetype_hull_matches_index(self, index_entries, archetype_yamls):
        """archetype.hull matches the hull column in INDEX.md."""
        mismatches = []
        for entry in index_entries:
            data = archetype_yamls.get(entry["path"])
            if not data:
                continue
            arch_hull = data.get("archetype", {}).get("hull")
            if arch_hull and arch_hull != entry["hull"]:
                mismatches.append(
                    f"{entry['path']}: INDEX says {entry['hull']!r}, "
                    f"archetype.hull says {arch_hull!r}"
                )
        assert not mismatches, f"Hull mismatches: {mismatches}"

    def test_tier_matches_index(self, index_entries, archetype_yamls):
        """archetype.skill_tier matches the tier column in INDEX.md."""
        mismatches = []
        for entry in index_entries:
            data = archetype_yamls.get(entry["path"])
            if not data:
                continue
            arch_tier = data.get("archetype", {}).get("skill_tier")
            if arch_tier and arch_tier != entry["tier"]:
                mismatches.append(
                    f"{entry['path']}: INDEX says {entry['tier']!r}, "
                    f"archetype.skill_tier says {arch_tier!r}"
                )
        assert not mismatches, f"Tier mismatches: {mismatches}"


# ===========================================================================
# 4. Roles Validation
# ===========================================================================


class TestRolesValidation:
    """Validate the roles field in archetype YAMLs and INDEX.md consistency."""

    def test_roles_values_valid(self, archetype_yamls):
        """All roles values must be from the canonical taxonomy."""
        bad = []
        for path, data in archetype_yamls.items():
            roles = data.get("roles")
            if roles is None:
                continue  # no roles field — exempt (pre-existing archetype)
            for role in roles:
                if role not in VALID_ROLES:
                    bad.append(
                        f"Invalid role '{role}' in {path}, "
                        f"must be one of: {sorted(VALID_ROLES)}"
                    )
        assert not bad, "\n".join(bad)

    def test_roles_count(self, archetype_yamls):
        """Archetypes with roles must have 1-3 values."""
        bad = []
        for path, data in archetype_yamls.items():
            roles = data.get("roles")
            if roles is None:
                continue
            n = len(roles)
            if n < 1 or n > 3:
                bad.append(f"roles must contain 1-3 values, got {n} in {path}")
        assert not bad, "\n".join(bad)

    def test_roles_yaml_index_consistency(self, index_entries, archetype_yamls):
        """YAML roles values must match the comma-separated Roles column in INDEX.md."""
        mismatches = []
        for entry in index_entries:
            data = archetype_yamls.get(entry["path"])
            if not data:
                continue
            yaml_roles = data.get("roles")
            if yaml_roles is None:
                # No roles in YAML — exempt from consistency check
                continue
            # Parse INDEX roles column (comma-separated, no spaces)
            index_roles_str = entry.get("roles", "")
            if index_roles_str:
                index_roles = sorted(index_roles_str.split(","))
            else:
                index_roles = []
            yaml_roles_sorted = sorted(yaml_roles)
            if yaml_roles_sorted != index_roles:
                mismatches.append(
                    f"{entry['path']}: YAML roles={yaml_roles_sorted}, "
                    f"INDEX roles={index_roles}"
                )
        assert not mismatches, f"Roles mismatches:\n" + "\n".join(mismatches)

    def test_roles_missing_warns(self, archetype_yamls):
        """Archetypes without roles emit a warning (not a failure)."""
        missing = [p for p, d in archetype_yamls.items() if d.get("roles") is None]
        if missing:
            warnings.warn(
                f"{len(missing)} archetype(s) without roles field: "
                f"{', '.join(missing[:5])}{'...' if len(missing) > 5 else ''}",
                stacklevel=1,
            )


# ===========================================================================
# 5. Shared Configs
# ===========================================================================


class TestSharedConfigs:
    """Validate shared configuration files parse and have expected structure."""

    def test_all_shared_yamls_parse(self, shared_configs):
        """All shared YAML files loaded without error."""
        assert len(shared_configs) >= 3, (
            f"Expected at least 3 shared configs, found {len(shared_configs)}: "
            f"{list(shared_configs.keys())}"
        )

    def test_skill_tiers_has_tier_definitions(self, shared_configs):
        """skill_tiers.yaml defines all recognized tiers."""
        tiers_data = shared_configs.get("skill_tiers.yaml", {})
        defined = set(tiers_data.get("tiers", {}).keys())
        missing = VALID_SKILL_TIERS - defined
        assert not missing, f"skill_tiers.yaml missing tier definitions: {missing}"

    def test_module_tiers_not_empty(self, shared_configs):
        """module_tiers.yaml has content."""
        data = shared_configs.get("module_tiers.yaml", {})
        assert data, "module_tiers.yaml is empty or missing"

    def test_faction_tuning_not_empty(self, shared_configs):
        """faction_tuning.yaml has content."""
        data = shared_configs.get("faction_tuning.yaml", {})
        assert data, "faction_tuning.yaml is empty or missing"


# ===========================================================================
# 6. Meta (Variant Selector) Files
# ===========================================================================


class TestVariantSelectors:
    """Validate meta.yaml variant selector files (non-archetype hull YAMLs)."""

    def test_variant_selectors_have_hull(self, all_hull_yamls):
        """Variant selector files (no archetype section) still declare a hull."""
        bad = []
        for path, data in all_hull_yamls.items():
            if "archetype" in data:
                continue  # actual archetype, tested above
            if not data.get("hull"):
                bad.append(path)
        assert not bad, f"Variant selectors missing 'hull' field: {bad}"

    def test_variant_selectors_have_tank_variants(self, all_hull_yamls):
        """Variant selector files declare tank_variants."""
        bad = []
        for path, data in all_hull_yamls.items():
            if "archetype" in data:
                continue
            if "tank_variants" not in data:
                bad.append(path)
        assert not bad, f"Variant selectors missing 'tank_variants': {bad}"
