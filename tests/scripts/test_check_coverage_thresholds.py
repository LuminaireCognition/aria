"""Tests for the per-module coverage threshold enforcement script."""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.scripts.check_coverage_thresholds import (
    aggregate_coverage,
    calculate_coverage_pct,
    check_thresholds,
    load_thresholds,
)


@pytest.fixture
def pyproject_with_thresholds(tmp_path: Path) -> Path:
    """Create a pyproject.toml with coverage thresholds."""
    p = tmp_path / "pyproject.toml"
    p.write_text(
        '[tool.aria.coverage_thresholds]\n'
        'core = 75\n'
        'fitting = 80\n'
        '"mcp/market" = 60\n'
    )
    return p


@pytest.fixture
def pyproject_empty(tmp_path: Path) -> Path:
    """Create a pyproject.toml without coverage thresholds."""
    p = tmp_path / "pyproject.toml"
    p.write_text("[tool.ruff]\ntarget-version = 'py311'\n")
    return p


@pytest.fixture
def sample_coverage_data() -> dict:
    """Sample coverage.json data."""
    return {
        "files": {
            "src/aria_esi/core/auth.py": {
                "summary": {
                    "num_statements": 100,
                    "missing_lines": 20,
                    "num_branches": 40,
                    "missing_branches": 5,
                }
            },
            "src/aria_esi/core/client.py": {
                "summary": {
                    "num_statements": 50,
                    "missing_lines": 5,
                    "num_branches": 20,
                    "missing_branches": 3,
                }
            },
            "src/aria_esi/fitting/eft_parser.py": {
                "summary": {
                    "num_statements": 200,
                    "missing_lines": 10,
                    "num_branches": 80,
                    "missing_branches": 6,
                }
            },
            "src/aria_esi/mcp/market/tools_prices.py": {
                "summary": {
                    "num_statements": 100,
                    "missing_lines": 30,
                    "num_branches": 40,
                    "missing_branches": 10,
                }
            },
            "src/aria_esi/mcp/market/tools_orders.py": {
                "summary": {
                    "num_statements": 80,
                    "missing_lines": 40,
                    "num_branches": 30,
                    "missing_branches": 20,
                }
            },
            "tests/test_something.py": {
                "summary": {
                    "num_statements": 50,
                    "missing_lines": 0,
                    "num_branches": 0,
                    "missing_branches": 0,
                }
            },
        }
    }


class TestLoadThresholds:
    def test_loads_thresholds(self, pyproject_with_thresholds: Path) -> None:
        result = load_thresholds(pyproject_with_thresholds)
        assert result == {"core": 75, "fitting": 80, "mcp/market": 60}

    def test_empty_when_no_section(self, pyproject_empty: Path) -> None:
        result = load_thresholds(pyproject_empty)
        assert result == {}


class TestAggregateCoverage:
    def test_groups_by_top_level_module(self, sample_coverage_data: dict) -> None:
        result = aggregate_coverage(sample_coverage_data)
        # core = auth.py + client.py
        assert result["core"]["stmts"] == 150
        assert result["core"]["miss"] == 25
        assert result["core"]["branches"] == 60
        assert result["core"]["branch_miss"] == 8

    def test_groups_mcp_two_levels(self, sample_coverage_data: dict) -> None:
        result = aggregate_coverage(sample_coverage_data)
        assert "mcp/market" in result
        assert result["mcp/market"]["stmts"] == 180

    def test_excludes_non_src_files(self, sample_coverage_data: dict) -> None:
        result = aggregate_coverage(sample_coverage_data)
        # tests/test_something.py should not appear
        for key in result:
            assert not key.startswith("tests")

    def test_fitting_standalone(self, sample_coverage_data: dict) -> None:
        result = aggregate_coverage(sample_coverage_data)
        assert result["fitting"]["stmts"] == 200
        assert result["fitting"]["miss"] == 10

    def test_empty_data(self) -> None:
        result = aggregate_coverage({"files": {}})
        assert result == {}


class TestCalculateCoveragePct:
    def test_full_coverage(self) -> None:
        pct = calculate_coverage_pct(
            {"stmts": 100, "miss": 0, "branches": 50, "branch_miss": 0}
        )
        assert pct == 100.0

    def test_zero_statements(self) -> None:
        pct = calculate_coverage_pct(
            {"stmts": 0, "miss": 0, "branches": 0, "branch_miss": 0}
        )
        assert pct == 100.0

    def test_partial_coverage(self) -> None:
        pct = calculate_coverage_pct(
            {"stmts": 100, "miss": 20, "branches": 0, "branch_miss": 0}
        )
        assert pct == pytest.approx(80.0)

    def test_combined_line_and_branch(self) -> None:
        # 100 stmts + 50 branches = 150 total, 10+5 = 15 missed => 90%
        pct = calculate_coverage_pct(
            {"stmts": 100, "miss": 10, "branches": 50, "branch_miss": 5}
        )
        assert pct == pytest.approx(90.0)


class TestCheckThresholds:
    def test_all_pass(self) -> None:
        thresholds = {"core": 75, "fitting": 80}
        modules = {
            "core": {"stmts": 100, "miss": 10, "branches": 0, "branch_miss": 0},
            "fitting": {"stmts": 100, "miss": 5, "branches": 0, "branch_miss": 0},
        }
        failures = check_thresholds(thresholds, modules)
        assert failures == []

    def test_one_failure(self) -> None:
        thresholds = {"core": 90, "fitting": 80}
        modules = {
            "core": {"stmts": 100, "miss": 20, "branches": 0, "branch_miss": 0},
            "fitting": {"stmts": 100, "miss": 5, "branches": 0, "branch_miss": 0},
        }
        failures = check_thresholds(thresholds, modules)
        assert len(failures) == 1
        assert failures[0][0] == "core"

    def test_missing_module_skipped(self) -> None:
        thresholds = {"nonexistent": 80}
        modules = {
            "core": {"stmts": 100, "miss": 0, "branches": 0, "branch_miss": 0},
        }
        failures = check_thresholds(thresholds, modules)
        assert failures == []

    def test_exact_threshold_passes(self) -> None:
        thresholds = {"core": 80.0}
        modules = {
            "core": {"stmts": 100, "miss": 20, "branches": 0, "branch_miss": 0},
        }
        failures = check_thresholds(thresholds, modules)
        assert failures == []
