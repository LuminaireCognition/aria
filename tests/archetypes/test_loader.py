"""
Tests for archetypes loader module.

Tests path resolution, YAML loading, hull manifest parsing, archetype loading,
and the ArchetypeLoader class with caching.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from aria_esi.archetypes.loader import (
    HULL_CLASS_MAP,
    ArchetypeLoader,
    find_hull_directory,
    get_archetypes_path,
    get_hull_class,
    get_hulls_path,
    get_project_root,
    get_shared_path,
    list_archetypes,
    load_archetype,
    load_damage_profiles,
    load_faction_tuning,
    load_hull_manifest,
    load_module_tiers,
    load_shared_config,
    load_skill_tiers,
    load_tank_archetypes,
    load_yaml_file,
)
from aria_esi.archetypes.models import (
    Archetype,
    HullManifest,
)


class TestPathResolution:
    """Tests for path resolution functions."""

    def test_get_project_root_exists(self) -> None:
        """Test project root has expected structure."""
        root = get_project_root()
        assert root.is_dir()
        # Should have reference/ and src/ directories
        assert (root / "reference").is_dir() or (root / "src").is_dir()

    def test_get_archetypes_path(self) -> None:
        """Test archetypes path resolution."""
        path = get_archetypes_path()
        assert "archetypes" in str(path)

    def test_get_shared_path(self) -> None:
        """Test shared config path resolution."""
        path = get_shared_path()
        assert "_shared" in str(path)

    def test_get_hulls_path(self) -> None:
        """Test hulls directory path resolution."""
        path = get_hulls_path()
        assert "hulls" in str(path)


class TestHullClassMapping:
    """Tests for hull class mapping."""

    @pytest.mark.parametrize(
        "hull,expected_class",
        [
            ("venture", "frigate"),
            ("heron", "frigate"),
            ("algos", "destroyer"),
            ("vexor", "cruiser"),
            ("drake", "battlecruiser"),
            ("raven", "battleship"),
        ],
    )
    def test_hull_class_map_entries(self, hull: str, expected_class: str) -> None:
        """Test known hull class mappings."""
        assert HULL_CLASS_MAP.get(hull) == expected_class

    def test_hull_class_map_is_lowercase(self) -> None:
        """Test all keys in hull class map are lowercase."""
        for key in HULL_CLASS_MAP:
            assert key == key.lower()


class TestGetHullClass:
    """Tests for get_hull_class function."""

    def test_get_known_hull(self) -> None:
        """Test getting class for known hull."""
        assert get_hull_class("Vexor") == "cruiser"

    def test_get_hull_case_insensitive(self) -> None:
        """Test hull lookup is case-insensitive."""
        assert get_hull_class("VEXOR") == "cruiser"
        assert get_hull_class("vexor") == "cruiser"
        assert get_hull_class("VeXoR") == "cruiser"

    def test_get_hull_with_spaces(self) -> None:
        """Test hull lookup converts spaces to underscores."""
        assert get_hull_class("Vexor Navy Issue") == "cruiser"

    def test_get_unknown_hull(self) -> None:
        """Test getting class for unknown hull returns None."""
        assert get_hull_class("UnknownShip") is None


class TestFindHullDirectory:
    """Tests for find_hull_directory function."""

    def test_find_known_hull(self, populated_archetypes: Path) -> None:
        """Test finding directory for known hull."""
        with patch(
            "aria_esi.archetypes.loader.get_archetypes_path",
            return_value=populated_archetypes,
        ):
            hull_dir = find_hull_directory("vexor")
            assert hull_dir is not None
            assert hull_dir.is_dir()
            assert "vexor" in str(hull_dir)

    def test_find_hull_case_insensitive(self, populated_archetypes: Path) -> None:
        """Test finding hull directory is case-insensitive."""
        with patch(
            "aria_esi.archetypes.loader.get_archetypes_path",
            return_value=populated_archetypes,
        ):
            hull_dir = find_hull_directory("VEXOR")
            assert hull_dir is not None

    def test_find_unknown_hull(self, populated_archetypes: Path) -> None:
        """Test finding unknown hull returns None."""
        with patch(
            "aria_esi.archetypes.loader.get_archetypes_path",
            return_value=populated_archetypes,
        ):
            hull_dir = find_hull_directory("unknownship")
            assert hull_dir is None

    def test_find_hull_search_all_classes(self, populated_archetypes: Path) -> None:
        """Test finding hull searches all class directories."""
        # Create a hull not in the mapping
        new_hull = populated_archetypes / "hulls" / "cruiser" / "custom_cruiser"
        new_hull.mkdir(parents=True)

        with patch(
            "aria_esi.archetypes.loader.get_archetypes_path",
            return_value=populated_archetypes,
        ):
            hull_dir = find_hull_directory("custom_cruiser")
            assert hull_dir is not None


class TestLoadYamlFile:
    """Tests for load_yaml_file function."""

    def test_load_valid_yaml(self, tmp_path: Path) -> None:
        """Test loading valid YAML file."""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text("key: value\nnumber: 42")

        result = load_yaml_file(yaml_file)
        assert result == {"key": "value", "number": 42}

    def test_load_empty_yaml(self, tmp_path: Path) -> None:
        """Test loading empty YAML file returns empty dict."""
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("")

        result = load_yaml_file(yaml_file)
        assert result == {}

    def test_load_nonexistent_file(self, tmp_path: Path) -> None:
        """Test loading nonexistent file raises FileNotFoundError."""
        yaml_file = tmp_path / "nonexistent.yaml"

        with pytest.raises(FileNotFoundError):
            load_yaml_file(yaml_file)

    def test_load_invalid_yaml(self, tmp_path: Path) -> None:
        """Test loading invalid YAML raises yaml.YAMLError."""
        yaml_file = tmp_path / "invalid.yaml"
        yaml_file.write_text("{ invalid yaml {{")

        with pytest.raises(yaml.YAMLError):
            load_yaml_file(yaml_file)


class TestLoadSharedConfig:
    """Tests for shared config loading functions."""

    def test_load_shared_config(self, populated_archetypes: Path) -> None:
        """Test loading shared configuration."""
        with patch(
            "aria_esi.archetypes.loader.get_shared_path",
            return_value=populated_archetypes / "_shared",
        ):
            config = load_shared_config("damage_profiles")
            assert "blood_raiders" in config
            assert "serpentis" in config

    def test_load_shared_config_not_found(self, populated_archetypes: Path) -> None:
        """Test loading nonexistent shared config raises error."""
        with patch(
            "aria_esi.archetypes.loader.get_shared_path",
            return_value=populated_archetypes / "_shared",
        ):
            with pytest.raises(FileNotFoundError):
                load_shared_config("nonexistent")


class TestLoadSharedConfigHelpers:
    """Tests for specific shared config helper functions."""

    def test_load_damage_profiles(self, populated_archetypes: Path) -> None:
        """Test load_damage_profiles helper."""
        with patch(
            "aria_esi.archetypes.loader.get_shared_path",
            return_value=populated_archetypes / "_shared",
        ):
            profiles = load_damage_profiles()
            assert isinstance(profiles, dict)

    def test_load_faction_tuning_not_found(self, populated_archetypes: Path) -> None:
        """Test load_faction_tuning with missing file."""
        with patch(
            "aria_esi.archetypes.loader.get_shared_path",
            return_value=populated_archetypes / "_shared",
        ):
            with pytest.raises(FileNotFoundError):
                load_faction_tuning()

    def test_load_module_tiers_not_found(self, populated_archetypes: Path) -> None:
        """Test load_module_tiers with missing file."""
        with patch(
            "aria_esi.archetypes.loader.get_shared_path",
            return_value=populated_archetypes / "_shared",
        ):
            with pytest.raises(FileNotFoundError):
                load_module_tiers()

    def test_load_skill_tiers_not_found(self, populated_archetypes: Path) -> None:
        """Test load_skill_tiers with missing file."""
        with patch(
            "aria_esi.archetypes.loader.get_shared_path",
            return_value=populated_archetypes / "_shared",
        ):
            with pytest.raises(FileNotFoundError):
                load_skill_tiers()

    def test_load_tank_archetypes_not_found(self, populated_archetypes: Path) -> None:
        """Test load_tank_archetypes with missing file."""
        with patch(
            "aria_esi.archetypes.loader.get_shared_path",
            return_value=populated_archetypes / "_shared",
        ):
            with pytest.raises(FileNotFoundError):
                load_tank_archetypes()


class TestLoadHullManifest:
    """Tests for load_hull_manifest function."""

    def test_load_valid_manifest(self, populated_archetypes: Path) -> None:
        """Test loading valid hull manifest."""
        with patch(
            "aria_esi.archetypes.loader.get_archetypes_path",
            return_value=populated_archetypes,
        ):
            manifest = load_hull_manifest("vexor")
            assert manifest is not None
            assert isinstance(manifest, HullManifest)
            assert manifest.hull == "Vexor"
            assert manifest.ship_class == "cruiser"
            assert manifest.faction == "gallente"

    def test_load_manifest_slots(self, populated_archetypes: Path) -> None:
        """Test manifest has correct slot layout."""
        with patch(
            "aria_esi.archetypes.loader.get_archetypes_path",
            return_value=populated_archetypes,
        ):
            manifest = load_hull_manifest("vexor")
            assert manifest is not None
            assert manifest.slots.high == 4
            assert manifest.slots.mid == 4
            assert manifest.slots.low == 5
            assert manifest.slots.rig == 3

    def test_load_manifest_drones(self, populated_archetypes: Path) -> None:
        """Test manifest has correct drone capacity."""
        with patch(
            "aria_esi.archetypes.loader.get_archetypes_path",
            return_value=populated_archetypes,
        ):
            manifest = load_hull_manifest("vexor")
            assert manifest is not None
            assert manifest.drones is not None
            assert manifest.drones.bandwidth == 75
            assert manifest.drones.bay == 125

    def test_load_manifest_fitting_rules(self, populated_archetypes: Path) -> None:
        """Test manifest has fitting rules."""
        with patch(
            "aria_esi.archetypes.loader.get_archetypes_path",
            return_value=populated_archetypes,
        ):
            manifest = load_hull_manifest("vexor")
            assert manifest is not None
            assert manifest.fitting_rules.tank_type == "armor_active"

    def test_load_manifest_unknown_hull(self, populated_archetypes: Path) -> None:
        """Test loading manifest for unknown hull returns None."""
        with patch(
            "aria_esi.archetypes.loader.get_archetypes_path",
            return_value=populated_archetypes,
        ):
            manifest = load_hull_manifest("unknownship")
            assert manifest is None


class TestLoadArchetype:
    """Tests for load_archetype function."""

    def test_load_valid_archetype(self, populated_archetypes: Path) -> None:
        """Test loading valid archetype."""
        with patch(
            "aria_esi.archetypes.loader.get_archetypes_path",
            return_value=populated_archetypes,
        ):
            archetype = load_archetype("vexor/pve/missions/l2/t1")
            assert archetype is not None
            assert isinstance(archetype, Archetype)

    def test_load_archetype_header(self, populated_archetypes: Path) -> None:
        """Test archetype has correct header."""
        with patch(
            "aria_esi.archetypes.loader.get_archetypes_path",
            return_value=populated_archetypes,
        ):
            archetype = load_archetype("vexor/pve/missions/l2/t1")
            assert archetype is not None
            assert archetype.archetype.hull == "Vexor"
            assert archetype.archetype.skill_tier == "t1"
            assert archetype.archetype.omega_required is False

    def test_load_archetype_eft(self, populated_archetypes: Path) -> None:
        """Test archetype has EFT fitting."""
        with patch(
            "aria_esi.archetypes.loader.get_archetypes_path",
            return_value=populated_archetypes,
        ):
            archetype = load_archetype("vexor/pve/missions/l2/t1")
            assert archetype is not None
            assert "[Vexor, PvE L2 T1]" in archetype.eft
            assert "Drone Damage Amplifier I" in archetype.eft

    def test_load_archetype_stats(self, populated_archetypes: Path) -> None:
        """Test archetype has stats."""
        with patch(
            "aria_esi.archetypes.loader.get_archetypes_path",
            return_value=populated_archetypes,
        ):
            archetype = load_archetype("vexor/pve/missions/l2/t1")
            assert archetype is not None
            assert archetype.stats.dps == 280
            assert archetype.stats.ehp == 18000
            assert archetype.stats.capacitor_stable is True

    def test_load_archetype_skills(self, populated_archetypes: Path) -> None:
        """Test archetype has skill requirements."""
        with patch(
            "aria_esi.archetypes.loader.get_archetypes_path",
            return_value=populated_archetypes,
        ):
            archetype = load_archetype("vexor/pve/missions/l2/t1")
            assert archetype is not None
            assert "Gallente Cruiser" in archetype.skill_requirements.required
            assert "Medium Drone Operation" in archetype.skill_requirements.recommended

    def test_load_archetype_notes(self, populated_archetypes: Path) -> None:
        """Test archetype has notes."""
        with patch(
            "aria_esi.archetypes.loader.get_archetypes_path",
            return_value=populated_archetypes,
        ):
            archetype = load_archetype("vexor/pve/missions/l2/t1")
            assert archetype is not None
            assert archetype.notes is not None
            assert "Level 2 missions" in archetype.notes.purpose

    def test_load_archetype_invalid_path(self, populated_archetypes: Path) -> None:
        """Test loading archetype with invalid path returns None."""
        with patch(
            "aria_esi.archetypes.loader.get_archetypes_path",
            return_value=populated_archetypes,
        ):
            archetype = load_archetype("invalid/path/format")
            assert archetype is None

    def test_load_archetype_unknown_hull(self, populated_archetypes: Path) -> None:
        """Test loading archetype for unknown hull returns None."""
        with patch(
            "aria_esi.archetypes.loader.get_archetypes_path",
            return_value=populated_archetypes,
        ):
            archetype = load_archetype("unknownship/pve/missions/l2/t1")
            assert archetype is None

    def test_load_archetype_nonexistent_file(self, populated_archetypes: Path) -> None:
        """Test loading nonexistent archetype file returns None."""
        with patch(
            "aria_esi.archetypes.loader.get_archetypes_path",
            return_value=populated_archetypes,
        ):
            archetype = load_archetype("vexor/pve/missions/l2/t2_optimal")
            assert archetype is None


class TestListArchetypes:
    """Tests for list_archetypes function."""

    def test_list_all_archetypes(self, populated_archetypes: Path) -> None:
        """Test listing all archetypes."""
        with patch(
            "aria_esi.archetypes.loader.get_archetypes_path",
            return_value=populated_archetypes,
        ):
            archetypes = list_archetypes()
            assert isinstance(archetypes, list)
            assert len(archetypes) >= 1
            assert "vexor/pve/missions/l2/t1" in archetypes

    def test_list_archetypes_by_hull(self, populated_archetypes: Path) -> None:
        """Test listing archetypes filtered by hull."""
        with patch(
            "aria_esi.archetypes.loader.get_archetypes_path",
            return_value=populated_archetypes,
        ):
            archetypes = list_archetypes(hull="vexor")
            assert len(archetypes) >= 1
            assert all("vexor" in a for a in archetypes)

    def test_list_archetypes_unknown_hull(self, populated_archetypes: Path) -> None:
        """Test listing archetypes for unknown hull returns empty."""
        with patch(
            "aria_esi.archetypes.loader.get_archetypes_path",
            return_value=populated_archetypes,
        ):
            archetypes = list_archetypes(hull="unknownship")
            assert archetypes == []

    def test_list_archetypes_sorted(self, populated_archetypes: Path) -> None:
        """Test listed archetypes are sorted."""
        with patch(
            "aria_esi.archetypes.loader.get_archetypes_path",
            return_value=populated_archetypes,
        ):
            archetypes = list_archetypes()
            assert archetypes == sorted(archetypes)


class TestArchetypeLoader:
    """Tests for ArchetypeLoader class."""

    def test_create_loader(self) -> None:
        """Test creating ArchetypeLoader."""
        loader = ArchetypeLoader()
        assert loader._manifest_cache == {}
        assert loader._archetype_cache == {}
        assert loader._shared_cache == {}

    def test_get_manifest_caches(self, populated_archetypes: Path) -> None:
        """Test get_manifest uses cache."""
        with patch(
            "aria_esi.archetypes.loader.get_archetypes_path",
            return_value=populated_archetypes,
        ):
            loader = ArchetypeLoader()

            # First call loads from disk
            manifest1 = loader.get_manifest("vexor")
            assert "vexor" in loader._manifest_cache

            # Second call uses cache
            manifest2 = loader.get_manifest("vexor")
            assert manifest1 is manifest2

    def test_get_manifest_case_insensitive(self, populated_archetypes: Path) -> None:
        """Test get_manifest is case-insensitive."""
        with patch(
            "aria_esi.archetypes.loader.get_archetypes_path",
            return_value=populated_archetypes,
        ):
            loader = ArchetypeLoader()
            manifest1 = loader.get_manifest("VEXOR")
            manifest2 = loader.get_manifest("vexor")
            # Both should return same cached result
            assert manifest1 is manifest2

    def test_get_archetype_caches(self, populated_archetypes: Path) -> None:
        """Test get_archetype uses cache."""
        with patch(
            "aria_esi.archetypes.loader.get_archetypes_path",
            return_value=populated_archetypes,
        ):
            loader = ArchetypeLoader()

            path = "vexor/pve/missions/l2/t1"
            archetype1 = loader.get_archetype(path)
            assert path in loader._archetype_cache

            archetype2 = loader.get_archetype(path)
            assert archetype1 is archetype2

    def test_get_shared_config_caches(self, populated_archetypes: Path) -> None:
        """Test get_shared_config uses cache."""
        with patch(
            "aria_esi.archetypes.loader.get_shared_path",
            return_value=populated_archetypes / "_shared",
        ):
            loader = ArchetypeLoader()

            config1 = loader.get_shared_config("damage_profiles")
            assert "damage_profiles" in loader._shared_cache

            config2 = loader.get_shared_config("damage_profiles")
            assert config1 is config2

    def test_get_shared_config_not_found(self, populated_archetypes: Path) -> None:
        """Test get_shared_config returns empty dict for missing file."""
        with patch(
            "aria_esi.archetypes.loader.get_shared_path",
            return_value=populated_archetypes / "_shared",
        ):
            loader = ArchetypeLoader()
            config = loader.get_shared_config("nonexistent")
            assert config == {}

    def test_list_archetypes_wrapper(self, populated_archetypes: Path) -> None:
        """Test loader.list_archetypes wraps module function."""
        with patch(
            "aria_esi.archetypes.loader.get_archetypes_path",
            return_value=populated_archetypes,
        ):
            loader = ArchetypeLoader()
            archetypes = loader.list_archetypes()
            assert isinstance(archetypes, list)

    def test_clear_cache(self, populated_archetypes: Path) -> None:
        """Test clear_cache empties all caches."""
        with patch(
            "aria_esi.archetypes.loader.get_archetypes_path",
            return_value=populated_archetypes,
        ), patch(
            "aria_esi.archetypes.loader.get_shared_path",
            return_value=populated_archetypes / "_shared",
        ):
            loader = ArchetypeLoader()

            # Populate caches
            loader.get_manifest("vexor")
            loader.get_archetype("vexor/pve/missions/l2/t1")
            loader.get_shared_config("damage_profiles")

            assert len(loader._manifest_cache) > 0
            assert len(loader._archetype_cache) > 0
            assert len(loader._shared_cache) > 0

            # Clear caches
            loader.clear_cache()

            assert loader._manifest_cache == {}
            assert loader._archetype_cache == {}
            assert loader._shared_cache == {}
