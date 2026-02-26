"""
Tests for Fitting Stats MCP Tool.

Tests EOS data validation, EFT parsing, damage profiles, pilot skills,
and calculation error paths in calculate_fit_stats.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aria_esi.mcp.fitting.tools_stats import register_stats_tools

# =============================================================================
# Test Fixtures
# =============================================================================


@dataclass
class MockEOSDataStatus:
    is_valid: bool = True
    data_path: Path = Path("/fake/eos-data")
    version: str | None = "2548611"
    fsd_built_files: list[str] | None = None
    fsd_lite_files: list[str] | None = None
    phobos_files: list[str] | None = None
    missing_files: list[str] | None = None
    total_records: int = 45000
    error_message: str | None = None

    def to_dict(self) -> dict:
        return {
            "is_valid": self.is_valid,
            "data_path": str(self.data_path),
            "version": self.version,
            "total_records": self.total_records,
        }


@pytest.fixture
def stats_tool():
    """Register stats tools and return the inner async function."""
    server = MagicMock()
    tools = {}

    def tool_decorator():
        def decorator(func):
            tools[func.__name__] = func
            return func

        return decorator

    server.tool = tool_decorator
    register_stats_tools(server)
    return tools["calculate_fit_stats"]


SAMPLE_EFT = "[Vexor, Test]\nDrone Damage Amplifier II"


# =============================================================================
# EOS Data Validation
# =============================================================================


class TestEOSDataMissing:
    @pytest.mark.anyio
    async def test_eos_data_missing(self, stats_tool) -> None:
        """Returns error when EOS data is missing."""
        from aria_esi.fitting import EOSDataError

        mock_manager = MagicMock()
        mock_manager.ensure_valid.side_effect = EOSDataError(
            "EOS data not found", missing_files=["types.json"]
        )

        with patch("aria_esi.fitting.get_eos_data_manager", return_value=mock_manager):
            result = await stats_tool(eft=SAMPLE_EFT)

        assert result["error"] == "eos_data_missing"
        assert result["missing_files"] == ["types.json"]
        assert "hint" in result


# =============================================================================
# EFT Parsing Errors
# =============================================================================


class TestEFTParsing:
    @pytest.mark.anyio
    async def test_type_resolution_error(self, stats_tool) -> None:
        """Returns error with suggestions when type name can't be resolved."""
        from aria_esi.fitting import TypeResolutionError

        mock_manager = MagicMock()
        mock_manager.ensure_valid.return_value = None

        with (
            patch("aria_esi.fitting.get_eos_data_manager", return_value=mock_manager),
            patch(
                "aria_esi.fitting.parse_eft",
                side_effect=TypeResolutionError("Vexor Navy Isue", suggestions=["Vexor Navy Issue"]),
            ),
        ):
            result = await stats_tool(eft="[Vexor Navy Isue, Test]")

        assert result["error"] == "type_resolution_error"
        assert result["type_name"] == "Vexor Navy Isue"
        assert "Vexor Navy Issue" in result["suggestions"]

    @pytest.mark.anyio
    async def test_eft_parse_error(self, stats_tool) -> None:
        """Returns error with line number on parse failure."""
        from aria_esi.fitting import EFTParseError

        mock_manager = MagicMock()
        mock_manager.ensure_valid.return_value = None

        with (
            patch("aria_esi.fitting.get_eos_data_manager", return_value=mock_manager),
            patch(
                "aria_esi.fitting.parse_eft",
                side_effect=EFTParseError("Invalid header", line_number=1),
            ),
        ):
            result = await stats_tool(eft="garbage input")

        assert result["error"] == "eft_parse_error"
        assert result["line_number"] == 1


# =============================================================================
# Damage Profile
# =============================================================================


class TestDamageProfile:
    @pytest.mark.anyio
    async def test_default_omni_profile(self, stats_tool) -> None:
        """Uses omni damage profile when none specified."""
        mock_manager = MagicMock()
        mock_manager.ensure_valid.return_value = None
        mock_parsed = MagicMock()
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"ship": "Vexor", "dps": {}}

        with (
            patch("aria_esi.fitting.get_eos_data_manager", return_value=mock_manager),
            patch("aria_esi.fitting.parse_eft", return_value=mock_parsed),
            patch("aria_esi.fitting.calculate_fit_stats", return_value=mock_result) as mock_calc,
        ):
            result = await stats_tool(eft=SAMPLE_EFT)

        assert result == {"ship": "Vexor", "dps": {}}
        # Check the damage profile passed was omni
        call_args = mock_calc.call_args
        dmg = call_args[0][1]
        assert dmg.em == 25.0
        assert dmg.thermal == 25.0

    @pytest.mark.anyio
    async def test_custom_damage_profile(self, stats_tool) -> None:
        """Constructs custom damage profile from input."""
        mock_manager = MagicMock()
        mock_manager.ensure_valid.return_value = None
        mock_parsed = MagicMock()
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"ship": "Vexor"}

        with (
            patch("aria_esi.fitting.get_eos_data_manager", return_value=mock_manager),
            patch("aria_esi.fitting.parse_eft", return_value=mock_parsed),
            patch("aria_esi.fitting.calculate_fit_stats", return_value=mock_result) as mock_calc,
        ):
            result = await stats_tool(
                eft=SAMPLE_EFT,
                damage_profile={"em": 50, "thermal": 40, "kinetic": 5, "explosive": 5},
            )

        assert result == {"ship": "Vexor"}
        dmg = mock_calc.call_args[0][1]
        assert dmg.em == 50.0
        assert dmg.thermal == 40.0

    @pytest.mark.anyio
    async def test_invalid_damage_profile(self, stats_tool) -> None:
        """Returns error on invalid damage profile values."""
        mock_manager = MagicMock()
        mock_manager.ensure_valid.return_value = None
        mock_parsed = MagicMock()

        with (
            patch("aria_esi.fitting.get_eos_data_manager", return_value=mock_manager),
            patch("aria_esi.fitting.parse_eft", return_value=mock_parsed),
        ):
            result = await stats_tool(
                eft=SAMPLE_EFT,
                damage_profile={"em": "not_a_number", "thermal": 25, "kinetic": 25, "explosive": 25},
            )

        assert result["error"] == "invalid_damage_profile"


# =============================================================================
# Pilot Skills
# =============================================================================


class TestPilotSkills:
    @pytest.mark.anyio
    async def test_pilot_skills_success(self, stats_tool) -> None:
        """Uses pilot skills when requested and available."""
        mock_manager = MagicMock()
        mock_manager.ensure_valid.return_value = None
        mock_parsed = MagicMock()
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"ship": "Vexor"}

        mock_fetch_result = MagicMock()
        mock_fetch_result.skills = {3436: 5, 33699: 4}
        mock_fetch_result.source = "cache"

        with (
            patch("aria_esi.fitting.get_eos_data_manager", return_value=mock_manager),
            patch("aria_esi.fitting.parse_eft", return_value=mock_parsed),
            patch("aria_esi.fitting.calculate_fit_stats", return_value=mock_result) as mock_calc,
            patch("aria_esi.fitting.fetch_pilot_skills", return_value=mock_fetch_result),
        ):
            result = await stats_tool(eft=SAMPLE_EFT, use_pilot_skills=True)

        assert result == {"ship": "Vexor"}
        # Skills should have been passed
        call_args = mock_calc.call_args
        assert call_args[0][2] == {3436: 5, 33699: 4}

    @pytest.mark.anyio
    async def test_pilot_skills_auth_error(self, stats_tool) -> None:
        """Returns auth error when skill fetch fails with auth error."""
        from aria_esi.fitting import SkillFetchError

        mock_manager = MagicMock()
        mock_manager.ensure_valid.return_value = None
        mock_parsed = MagicMock()

        with (
            patch("aria_esi.fitting.get_eos_data_manager", return_value=mock_manager),
            patch("aria_esi.fitting.parse_eft", return_value=mock_parsed),
            patch(
                "aria_esi.fitting.fetch_pilot_skills",
                side_effect=SkillFetchError("Not authenticated", is_auth_error=True),
            ),
        ):
            result = await stats_tool(eft=SAMPLE_EFT, use_pilot_skills=True)

        assert result["error"] == "authentication_required"

    @pytest.mark.anyio
    async def test_pilot_skills_non_auth_error_falls_back(self, stats_tool) -> None:
        """Falls back to all-V on non-auth skill fetch errors."""
        from aria_esi.fitting import SkillFetchError

        mock_manager = MagicMock()
        mock_manager.ensure_valid.return_value = None
        mock_parsed = MagicMock()
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"ship": "Vexor"}

        with (
            patch("aria_esi.fitting.get_eos_data_manager", return_value=mock_manager),
            patch("aria_esi.fitting.parse_eft", return_value=mock_parsed),
            patch("aria_esi.fitting.calculate_fit_stats", return_value=mock_result) as mock_calc,
            patch(
                "aria_esi.fitting.fetch_pilot_skills",
                side_effect=SkillFetchError("Cache expired"),
            ),
        ):
            result = await stats_tool(eft=SAMPLE_EFT, use_pilot_skills=True)

        assert result == {"ship": "Vexor"}
        # skill_levels should be None (all-V fallback)
        assert mock_calc.call_args[0][2] is None


# =============================================================================
# Calculation Errors
# =============================================================================


class TestCalculation:
    @pytest.mark.anyio
    async def test_successful_calculation(self, stats_tool) -> None:
        """Returns result.to_dict() on success."""
        mock_manager = MagicMock()
        mock_manager.ensure_valid.return_value = None
        mock_parsed = MagicMock()
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {
            "ship": {"type": "Vexor", "name": "Test"},
            "dps": {"total": 500},
            "tank": {"ehp": 20000},
        }

        with (
            patch("aria_esi.fitting.get_eos_data_manager", return_value=mock_manager),
            patch("aria_esi.fitting.parse_eft", return_value=mock_parsed),
            patch("aria_esi.fitting.calculate_fit_stats", return_value=mock_result),
        ):
            result = await stats_tool(eft=SAMPLE_EFT)

        assert result["ship"]["type"] == "Vexor"
        assert result["dps"]["total"] == 500

    @pytest.mark.anyio
    async def test_eos_bridge_error(self, stats_tool) -> None:
        """Returns EOS calculation error on bridge failure."""
        from aria_esi.fitting import EOSBridgeError

        mock_manager = MagicMock()
        mock_manager.ensure_valid.return_value = None
        mock_parsed = MagicMock()

        with (
            patch("aria_esi.fitting.get_eos_data_manager", return_value=mock_manager),
            patch("aria_esi.fitting.parse_eft", return_value=mock_parsed),
            patch(
                "aria_esi.fitting.calculate_fit_stats",
                side_effect=EOSBridgeError("Calculation failed"),
            ),
        ):
            result = await stats_tool(eft=SAMPLE_EFT)

        assert result["error"] == "eos_calculation_error"

    @pytest.mark.anyio
    async def test_unexpected_error(self, stats_tool) -> None:
        """Returns generic error on unexpected exception."""
        mock_manager = MagicMock()
        mock_manager.ensure_valid.return_value = None
        mock_parsed = MagicMock()

        with (
            patch("aria_esi.fitting.get_eos_data_manager", return_value=mock_manager),
            patch("aria_esi.fitting.parse_eft", return_value=mock_parsed),
            patch(
                "aria_esi.fitting.calculate_fit_stats",
                side_effect=RuntimeError("Something unexpected"),
            ),
        ):
            result = await stats_tool(eft=SAMPLE_EFT)

        assert result["error"] == "calculation_error"
        assert "unexpected" in result["message"].lower()
