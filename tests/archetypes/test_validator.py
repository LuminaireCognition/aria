"""
Tests for archetypes validator module.

Tests schema validation, alpha clone restrictions, EOS validation,
and consistency checking between archetypes and manifests.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from aria_esi.archetypes.models import (
    Archetype,
    ArchetypeHeader,
    DamageTuning,
    FittingRules,
    HullManifest,
    SkillRequirements,
    SlotLayout,
    Stats,
)
from aria_esi.archetypes.validator import (
    ALPHA_FORBIDDEN_SHIPS,
    ArchetypeValidator,
    ValidationIssue,
    ValidationResult,
    _check_alpha_restrictions,
    _check_alpha_ship,
    _validate_consistency,
    _validate_schema,
    _validate_with_eos,
    validate_all_archetypes,
    validate_archetype,
)

# =============================================================================
# ValidationIssue Tests
# =============================================================================


class TestValidationIssue:
    """Tests for ValidationIssue dataclass."""

    def test_to_dict_basic(self) -> None:
        """Test ValidationIssue.to_dict() with basic data."""
        issue = ValidationIssue(
            level="error",
            category="schema",
            message="Missing required field: eft",
            path="vexor/pve/missions/l2/t1",
        )

        result = issue.to_dict()
        assert result["level"] == "error"
        assert result["category"] == "schema"
        assert result["message"] == "Missing required field: eft"
        assert result["path"] == "vexor/pve/missions/l2/t1"

    def test_to_dict_without_path(self) -> None:
        """Test ValidationIssue.to_dict() without path."""
        issue = ValidationIssue(
            level="warning",
            category="alpha",
            message="T2 module detected",
        )

        result = issue.to_dict()
        assert result["path"] is None


# =============================================================================
# ValidationResult Tests
# =============================================================================


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_errors_property(self) -> None:
        """Test errors property filters correctly."""
        result = ValidationResult(
            path="test/path",
            is_valid=False,
            issues=[
                ValidationIssue("error", "schema", "Error 1"),
                ValidationIssue("warning", "alpha", "Warning 1"),
                ValidationIssue("error", "schema", "Error 2"),
                ValidationIssue("info", "eos", "Info 1"),
            ],
        )

        errors = result.errors
        assert len(errors) == 2
        assert all(e.level == "error" for e in errors)

    def test_warnings_property(self) -> None:
        """Test warnings property filters correctly."""
        result = ValidationResult(
            path="test/path",
            is_valid=True,
            issues=[
                ValidationIssue("error", "schema", "Error 1"),
                ValidationIssue("warning", "alpha", "Warning 1"),
                ValidationIssue("warning", "consistency", "Warning 2"),
            ],
        )

        warnings = result.warnings
        assert len(warnings) == 2
        assert all(w.level == "warning" for w in warnings)

    def test_to_dict(self) -> None:
        """Test ValidationResult.to_dict()."""
        result = ValidationResult(
            path="vexor/pve/missions/l2/t1",
            is_valid=False,
            issues=[
                ValidationIssue("error", "schema", "Error 1"),
                ValidationIssue("warning", "alpha", "Warning 1"),
            ],
        )

        output = result.to_dict()
        assert output["path"] == "vexor/pve/missions/l2/t1"
        assert output["is_valid"] is False
        assert output["error_count"] == 1
        assert output["warning_count"] == 1
        assert len(output["issues"]) == 2


# =============================================================================
# Alpha Restriction Tests
# =============================================================================


class TestCheckAlphaRestrictions:
    """Tests for _check_alpha_restrictions function."""

    def test_detects_t2_module(self) -> None:
        """Test detection of T2 modules."""
        eft = """[Vexor, Alpha Test]
Drone Damage Amplifier II
Medium Armor Repairer II"""

        issues = _check_alpha_restrictions(eft)

        assert len(issues) == 2
        assert all(i.level == "error" for i in issues)
        assert all(i.category == "alpha" for i in issues)

    def test_allows_t1_modules(self) -> None:
        """Test T1 modules pass validation."""
        eft = """[Vexor, Alpha Test]
Drone Damage Amplifier I
Medium Armor Repairer I"""

        issues = _check_alpha_restrictions(eft)

        assert len(issues) == 0

    def test_allows_meta_modules(self) -> None:
        """Test meta/compact modules pass validation."""
        eft = """[Vexor, Alpha Test]
Compact Drone Damage Amplifier
Enduring Armor Repairer"""

        issues = _check_alpha_restrictions(eft)

        assert len(issues) == 0

    def test_detects_forbidden_modules(self) -> None:
        """Test detection of specifically forbidden modules."""
        eft = """[Paladin, Test]
Siege Module I"""

        issues = _check_alpha_restrictions(eft)

        assert len(issues) >= 1
        assert any("Siege Module" in i.message for i in issues)

    def test_skips_empty_slots(self) -> None:
        """Test empty slot markers are skipped."""
        eft = """[Vexor, Test]
[Empty Low slot]
[Empty Mid slot]
Drone Damage Amplifier I"""

        issues = _check_alpha_restrictions(eft)

        assert len(issues) == 0

    def test_skips_header_line(self) -> None:
        """Test header line is skipped."""
        # Header has "]" which could confuse parsing
        eft = "[Vexor, Alpha Clone Mission Runner II]\nModule I"

        issues = _check_alpha_restrictions(eft)

        # Should not flag the "II" in fit name
        assert len(issues) == 0


class TestCheckAlphaShip:
    """Tests for _check_alpha_ship function."""

    def test_allows_standard_ships(self) -> None:
        """Test standard ships pass validation."""
        eft = "[Vexor, Test]\nModule"

        issues = _check_alpha_ship(eft)

        assert len(issues) == 0

    def test_forbidden_ship_patterns(self) -> None:
        """Test ALPHA_FORBIDDEN_SHIPS patterns exist."""
        # Verify the constant has expected patterns
        assert len(ALPHA_FORBIDDEN_SHIPS) > 0
        # Should include major restricted classes
        patterns_str = " ".join(ALPHA_FORBIDDEN_SHIPS)
        assert "Marauder" in patterns_str
        assert "Strategic Cruiser" in patterns_str


# =============================================================================
# Schema Validation Tests
# =============================================================================


class TestValidateSchema:
    """Tests for _validate_schema function."""

    def test_valid_archetype(self) -> None:
        """Test valid archetype passes schema validation."""
        archetype = Archetype(
            archetype=ArchetypeHeader(hull="Vexor", skill_tier="t1"),
            eft="[Vexor, Test]\nDrone Damage Amplifier I",
            skill_requirements=SkillRequirements(),
            stats=Stats(dps=200, ehp=20000),
        )

        issues = _validate_schema(archetype, "vexor/pve/t1")

        errors = [i for i in issues if i.level == "error"]
        assert len(errors) == 0

    def test_missing_eft(self) -> None:
        """Test missing EFT is detected."""
        archetype = Archetype(
            archetype=ArchetypeHeader(hull="Vexor", skill_tier="t1"),
            eft="",  # Empty EFT
            skill_requirements=SkillRequirements(),
            stats=Stats(dps=200, ehp=20000),
        )

        issues = _validate_schema(archetype, "vexor/pve/t1")

        assert any("eft" in i.message.lower() for i in issues)

    def test_missing_hull(self) -> None:
        """Test missing hull is detected."""
        archetype = Archetype(
            archetype=ArchetypeHeader(hull="", skill_tier="t1"),
            eft="[Vexor, Test]",
            skill_requirements=SkillRequirements(),
            stats=Stats(dps=200, ehp=20000),
        )

        issues = _validate_schema(archetype, "vexor/pve/t1")

        assert any("hull" in i.message.lower() for i in issues)

    def test_missing_skill_tier(self) -> None:
        """Test missing skill_tier is detected."""
        archetype = Archetype(
            archetype=ArchetypeHeader(hull="Vexor", skill_tier=""),  # type: ignore[arg-type]
            eft="[Vexor, Test]",
            skill_requirements=SkillRequirements(),
            stats=Stats(dps=200, ehp=20000),
        )

        issues = _validate_schema(archetype, "vexor/pve/t1")

        assert any("skill_tier" in i.message.lower() for i in issues)

    def test_invalid_skill_tier(self) -> None:
        """Test invalid skill_tier value is detected."""
        archetype = Archetype(
            archetype=ArchetypeHeader(hull="Vexor", skill_tier="invalid"),  # type: ignore[arg-type]
            eft="[Vexor, Test]",
            skill_requirements=SkillRequirements(),
            stats=Stats(dps=200, ehp=20000),
        )

        issues = _validate_schema(archetype, "vexor/pve/t1")

        assert any("invalid" in i.message.lower() and "skill_tier" in i.message.lower() for i in issues)

    def test_legacy_tier_warning(self) -> None:
        """Test legacy tier names generate warning."""
        archetype = Archetype(
            archetype=ArchetypeHeader(hull="Vexor", skill_tier="medium"),  # type: ignore[arg-type]
            eft="[Vexor, Test]",
            skill_requirements=SkillRequirements(),
            stats=Stats(dps=200, ehp=20000),
        )

        issues = _validate_schema(archetype, "vexor/pve/medium")

        warnings = [i for i in issues if i.level == "warning"]
        assert any("legacy" in w.message.lower() for w in warnings)

    def test_invalid_eft_header(self) -> None:
        """Test invalid EFT header is detected."""
        archetype = Archetype(
            archetype=ArchetypeHeader(hull="Vexor", skill_tier="t1"),
            eft="Invalid EFT without header\nDrone Damage Amplifier I",
            skill_requirements=SkillRequirements(),
            stats=Stats(dps=200, ehp=20000),
        )

        issues = _validate_schema(archetype, "vexor/pve/t1")

        assert any("eft" in i.message.lower() and "header" in i.message.lower() for i in issues)

    def test_negative_dps(self) -> None:
        """Test negative DPS is detected."""
        archetype = Archetype(
            archetype=ArchetypeHeader(hull="Vexor", skill_tier="t1"),
            eft="[Vexor, Test]",
            skill_requirements=SkillRequirements(),
            stats=Stats(dps=-100, ehp=20000),
        )

        issues = _validate_schema(archetype, "vexor/pve/t1")

        assert any("dps" in i.message.lower() for i in issues)

    def test_negative_ehp(self) -> None:
        """Test negative EHP is detected."""
        archetype = Archetype(
            archetype=ArchetypeHeader(hull="Vexor", skill_tier="t1"),
            eft="[Vexor, Test]",
            skill_requirements=SkillRequirements(),
            stats=Stats(dps=200, ehp=-5000),
        )

        issues = _validate_schema(archetype, "vexor/pve/t1")

        assert any("ehp" in i.message.lower() for i in issues)


# =============================================================================
# Consistency Validation Tests
# =============================================================================


class TestValidateConsistency:
    """Tests for _validate_consistency function."""

    def test_no_manifest(self) -> None:
        """Test warning when no manifest found."""
        archetype = Archetype(
            archetype=ArchetypeHeader(hull="Vexor", skill_tier="t1"),
            eft="[Vexor, Test]",
            skill_requirements=SkillRequirements(),
            stats=Stats(dps=200, ehp=20000),
        )

        issues = _validate_consistency(archetype, None, "vexor/pve/t1")

        assert len(issues) == 1
        assert issues[0].level == "warning"
        assert "manifest" in issues[0].message.lower()

    def test_hull_mismatch(self) -> None:
        """Test error when hull names don't match."""
        archetype = Archetype(
            archetype=ArchetypeHeader(hull="Vexor", skill_tier="t1"),
            eft="[Vexor, Test]",
            skill_requirements=SkillRequirements(),
            stats=Stats(dps=200, ehp=20000),
        )

        manifest = HullManifest(
            hull="Drake",  # Different hull!
            ship_class="battlecruiser",
            faction="caldari",
            tech_level=1,
            slots=SlotLayout(high=7, mid=5, low=4, rig=3),
            drones=None,
            bonuses=[],
            roles=[],
            fitting_rules=FittingRules(tank_type="shield_active"),
        )

        issues = _validate_consistency(archetype, manifest, "vexor/pve/t1")

        errors = [i for i in issues if i.level == "error"]
        assert len(errors) >= 1
        assert any("hull mismatch" in e.message.lower() for e in errors)

    def test_tank_profile_mismatch(self) -> None:
        """Test warning when tank profiles don't match."""
        archetype = Archetype(
            archetype=ArchetypeHeader(hull="Vexor", skill_tier="t1"),
            eft="[Vexor, Test]",
            skill_requirements=SkillRequirements(),
            stats=Stats(dps=200, ehp=20000),
            damage_tuning=DamageTuning(
                default_damage="thermal",
                tank_profile="shield_active",  # Doesn't match manifest
            ),
        )

        manifest = HullManifest(
            hull="Vexor",
            ship_class="cruiser",
            faction="gallente",
            tech_level=1,
            slots=SlotLayout(high=4, mid=4, low=5, rig=3),
            drones=None,
            bonuses=[],
            roles=[],
            fitting_rules=FittingRules(tank_type="armor_active"),
        )

        issues = _validate_consistency(archetype, manifest, "vexor/pve/t1")

        warnings = [i for i in issues if i.level == "warning"]
        assert any("tank" in w.message.lower() for w in warnings)

    def test_matching_hull_and_tank(self) -> None:
        """Test no issues when hull and tank match."""
        archetype = Archetype(
            archetype=ArchetypeHeader(hull="Vexor", skill_tier="t1"),
            eft="[Vexor, Test]",
            skill_requirements=SkillRequirements(),
            stats=Stats(dps=200, ehp=20000),
            damage_tuning=DamageTuning(
                default_damage="thermal",
                tank_profile="armor_active",
            ),
        )

        manifest = HullManifest(
            hull="Vexor",
            ship_class="cruiser",
            faction="gallente",
            tech_level=1,
            slots=SlotLayout(high=4, mid=4, low=5, rig=3),
            drones=None,
            bonuses=[],
            roles=[],
            fitting_rules=FittingRules(tank_type="armor_active"),
        )

        issues = _validate_consistency(archetype, manifest, "vexor/pve/t1")

        # Only warnings, no errors
        errors = [i for i in issues if i.level == "error"]
        assert len(errors) == 0


# =============================================================================
# Omega/T2 Consistency Validation Tests
# =============================================================================


class TestHasT2ModulesValidator:
    """Tests for _has_t2_modules function in validator."""

    def test_detects_t2_modules(self) -> None:
        """Test T2 module detection."""
        from aria_esi.archetypes.validator import _has_t2_modules

        eft = """[Vexor, Test]
        Drone Damage Amplifier II
        Medium Armor Repairer I
        """
        assert _has_t2_modules(eft) is True

    def test_detects_t2_with_charge(self) -> None:
        """Test T2 module detection with charge."""
        from aria_esi.archetypes.validator import _has_t2_modules

        eft = """[Vexor, Test]
        Heavy Missile Launcher II, Scourge Fury Heavy Missile
        """
        assert _has_t2_modules(eft) is True

    def test_no_t2_modules(self) -> None:
        """Test detection passes when no T2 modules."""
        from aria_esi.archetypes.validator import _has_t2_modules

        eft = """[Vexor, Test]
        Drone Damage Amplifier I
        Medium ACM Compact Armor Repairer
        """
        assert _has_t2_modules(eft) is False

    def test_skips_header(self) -> None:
        """Test that header line is not checked."""
        from aria_esi.archetypes.validator import _has_t2_modules

        # "Vexor II" would match the pattern but shouldn't trigger
        eft = """[Vexor Navy Issue II Edition, Test]
        Drone Damage Amplifier I
        """
        assert _has_t2_modules(eft) is False


class TestValidateOmegaConsistency:
    """Tests for _validate_omega_consistency function."""

    def test_omega_required_true_with_t2(self) -> None:
        """Test no warning when omega_required=true with T2 modules."""
        from aria_esi.archetypes.validator import _validate_omega_consistency

        archetype = Archetype(
            archetype=ArchetypeHeader(hull="Vexor", skill_tier="t2_optimal", omega_required=True),
            eft="""[Vexor, Test]
            Drone Damage Amplifier II
            Medium Armor Repairer II
            """,
            skill_requirements=SkillRequirements(),
            stats=Stats(dps=200, ehp=20000),
        )

        issues = _validate_omega_consistency(archetype, "vexor/pve/t2_optimal")
        assert len(issues) == 0

    def test_omega_required_false_without_t2(self) -> None:
        """Test no warning when omega_required=false without T2 modules."""
        from aria_esi.archetypes.validator import _validate_omega_consistency

        archetype = Archetype(
            archetype=ArchetypeHeader(hull="Vexor", skill_tier="t1", omega_required=False),
            eft="""[Vexor, Test]
            Drone Damage Amplifier I
            Medium ACM Compact Armor Repairer
            """,
            skill_requirements=SkillRequirements(),
            stats=Stats(dps=200, ehp=20000),
        )

        issues = _validate_omega_consistency(archetype, "vexor/pve/t1")
        assert len(issues) == 0

    def test_omega_required_false_with_t2_warning(self) -> None:
        """Test warning when omega_required=false but has T2 modules."""
        from aria_esi.archetypes.validator import _validate_omega_consistency

        archetype = Archetype(
            archetype=ArchetypeHeader(hull="Vexor", skill_tier="meta", omega_required=False),
            eft="""[Vexor, Test]
            Drone Damage Amplifier II
            Medium Armor Repairer I
            """,
            skill_requirements=SkillRequirements(),
            stats=Stats(dps=200, ehp=20000),
        )

        issues = _validate_omega_consistency(archetype, "vexor/pve/meta")

        assert len(issues) == 1
        assert issues[0].level == "warning"
        assert issues[0].category == "consistency"
        assert "omega_required=false" in issues[0].message
        assert "T2 modules" in issues[0].message


# =============================================================================
# EOS Validation Tests
# =============================================================================


class TestValidateWithEos:
    """Tests for _validate_with_eos function."""

    def test_eos_not_available(self) -> None:
        """Test graceful handling when EOS not available."""
        archetype = Archetype(
            archetype=ArchetypeHeader(hull="Vexor", skill_tier="t1"),
            eft="[Vexor, Test]",
            skill_requirements=SkillRequirements(),
            stats=Stats(dps=200, ehp=20000),
        )

        with patch(
            "aria_esi.fitting.get_eos_data_manager",
            side_effect=ImportError("EOS not available"),
        ):
            issues = _validate_with_eos(archetype, "vexor/pve/t1")

        # Should return info about EOS being unavailable
        assert any("eos" in i.message.lower() for i in issues)

    def test_eos_data_invalid(self) -> None:
        """Test handling when EOS data is invalid."""
        archetype = Archetype(
            archetype=ArchetypeHeader(hull="Vexor", skill_tier="t1"),
            eft="[Vexor, Test]",
            skill_requirements=SkillRequirements(),
            stats=Stats(dps=200, ehp=20000),
        )

        with patch(
            "aria_esi.fitting.get_eos_data_manager"
        ) as mock_eos:
            mock_manager = MagicMock()
            mock_status = MagicMock()
            mock_status.is_valid = False
            mock_manager.validate.return_value = mock_status
            mock_eos.return_value = mock_manager

            issues = _validate_with_eos(archetype, "vexor/pve/t1")

        assert any("not available" in i.message.lower() for i in issues)


# =============================================================================
# ArchetypeValidator Class Tests
# =============================================================================


class TestArchetypeValidator:
    """Tests for ArchetypeValidator class."""

    def test_create_validator(self) -> None:
        """Test creating validator instance."""
        validator = ArchetypeValidator()

        assert validator.use_eos is False
        assert validator._loader is not None

    def test_create_validator_with_eos(self) -> None:
        """Test creating validator with EOS enabled."""
        validator = ArchetypeValidator(use_eos=True)

        assert validator.use_eos is True

    def test_validate_archetype_not_found(self) -> None:
        """Test validating nonexistent archetype."""
        validator = ArchetypeValidator()

        with patch.object(validator._loader, "get_archetype", return_value=None):
            result = validator.validate_archetype("unknown/path/t1")

        assert result.is_valid is False
        assert len(result.errors) >= 1
        assert "not found" in result.errors[0].message.lower()

    def test_validate_archetype_alpha_tier(self) -> None:
        """Test alpha tier gets alpha restriction checks."""
        validator = ArchetypeValidator()

        archetype = Archetype(
            archetype=ArchetypeHeader(hull="Vexor", skill_tier="alpha"),  # type: ignore[arg-type]
            eft="[Vexor, Alpha Test]\nDrone Damage Amplifier II",  # T2 module!
            skill_requirements=SkillRequirements(),
            stats=Stats(dps=200, ehp=20000),
        )

        with patch.object(validator._loader, "get_archetype", return_value=archetype):
            with patch.object(validator._loader, "get_manifest", return_value=None):
                result = validator.validate_archetype("vexor/pve/alpha")

        # Should have alpha restriction error
        alpha_errors = [i for i in result.issues if i.category == "alpha"]
        assert len(alpha_errors) >= 1

    def test_validate_archetype_success(self, populated_archetypes: Path) -> None:
        """Test successful validation of archetype."""
        with patch(
            "aria_esi.archetypes.loader.get_archetypes_path",
            return_value=populated_archetypes,
        ):
            validator = ArchetypeValidator()
            result = validator.validate_archetype("vexor/pve/missions/l2/t1")

            # Should be valid (sample data is properly formed)
            assert len(result.errors) == 0 or result.is_valid

    def test_validate_all(self) -> None:
        """Test validate_all returns list of results."""
        validator = ArchetypeValidator()

        with patch(
            "aria_esi.archetypes.validator.list_archetypes", return_value=["path1", "path2"]
        ), patch.object(
            validator, "validate_archetype"
        ) as mock_validate:
            mock_validate.return_value = ValidationResult(path="test", is_valid=True)

            results = validator.validate_all()

        assert len(results) == 2
        assert mock_validate.call_count == 2

    def test_validate_all_with_hull_filter(self) -> None:
        """Test validate_all respects hull filter."""
        validator = ArchetypeValidator()

        with patch(
            "aria_esi.archetypes.validator.list_archetypes"
        ) as mock_list, patch.object(
            validator, "validate_archetype"
        ) as mock_validate:
            mock_list.return_value = ["vexor/pve/t1"]
            mock_validate.return_value = ValidationResult(path="test", is_valid=True)

            results = validator.validate_all(hull="vexor")

            mock_list.assert_called_once_with("vexor")

    def test_validate_manifest(self) -> None:
        """Test manifest validation."""
        validator = ArchetypeValidator()

        manifest = HullManifest(
            hull="Vexor",
            ship_class="cruiser",
            faction="gallente",
            tech_level=1,
            slots=SlotLayout(high=4, mid=4, low=5, rig=3),
            drones=None,
            bonuses=["Some bonus"],
            roles=["combat"],
            fitting_rules=FittingRules(tank_type="armor_active"),
        )

        with patch.object(validator._loader, "get_manifest", return_value=manifest):
            result = validator.validate_manifest("vexor")

        assert result.is_valid is True
        assert result.manifest is manifest

    def test_validate_manifest_not_found(self) -> None:
        """Test manifest validation when not found."""
        validator = ArchetypeValidator()

        with patch.object(validator._loader, "get_manifest", return_value=None):
            result = validator.validate_manifest("unknown")

        assert result.is_valid is False
        assert len(result.errors) >= 1

    def test_validate_manifest_missing_hull(self) -> None:
        """Test manifest validation with missing hull."""
        validator = ArchetypeValidator()

        manifest = HullManifest(
            hull="",  # Missing!
            ship_class="cruiser",
            faction="gallente",
            tech_level=1,
            slots=SlotLayout(high=4, mid=4, low=5, rig=3),
            drones=None,
            bonuses=[],
            roles=[],
            fitting_rules=FittingRules(tank_type="armor_active"),
        )

        with patch.object(validator._loader, "get_manifest", return_value=manifest):
            result = validator.validate_manifest("unknown")

        assert result.is_valid is False
        assert any("hull" in e.message.lower() for e in result.errors)


# =============================================================================
# Convenience Function Tests
# =============================================================================


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_validate_archetype_function(self) -> None:
        """Test validate_archetype convenience function."""
        with patch(
            "aria_esi.archetypes.validator.ArchetypeValidator"
        ) as MockValidator:
            mock_instance = MockValidator.return_value
            mock_instance.validate_archetype.return_value = ValidationResult(
                path="test", is_valid=True
            )

            result = validate_archetype("vexor/pve/t1")

            MockValidator.assert_called_once_with(use_eos=False)
            mock_instance.validate_archetype.assert_called_once_with("vexor/pve/t1")
            assert result.is_valid is True

    def test_validate_archetype_function_with_eos(self) -> None:
        """Test validate_archetype with EOS enabled."""
        with patch(
            "aria_esi.archetypes.validator.ArchetypeValidator"
        ) as MockValidator:
            mock_instance = MockValidator.return_value
            mock_instance.validate_archetype.return_value = ValidationResult(
                path="test", is_valid=True
            )

            validate_archetype("vexor/pve/t1", use_eos=True)

            MockValidator.assert_called_once_with(use_eos=True)

    def test_validate_all_archetypes_function(self) -> None:
        """Test validate_all_archetypes convenience function."""
        with patch(
            "aria_esi.archetypes.validator.ArchetypeValidator"
        ) as MockValidator:
            mock_instance = MockValidator.return_value
            mock_instance.validate_all.return_value = []

            results = validate_all_archetypes(hull="vexor", use_eos=True)

            MockValidator.assert_called_once_with(use_eos=True)
            mock_instance.validate_all.assert_called_once_with("vexor")
            assert results == []
