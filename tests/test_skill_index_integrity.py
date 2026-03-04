"""
Skill Index Integrity Tests.

Validates that `.claude/skills/_index.json` stays in sync with the actual
SKILL.md files on disk. Replaces the validation that the deleted
`aria-skill-index.py` generator script used to provide at boot time.

These tests run as part of CI to catch drift bugs in the hand-maintained index.

See: ADR-002 (Skill Metadata Schema), CONTEXT_EFFICIENCY_PROPOSAL.md Phase 2.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent
SKILLS_DIR = PROJECT_ROOT / ".claude" / "skills"
INDEX_PATH = SKILLS_DIR / "_index.json"
PERSONAS_DIR = PROJECT_ROOT / "personas"

VALID_CATEGORIES = {"tactical", "operations", "financial", "identity", "system", "industry"}
VALID_MODELS = {"haiku", "sonnet", "claude-opus-4-6"}
VALID_DISPATCHERS = {"universe", "market", "sde", "skills", "fitting", "killmails", "pilot", "status"}

# Known trigger collisions: triggers claimed by multiple SKILL.md files where
# the trigger_map intentionally resolves to one skill over another.
# Format: {trigger_lower: skill_it_maps_to}
KNOWN_TRIGGER_COLLISIONS = {
    "where am i": "orient",  # also in esi-query
    "my standings": "standings",  # also in esi-query
}


@pytest.fixture(scope="module")
def index_data() -> dict:
    """Load and return the parsed _index.json."""
    return json.loads(INDEX_PATH.read_text())


@pytest.fixture(scope="module")
def skills_list(index_data) -> list[dict]:
    """Return the skills array from the index."""
    return index_data["skills"]


@pytest.fixture(scope="module")
def skills_by_name(skills_list) -> dict[str, dict]:
    """Return skills keyed by name."""
    return {s["name"]: s for s in skills_list}


@pytest.fixture(scope="module")
def skill_dirs_on_disk() -> set[str]:
    """Return set of skill directory names that contain a SKILL.md."""
    return {
        d.name
        for d in SKILLS_DIR.iterdir()
        if d.is_dir() and (d / "SKILL.md").exists()
    }


@pytest.fixture(scope="module")
def frontmatters(skill_dirs_on_disk) -> dict[str, dict]:
    """Parse YAML frontmatter from every SKILL.md on disk."""
    result = {}
    for name in skill_dirs_on_disk:
        skill_md = SKILLS_DIR / name / "SKILL.md"
        text = skill_md.read_text()
        match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
        if match:
            result[name] = yaml.safe_load(match.group(1))
    return result


@pytest.fixture(scope="module")
def overlay_skills_on_disk() -> set[str]:
    """Return set of skill names that have at least one persona overlay file."""
    overlays = set()
    for persona_dir in PERSONAS_DIR.iterdir():
        if not persona_dir.is_dir():
            continue
        overlay_dir = persona_dir / "skill-overlays"
        if overlay_dir.is_dir():
            for f in overlay_dir.iterdir():
                if f.suffix == ".md":
                    overlays.add(f.stem)
    return overlays


# ===========================================================================
# 1. TestIndexSchemaIntegrity — structural correctness
# ===========================================================================


class TestIndexSchemaIntegrity:
    """Validate structural correctness of _index.json."""

    def test_skill_count_matches_entries(self, index_data, skills_list):
        """skill_count field matches actual array length."""
        assert index_data["skill_count"] == len(skills_list)

    def test_no_duplicate_skill_names(self, skills_list):
        """No duplicate skill names (catches copy-paste errors)."""
        names = [s["name"] for s in skills_list]
        assert len(names) == len(set(names)), f"Duplicates: {[n for n in names if names.count(n) > 1]}"

    def test_required_fields_present(self, skills_list):
        """Every skill entry has required fields."""
        required = {"name", "description", "path", "directory"}
        for skill in skills_list:
            missing = required - set(skill.keys())
            assert not missing, f"Skill '{skill.get('name', '?')}' missing: {missing}"

    def test_optional_fields_have_correct_types(self, skills_list):
        """Optional fields have correct types when present."""
        type_rules = {
            "triggers": list,
            "requires_pilot": bool,
            "has_persona_overlay": bool,
            "model": str,
            "category": str,
            "data_sources": list,
            "prerequisite_files": list,
            "external_sources": list,
            "esi_scopes": list,
            "required_tools": list,
        }
        for skill in skills_list:
            for field, expected_type in type_rules.items():
                if field in skill:
                    assert isinstance(skill[field], expected_type), (
                        f"Skill '{skill['name']}': {field} should be {expected_type.__name__}, "
                        f"got {type(skill[field]).__name__}"
                    )

    def test_schema_version_present(self, index_data):
        """schema_version field exists and is a known version."""
        assert "schema_version" in index_data
        assert index_data["schema_version"] == "1.0"

    def test_valid_categories(self, skills_list):
        """All skills use recognized category values."""
        for skill in skills_list:
            if "category" in skill:
                assert skill["category"] in VALID_CATEGORIES, (
                    f"Skill '{skill['name']}' has unknown category '{skill['category']}'"
                )

    def test_valid_models(self, skills_list):
        """All skills use recognized model values."""
        for skill in skills_list:
            if "model" in skill:
                assert skill["model"] in VALID_MODELS, (
                    f"Skill '{skill['name']}' has unknown model '{skill['model']}'"
                )

    def test_required_tools_field_present(self, skills_list):
        """Every skill has a required_tools field."""
        for skill in skills_list:
            assert "required_tools" in skill, (
                f"Skill '{skill['name']}' missing required_tools field"
            )

    def test_required_tools_is_list_of_strings(self, skills_list):
        """required_tools is a list of strings."""
        for skill in skills_list:
            rt = skill.get("required_tools")
            if rt is None:
                continue
            assert isinstance(rt, list), (
                f"Skill '{skill['name']}': required_tools should be list, "
                f"got {type(rt).__name__}"
            )
            for entry in rt:
                assert isinstance(entry, str), (
                    f"Skill '{skill['name']}': required_tools entry {entry!r} "
                    f"should be str, got {type(entry).__name__}"
                )

    def test_required_tools_format(self, skills_list):
        """required_tools entries follow dispatcher.action format with known dispatchers."""
        for skill in skills_list:
            for entry in skill.get("required_tools", []):
                parts = entry.split(".", 1)
                assert len(parts) == 2, (
                    f"Skill '{skill['name']}': required_tools entry '{entry}' "
                    f"must be 'dispatcher.action' format"
                )
                dispatcher, action = parts
                assert dispatcher in VALID_DISPATCHERS, (
                    f"Skill '{skill['name']}': unknown dispatcher '{dispatcher}' "
                    f"in required_tools entry '{entry}'. "
                    f"Valid: {sorted(VALID_DISPATCHERS)}"
                )
                assert action, (
                    f"Skill '{skill['name']}': empty action in '{entry}'"
                )


# ===========================================================================
# 2. TestIndexDiskSync — index matches what's on disk
# ===========================================================================


class TestIndexDiskSync:
    """Validate index entries match skill directories on disk."""

    def test_every_indexed_skill_has_skill_md(self, skills_list):
        """Every indexed skill has a corresponding SKILL.md on disk."""
        for skill in skills_list:
            skill_md = SKILLS_DIR / skill["directory"] / "SKILL.md"
            assert skill_md.exists(), (
                f"Index entry '{skill['name']}' points to missing {skill_md}"
            )

    def test_every_skill_md_is_in_index(self, skills_by_name, skill_dirs_on_disk):
        """Every SKILL.md on disk is registered in the index."""
        indexed = set(skills_by_name.keys())
        unindexed = skill_dirs_on_disk - indexed
        assert not unindexed, f"Skills on disk but not in index: {unindexed}"

    def test_path_field_matches_convention(self, skills_list):
        """path field follows .claude/skills/{name}/SKILL.md convention."""
        for skill in skills_list:
            expected = f".claude/skills/{skill['name']}/SKILL.md"
            assert skill["path"] == expected, (
                f"Skill '{skill['name']}': path '{skill['path']}' != '{expected}'"
            )

    def test_directory_field_matches_name(self, skills_list):
        """directory field equals name field."""
        for skill in skills_list:
            assert skill["directory"] == skill["name"], (
                f"Skill '{skill['name']}': directory '{skill['directory']}' != name"
            )


# ===========================================================================
# 3. TestIndexFrontmatterSync — index entries match SKILL.md frontmatter
# ===========================================================================


class TestIndexFrontmatterSync:
    """Validate index entries match their SKILL.md YAML frontmatter."""

    def test_name_matches_frontmatter(self, skills_by_name, frontmatters):
        """Index name matches SKILL.md frontmatter name."""
        for name, fm in frontmatters.items():
            if name not in skills_by_name:
                continue  # caught by TestIndexDiskSync
            assert skills_by_name[name]["name"] == fm.get("name"), (
                f"Skill '{name}': index name '{skills_by_name[name]['name']}' "
                f"!= frontmatter name '{fm.get('name')}'"
            )

    def test_description_matches_frontmatter(self, skills_by_name, frontmatters):
        """Index description matches SKILL.md frontmatter description."""
        for name, fm in frontmatters.items():
            if name not in skills_by_name:
                continue
            if "description" not in fm:
                continue
            assert skills_by_name[name]["description"] == fm["description"], (
                f"Skill '{name}': description drift between index and SKILL.md"
            )

    def test_model_matches_frontmatter(self, skills_by_name, frontmatters):
        """Index model matches SKILL.md frontmatter model."""
        for name, fm in frontmatters.items():
            if name not in skills_by_name:
                continue
            if "model" not in fm:
                continue
            assert skills_by_name[name].get("model") == fm["model"], (
                f"Skill '{name}': index model '{skills_by_name[name].get('model')}' "
                f"!= frontmatter model '{fm['model']}'"
            )

    def test_category_matches_frontmatter(self, skills_by_name, frontmatters):
        """Index category matches SKILL.md frontmatter category."""
        for name, fm in frontmatters.items():
            if name not in skills_by_name:
                continue
            if "category" not in fm:
                continue
            assert skills_by_name[name].get("category") == fm["category"], (
                f"Skill '{name}': index category '{skills_by_name[name].get('category')}' "
                f"!= frontmatter category '{fm['category']}'"
            )


# ===========================================================================
# 4. TestByCategoryConsistency — by_category section is correct
# ===========================================================================


class TestByCategoryConsistency:
    """Validate by_category section matches skill entries."""

    def test_all_skills_appear_in_by_category(self, index_data, skills_list):
        """Every skill appears in exactly one by_category bucket."""
        by_cat = index_data["by_category"]
        categorized = set()
        for names in by_cat.values():
            categorized.update(names)

        for skill in skills_list:
            assert skill["name"] in categorized, (
                f"Skill '{skill['name']}' missing from by_category"
            )

    def test_by_category_entries_exist_in_skills(self, index_data, skills_by_name):
        """Every name in by_category exists as a skill entry."""
        by_cat = index_data["by_category"]
        for category, names in by_cat.items():
            for name in names:
                assert name in skills_by_name, (
                    f"by_category['{category}'] lists '{name}' which is not in skills"
                )

    def test_category_assignment_matches_skill(self, index_data, skills_by_name):
        """Skills appear in the category matching their category field."""
        by_cat = index_data["by_category"]
        for category, names in by_cat.items():
            for name in names:
                if name in skills_by_name:
                    skill_cat = skills_by_name[name].get("category")
                    assert skill_cat == category, (
                        f"Skill '{name}' is in by_category['{category}'] "
                        f"but its category field is '{skill_cat}'"
                    )


# ===========================================================================
# 5. TestTriggerMapConsistency — trigger_map section is correct
# ===========================================================================


class TestTriggerMapConsistency:
    """Validate trigger_map section matches skill triggers."""

    def test_all_skill_triggers_in_trigger_map(self, index_data, skills_list):
        """Every trigger from every skill appears in trigger_map."""
        trigger_map = index_data["trigger_map"]
        trigger_map_lower = {k.lower(): v for k, v in trigger_map.items()}

        for skill in skills_list:
            for trigger in skill.get("triggers", []):
                t_lower = trigger.lower()
                assert t_lower in trigger_map_lower, (
                    f"Skill '{skill['name']}' trigger '{trigger}' missing from trigger_map"
                )

    def test_trigger_map_entries_reference_valid_skills(self, index_data, skills_by_name):
        """Every trigger_map value references an existing skill."""
        for trigger, skill_name in index_data["trigger_map"].items():
            assert skill_name in skills_by_name, (
                f"trigger_map['{trigger}'] -> '{skill_name}' which doesn't exist"
            )

    def test_trigger_map_values_match_skill_triggers(self, index_data, skills_by_name):
        """Each trigger_map entry points to a skill that actually claims that trigger."""
        trigger_map = index_data["trigger_map"]

        # Build reverse map: for each skill, collect its triggers (lowercased)
        skill_triggers = {}
        for skill in index_data["skills"]:
            skill_triggers[skill["name"]] = {
                t.lower() for t in skill.get("triggers", [])
            }

        for trigger, target_skill in trigger_map.items():
            t_lower = trigger.lower()
            # The target skill must claim this trigger, OR it's a known collision
            # where a different skill also claims it
            if t_lower in KNOWN_TRIGGER_COLLISIONS:
                assert target_skill == KNOWN_TRIGGER_COLLISIONS[t_lower], (
                    f"Known collision '{trigger}' maps to '{target_skill}' "
                    f"but expected '{KNOWN_TRIGGER_COLLISIONS[t_lower]}'"
                )
                continue

            assert t_lower in skill_triggers.get(target_skill, set()), (
                f"trigger_map['{trigger}'] -> '{target_skill}' but that skill "
                f"doesn't list '{trigger}' in its triggers"
            )

    def test_trigger_collisions_documented(self, index_data):
        """All trigger collisions are documented in KNOWN_TRIGGER_COLLISIONS.

        A collision is when multiple skills claim the same trigger (lowercased)
        but the trigger_map can only point to one.
        """
        # Collect all triggers across all skills
        trigger_owners: dict[str, list[str]] = {}
        for skill in index_data["skills"]:
            for trigger in skill.get("triggers", []):
                t_lower = trigger.lower()
                trigger_owners.setdefault(t_lower, []).append(skill["name"])

        # Find collisions (trigger claimed by >1 skill)
        collisions = {t: owners for t, owners in trigger_owners.items() if len(owners) > 1}

        undocumented = set(collisions.keys()) - set(KNOWN_TRIGGER_COLLISIONS.keys())
        assert not undocumented, (
            f"Undocumented trigger collisions: "
            + ", ".join(f"'{t}' claimed by {collisions[t]}" for t in undocumented)
        )


# ===========================================================================
# 6. TestPersonaOverlaySync — has_persona_overlay matches disk
# ===========================================================================


class TestPersonaOverlaySync:
    """Validate has_persona_overlay flags match actual overlay files on disk."""

    def test_overlay_flag_matches_disk(self, skills_by_name, overlay_skills_on_disk):
        """Skills with has_persona_overlay=true must have an overlay on disk."""
        for name, skill in skills_by_name.items():
            if skill.get("has_persona_overlay"):
                assert name in overlay_skills_on_disk, (
                    f"Skill '{name}' has has_persona_overlay=true but no overlay "
                    f"file exists in any personas/*/skill-overlays/ directory"
                )

    def test_all_disk_overlays_flagged(self, skills_by_name, overlay_skills_on_disk):
        """Skills with overlay files on disk should be flagged in the index."""
        for name in overlay_skills_on_disk:
            if name not in skills_by_name:
                continue  # not our concern — caught by TestIndexDiskSync
            assert skills_by_name[name].get("has_persona_overlay") is True, (
                f"Skill '{name}' has overlay files on disk but "
                f"has_persona_overlay is not true in the index"
            )


# ===========================================================================
# 7. TestAdr002SemanticRules — ADR-002 business rules
# ===========================================================================


class TestAdr002SemanticRules:
    """Validate ADR-002 semantic rules for skill metadata."""

    def test_requires_pilot_has_data_sources_or_esi_scopes(self, skills_list):
        """Pilot-dependent skills should declare data needs (data_sources or esi_scopes).

        This is a soft check — some pilot-dependent skills legitimately have no
        declared data sources (e.g., they use pilot context implicitly via ESI
        queries at runtime). We track exceptions explicitly.
        """
        # Skills that require_pilot but legitimately have no data_sources/esi_scopes
        # (they query ESI at runtime without pre-declared scopes)
        KNOWN_EXCEPTIONS = {
            "corp",  # queries corp endpoints dynamically
            "fitting",  # uses fitting tool, pilot context is optional
            "journal",  # writes to local files using pilot path
            "mark-assessment",  # has data_sources but no esi_scopes
            "mining-advisory",  # has data_sources but no esi_scopes
            "ransom-calc",  # has data_sources but no esi_scopes
            "threat-assessment",  # has data_sources but no esi_scopes
        }

        for skill in skills_list:
            if not skill.get("requires_pilot"):
                continue
            if skill["name"] in KNOWN_EXCEPTIONS:
                continue

            has_data = bool(skill.get("data_sources")) or bool(skill.get("esi_scopes"))
            assert has_data, (
                f"Skill '{skill['name']}' requires_pilot=true but has no "
                f"data_sources or esi_scopes declared"
            )

    def test_esi_scopes_skills_require_pilot(self, skills_list):
        """Skills with esi_scopes must have requires_pilot=true."""
        for skill in skills_list:
            if skill.get("esi_scopes"):
                assert skill.get("requires_pilot") is True, (
                    f"Skill '{skill['name']}' declares esi_scopes but "
                    f"requires_pilot is not true"
                )
