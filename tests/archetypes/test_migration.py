"""
Tests for archetypes migration module.

Tests tier name migration from legacy (low/medium/high/alpha) to new
(t1/meta/t2_budget/t2_optimal) naming scheme, and omega_required flag updates.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from aria_esi.archetypes.migration import (
    META_PATTERNS,
    T2_PATTERNS,
    MigrationAction,
    MigrationResult,
    _determine_omega_required,
    _get_new_tier_name,
    _has_t2_modules,
    _load_yaml_preserve_order,
    _migrate_file,
    _update_yaml_content,
    migrate_archetypes,
    run_migration,
    update_omega_flags,
)
from aria_esi.archetypes.models import TIER_MIGRATION_MAP

# =============================================================================
# MigrationAction Tests
# =============================================================================


class TestMigrationAction:
    """Tests for MigrationAction dataclass."""

    def test_to_dict_basic(self) -> None:
        """Test MigrationAction.to_dict() with basic data."""
        action = MigrationAction(
            action_type="rename",
            source_path=Path("/test/low.yaml"),
            target_path=Path("/test/t1.yaml"),
            changes=["skill_tier: low -> t1"],
        )

        result = action.to_dict()
        assert result["action"] == "rename"
        assert result["source"] == "/test/low.yaml"
        assert result["target"] == "/test/t1.yaml"
        assert result["changes"] == ["skill_tier: low -> t1"]
        assert "error" not in result

    def test_to_dict_with_error(self) -> None:
        """Test MigrationAction.to_dict() with error."""
        action = MigrationAction(
            action_type="skip",
            source_path=Path("/test/invalid.yaml"),
            error="Failed to parse YAML",
        )

        result = action.to_dict()
        assert result["action"] == "skip"
        assert result["error"] == "Failed to parse YAML"

    def test_to_dict_skip_action(self) -> None:
        """Test MigrationAction.to_dict() for skip action."""
        action = MigrationAction(
            action_type="skip",
            source_path=Path("/test/t1.yaml"),
            changes=["Already using new tier name"],
        )

        result = action.to_dict()
        assert result["action"] == "skip"
        assert "target" not in result


# =============================================================================
# MigrationResult Tests
# =============================================================================


class TestMigrationResult:
    """Tests for MigrationResult dataclass."""

    def test_to_dict(self) -> None:
        """Test MigrationResult.to_dict()."""
        result = MigrationResult(
            total_files=10,
            migrated=5,
            skipped=4,
            errors=1,
            actions=[
                MigrationAction("rename", Path("/a.yaml")),
                MigrationAction("skip", Path("/b.yaml")),
            ],
        )

        output = result.to_dict()
        assert output["total_files"] == 10
        assert output["migrated"] == 5
        assert output["skipped"] == 4
        assert output["errors"] == 1
        assert len(output["actions"]) == 2


# =============================================================================
# T2 Module Detection Tests
# =============================================================================


class TestHasT2Modules:
    """Tests for _has_t2_modules function."""

    def test_detects_t2_suffix(self) -> None:
        """Test detection of standard T2 suffix."""
        eft = """[Vexor, Test]
Drone Damage Amplifier II
Medium Armor Repairer II"""

        assert _has_t2_modules(eft) is True

    def test_detects_t2_with_charge(self) -> None:
        """Test detection of T2 with charge loaded."""
        eft = """[Vexor, Test]
Medium Armor Repairer II, Nanite Repair Paste"""

        assert _has_t2_modules(eft) is True

    def test_no_t2_modules(self) -> None:
        """Test no false positives for T1/meta modules."""
        eft = """[Vexor, Test]
Drone Damage Amplifier I
Compact Armor Repairer"""

        assert _has_t2_modules(eft) is False

    def test_empty_eft(self) -> None:
        """Test empty EFT returns False."""
        assert _has_t2_modules("") is False

    def test_t2_patterns_constant(self) -> None:
        """Test T2_PATTERNS constant has expected patterns."""
        assert len(T2_PATTERNS) >= 2
        # Should match " II" at end and " II," for charges
        assert any("II$" in p for p in T2_PATTERNS)
        assert any("II," in p for p in T2_PATTERNS)

    def test_meta_patterns_constant(self) -> None:
        """Test META_PATTERNS constant has expected patterns."""
        assert "Compact" in META_PATTERNS
        assert "Enduring" in META_PATTERNS


# =============================================================================
# Omega Required Determination Tests
# =============================================================================


class TestDetermineOmegaRequired:
    """Tests for _determine_omega_required function."""

    def test_alpha_tier_not_required(self) -> None:
        """Test alpha tier explicitly not omega required."""
        data = {
            "eft": "[Vexor, Test]\nDrone Damage Amplifier I",
            "archetype": {"skill_tier": "alpha"},
        }

        assert _determine_omega_required(data) is False

    def test_high_tier_required(self) -> None:
        """Test high tier assumed omega required."""
        data = {
            "eft": "[Vexor, Test]\nDrone Damage Amplifier II",
            "archetype": {"skill_tier": "high"},
        }

        assert _determine_omega_required(data) is True

    def test_medium_tier_with_t2(self) -> None:
        """Test medium tier with T2 modules requires omega."""
        data = {
            "eft": "[Vexor, Test]\nDrone Damage Amplifier II",
            "archetype": {"skill_tier": "medium"},
        }

        assert _determine_omega_required(data) is True

    def test_medium_tier_without_t2(self) -> None:
        """Test medium tier without T2 doesn't require omega."""
        data = {
            "eft": "[Vexor, Test]\nDrone Damage Amplifier I",
            "archetype": {"skill_tier": "medium"},
        }

        assert _determine_omega_required(data) is False

    def test_low_tier_not_required(self) -> None:
        """Test low tier typically doesn't require omega."""
        data = {
            "eft": "[Vexor, Test]\nDrone Damage Amplifier I",
            "archetype": {"skill_tier": "low"},
        }

        assert _determine_omega_required(data) is False


# =============================================================================
# Tier Name Mapping Tests
# =============================================================================


class TestGetNewTierName:
    """Tests for _get_new_tier_name function."""

    @pytest.mark.parametrize(
        "old_tier,expected_new",
        [
            ("low", "t1"),
            ("medium", "meta"),
            ("high", "t2_optimal"),
            ("alpha", "t1"),
        ],
    )
    def test_known_mappings(self, old_tier: str, expected_new: str) -> None:
        """Test known tier mappings."""
        assert _get_new_tier_name(old_tier) == expected_new

    def test_unknown_tier_unchanged(self) -> None:
        """Test unknown tier names pass through unchanged."""
        assert _get_new_tier_name("custom") == "custom"

    def test_new_tier_unchanged(self) -> None:
        """Test new tier names pass through unchanged."""
        assert _get_new_tier_name("t1") == "t1"
        assert _get_new_tier_name("meta") == "meta"
        assert _get_new_tier_name("t2_optimal") == "t2_optimal"

    def test_tier_migration_map_complete(self) -> None:
        """Test TIER_MIGRATION_MAP has all legacy tiers."""
        assert "low" in TIER_MIGRATION_MAP
        assert "medium" in TIER_MIGRATION_MAP
        assert "high" in TIER_MIGRATION_MAP
        assert "alpha" in TIER_MIGRATION_MAP


# =============================================================================
# YAML Handling Tests
# =============================================================================


class TestLoadYamlPreserveOrder:
    """Tests for _load_yaml_preserve_order function."""

    def test_load_valid_yaml(self, tmp_path: Path) -> None:
        """Test loading valid YAML file."""
        yaml_file = tmp_path / "test.yaml"
        content = "key: value\nnumber: 42"
        yaml_file.write_text(content)

        data, raw = _load_yaml_preserve_order(yaml_file)

        assert data == {"key": "value", "number": 42}
        assert raw == content

    def test_load_empty_yaml(self, tmp_path: Path) -> None:
        """Test loading empty YAML returns empty dict."""
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("")

        data, raw = _load_yaml_preserve_order(yaml_file)

        assert data == {}
        assert raw == ""


class TestUpdateYamlContent:
    """Tests for _update_yaml_content function."""

    def test_update_skill_tier(self) -> None:
        """Test updating skill_tier in YAML content."""
        content = """archetype:
  hull: Vexor
  skill_tier: low"""

        updated = _update_yaml_content(content, "low", "t1")

        assert "skill_tier: t1" in updated
        assert "skill_tier: low" not in updated

    def test_add_omega_required(self) -> None:
        """Test adding omega_required field."""
        content = """archetype:
  hull: Vexor
  skill_tier: t1"""

        updated = _update_yaml_content(content, "t1", "t1", add_omega_required=False)

        assert "omega_required: false" in updated

    def test_skip_omega_if_present(self) -> None:
        """Test omega_required not duplicated if present."""
        content = """archetype:
  hull: Vexor
  skill_tier: t1
  omega_required: true"""

        updated = _update_yaml_content(content, "t1", "t1", add_omega_required=False)

        # Should only have one omega_required
        assert updated.count("omega_required") == 1


# =============================================================================
# File Migration Tests
# =============================================================================


class TestMigrateFile:
    """Tests for _migrate_file function."""

    def test_already_migrated(self, tmp_path: Path) -> None:
        """Test file with new tier name is skipped."""
        yaml_file = tmp_path / "t1.yaml"
        yaml_file.write_text("archetype:\n  skill_tier: t1")

        action = _migrate_file(yaml_file, dry_run=True)

        assert action.action_type == "skip"
        assert "Already using new tier name" in action.changes[0]

    def test_unknown_tier(self, tmp_path: Path) -> None:
        """Test file with unknown tier is skipped."""
        yaml_file = tmp_path / "custom.yaml"
        yaml_file.write_text("archetype:\n  skill_tier: custom")

        action = _migrate_file(yaml_file, dry_run=True)

        assert action.action_type == "skip"
        assert "Unknown tier" in action.changes[0]

    def test_dry_run_migration(self, tmp_path: Path) -> None:
        """Test dry run reports changes without modifying."""
        yaml_file = tmp_path / "low.yaml"
        yaml_file.write_text("""archetype:
  hull: Vexor
  skill_tier: low
eft: |
  [Vexor, Test]
  Drone Damage Amplifier I""")

        action = _migrate_file(yaml_file, dry_run=True)

        assert action.action_type == "rename"
        assert action.target_path == tmp_path / "t1.yaml"
        assert "skill_tier: low -> t1" in action.changes
        # Original file should still exist
        assert yaml_file.exists()
        # Target should not exist yet
        assert not action.target_path.exists()

    def test_actual_migration(self, tmp_path: Path) -> None:
        """Test actual migration creates new file and removes old."""
        yaml_file = tmp_path / "low.yaml"
        yaml_file.write_text("""archetype:
  hull: Vexor
  skill_tier: low
eft: |
  [Vexor, Test]
  Drone Damage Amplifier I""")

        action = _migrate_file(yaml_file, dry_run=False)

        assert action.action_type == "rename"
        # Old file should be removed
        assert not yaml_file.exists()
        # New file should exist
        target = tmp_path / "t1.yaml"
        assert target.exists()

        # Verify content was updated
        new_content = target.read_text()
        assert "skill_tier: t1" in new_content
        assert "omega_required" in new_content

    def test_target_exists_no_force(self, tmp_path: Path) -> None:
        """Test migration skipped when target exists without force."""
        source = tmp_path / "low.yaml"
        target = tmp_path / "t1.yaml"
        source.write_text("archetype:\n  skill_tier: low")
        target.write_text("existing content")

        action = _migrate_file(source, dry_run=True, force=False)

        assert action.action_type == "skip"
        assert "already exists" in action.changes[0]

    def test_target_exists_with_force(self, tmp_path: Path) -> None:
        """Test migration proceeds when target exists with force."""
        source = tmp_path / "low.yaml"
        target = tmp_path / "t1.yaml"
        source.write_text("""archetype:
  hull: Vexor
  skill_tier: low
eft: |
  [Vexor, Test]""")
        target.write_text("existing content")

        action = _migrate_file(source, dry_run=False, force=True)

        assert action.action_type == "rename"

    def test_invalid_yaml_file(self, tmp_path: Path) -> None:
        """Test migration handles invalid YAML gracefully."""
        yaml_file = tmp_path / "low.yaml"
        yaml_file.write_text("{ invalid yaml {{")

        action = _migrate_file(yaml_file, dry_run=True)

        assert action.action_type == "skip"
        assert action.error is not None
        assert "yaml" in action.error.lower()


# =============================================================================
# Batch Migration Tests
# =============================================================================


class TestMigrateArchetypes:
    """Tests for migrate_archetypes function."""

    def test_empty_hulls_directory(self, tmp_path: Path) -> None:
        """Test migration with empty hulls directory."""
        with patch(
            "aria_esi.archetypes.migration.get_hulls_path",
            return_value=tmp_path / "nonexistent",
        ):
            result = migrate_archetypes()

        assert result.total_files == 0

    def test_migrate_single_hull(self, tmp_path: Path) -> None:
        """Test migration filtered to single hull."""
        # Create hull directory structure
        hull_dir = tmp_path / "cruiser" / "vexor" / "pve"
        hull_dir.mkdir(parents=True)

        yaml_file = hull_dir / "low.yaml"
        yaml_file.write_text("""archetype:
  hull: Vexor
  skill_tier: low
eft: |
  [Vexor, Test]""")

        with patch(
            "aria_esi.archetypes.migration.get_hulls_path", return_value=tmp_path
        ):
            result = migrate_archetypes(hull="vexor", dry_run=True)

        assert result.total_files == 1
        assert result.migrated == 1

    def test_skip_manifest_files(self, tmp_path: Path) -> None:
        """Test manifest.yaml files are skipped."""
        hull_dir = tmp_path / "cruiser" / "vexor"
        hull_dir.mkdir(parents=True)

        manifest = hull_dir / "manifest.yaml"
        manifest.write_text("hull: Vexor")

        with patch(
            "aria_esi.archetypes.migration.get_hulls_path", return_value=tmp_path
        ):
            result = migrate_archetypes(dry_run=True)

        assert result.total_files == 0


# =============================================================================
# Update Omega Flags Tests
# =============================================================================


class TestUpdateOmegaFlags:
    """Tests for update_omega_flags function."""

    def test_skip_if_present(self, tmp_path: Path) -> None:
        """Test skips files that already have omega_required."""
        hull_dir = tmp_path / "cruiser" / "vexor" / "pve"
        hull_dir.mkdir(parents=True)

        yaml_file = hull_dir / "t1.yaml"
        yaml_file.write_text("""archetype:
  skill_tier: t1
  omega_required: false""")

        with patch(
            "aria_esi.archetypes.migration.get_hulls_path", return_value=tmp_path
        ):
            result = update_omega_flags(dry_run=True)

        assert result.skipped == 1
        assert result.migrated == 0

    def test_add_omega_required(self, tmp_path: Path) -> None:
        """Test adds omega_required to files missing it."""
        hull_dir = tmp_path / "cruiser" / "vexor" / "pve"
        hull_dir.mkdir(parents=True)

        yaml_file = hull_dir / "t1.yaml"
        yaml_file.write_text("""archetype:
  skill_tier: t1
eft: |
  [Vexor, Test]
  Drone Damage Amplifier I""")

        with patch(
            "aria_esi.archetypes.migration.get_hulls_path", return_value=tmp_path
        ):
            result = update_omega_flags(dry_run=False)

        assert result.migrated == 1

        # Verify file was updated
        updated = yaml_file.read_text()
        assert "omega_required" in updated


# =============================================================================
# Run Migration Tests
# =============================================================================


class TestRunMigration:
    """Tests for run_migration convenience function."""

    def test_run_migration_dry_run(self) -> None:
        """Test run_migration returns dict result."""
        with patch(
            "aria_esi.archetypes.migration.migrate_archetypes"
        ) as mock_migrate:
            mock_migrate.return_value = MigrationResult(
                total_files=10, migrated=5, skipped=4, errors=1
            )

            result = run_migration(dry_run=True)

        assert isinstance(result, dict)
        assert result["total_files"] == 10
        assert result["migrated"] == 5

    def test_run_migration_with_hull_filter(self) -> None:
        """Test run_migration passes hull filter."""
        with patch(
            "aria_esi.archetypes.migration.migrate_archetypes"
        ) as mock_migrate:
            mock_migrate.return_value = MigrationResult()

            run_migration(hull="vexor", dry_run=True)

            mock_migrate.assert_called_once_with(
                hull="vexor", dry_run=True, force=False
            )
