"""
Tests for archetypes selection module.

Tests skill-aware fit selection including skill checking, tank adequacy,
damage matching, tier discovery, and the main selection algorithm.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from aria_esi.archetypes.models import (
    Archetype,
    DamageTuning,
    MissionContext,
    Stats,
)
from aria_esi.archetypes.selection import (
    TIER_FILES,
    TIER_PRIORITY,
    FitCandidate,
    SelectionResult,
    _check_damage_match,
    _check_skill_requirements,
    _check_tank_adequacy,
    _discover_tiers,
    can_fly_archetype,
    get_recommended_fit,
    select_fits,
)

# =============================================================================
# FitCandidate Tests
# =============================================================================


class TestFitCandidate:
    """Tests for FitCandidate dataclass."""

    def test_to_dict_basic(self) -> None:
        """Test FitCandidate.to_dict() with minimal data."""
        archetype = MagicMock(spec=Archetype)
        archetype.to_dict.return_value = {"hull": "Vexor"}

        candidate = FitCandidate(
            archetype=archetype,
            tier="t1",
            can_fly=True,
        )

        result = candidate.to_dict()
        assert result["tier"] == "t1"
        assert result["can_fly"] is True
        assert result["missing_skills_count"] == 0
        assert result["tank_adequate"] is True
        assert result["damage_match"] is True
        assert result["estimated_isk"] is None
        assert result["archetype"] == {"hull": "Vexor"}

    def test_to_dict_with_missing_skills(self) -> None:
        """Test FitCandidate.to_dict() with missing skills."""
        archetype = MagicMock(spec=Archetype)
        archetype.to_dict.return_value = {}

        candidate = FitCandidate(
            archetype=archetype,
            tier="t2_optimal",
            can_fly=False,
            missing_skills=[
                {"skill_id": 3336, "required": 5, "current": 3},
                {"skill_id": 3426, "required": 4, "current": 0},
            ],
            tank_adequate=False,
            damage_match=False,
            estimated_isk=15_000_000,
        )

        result = candidate.to_dict()
        assert result["can_fly"] is False
        assert result["missing_skills_count"] == 2
        assert result["tank_adequate"] is False
        assert result["damage_match"] is False
        assert result["estimated_isk"] == 15_000_000

    def test_to_dict_with_none_archetype(self) -> None:
        """Test FitCandidate.to_dict() with None archetype."""
        candidate = FitCandidate(
            archetype=None,  # type: ignore[arg-type]
            tier="meta",
            can_fly=False,
        )

        result = candidate.to_dict()
        assert result["archetype"] is None


# =============================================================================
# SelectionResult Tests
# =============================================================================


class TestSelectionResult:
    """Tests for SelectionResult dataclass."""

    def test_to_dict_empty(self) -> None:
        """Test SelectionResult.to_dict() with no results."""
        result = SelectionResult()

        output = result.to_dict()
        assert output["selection_mode"] == "none"
        assert output["filters_applied"] == []
        assert output["warnings"] == []
        assert output["candidates_count"] == 0
        assert "recommended" not in output
        assert "efficient" not in output
        assert "premium" not in output

    def test_to_dict_single_mode(self) -> None:
        """Test SelectionResult.to_dict() with single recommendation."""
        archetype = MagicMock(spec=Archetype)
        archetype.to_dict.return_value = {"hull": "Vexor"}

        recommended = FitCandidate(archetype=archetype, tier="meta", can_fly=True)
        result = SelectionResult(
            recommended=recommended,
            selection_mode="single",
            filters_applied=["Found 1 tier(s)"],
        )

        output = result.to_dict()
        assert output["selection_mode"] == "single"
        assert "recommended" in output
        assert output["recommended"]["tier"] == "meta"

    def test_to_dict_dual_mode(self) -> None:
        """Test SelectionResult.to_dict() with dual efficient/premium."""
        archetype_eff = MagicMock(spec=Archetype)
        archetype_eff.to_dict.return_value = {"hull": "Vexor"}
        archetype_prem = MagicMock(spec=Archetype)
        archetype_prem.to_dict.return_value = {"hull": "Vexor"}

        efficient = FitCandidate(archetype=archetype_eff, tier="t1", can_fly=True)
        premium = FitCandidate(archetype=archetype_prem, tier="t2_optimal", can_fly=True)

        result = SelectionResult(
            efficient=efficient,
            premium=premium,
            selection_mode="dual",
        )

        output = result.to_dict()
        assert output["selection_mode"] == "dual"
        assert "efficient" in output
        assert "premium" in output
        assert output["efficient"]["tier"] == "t1"
        assert output["premium"]["tier"] == "t2_optimal"


# =============================================================================
# Skill Requirement Checking Tests
# =============================================================================


class TestCheckSkillRequirements:
    """Tests for _check_skill_requirements function."""

    def test_check_with_all_skills_met(self) -> None:
        """Test skill check when all requirements are met."""
        archetype = MagicMock(spec=Archetype)
        archetype.eft = "[Vexor, Test]\nDrone Damage Amplifier I"

        # Mock the skill requirements database
        with patch(
            "aria_esi.fitting.skills._load_skill_requirements"
        ) as mock_load, patch("aria_esi.fitting.parse_eft") as mock_parse:
            mock_load.return_value = {}  # No requirements
            mock_parse.return_value = MagicMock(
                ship_type_id=627,  # Vexor
                low_slots=[],
                mid_slots=[],
                high_slots=[],
                rigs=[],
                drones=[],
            )

            can_fly, missing = _check_skill_requirements(archetype, {3336: 5})
            assert can_fly is True
            assert missing == []

    def test_check_with_missing_skills(self) -> None:
        """Test skill check with missing requirements."""
        archetype = MagicMock(spec=Archetype)
        archetype.eft = "[Vexor, Test]\nDrone Damage Amplifier II"
        archetype.hull = "Vexor"

        with patch(
            "aria_esi.fitting.skills._load_skill_requirements"
        ) as mock_load, patch("aria_esi.fitting.parse_eft") as mock_parse:
            # Skill 3336 (Drones) required at level 5
            mock_load.return_value = {627: {3336: 5}}
            mock_parse.return_value = MagicMock(
                ship_type_id=627,
                low_slots=[],
                mid_slots=[],
                high_slots=[],
                rigs=[],
                drones=[],
            )

            # Pilot only has level 3
            can_fly, missing = _check_skill_requirements(archetype, {3336: 3})
            assert can_fly is False
            assert len(missing) == 1
            assert missing[0]["skill_id"] == 3336
            assert missing[0]["required"] == 5
            assert missing[0]["current"] == 3

    def test_check_with_load_failure(self) -> None:
        """Test skill check gracefully handles load failure."""
        archetype = MagicMock(spec=Archetype)
        archetype.eft = "[Vexor, Test]"
        archetype.hull = "Vexor"

        with patch(
            "aria_esi.fitting.skills._load_skill_requirements"
        ) as mock_load:
            mock_load.side_effect = FileNotFoundError("No skill data")

            # Should assume can fly when can't check
            can_fly, missing = _check_skill_requirements(archetype, {})
            assert can_fly is True
            assert missing == []

    def test_check_with_parse_failure(self) -> None:
        """Test skill check gracefully handles EFT parse failure."""
        archetype = MagicMock(spec=Archetype)
        archetype.eft = "invalid eft"
        archetype.hull = "Vexor"

        with patch(
            "aria_esi.fitting.skills._load_skill_requirements"
        ) as mock_load, patch("aria_esi.fitting.parse_eft") as mock_parse:
            mock_load.return_value = {}
            mock_parse.side_effect = ValueError("Parse error")

            # Should assume can fly when can't parse
            can_fly, missing = _check_skill_requirements(archetype, {})
            assert can_fly is True
            assert missing == []


# =============================================================================
# Tank Adequacy Tests
# =============================================================================


class TestCheckTankAdequacy:
    """Tests for _check_tank_adequacy function."""

    def test_no_mission_context(self) -> None:
        """Test tank check returns True with no mission context."""
        archetype = MagicMock(spec=Archetype)

        result = _check_tank_adequacy(archetype, None)
        assert result is True

    def test_active_tank_adequate(self) -> None:
        """Test active tank meeting threshold."""
        archetype = MagicMock(spec=Archetype)
        archetype.stats = Stats(dps=0, ehp=20000, tank_type="active", tank_regen=100)

        mission = MissionContext(mission_level=2)

        result = _check_tank_adequacy(archetype, mission)
        assert result is True

    def test_active_tank_inadequate(self) -> None:
        """Test active tank below threshold."""
        archetype = MagicMock(spec=Archetype)
        archetype.stats = Stats(dps=0, ehp=10000, tank_type="active", tank_regen=20)

        mission = MissionContext(mission_level=3)  # Requires 150 EHP/s

        result = _check_tank_adequacy(archetype, mission)
        assert result is False

    def test_buffer_tank_adequate(self) -> None:
        """Test buffer tank meeting threshold."""
        archetype = MagicMock(spec=Archetype)
        archetype.stats = Stats(dps=0, ehp=50000, tank_type="buffer")

        mission = MissionContext(mission_level=2)  # Requires 20000 EHP

        result = _check_tank_adequacy(archetype, mission)
        assert result is True

    def test_buffer_tank_inadequate(self) -> None:
        """Test buffer tank below threshold."""
        archetype = MagicMock(spec=Archetype)
        archetype.stats = Stats(dps=0, ehp=15000, tank_type="buffer")

        mission = MissionContext(mission_level=2)  # Requires 20000 EHP

        result = _check_tank_adequacy(archetype, mission)
        assert result is False

    def test_tank_type_fallback(self) -> None:
        """Test fallback to active tank when tank_type is None."""
        archetype = MagicMock(spec=Archetype)
        archetype.stats = Stats(dps=0, ehp=20000, tank_sustained=60)

        mission = MissionContext(mission_level=2)  # Requires 50 EHP/s

        result = _check_tank_adequacy(archetype, mission)
        assert result is True


# =============================================================================
# Damage Match Tests
# =============================================================================


class TestCheckDamageMatch:
    """Tests for _check_damage_match function."""

    def test_no_mission_context(self) -> None:
        """Test damage match returns True with no mission context."""
        archetype = MagicMock(spec=Archetype)

        result = _check_damage_match(archetype, None)
        assert result is True

    def test_no_enemy_weakness(self) -> None:
        """Test damage match returns True with no enemy weakness specified."""
        archetype = MagicMock(spec=Archetype)
        mission = MissionContext(mission_level=2)

        result = _check_damage_match(archetype, mission)
        assert result is True

    def test_damage_matches_weakness(self) -> None:
        """Test damage type matches enemy weakness."""
        archetype = MagicMock(spec=Archetype)
        archetype.stats = Stats(dps=300, ehp=20000, primary_damage=["thermal"])
        archetype.damage_tuning = None

        mission = MissionContext(mission_level=2, enemy_weakness="thermal")

        result = _check_damage_match(archetype, mission)
        assert result is True

    def test_damage_no_match(self) -> None:
        """Test damage type doesn't match enemy weakness."""
        archetype = MagicMock(spec=Archetype)
        archetype.stats = Stats(dps=300, ehp=20000, primary_damage=["kinetic"])
        archetype.damage_tuning = None

        mission = MissionContext(mission_level=2, enemy_weakness="thermal")

        result = _check_damage_match(archetype, mission)
        assert result is False

    def test_fallback_to_damage_tuning(self) -> None:
        """Test fallback to damage_tuning.default_damage."""
        archetype = MagicMock(spec=Archetype)
        archetype.stats = Stats(dps=300, ehp=20000)  # No primary_damage
        archetype.damage_tuning = DamageTuning(
            default_damage="thermal", tank_profile="armor_active"
        )

        mission = MissionContext(mission_level=2, enemy_weakness="thermal")

        result = _check_damage_match(archetype, mission)
        assert result is True


# =============================================================================
# Tier Discovery Tests
# =============================================================================


class TestDiscoverTiers:
    """Tests for _discover_tiers function."""

    def test_discover_with_valid_path(self, populated_archetypes: Path) -> None:
        """Test tier discovery finds existing tiers."""
        with patch(
            "aria_esi.archetypes.selection.find_hull_directory"
        ) as mock_find:
            hull_dir = populated_archetypes / "hulls" / "cruiser" / "vexor"
            mock_find.return_value = hull_dir

            tiers = _discover_tiers("vexor/pve/missions/l2")

            assert len(tiers) >= 1
            # Should find t1.yaml
            tier_names = [t[0] for t in tiers]
            assert "t1" in tier_names

    def test_discover_invalid_path(self) -> None:
        """Test tier discovery with invalid path."""
        tiers = _discover_tiers("ab")  # Too short

        assert tiers == []

    def test_discover_hull_not_found(self) -> None:
        """Test tier discovery when hull doesn't exist."""
        with patch(
            "aria_esi.archetypes.selection.find_hull_directory"
        ) as mock_find:
            mock_find.return_value = None

            tiers = _discover_tiers("unknownship/pve/missions/l2")

            assert tiers == []

    def test_tier_priority_order(self) -> None:
        """Test TIER_PRIORITY constant has expected order."""
        assert TIER_PRIORITY[0] == "t2_optimal"
        assert TIER_PRIORITY[-1] == "t1"
        assert len(TIER_PRIORITY) == 4

    def test_tier_files_mapping(self) -> None:
        """Test TIER_FILES has all tiers mapped."""
        for tier in TIER_PRIORITY:
            assert tier in TIER_FILES
            assert len(TIER_FILES[tier]) >= 1


# =============================================================================
# Main Selection Algorithm Tests
# =============================================================================


class TestSelectFits:
    """Tests for select_fits function."""

    def test_select_no_tiers_found(self) -> None:
        """Test selection when no tiers are found."""
        with patch(
            "aria_esi.archetypes.selection._discover_tiers"
        ) as mock_discover:
            mock_discover.return_value = []

            result = select_fits("unknown/path", {})

            assert result.selection_mode == "none"
            assert len(result.warnings) > 0
            assert "No archetype files found" in result.warnings[0]

    def test_select_single_flyable(self, populated_archetypes: Path) -> None:
        """Test selection with single flyable fit."""
        with patch(
            "aria_esi.archetypes.selection.find_hull_directory"
        ) as mock_find, patch(
            "aria_esi.archetypes.selection._check_skill_requirements"
        ) as mock_skills:
            mock_find.return_value = (
                populated_archetypes / "hulls" / "cruiser" / "vexor"
            )
            mock_skills.return_value = (True, [])

            result = select_fits("vexor/pve/missions/l2", {})

            assert result.selection_mode in ("single", "none")

    def test_select_alpha_clone_filtering(self) -> None:
        """Test alpha clone filters out omega-required fits."""
        with patch(
            "aria_esi.archetypes.selection._discover_tiers"
        ) as mock_discover, patch(
            "aria_esi.archetypes.selection.load_yaml_file"
        ) as mock_load:
            mock_discover.return_value = [("t2_optimal", Path("/fake/t2_optimal.yaml"))]
            mock_load.return_value = {
                "archetype": {"omega_required": True, "skill_tier": "t2_optimal"}
            }

            result = select_fits("vexor/pve/missions/l2", {}, clone_status="alpha")

            # Should have no candidates since omega required
            assert result.selection_mode == "none"


# =============================================================================
# Convenience Function Tests
# =============================================================================


class TestGetRecommendedFit:
    """Tests for get_recommended_fit function."""

    def test_get_recommended_returns_archetype(self) -> None:
        """Test get_recommended_fit returns archetype when found."""
        mock_archetype = MagicMock(spec=Archetype)

        with patch(
            "aria_esi.archetypes.selection.select_fits"
        ) as mock_select:
            mock_result = SelectionResult(
                recommended=FitCandidate(
                    archetype=mock_archetype, tier="meta", can_fly=True
                ),
                selection_mode="single",
            )
            mock_select.return_value = mock_result

            result = get_recommended_fit("vexor/pve/missions/l2", {})

            assert result is mock_archetype

    def test_get_recommended_fallback_to_efficient(self) -> None:
        """Test get_recommended_fit falls back to efficient."""
        mock_archetype = MagicMock(spec=Archetype)

        with patch(
            "aria_esi.archetypes.selection.select_fits"
        ) as mock_select:
            mock_result = SelectionResult(
                efficient=FitCandidate(
                    archetype=mock_archetype, tier="t1", can_fly=True
                ),
                selection_mode="dual",
            )
            mock_select.return_value = mock_result

            result = get_recommended_fit("vexor/pve/missions/l2", {})

            assert result is mock_archetype

    def test_get_recommended_returns_none(self) -> None:
        """Test get_recommended_fit returns None when no fit found."""
        with patch(
            "aria_esi.archetypes.selection.select_fits"
        ) as mock_select:
            mock_select.return_value = SelectionResult()

            result = get_recommended_fit("vexor/pve/missions/l2", {})

            assert result is None


class TestCanFlyArchetype:
    """Tests for can_fly_archetype function."""

    def test_can_fly_existing_archetype(self, populated_archetypes: Path) -> None:
        """Test can_fly_archetype with existing archetype."""
        with patch(
            "aria_esi.archetypes.selection.ArchetypeLoader"
        ) as MockLoader, patch(
            "aria_esi.archetypes.selection._check_skill_requirements"
        ) as mock_check:
            mock_loader = MockLoader.return_value
            mock_archetype = MagicMock(spec=Archetype)
            mock_loader.get_archetype.return_value = mock_archetype
            mock_check.return_value = (True, [])

            can_fly, missing = can_fly_archetype("vexor/pve/missions/l2/t1", {})

            assert can_fly is True
            assert missing == []

    def test_can_fly_nonexistent_archetype(self) -> None:
        """Test can_fly_archetype with nonexistent archetype."""
        with patch(
            "aria_esi.archetypes.selection.ArchetypeLoader"
        ) as MockLoader:
            mock_loader = MockLoader.return_value
            mock_loader.get_archetype.return_value = None

            can_fly, missing = can_fly_archetype("unknown/path/t1", {})

            assert can_fly is False
            assert len(missing) == 1
            assert "error" in missing[0]
