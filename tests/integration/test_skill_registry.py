"""
Golden Integration Test for SkillRegistry — validates ALL_SKILL_NAMES
resolve against a real seeded SDE database.

This is the primary regression gate: if a skill name is misspelled or
removed from the SDE, this test fails at CI time rather than silently
at runtime.

Usage:
    uv run pytest tests/integration/test_skill_registry.py -v

Skipped if SDE is not seeded.
"""

from __future__ import annotations

import pytest

from aria_esi.mcp.market.database import get_market_database


def sde_is_seeded() -> bool:
    """Check if SDE data has been imported."""
    try:
        db = get_market_database()
        conn = db._get_connection()
        cursor = conn.execute("SELECT COUNT(*) FROM types WHERE published = 1")
        count = cursor.fetchone()[0]
        return count > 1000
    except Exception:
        return False


requires_sde = pytest.mark.skipif(
    not sde_is_seeded(),
    reason="SDE not seeded. Run 'uv run aria-esi sde-seed' first.",
)


@requires_sde
class TestSkillRegistryGolden:
    """Golden tests that validate skill names against real SDE data."""

    def test_all_skill_names_resolve_against_sde(self):
        """Every name in ALL_SKILL_NAMES resolves to a real type_id."""
        from aria_esi.fitting.skill_registry import ALL_SKILL_NAMES
        from aria_esi.mcp.sde.queries import get_sde_query_service

        sde = get_sde_query_service()
        resolved = sde.resolve_skill_ids(ALL_SKILL_NAMES)
        assert len(resolved) == len(ALL_SKILL_NAMES)
        # Every resolved value should be a positive integer
        for name, type_id in resolved.items():
            assert isinstance(type_id, int), f"{name} resolved to non-int: {type_id}"
            assert type_id > 0, f"{name} resolved to non-positive ID: {type_id}"


@requires_sde
class TestYamlValidationGolden:
    """Golden tests that validate YAML files against real SDE data."""

    def test_breakpoint_skills_yaml_valid(self):
        from aria_esi.mcp.sde.tools_easy80 import (
            load_breakpoint_skills,
            validate_yaml_skill_references,
        )

        data = load_breakpoint_skills()
        warnings = validate_yaml_skill_references(
            data, "breakpoint_skills.yaml", "breakpoint_skills"
        )
        assert warnings == [], f"Unresolvable skills in breakpoint_skills.yaml: {warnings}"

    def test_efficacy_rules_yaml_valid(self):
        from aria_esi.mcp.sde.tools_easy80 import (
            load_efficacy_rules,
            validate_yaml_skill_references,
        )

        data = load_efficacy_rules()
        warnings = validate_yaml_skill_references(
            data, "ship_efficacy_rules.yaml", "ship_efficacy_rules"
        )
        assert warnings == [], f"Unresolvable skills in ship_efficacy_rules.yaml: {warnings}"

    def test_meta_alternatives_yaml_valid(self):
        from aria_esi.mcp.sde.tools_easy80 import (
            load_meta_alternatives,
            validate_yaml_skill_references,
        )

        data = load_meta_alternatives()
        warnings = validate_yaml_skill_references(
            data, "meta_module_alternatives.yaml", "meta_module_alternatives"
        )
        assert warnings == [], f"Unresolvable skills in meta_module_alternatives.yaml: {warnings}"
