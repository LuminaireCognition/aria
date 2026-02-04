"""
Tests for archetypes tuning module.

Tests faction-specific module and drone substitutions for damage optimization.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from aria_esi.archetypes.models import (
    Archetype,
    ArchetypeHeader,
    DamageTuning,
    FactionOverride,
    ModuleSubstitution,
    RigSubstitution,
    SkillRequirements,
    Stats,
)
from aria_esi.archetypes.tuning import (
    TuningResult,
    _modify_eft_header,
    _parse_eft_header,
    _substitute_drone,
    _substitute_module,
    apply_faction_tuning,
    get_faction_damage_profile,
    get_recommended_damage_type,
    list_supported_factions,
)

# =============================================================================
# TuningResult Tests
# =============================================================================


class TestTuningResult:
    """Tests for TuningResult dataclass."""

    def test_to_dict_basic(self) -> None:
        """Test TuningResult.to_dict() with basic data."""
        result = TuningResult(
            original_eft="[Vexor, Original]",
            tuned_eft="[Vexor, Original - Anti-Serpentis]",
            faction="serpentis",
            tank_profile="armor_active",
        )

        output = result.to_dict()
        assert output["faction"] == "serpentis"
        assert output["tank_profile"] == "armor_active"
        assert output["substitutions"] == []
        assert output["drone_changes"] == []
        assert output["warnings"] == []

    def test_to_dict_with_substitutions(self) -> None:
        """Test TuningResult.to_dict() with module substitutions."""
        result = TuningResult(
            original_eft="[Vexor, Original]",
            tuned_eft="[Vexor, Tuned]",
            faction="blood_raiders",
            tank_profile="armor_active",
            substitutions=[
                {
                    "type": "resist_module",
                    "from": "Adaptive Armor Hardener",
                    "to": "EM Hardener II",
                }
            ],
            drone_changes=[
                {
                    "role": "primary",
                    "from_damage": "thermal",
                    "to_damage": "em",
                }
            ],
        )

        output = result.to_dict()
        assert len(output["substitutions"]) == 1
        assert len(output["drone_changes"]) == 1


# =============================================================================
# EFT Header Parsing Tests
# =============================================================================


class TestParseEftHeader:
    """Tests for _parse_eft_header function."""

    def test_parse_standard_header(self) -> None:
        """Test parsing standard EFT header."""
        eft = "[Vexor, My Mission Runner]\nDrone Damage Amplifier II"

        ship, fit_name = _parse_eft_header(eft)

        assert ship == "Vexor"
        assert fit_name == "My Mission Runner"

    def test_parse_header_no_fit_name(self) -> None:
        """Test parsing header without fit name."""
        eft = "[Vexor]\nDrone Damage Amplifier II"

        ship, fit_name = _parse_eft_header(eft)

        assert ship == "Vexor"
        assert fit_name == ""

    def test_parse_header_with_spaces(self) -> None:
        """Test parsing header with spaces in names."""
        eft = "[Vexor Navy Issue, L2 Mission Runner]\nModule"

        ship, fit_name = _parse_eft_header(eft)

        assert ship == "Vexor Navy Issue"
        assert fit_name == "L2 Mission Runner"

    def test_parse_header_empty_eft(self) -> None:
        """Test parsing empty EFT string."""
        ship, fit_name = _parse_eft_header("")

        assert ship == ""
        assert fit_name == ""

    def test_parse_header_no_header_line(self) -> None:
        """Test parsing EFT without header line."""
        eft = "Drone Damage Amplifier II\nMedium Armor Repairer II"

        ship, fit_name = _parse_eft_header(eft)

        assert ship == ""
        assert fit_name == ""


# =============================================================================
# EFT Header Modification Tests
# =============================================================================


class TestModifyEftHeader:
    """Tests for _modify_eft_header function."""

    def test_modify_header_with_suffix(self) -> None:
        """Test adding suffix to existing fit name."""
        eft = "[Vexor, Mission Runner]\nDrone Damage Amplifier II"

        result = _modify_eft_header(eft, "Anti-Serpentis")

        assert "[Vexor, Mission Runner - Anti-Serpentis]" in result
        assert "Drone Damage Amplifier II" in result

    def test_modify_header_no_fit_name(self) -> None:
        """Test adding suffix when no fit name exists."""
        eft = "[Vexor]\nDrone Damage Amplifier II"

        result = _modify_eft_header(eft, "Anti-Serpentis")

        assert "[Vexor, Anti-Serpentis]" in result

    def test_modify_preserves_content(self) -> None:
        """Test modification preserves rest of EFT."""
        eft = """[Vexor, Test]
Drone Damage Amplifier II
Medium Armor Repairer II

Hobgoblin II x5"""

        result = _modify_eft_header(eft, "Anti-Blood")

        assert "Drone Damage Amplifier II" in result
        assert "Medium Armor Repairer II" in result
        assert "Hobgoblin II x5" in result


# =============================================================================
# Module Substitution Tests
# =============================================================================


class TestSubstituteModule:
    """Tests for _substitute_module function."""

    def test_substitute_exact_match(self) -> None:
        """Test substituting exact module name."""
        eft = """[Vexor, Test]
Energized Adaptive Nano Membrane II
Drone Damage Amplifier II"""

        new_eft, was_sub = _substitute_module(
            eft,
            "Energized Adaptive Nano Membrane II",
            "Energized EM Membrane II",
        )

        assert was_sub is True
        assert "Energized EM Membrane II" in new_eft
        assert "Energized Adaptive Nano Membrane II" not in new_eft

    def test_substitute_module_with_charge(self) -> None:
        """Test substituting module that has a charge loaded."""
        eft = """[Vexor, Test]
Medium Armor Repairer II, Nanite Repair Paste
Drone Damage Amplifier II"""

        new_eft, was_sub = _substitute_module(
            eft,
            "Medium Armor Repairer II",
            "Large Armor Repairer II",
        )

        assert was_sub is True
        assert "Large Armor Repairer II, Nanite Repair Paste" in new_eft

    def test_substitute_not_found(self) -> None:
        """Test substitution when module not found."""
        eft = """[Vexor, Test]
Drone Damage Amplifier II"""

        new_eft, was_sub = _substitute_module(eft, "Unknown Module", "New Module")

        assert was_sub is False
        assert new_eft == eft

    def test_substitute_only_first_occurrence(self) -> None:
        """Test substitution only replaces first occurrence."""
        eft = """[Vexor, Test]
Energized Adaptive Nano Membrane II
Energized Adaptive Nano Membrane II"""

        new_eft, was_sub = _substitute_module(
            eft,
            "Energized Adaptive Nano Membrane II",
            "Energized EM Membrane II",
        )

        assert was_sub is True
        # Count occurrences
        assert new_eft.count("Energized EM Membrane II") == 1
        assert new_eft.count("Energized Adaptive Nano Membrane II") == 1


# =============================================================================
# Drone Substitution Tests
# =============================================================================


class TestSubstituteDrone:
    """Tests for _substitute_drone function."""

    def test_substitute_medium_drones(self) -> None:
        """Test substituting medium drones by damage type."""
        eft = """[Vexor, Test]
Hammerhead II x5"""

        with patch(
            "aria_esi.archetypes.tuning.load_faction_tuning"
        ) as mock_load:
            mock_load.return_value = {
                "drone_types": {
                    "thermal": {"medium": "Hammerhead"},
                    "kinetic": {"medium": "Vespa"},
                },
                "drone_tech_suffix": {"t2_optimal": " II", "meta": " I"},
            }

            new_eft, was_sub = _substitute_drone(
                eft,
                from_damage="thermal",
                to_damage="kinetic",
                drone_size="medium",
                skill_tier="t2_optimal",
            )

            assert was_sub is True
            assert "Vespa II x5" in new_eft
            assert "Hammerhead II" not in new_eft

    def test_substitute_light_drones(self) -> None:
        """Test substituting light (anti-frigate) drones."""
        eft = """[Vexor, Test]
Hobgoblin II x5"""

        with patch(
            "aria_esi.archetypes.tuning.load_faction_tuning"
        ) as mock_load:
            mock_load.return_value = {
                "drone_types": {
                    "thermal": {"light": "Hobgoblin"},
                    "em": {"light": "Acolyte"},
                },
                "drone_tech_suffix": {"t2_optimal": " II"},
            }

            new_eft, was_sub = _substitute_drone(
                eft,
                from_damage="thermal",
                to_damage="em",
                drone_size="light",
                skill_tier="t2_optimal",
            )

            assert was_sub is True
            assert "Acolyte II x5" in new_eft

    def test_substitute_drone_not_found(self) -> None:
        """Test drone substitution when drones not in fit."""
        eft = """[Vexor, Test]
Drone Damage Amplifier II"""

        with patch(
            "aria_esi.archetypes.tuning.load_faction_tuning"
        ) as mock_load:
            mock_load.return_value = {
                "drone_types": {"thermal": {"medium": "Hammerhead"}},
                "drone_tech_suffix": {},
            }

            new_eft, was_sub = _substitute_drone(
                eft,
                from_damage="thermal",
                to_damage="kinetic",
                drone_size="medium",
                skill_tier="meta",
            )

            assert was_sub is False

    def test_substitute_drone_config_not_found(self) -> None:
        """Test drone substitution when config file missing."""
        eft = """[Vexor, Test]
Hammerhead II x5"""

        with patch(
            "aria_esi.archetypes.tuning.load_faction_tuning"
        ) as mock_load:
            mock_load.side_effect = FileNotFoundError("Config not found")

            new_eft, was_sub = _substitute_drone(
                eft,
                from_damage="thermal",
                to_damage="kinetic",
                drone_size="medium",
                skill_tier="t2_optimal",
            )

            assert was_sub is False
            assert new_eft == eft


# =============================================================================
# Apply Faction Tuning Tests
# =============================================================================


class TestApplyFactionTuning:
    """Tests for apply_faction_tuning function."""

    def test_tuning_no_damage_tuning(self) -> None:
        """Test tuning archetype without damage_tuning config."""
        archetype = MagicMock(spec=Archetype)
        archetype.eft = "[Vexor, Test]\nDrone Damage Amplifier II"
        archetype.damage_tuning = None

        result = apply_faction_tuning(archetype, "serpentis")

        assert result.faction == "serpentis"
        assert len(result.warnings) > 0
        assert "no damage_tuning" in result.warnings[0]

    def test_tuning_config_not_found(self) -> None:
        """Test tuning when faction config is not found."""
        archetype = MagicMock(spec=Archetype)
        archetype.eft = "[Vexor, Test]\nDrone Damage Amplifier II"
        archetype.damage_tuning = DamageTuning(
            default_damage="thermal",
            tank_profile="armor_active",
        )

        with patch(
            "aria_esi.archetypes.tuning.load_faction_tuning"
        ) as mock_load:
            mock_load.side_effect = FileNotFoundError("Not found")

            result = apply_faction_tuning(archetype, "serpentis")

            assert len(result.warnings) > 0
            assert "not found" in result.warnings[0]

    def test_tuning_applies_module_overrides(self) -> None:
        """Test tuning applies archetype-specific module overrides."""
        # Create a proper Archetype with the right structure
        archetype = Archetype(
            archetype=ArchetypeHeader(hull="Vexor", skill_tier="t2_optimal"),
            eft="""[Vexor, Test]
Energized Adaptive Nano Membrane II
Drone Damage Amplifier II""",
            skill_requirements=SkillRequirements(),
            stats=Stats(dps=300, ehp=20000),
            damage_tuning=DamageTuning(
                default_damage="thermal",
                tank_profile="armor_active",
                overrides={
                    "serpentis": FactionOverride(
                        modules=[
                            ModuleSubstitution(
                                from_module="Energized Adaptive Nano Membrane II",
                                to_module="Energized Kinetic Membrane II",
                            )
                        ]
                    )
                },
            ),
        )

        with patch(
            "aria_esi.archetypes.tuning.load_faction_tuning"
        ) as mock_load:
            # Need to provide valid faction rules that return non-None
            mock_load.return_value = {
                "armor_active": {"serpentis": {"modules": [], "drones": {}}},
            }

            result = apply_faction_tuning(archetype, "serpentis")

            # The override is in damage_tuning.overrides, so it should be applied
            assert "Energized Kinetic Membrane II" in result.tuned_eft
            assert len(result.substitutions) > 0

    def test_tuning_applies_rig_overrides(self) -> None:
        """Test tuning applies rig substitutions."""
        archetype = Archetype(
            archetype=ArchetypeHeader(hull="Vexor", skill_tier="meta"),
            eft="""[Vexor, Test]
Medium Anti-Thermal Pump I""",
            skill_requirements=SkillRequirements(),
            stats=Stats(dps=300, ehp=20000),
            damage_tuning=DamageTuning(
                default_damage="thermal",
                tank_profile="armor_active",
                overrides={
                    "blood_raiders": FactionOverride(
                        rigs=[
                            RigSubstitution(
                                from_rig="Medium Anti-Thermal Pump I",
                                to_rig="Medium Anti-EM Pump I",
                            )
                        ]
                    )
                },
            ),
        )

        with patch(
            "aria_esi.archetypes.tuning.load_faction_tuning"
        ) as mock_load:
            mock_load.return_value = {"armor_active": {"blood_raiders": {"modules": [], "drones": {}}}}

            result = apply_faction_tuning(archetype, "blood_raiders")

            assert "Medium Anti-EM Pump I" in result.tuned_eft
            assert any(s["type"] == "rig_override" for s in result.substitutions)

    def test_tuning_modifies_header(self) -> None:
        """Test tuning adds faction suffix to fit name."""
        archetype = Archetype(
            archetype=ArchetypeHeader(hull="Vexor", skill_tier="t1"),
            eft="[Vexor, Mission Runner]\nDrone Damage Amplifier II",
            skill_requirements=SkillRequirements(),
            stats=Stats(dps=300, ehp=20000),
            damage_tuning=DamageTuning(
                default_damage="thermal",
                tank_profile="armor_active",
            ),
        )

        with patch(
            "aria_esi.archetypes.tuning.load_faction_tuning"
        ) as mock_load:
            mock_load.return_value = {"armor_active": {"serpentis": {"modules": [], "drones": {}}}}

            result = apply_faction_tuning(archetype, "serpentis")

            assert "Anti-Serpentis" in result.tuned_eft

    def test_tuning_faction_inheritance(self) -> None:
        """Test tuning with faction rule inheritance."""
        archetype = MagicMock(spec=Archetype)
        archetype.eft = "[Vexor, Test]\nModule"
        archetype.damage_tuning = DamageTuning(
            default_damage="thermal",
            tank_profile="armor_active",
        )
        archetype.archetype = ArchetypeHeader(hull="Vexor", skill_tier="t1")

        with patch(
            "aria_esi.archetypes.tuning.load_faction_tuning"
        ) as mock_load:
            mock_load.return_value = {
                "armor_active": {
                    "mordus_legion": {"inherit": "guristas"},
                    "guristas": {"drones": {"primary": "kinetic"}},
                }
            }

            result = apply_faction_tuning(archetype, "mordus_legion")

            assert "inherited rules from guristas" in result.warnings[0]


# =============================================================================
# Utility Function Tests
# =============================================================================


class TestGetFactionDamageProfile:
    """Tests for get_faction_damage_profile function."""

    def test_get_known_faction(self) -> None:
        """Test getting damage profile for known faction."""
        with patch(
            "aria_esi.archetypes.tuning.load_shared_config"
        ) as mock_load:
            mock_load.return_value = {
                "factions": {
                    "serpentis": {
                        "damage_dealt": {"kinetic": 50, "thermal": 50},
                        "weakness": "thermal",
                    }
                }
            }

            profile = get_faction_damage_profile("serpentis")

            assert profile is not None
            assert profile["weakness"] == "thermal"

    def test_get_unknown_faction(self) -> None:
        """Test getting damage profile for unknown faction."""
        with patch(
            "aria_esi.archetypes.tuning.load_shared_config"
        ) as mock_load:
            mock_load.return_value = {"factions": {}}

            profile = get_faction_damage_profile("unknown")

            assert profile is None

    def test_get_faction_config_not_found(self) -> None:
        """Test graceful handling when config not found."""
        with patch(
            "aria_esi.archetypes.tuning.load_shared_config"
        ) as mock_load:
            mock_load.side_effect = FileNotFoundError("Not found")

            profile = get_faction_damage_profile("serpentis")

            assert profile is None


class TestListSupportedFactions:
    """Tests for list_supported_factions function."""

    def test_list_factions(self) -> None:
        """Test listing supported factions."""
        with patch(
            "aria_esi.archetypes.tuning.load_shared_config"
        ) as mock_load:
            mock_load.return_value = {
                "factions": {
                    "serpentis": {},
                    "guristas": {},
                    "blood_raiders": {},
                }
            }

            factions = list_supported_factions()

            assert len(factions) == 3
            assert "serpentis" in factions
            assert factions == sorted(factions)  # Should be sorted

    def test_list_factions_config_not_found(self) -> None:
        """Test empty list when config not found."""
        with patch(
            "aria_esi.archetypes.tuning.load_shared_config"
        ) as mock_load:
            mock_load.side_effect = FileNotFoundError("Not found")

            factions = list_supported_factions()

            assert factions == []


class TestGetRecommendedDamageType:
    """Tests for get_recommended_damage_type function."""

    def test_get_recommended_damage(self) -> None:
        """Test getting recommended damage type."""
        with patch(
            "aria_esi.archetypes.tuning.get_faction_damage_profile"
        ) as mock_get:
            mock_get.return_value = {"weakness": "thermal"}

            damage_type = get_recommended_damage_type("serpentis")

            assert damage_type == "thermal"

    def test_get_recommended_damage_no_profile(self) -> None:
        """Test getting recommended damage when no profile."""
        with patch(
            "aria_esi.archetypes.tuning.get_faction_damage_profile"
        ) as mock_get:
            mock_get.return_value = None

            damage_type = get_recommended_damage_type("unknown")

            assert damage_type is None
