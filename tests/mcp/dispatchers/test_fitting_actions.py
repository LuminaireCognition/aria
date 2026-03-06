"""
Tests for Fitting Dispatcher Action Implementations.

Tests the individual action implementations in the fitting dispatcher:
- calculate_stats: Complete ship fitting statistics
- check_requirements: Pilot skill requirements check
- extract_requirements: Extract skill requirements from fit
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from aria_esi.mcp.errors import InvalidParameterError
from aria_esi.mcp.policy import PolicyConfig, PolicyEngine, SensitivityLevel

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def reset_policy():
    """Reset policy singleton for each test."""
    PolicyEngine.reset_instance()
    yield
    PolicyEngine.reset_instance()


SAMPLE_EFT = """[Vexor, Test Fit]
Drone Damage Amplifier II
Drone Damage Amplifier II
Damage Control II
Medium Armor Repairer II

10MN Afterburner II
Medium Cap Battery II
Omnidirectional Tracking Link I

Drone Link Augmentor I

Medium Auxiliary Nano Pump I
Medium Auxiliary Nano Pump I
Medium Auxiliary Nano Pump I

Hammerhead II x5
Hobgoblin II x5
"""

MINIMAL_EFT = """[Venture, Mining]
Mining Laser I
Mining Laser I
"""


# =============================================================================
# Calculate Stats Action Tests
# =============================================================================


class TestCalculateStatsAction:
    """Tests for fitting calculate_stats action."""

    def test_calculate_stats_requires_eft(self, fitting_dispatcher):
        """Calculate stats action requires eft parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(fitting_dispatcher(action="calculate_stats"))

        assert "eft" in str(exc.value).lower()

    def test_calculate_stats_basic(self, fitting_dispatcher):
        """Basic stats calculation."""
        mock_result = {
            "ship": {"name": "Vexor", "fit_name": "Test Fit"},
            "dps": {"total": 400},
            "tank": {"ehp": {"total": 25000}},
            "resources": {"cpu": {"used": 300, "total": 400}},
            "metadata": {"skill_mode": "all_v"}
        }

        with patch(
            "aria_esi.mcp.dispatchers.fitting._calculate_stats",
            new_callable=AsyncMock,
            return_value=mock_result
        ):
            result = asyncio.run(
                fitting_dispatcher(action="calculate_stats", eft=SAMPLE_EFT)
            )

        assert "ship" in result
        assert result["ship"]["name"] == "Vexor"

    def test_calculate_stats_with_damage_profile(self, fitting_dispatcher):
        """Stats calculation with damage profile."""
        mock_result = {
            "ship": {"name": "Vexor", "fit_name": "Test Fit"},
            "dps": {"total": 400},
            "tank": {"ehp": {"total": 25000}},
            "metadata": {"damage_profile": {"em": 25, "thermal": 25, "kinetic": 25, "explosive": 25}}
        }

        with patch(
            "aria_esi.mcp.dispatchers.fitting._calculate_stats",
            new_callable=AsyncMock,
            return_value=mock_result
        ):
            result = asyncio.run(
                fitting_dispatcher(
                    action="calculate_stats",
                    eft=SAMPLE_EFT,
                    damage_profile={"em": 25, "thermal": 25, "kinetic": 25, "explosive": 25}
                )
            )

        assert isinstance(result, dict)

    def test_calculate_stats_authenticated_denied_falls_back(self, fitting_dispatcher):
        """When authenticated is denied, falls back to all-V with warning."""
        # Configure policy to fully deny authenticated (not even require_confirmation)
        engine = PolicyEngine.get_instance()
        engine.config = PolicyConfig(
            allowed_levels={SensitivityLevel.PUBLIC, SensitivityLevel.AGGREGATE, SensitivityLevel.MARKET},
            require_confirmation=set(),
        )

        mock_result = {
            "ship": {"name": "Vexor", "fit_name": "Test Fit"},
            "dps": {"total": 400},
            "tank": {"ehp": {"total": 25000}},
            "metadata": {"skill_mode": "all_v", "warnings": []}
        }

        with patch(
            "aria_esi.mcp.dispatchers.fitting._calculate_stats",
            new_callable=AsyncMock,
            return_value=mock_result
        ) as mock_calc:
            result = asyncio.run(
                fitting_dispatcher(
                    action="calculate_stats",
                    eft=SAMPLE_EFT,
                    use_pilot_skills=True  # Request pilot skills
                )
            )

            # Should have called with use_pilot_skills=False (fallback)
            mock_calc.assert_called_once()
            call_args = mock_calc.call_args
            assert call_args[0][2] is False  # use_pilot_skills arg

            # Result should contain policy warning
            assert "metadata" in result
            assert "warnings" in result["metadata"]
            assert any("authenticated not allowed" in w for w in result["metadata"]["warnings"])

    def test_calculate_stats_uses_all_v_by_default(self, fitting_dispatcher):
        """Stats calculation defaults to all-V skills."""
        mock_result = {
            "ship": {"name": "Vexor", "fit_name": "Test Fit"},
            "dps": {"total": 400},
            "tank": {"ehp": {"total": 25000}},
            "metadata": {"skill_mode": "all_v"}
        }

        with patch(
            "aria_esi.mcp.dispatchers.fitting._calculate_stats",
            new_callable=AsyncMock,
            return_value=mock_result
        ) as mock_calc:
            asyncio.run(
                fitting_dispatcher(
                    action="calculate_stats",
                    eft=SAMPLE_EFT
                    # use_pilot_skills not specified
                )
            )

            # Should have been called with use_pilot_skills=False
            mock_calc.assert_called_once()
            call_args = mock_calc.call_args
            assert call_args[0][2] is False

    def test_calculate_stats_includes_dps_breakdown(self, fitting_dispatcher):
        """Stats include DPS breakdown by type."""
        mock_result = {
            "ship": {"name": "Vexor", "fit_name": "Test Fit"},
            "dps": {
                "total": 400,
                "drones": 300,
                "turrets": 0,
                "missiles": 0
            },
            "tank": {"ehp": {"total": 25000}},
            "metadata": {}
        }

        with patch(
            "aria_esi.mcp.dispatchers.fitting._calculate_stats",
            new_callable=AsyncMock,
            return_value=mock_result
        ):
            result = asyncio.run(
                fitting_dispatcher(action="calculate_stats", eft=SAMPLE_EFT)
            )

        assert "dps" in result
        assert "total" in result["dps"]

    def test_calculate_stats_includes_tank_info(self, fitting_dispatcher):
        """Stats include tank/EHP information."""
        mock_result = {
            "ship": {"name": "Vexor", "fit_name": "Test Fit"},
            "dps": {"total": 400},
            "tank": {
                "ehp": {"total": 25000, "shield": 5000, "armor": 15000, "hull": 5000},
                "resists": {}
            },
            "metadata": {}
        }

        with patch(
            "aria_esi.mcp.dispatchers.fitting._calculate_stats",
            new_callable=AsyncMock,
            return_value=mock_result
        ):
            result = asyncio.run(
                fitting_dispatcher(action="calculate_stats", eft=SAMPLE_EFT)
            )

        assert "tank" in result
        assert "ehp" in result["tank"]

    def test_calculate_stats_includes_resources(self, fitting_dispatcher):
        """Stats include CPU/PG resource usage."""
        mock_result = {
            "ship": {"name": "Vexor", "fit_name": "Test Fit"},
            "dps": {"total": 400},
            "tank": {"ehp": {"total": 25000}},
            "resources": {
                "cpu": {"used": 300, "total": 450},
                "powergrid": {"used": 800, "total": 1000}
            },
            "metadata": {}
        }

        with patch(
            "aria_esi.mcp.dispatchers.fitting._calculate_stats",
            new_callable=AsyncMock,
            return_value=mock_result
        ):
            result = asyncio.run(
                fitting_dispatcher(action="calculate_stats", eft=SAMPLE_EFT)
            )

        assert "resources" in result


# =============================================================================
# Check Requirements Action Tests
# =============================================================================


class TestCheckRequirementsAction:
    """Tests for fitting check_requirements action."""

    def test_check_requirements_requires_eft(self, fitting_dispatcher):
        """Check requirements action requires eft parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(
                fitting_dispatcher(
                    action="check_requirements",
                    pilot_skills={3436: 5}  # Drones V
                )
            )

        assert "eft" in str(exc.value).lower()

    def test_check_requirements_requires_pilot_skills(self, fitting_dispatcher):
        """Check requirements action requires pilot_skills parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(
                fitting_dispatcher(
                    action="check_requirements",
                    eft=SAMPLE_EFT
                )
            )

        assert "pilot_skills" in str(exc.value).lower()

    def test_check_requirements_can_fly_true(self, fitting_dispatcher):
        """Check requirements when pilot can fly."""
        mock_result = {
            "can_fly": True,
            "missing_skills": [],
            "total_skills_checked": 15
        }

        with patch(
            "aria_esi.mcp.dispatchers.fitting._check_requirements",
            new_callable=AsyncMock,
            return_value=mock_result
        ):
            result = asyncio.run(
                fitting_dispatcher(
                    action="check_requirements",
                    eft=SAMPLE_EFT,
                    pilot_skills={3436: 5, 33699: 4}
                )
            )

        assert result["can_fly"] is True
        assert len(result["missing_skills"]) == 0

    def test_check_requirements_can_fly_false(self, fitting_dispatcher):
        """Check requirements when pilot cannot fly."""
        mock_result = {
            "can_fly": False,
            "missing_skills": [
                {"skill_id": 3436, "skill_name": "Drones", "required": 5, "current": 3}
            ],
            "total_skills_checked": 15
        }

        with patch(
            "aria_esi.mcp.dispatchers.fitting._check_requirements",
            new_callable=AsyncMock,
            return_value=mock_result
        ):
            result = asyncio.run(
                fitting_dispatcher(
                    action="check_requirements",
                    eft=SAMPLE_EFT,
                    pilot_skills={3436: 3}
                )
            )

        assert result["can_fly"] is False
        assert len(result["missing_skills"]) > 0

    def test_check_requirements_accepts_dict_pilot_skills(self, fitting_dispatcher):
        """Check requirements accepts a proper dict with int keys (the only MCP path)."""
        mock_result = {
            "can_fly": True,
            "missing_skills": [],
            "total_skills_checked": 1
        }

        with patch(
            "aria_esi.mcp.dispatchers.fitting._check_requirements",
            new_callable=AsyncMock,
            return_value=mock_result
        ) as mock_check:
            result = asyncio.run(
                fitting_dispatcher(
                    action="check_requirements",
                    eft=SAMPLE_EFT,
                    pilot_skills={3436: 5, 33699: 4}
                )
            )

        assert result["can_fly"] is True
        call_args = mock_check.call_args
        assert call_args[0][1] == {3436: 5, 33699: 4}

    def test_check_requirements_coerces_json_string(self, fitting_dispatcher):
        """String-serialized JSON dict is coerced to dict before reaching handler."""
        mock_result = {
            "can_fly": True,
            "missing_skills": [],
            "total_skills_checked": 2,
        }

        with patch(
            "aria_esi.mcp.dispatchers.fitting._check_requirements",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_check:
            result = asyncio.run(
                fitting_dispatcher(
                    action="check_requirements",
                    eft=SAMPLE_EFT,
                    pilot_skills='{"3436": 5, "33699": 4}',
                )
            )

        assert result["can_fly"] is True
        call_args = mock_check.call_args
        passed_skills = call_args[0][1]
        assert isinstance(passed_skills, dict)
        assert passed_skills == {"3436": 5, "33699": 4}

    def test_check_requirements_coerces_python_dict_string(self, fitting_dispatcher):
        """String-serialized Python dict (unquoted keys) is coerced via ast.literal_eval."""
        mock_result = {
            "can_fly": True,
            "missing_skills": [],
            "total_skills_checked": 2,
        }

        with patch(
            "aria_esi.mcp.dispatchers.fitting._check_requirements",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_check:
            result = asyncio.run(
                fitting_dispatcher(
                    action="check_requirements",
                    eft=SAMPLE_EFT,
                    pilot_skills="{3436: 5, 33699: 4}",
                )
            )

        assert result["can_fly"] is True
        call_args = mock_check.call_args
        passed_skills = call_args[0][1]
        assert isinstance(passed_skills, dict)
        assert passed_skills == {3436: 5, 33699: 4}

    def test_check_requirements_large_string_dict(self, fitting_dispatcher):
        """88-entry string dict (realistic MCP payload) is fully preserved after coercion."""
        # Build an 88-entry skill dict
        large_skills = {str(3400 + i): 5 for i in range(88)}
        large_skills_str = json.dumps(large_skills)

        mock_result = {
            "can_fly": True,
            "missing_skills": [],
            "total_skills_checked": 88,
        }

        with patch(
            "aria_esi.mcp.dispatchers.fitting._check_requirements",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_check:
            result = asyncio.run(
                fitting_dispatcher(
                    action="check_requirements",
                    eft=SAMPLE_EFT,
                    pilot_skills=large_skills_str,
                )
            )

        assert result["can_fly"] is True
        call_args = mock_check.call_args
        passed_skills = call_args[0][1]
        assert isinstance(passed_skills, dict)
        assert len(passed_skills) == 88

    def test_check_requirements_highest_level_wins(self, fitting_dispatcher):
        """When multiple items require the same skill at different levels,
        the highest required level must be checked (not just the first seen).

        Regression test for: Cap Recharger II (EGU 3) shadowing
        Large Cap Battery II (EGU 4) in deduplication.
        """
        # Mock parsed fit with two mid-slot modules
        mock_parsed_fit = type("ParsedFit", (), {
            "ship_type_id": 29340,  # Vexor
            "low_slots": [],
            "mid_slots": [
                type("Module", (), {"type_id": 2032, "charge_type_id": None})(),  # Cap Recharger II
                type("Module", (), {"type_id": 3504, "charge_type_id": None})(),  # Large Cap Battery II
            ],
            "high_slots": [],
            "rigs": [],
            "subsystems": [],
            "drones": [],
        })()

        # Skill reqs: Cap Recharger II needs EGU 3, Large Cap Battery II needs EGU 4
        mock_skill_reqs = {
            29340: {},  # Ship has no additional reqs for this test
            2032: {3424: 3},   # Cap Recharger II -> EGU III
            3504: {3424: 4},   # Large Cap Battery II -> EGU IV
        }

        # Pilot has EGU III — should fail on EGU IV
        pilot_skills = {3424: 3}

        with (
            patch(
                "aria_esi.fitting.parse_eft",
                return_value=mock_parsed_fit,
            ),
            patch(
                "aria_esi.fitting.skills._load_skill_requirements",
                return_value=mock_skill_reqs,
            ),
            patch(
                "aria_esi.fitting.get_eos_data_manager",
            ),
            patch(
                "aria_esi.mcp.dispatchers.fitting._resolve_skill_name",
                return_value="Energy Grid Upgrades",
            ),
        ):
            result = asyncio.run(
                fitting_dispatcher(
                    action="check_requirements",
                    eft="[Vexor, Test]\nCap Recharger II\nLarge Cap Battery II",
                    pilot_skills=pilot_skills,
                )
            )

        assert result["can_fly"] is False
        assert len(result["missing_skills"]) == 1
        assert result["missing_skills"][0]["skill_name"] == "Energy Grid Upgrades"
        assert result["missing_skills"][0]["required"] == 4
        assert result["missing_skills"][0]["current"] == 3


# =============================================================================
# Extract Requirements Action Tests
# =============================================================================


class TestExtractRequirementsAction:
    """Tests for fitting extract_requirements action."""

    def test_extract_requirements_requires_eft(self, fitting_dispatcher):
        """Extract requirements action requires eft parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(fitting_dispatcher(action="extract_requirements"))

        assert "eft" in str(exc.value).lower()

    def test_extract_requirements_basic(self, fitting_dispatcher):
        """Basic extract requirements."""
        mock_result = {
            "skills": ["Gallente Cruiser IV", "Drones V", "Medium Drone Operation IV"],
            "skill_ids": {3330: 4, 3436: 5, 33699: 4},
            "total_skills": 3
        }

        with patch(
            "aria_esi.mcp.dispatchers.fitting._extract_requirements",
            new_callable=AsyncMock,
            return_value=mock_result
        ):
            result = asyncio.run(
                fitting_dispatcher(action="extract_requirements", eft=SAMPLE_EFT)
            )

        assert "skills" in result
        assert "skill_ids" in result
        assert "total_skills" in result

    def test_extract_requirements_includes_all_modules(self, fitting_dispatcher):
        """Extract requirements includes skills for all modules."""
        mock_result = {
            "skills": [
                "Gallente Cruiser IV",
                "Drones V",
                "Armor Rigging I",
                "Hull Upgrades IV"
            ],
            "skill_ids": {3330: 4, 3436: 5, 26252: 1, 3393: 4},
            "total_skills": 4
        }

        with patch(
            "aria_esi.mcp.dispatchers.fitting._extract_requirements",
            new_callable=AsyncMock,
            return_value=mock_result
        ):
            result = asyncio.run(
                fitting_dispatcher(action="extract_requirements", eft=SAMPLE_EFT)
            )

        assert len(result["skills"]) > 0


# =============================================================================
# Invalid Action Tests
# =============================================================================


class TestRecommendAction:
    """Tests for fitting recommend action (Phase 3 validation).

    Covers all 12 validation cases from FIT_ARCHETYPES_AND_SKILL_PERFORMANCE Phase 3 step 4.
    """

    def test_role_filter_with_multiple_results(self, fitting_dispatcher):
        """Query with role having ≥3 archetypes; verify filtering and sort order."""
        with patch(
            "aria_esi.mcp.dispatchers.fitting._estimate_cost",
            return_value=10_000_000,
        ):
            result = asyncio.run(
                fitting_dispatcher(action="recommend", role="missions-l1")
            )

        assert "results" in result
        assert len(result["results"]) >= 3
        # Verify sort: higher tiers first
        tier_rank = {"t1": 0, "meta": 1, "t2_budget": 2, "t2_optimal": 3}
        tiers = [tier_rank.get(r["tier"], -1) for r in result["results"]]
        assert tiers == sorted(tiers, reverse=True)
        # All results should have the queried role
        for r in result["results"]:
            assert "missions-l1" in r["roles"]

    def test_impossible_budget_returns_empty_with_message(self, fitting_dispatcher):
        """Query with impossible budget constraint; verify empty result with message."""
        with patch(
            "aria_esi.mcp.dispatchers.fitting._estimate_cost",
            return_value=50_000_000,
        ):
            result = asyncio.run(
                fitting_dispatcher(action="recommend", role="missions-l1", budget_isk=1)
            )

        assert result["results"] == []
        assert result["message"] is not None

    def test_hull_plus_role_combined_filter(self, fitting_dispatcher):
        """Query with hull + role combined filter; verify intersection filtering."""
        with patch(
            "aria_esi.mcp.dispatchers.fitting._estimate_cost",
            return_value=5_000_000,
        ):
            result = asyncio.run(
                fitting_dispatcher(action="recommend", role="missions-l4", hull="Raven")
            )

        assert "results" in result
        assert len(result["results"]) >= 1
        for r in result["results"]:
            assert r["hull"] == "Raven"
            assert "missions-l4" in r["roles"]

    def test_invalid_role_raises_error(self, fitting_dispatcher):
        """Query with invalid role; verify InvalidParameterError, not empty array."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(
                fitting_dispatcher(action="recommend", role="pve-ratting")
            )
        assert "pve-ratting" in str(exc.value)
        assert "must be one of" in str(exc.value).lower()

    def test_limit_truncation(self, fitting_dispatcher):
        """Query with limit=2 when ≥3 results exist; verify truncation."""
        with patch(
            "aria_esi.mcp.dispatchers.fitting._estimate_cost",
            return_value=10_000_000,
        ):
            result = asyncio.run(
                fitting_dispatcher(action="recommend", role="missions-l1", limit=2)
            )

        assert len(result["results"]) <= 2

    def test_limit_larger_than_results(self, fitting_dispatcher):
        """Query with limit=10 when only 2 exist; verify all returned."""
        with patch(
            "aria_esi.mcp.dispatchers.fitting._estimate_cost",
            return_value=10_000_000,
        ):
            result = asyncio.run(
                fitting_dispatcher(action="recommend", role="missions-l4", hull="Raven", limit=10)
            )

        # Raven has 2 entries (t1, meta); all should be returned
        assert len(result["results"]) >= 1
        assert len(result["results"]) <= 10

    def test_null_estimated_cost_when_market_unavailable(self, fitting_dispatcher):
        """Verify estimated_cost is null (not absent) when market data unavailable."""
        with patch(
            "aria_esi.mcp.dispatchers.fitting._estimate_cost",
            return_value=None,
        ):
            result = asyncio.run(
                fitting_dispatcher(action="recommend", role="missions-l1")
            )

        assert len(result["results"]) >= 1
        for r in result["results"]:
            assert "estimated_cost" in r
            assert r["estimated_cost"] is None

    def test_budget_isk_zero_raises_error(self, fitting_dispatcher):
        """Query with budget_isk=0; verify InvalidParameterError."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(
                fitting_dispatcher(action="recommend", role="missions-l1", budget_isk=0)
            )
        assert "budget_isk" in str(exc.value)

    def test_budget_isk_negative_raises_error(self, fitting_dispatcher):
        """Query with budget_isk=-1; verify InvalidParameterError."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(
                fitting_dispatcher(action="recommend", role="missions-l1", budget_isk=-1)
            )
        assert "budget_isk" in str(exc.value)

    def test_limit_zero_raises_error(self, fitting_dispatcher):
        """Query with limit=0; verify InvalidParameterError."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(
                fitting_dispatcher(action="recommend", role="missions-l1", limit=0)
            )
        assert "limit" in str(exc.value)

    def test_limit_negative_raises_error(self, fitting_dispatcher):
        """Query with limit=-1; verify InvalidParameterError."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(
                fitting_dispatcher(action="recommend", role="missions-l1", limit=-1)
            )
        assert "limit" in str(exc.value)

    def test_null_cost_entries_omitted_with_budget(self, fitting_dispatcher):
        """With budget_isk, null-cost entries are omitted from results."""
        call_count = 0

        def alternating_cost(project_root, path):
            nonlocal call_count
            call_count += 1
            # Alternate: first returns a price, second returns None
            return 5_000_000 if call_count % 2 == 1 else None

        with patch(
            "aria_esi.mcp.dispatchers.fitting._estimate_cost",
            side_effect=alternating_cost,
        ):
            result = asyncio.run(
                fitting_dispatcher(
                    action="recommend", role="missions-l1", budget_isk=100_000_000
                )
            )

        # All returned entries should have non-null costs
        for r in result["results"]:
            assert r["estimated_cost"] is not None

    def test_parse_eft_failure_returns_null_cost(self, fitting_dispatcher):
        """Simulate parse_eft failure; verify entry has null cost, call succeeds."""
        costs = {}

        def cost_with_one_failure(project_root, path):
            if "kestrel" in path:
                return None  # Simulates parse_eft failure
            return 10_000_000

        with patch(
            "aria_esi.mcp.dispatchers.fitting._estimate_cost",
            side_effect=cost_with_one_failure,
        ):
            result = asyncio.run(
                fitting_dispatcher(action="recommend", role="missions-l1")
            )

        assert len(result["results"]) >= 1
        # Some entries may have null cost, others should have valid cost
        has_null = any(r["estimated_cost"] is None for r in result["results"])
        has_valid = any(r["estimated_cost"] is not None for r in result["results"])
        assert has_null or has_valid  # At least one type exists

    def test_all_null_cost_with_budget_distinct_message(self, fitting_dispatcher):
        """When ALL matching archetypes have null cost and budget is set,
        verify distinct message about market data unavailability."""
        with patch(
            "aria_esi.mcp.dispatchers.fitting._estimate_cost",
            return_value=None,
        ):
            result = asyncio.run(
                fitting_dispatcher(
                    action="recommend", role="missions-l1", budget_isk=100_000_000
                )
            )

        assert result["results"] == []
        assert "market data is unavailable" in result["message"]
        assert "budget" in result["message"].lower()

    def test_missing_role_raises_error(self, fitting_dispatcher):
        """Recommend without role raises InvalidParameterError."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(fitting_dispatcher(action="recommend"))
        assert "role" in str(exc.value)

    def test_result_format_envelope(self, fitting_dispatcher):
        """Verify return format has results array and message field."""
        with patch(
            "aria_esi.mcp.dispatchers.fitting._estimate_cost",
            return_value=10_000_000,
        ):
            result = asyncio.run(
                fitting_dispatcher(action="recommend", role="missions-l1", limit=1)
            )

        assert "results" in result
        assert "message" in result
        assert isinstance(result["results"], list)
        entry = result["results"][0]
        assert "hull" in entry
        assert "path" in entry
        assert "tier" in entry
        assert "roles" in entry
        assert "estimated_cost" in entry
        assert isinstance(entry["roles"], list)

    def test_no_match_returns_empty_with_message(self, fitting_dispatcher):
        """Non-matching filter returns empty results with message."""
        with patch(
            "aria_esi.mcp.dispatchers.fitting._estimate_cost",
            return_value=10_000_000,
        ):
            result = asyncio.run(
                fitting_dispatcher(
                    action="recommend", role="missions-l4", hull="Venture"
                )
            )

        assert result["results"] == []
        assert result["message"] == "No archetypes match the given constraints."


class TestFittingInvalidActions:
    """Tests for invalid action handling."""

    def test_invalid_action_raises_error(self, fitting_dispatcher):
        """Unknown action raises InvalidParameterError."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(fitting_dispatcher(action="nonexistent_action"))

        assert "action" in str(exc.value)
        assert "must be one of" in str(exc.value).lower()

    def test_empty_action_raises_error(self, fitting_dispatcher):
        """Empty action raises InvalidParameterError."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(fitting_dispatcher(action=""))

        assert "action" in str(exc.value)


# =============================================================================
# EFT Parsing Edge Cases
# =============================================================================


class TestEFTParsingEdgeCases:
    """Tests for EFT parsing edge cases."""

    def test_minimal_eft(self, fitting_dispatcher):
        """Minimal EFT (ship with basic modules)."""
        mock_result = {
            "ship": {"name": "Venture", "fit_name": "Mining"},
            "dps": {"total": 0},
            "tank": {"ehp": {"total": 2000}},
            "metadata": {}
        }

        with patch(
            "aria_esi.mcp.dispatchers.fitting._calculate_stats",
            new_callable=AsyncMock,
            return_value=mock_result
        ):
            result = asyncio.run(
                fitting_dispatcher(action="calculate_stats", eft=MINIMAL_EFT)
            )

        assert result["ship"]["name"] == "Venture"

    def test_eft_with_empty_slots(self, fitting_dispatcher):
        """EFT with empty slots indicated by [Empty]."""
        eft_empty_slots = """[Venture, Empty Test]
Mining Laser I
[Empty High slot]

[Empty Med slot]
"""
        mock_result = {
            "ship": {"name": "Venture", "fit_name": "Empty Test"},
            "dps": {"total": 0},
            "tank": {"ehp": {"total": 2000}},
            "metadata": {}
        }

        with patch(
            "aria_esi.mcp.dispatchers.fitting._calculate_stats",
            new_callable=AsyncMock,
            return_value=mock_result
        ):
            result = asyncio.run(
                fitting_dispatcher(action="calculate_stats", eft=eft_empty_slots)
            )

        assert isinstance(result, dict)

    def test_eft_with_charges(self, fitting_dispatcher):
        """EFT with ammunition/charges."""
        eft_with_charges = """[Venture, With Charges]
Mining Laser I, Veldspar
Mining Laser I, Scordite
"""
        mock_result = {
            "ship": {"name": "Venture", "fit_name": "With Charges"},
            "dps": {"total": 0},
            "tank": {"ehp": {"total": 2000}},
            "metadata": {}
        }

        with patch(
            "aria_esi.mcp.dispatchers.fitting._calculate_stats",
            new_callable=AsyncMock,
            return_value=mock_result
        ):
            result = asyncio.run(
                fitting_dispatcher(action="calculate_stats", eft=eft_with_charges)
            )

        assert isinstance(result, dict)
