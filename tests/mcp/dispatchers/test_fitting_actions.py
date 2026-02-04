"""
Tests for Fitting Dispatcher Action Implementations.

Tests the individual action implementations in the fitting dispatcher:
- calculate_stats: Complete ship fitting statistics
- check_requirements: Pilot skill requirements check
- extract_requirements: Extract skill requirements from fit
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

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
        # Configure policy to deny authenticated
        engine = PolicyEngine.get_instance()
        engine.config = PolicyConfig(
            allowed_levels={SensitivityLevel.PUBLIC, SensitivityLevel.AGGREGATE, SensitivityLevel.MARKET}
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
            result = asyncio.run(
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
