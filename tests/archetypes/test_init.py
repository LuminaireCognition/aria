"""
Tests for archetypes module __init__.py exports.

Verifies that all expected symbols are exported and accessible.
"""

from __future__ import annotations

import aria_esi.archetypes as archetypes


class TestModuleExports:
    """Tests for archetypes module exports."""

    def test_all_defined(self) -> None:
        """Test __all__ is defined and contains expected entries."""
        assert hasattr(archetypes, "__all__")
        assert isinstance(archetypes.__all__, list)
        assert len(archetypes.__all__) > 0

    def test_loader_exports(self) -> None:
        """Test loader functions are exported."""
        # Verify loader functions are accessible
        assert hasattr(archetypes, "ArchetypeLoader")
        assert hasattr(archetypes, "get_archetypes_path")
        assert hasattr(archetypes, "list_archetypes")
        assert hasattr(archetypes, "load_archetype")
        assert hasattr(archetypes, "load_hull_manifest")
        assert hasattr(archetypes, "load_shared_config")

    def test_model_exports(self) -> None:
        """Test model classes are exported."""
        # Verify model classes are accessible
        assert hasattr(archetypes, "Archetype")
        assert hasattr(archetypes, "ArchetypePath")
        assert hasattr(archetypes, "HullManifest")
        assert hasattr(archetypes, "DamageTuning")
        assert hasattr(archetypes, "DroneConfig")
        assert hasattr(archetypes, "EmptySlotConfig")
        assert hasattr(archetypes, "FittingRules")
        assert hasattr(archetypes, "MissionContext")
        assert hasattr(archetypes, "ModuleSubstitution")
        assert hasattr(archetypes, "SkillRequirements")
        assert hasattr(archetypes, "Stats")
        assert hasattr(archetypes, "TankProfile")
        assert hasattr(archetypes, "TankType")
        assert hasattr(archetypes, "UpgradePath")

    def test_type_aliases_exported(self) -> None:
        """Test type aliases are exported."""
        assert hasattr(archetypes, "SkillTier")
        assert hasattr(archetypes, "TIER_MIGRATION_MAP")

    def test_tuning_exports(self) -> None:
        """Test tuning function is exported."""
        assert hasattr(archetypes, "apply_faction_tuning")

    def test_migration_exports(self) -> None:
        """Test migration functions are exported."""
        assert hasattr(archetypes, "migrate_archetypes")
        assert hasattr(archetypes, "run_migration")
        assert hasattr(archetypes, "update_omega_flags")

    def test_selection_exports(self) -> None:
        """Test selection functions are exported."""
        assert hasattr(archetypes, "SelectionResult")
        assert hasattr(archetypes, "can_fly_archetype")
        assert hasattr(archetypes, "get_recommended_fit")
        assert hasattr(archetypes, "select_fits")

    def test_pricing_exports(self) -> None:
        """Test pricing functions are exported."""
        assert hasattr(archetypes, "estimate_fit_price")
        assert hasattr(archetypes, "update_archetype_price")

    def test_validator_exports(self) -> None:
        """Test validator functions are exported."""
        assert hasattr(archetypes, "ArchetypeValidator")
        assert hasattr(archetypes, "ValidationResult")
        assert hasattr(archetypes, "validate_archetype")
        assert hasattr(archetypes, "validate_all_archetypes")

    def test_all_matches_exports(self) -> None:
        """Test __all__ contains only defined names."""
        for name in archetypes.__all__:
            assert hasattr(archetypes, name), f"__all__ contains '{name}' but it's not exported"

    def test_imports_are_types(self) -> None:
        """Test that imported symbols are the expected types."""
        # ArchetypeLoader should be a class
        assert isinstance(archetypes.ArchetypeLoader, type)

        # Functions should be callable
        assert callable(archetypes.get_archetypes_path)
        assert callable(archetypes.load_archetype)
        assert callable(archetypes.list_archetypes)
