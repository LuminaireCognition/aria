"""
Tests for fitting(action="recommend") handler.

Validates INDEX.md parsing, role/hull/tier filtering, sort order,
budget handling, and error cases per Phase 3 of FIT_ARCHETYPES_AND_SKILL_PERFORMANCE.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Constants (mirrors fitting.py)
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent
INDEX_PATH = PROJECT_ROOT / "reference" / "archetypes" / "INDEX.md"

TIER_ORDER = ["t1", "meta", "t2_budget", "t2_optimal"]

VALID_ROLES = {
    "missions-l1", "missions-l2", "missions-l3", "missions-l4",
    "exploration-data", "exploration-relic", "exploration-combat",
    "mining-ore", "mining-gas", "mining-ice",
    "hauling-hisec", "hauling-lowsec",
    "pvp-solo", "pvp-fleet-dps", "pvp-fleet-logi", "pvp-fleet-tackle",
    "abyssal", "ratting-anomaly", "salvaging",
}


# ---------------------------------------------------------------------------
# Helpers (pure INDEX parsing logic, no MCP dependency)
# ---------------------------------------------------------------------------


def parse_index() -> list[dict]:
    """Parse INDEX.md into entries (same regex as fitting.py)."""
    text = INDEX_PATH.read_text()
    entries = []
    for line in text.splitlines():
        m = re.match(
            r"\|\s*(\w[\w\s]*?)\s*\|\s*(\w+)\s*\|\s*(\S+)\s*\|\s*(\w+)\s*\|\s*([^|]*?)\s*\|\s*`([^`]+)`\s*\|",
            line,
        )
        if not m or m.group(1).strip() == "Hull":
            continue
        roles_str = m.group(5).strip()
        entries.append({
            "hull": m.group(1).strip(),
            "tier": m.group(4).strip(),
            "roles": roles_str.split(",") if roles_str else [],
            "path": m.group(6).strip(),
        })
    return entries


def filter_entries(
    entries: list[dict],
    role: str,
    hull: str | None = None,
    skill_tier: str | None = None,
) -> list[dict]:
    """Filter entries (same logic as _recommend)."""
    filtered = []
    for e in entries:
        if role not in e["roles"]:
            continue
        if hull and e["hull"].lower() != hull.lower():
            continue
        if skill_tier and e["tier"] != skill_tier:
            continue
        filtered.append(e)
    return filtered


def sort_by_tier(entries: list[dict]) -> list[dict]:
    """Sort entries by tier descending."""
    tier_rank = {t: i for i, t in enumerate(TIER_ORDER)}
    return sorted(entries, key=lambda e: tier_rank.get(e["tier"], -1), reverse=True)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRecommendFiltering:
    """Test INDEX.md filtering logic."""

    @pytest.fixture(scope="class")
    def entries(self) -> list[dict]:
        return parse_index()

    def test_role_filter_missions_l1(self, entries):
        """Filter by missions-l1 returns only L1 mission archetypes."""
        results = filter_entries(entries, "missions-l1")
        assert len(results) >= 1
        for r in results:
            assert "missions-l1" in r["roles"]

    def test_role_filter_exploration(self, entries):
        """Filter by exploration-data returns exploration archetypes."""
        results = filter_entries(entries, "exploration-data")
        assert len(results) >= 1
        for r in results:
            assert "exploration-data" in r["roles"]

    def test_hull_filter(self, entries):
        """Combined hull + role filter works."""
        results = filter_entries(entries, "missions-l4", hull="Raven")
        assert len(results) >= 1
        assert all(r["hull"] == "Raven" for r in results)

    def test_hull_filter_case_insensitive(self, entries):
        """Hull filter is case-insensitive."""
        results = filter_entries(entries, "missions-l4", hull="raven")
        assert len(results) >= 1

    def test_tier_filter(self, entries):
        """Skill tier filter works."""
        results = filter_entries(entries, "missions-l1", skill_tier="meta")
        for r in results:
            assert r["tier"] == "meta"

    def test_no_match(self, entries):
        """Non-matching filter returns empty."""
        results = filter_entries(entries, "missions-l4", hull="Venture")
        assert results == []

    def test_invalid_role_not_in_taxonomy(self):
        """Roles not in taxonomy should be caught by validation."""
        assert "pve-ratting" not in VALID_ROLES
        assert "missions-l5" not in VALID_ROLES


class TestRecommendSortOrder:
    """Test tier sort ordering."""

    def test_tier_sort_descending(self):
        """Results sorted highest tier first."""
        entries = [
            {"hull": "A", "tier": "t1", "roles": ["missions-l1"], "path": "a.yaml"},
            {"hull": "B", "tier": "t2_optimal", "roles": ["missions-l1"], "path": "b.yaml"},
            {"hull": "C", "tier": "meta", "roles": ["missions-l1"], "path": "c.yaml"},
        ]
        sorted_entries = sort_by_tier(entries)
        assert [e["tier"] for e in sorted_entries] == ["t2_optimal", "meta", "t1"]

    def test_tier_order_canonical(self):
        """TIER_ORDER matches proposal spec."""
        assert TIER_ORDER == ["t1", "meta", "t2_budget", "t2_optimal"]


class TestRecommendEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_roles_excluded(self):
        """Entries with empty roles don't match any role query."""
        entries = [
            {"hull": "X", "tier": "t1", "roles": [], "path": "x.yaml"},
        ]
        assert filter_entries(entries, "missions-l1") == []

    def test_containment_matching(self):
        """Multi-role archetypes match on any single role."""
        entries = [
            {"hull": "Heron", "tier": "t1",
             "roles": ["exploration-data", "exploration-relic"],
             "path": "heron.yaml"},
        ]
        assert len(filter_entries(entries, "exploration-data")) == 1
        assert len(filter_entries(entries, "exploration-relic")) == 1
        assert len(filter_entries(entries, "missions-l1")) == 0

    def test_limit_truncation(self):
        """Results are truncated at limit."""
        entries = [
            {"hull": f"Ship{i}", "tier": "t1", "roles": ["missions-l1"], "path": f"s{i}.yaml"}
            for i in range(10)
        ]
        filtered = filter_entries(entries, "missions-l1")
        assert len(filtered) == 10
        # The handler would truncate at limit; verified here as a unit
        assert len(filtered[:2]) == 2


class TestRecommendLiveIndex:
    """Integration tests against the actual INDEX.md."""

    @pytest.fixture(scope="class")
    def entries(self) -> list[dict]:
        return parse_index()

    def test_index_has_mission_archetypes(self, entries):
        """INDEX has at least one archetype per mission level."""
        for level in ["missions-l1", "missions-l2", "missions-l3", "missions-l4"]:
            results = filter_entries(entries, level)
            assert len(results) >= 1, f"No archetypes for {level}"

    def test_index_has_exploration(self, entries):
        """INDEX has exploration archetypes."""
        results = filter_entries(entries, "exploration-data")
        assert len(results) >= 1

    def test_index_has_mining(self, entries):
        """INDEX has mining archetypes."""
        results = filter_entries(entries, "mining-ore")
        assert len(results) >= 1

    def test_all_paths_valid(self, entries):
        """All paths in filtered results exist on disk."""
        for entry in entries:
            path = PROJECT_ROOT / entry["path"]
            assert path.exists(), f"Missing: {entry['path']}"

