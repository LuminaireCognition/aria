"""
Tests for EOS Data Management.

Tests cover:
- EOSDataManager validation
- Missing directory handling
- Missing file detection
- Version extraction
- Status caching
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aria_esi.core.config import get_settings
from aria_esi.fitting.eos_data import (
    OPTIONAL_FSD_BUILT_FILES,
    REQUIRED_FSD_BUILT_FILES,
    REQUIRED_FSD_LITE_FILES,
    REQUIRED_PHOBOS_FILES,
    EOSDataError,
    EOSDataManager,
    EOSDataStatus,
    get_eos_data_manager,
    reset_eos_data_manager,
)

# =============================================================================
# EOSDataManager Tests
# =============================================================================


class TestEOSDataManager:
    """Tests for EOSDataManager class."""

    def test_init_with_default_path(self):
        """Test initialization with default data path (from settings)."""
        manager = EOSDataManager()
        assert manager.data_path == get_settings().eos_data_path

    def test_init_with_custom_path(self, tmp_path: Path):
        """Test initialization with custom path."""
        manager = EOSDataManager(data_path=tmp_path)
        assert manager.data_path == tmp_path

    def test_init_with_string_path(self, tmp_path: Path):
        """Test initialization with string path."""
        manager = EOSDataManager(data_path=str(tmp_path))
        assert manager.data_path == tmp_path

    def test_fsd_built_path(self, tmp_path: Path):
        """Test fsd_built_path property."""
        manager = EOSDataManager(data_path=tmp_path)
        assert manager.fsd_built_path == tmp_path / "fsd_built"

    def test_fsd_lite_path(self, tmp_path: Path):
        """Test fsd_lite_path property."""
        manager = EOSDataManager(data_path=tmp_path)
        assert manager.fsd_lite_path == tmp_path / "fsd_lite"

    def test_phobos_path(self, tmp_path: Path):
        """Test phobos_path property."""
        manager = EOSDataManager(data_path=tmp_path)
        assert manager.phobos_path == tmp_path / "phobos"

    def test_cache_path(self, tmp_path: Path):
        """Test cache_path property."""
        manager = EOSDataManager(data_path=tmp_path)
        assert manager.cache_path == tmp_path / "eos-cache.json.bz2"


# =============================================================================
# Validation Tests
# =============================================================================


class TestValidation:
    """Tests for data validation."""

    def test_validate_missing_directory(self, tmp_path: Path):
        """Test validation when directory doesn't exist."""
        non_existent = tmp_path / "does-not-exist"
        manager = EOSDataManager(data_path=non_existent)

        status = manager.validate()

        assert status.is_valid is False
        assert "data directory does not exist" in status.missing_files[0]
        assert status.error_message is not None

    def test_validate_valid_data(self, mock_eos_data_path: Path):
        """Test validation with complete data."""
        manager = EOSDataManager(data_path=mock_eos_data_path)

        status = manager.validate()

        assert status.is_valid is True
        assert len(status.missing_files) == 0
        assert status.error_message is None

    def test_validate_missing_fsd_built_files(self, incomplete_eos_data_path: Path):
        """Test validation with missing fsd_built files."""
        manager = EOSDataManager(data_path=incomplete_eos_data_path)

        status = manager.validate()

        assert status.is_valid is False
        # Should report missing types.json among others
        missing = [f for f in status.missing_files if "types.json" in f]
        assert len(missing) > 0

    def test_validate_lists_all_missing_files(self, tmp_path: Path):
        """Test that validation lists all missing files."""
        # Create empty structure
        data_path = tmp_path / "eos-data"
        data_path.mkdir()
        (data_path / "fsd_built").mkdir()
        (data_path / "fsd_lite").mkdir()
        (data_path / "phobos").mkdir()

        manager = EOSDataManager(data_path=data_path)
        status = manager.validate()

        assert status.is_valid is False
        # Should have multiple missing files
        assert len(status.missing_files) >= len(REQUIRED_FSD_BUILT_FILES)

    def test_validate_returns_file_lists(self, mock_eos_data_path: Path):
        """Test that validation returns found file lists."""
        manager = EOSDataManager(data_path=mock_eos_data_path)

        status = manager.validate()

        # Should have found fsd_built files
        assert len(status.fsd_built_files) > 0
        # Should have found fsd_lite files
        assert len(status.fsd_lite_files) > 0
        # Should have found phobos files
        assert len(status.phobos_files) > 0


# =============================================================================
# Version Extraction Tests
# =============================================================================


class TestVersionExtraction:
    """Tests for version extraction from metadata."""

    def test_extract_version_from_metadata(self, mock_eos_data_path: Path):
        """Test version extraction from metadata.json."""
        manager = EOSDataManager(data_path=mock_eos_data_path)

        status = manager.validate()

        assert status.version == "2564511"

    def test_extract_version_missing_metadata(self, tmp_path: Path):
        """Test version when metadata.json is missing."""
        # Create minimal structure without metadata
        data_path = tmp_path / "eos-data"
        data_path.mkdir()
        (data_path / "fsd_built").mkdir()
        (data_path / "fsd_lite").mkdir()
        (data_path / "phobos").mkdir()

        manager = EOSDataManager(data_path=data_path)
        version = manager._get_version()

        assert version is None

    def test_extract_version_invalid_metadata(self, tmp_path: Path):
        """Test version with invalid metadata format."""
        data_path = tmp_path / "eos-data"
        data_path.mkdir()
        phobos = data_path / "phobos"
        phobos.mkdir()

        # Write invalid JSON
        (phobos / "metadata.json").write_text("not valid json")

        manager = EOSDataManager(data_path=data_path)
        version = manager._get_version()

        assert version is None


# =============================================================================
# Status Caching Tests
# =============================================================================


class TestStatusCaching:
    """Tests for status caching behavior."""

    def test_get_status_validates_on_first_call(self, mock_eos_data_path: Path):
        """Test that get_status validates on first call."""
        manager = EOSDataManager(data_path=mock_eos_data_path)

        # Clear cache
        manager._status_cache = None

        status = manager.get_status()

        assert status.is_valid is True
        assert manager._status_cache is not None

    def test_get_status_returns_cached(self, mock_eos_data_path: Path):
        """Test that get_status returns cached status."""
        manager = EOSDataManager(data_path=mock_eos_data_path)

        # First call validates
        status1 = manager.get_status()

        # Modify cache to verify it's returned
        manager._status_cache = EOSDataStatus(
            is_valid=False,
            data_path=mock_eos_data_path,
            version="cached",
            fsd_built_files=[],
            fsd_lite_files=[],
            phobos_files=[],
            missing_files=["test"],
            total_records=0,
            error_message="cached error",
        )

        # Second call should return cached
        status2 = manager.get_status()

        assert status2.version == "cached"
        assert status2.error_message == "cached error"

    def test_invalidate_cache(self, mock_eos_data_path: Path):
        """Test cache invalidation."""
        manager = EOSDataManager(data_path=mock_eos_data_path)

        # Prime cache
        manager.get_status()
        assert manager._status_cache is not None

        # Invalidate
        manager.invalidate_cache()

        assert manager._status_cache is None


# =============================================================================
# ensure_valid Tests
# =============================================================================


class TestEnsureValid:
    """Tests for ensure_valid method."""

    def test_ensure_valid_passes_with_valid_data(self, mock_eos_data_path: Path):
        """Test ensure_valid passes with valid data."""
        manager = EOSDataManager(data_path=mock_eos_data_path)

        # Should not raise
        manager.ensure_valid()

    def test_ensure_valid_raises_with_invalid_data(self, incomplete_eos_data_path: Path):
        """Test ensure_valid raises EOSDataError with invalid data."""
        manager = EOSDataManager(data_path=incomplete_eos_data_path)

        with pytest.raises(EOSDataError) as exc_info:
            manager.ensure_valid()

        assert len(exc_info.value.missing_files) > 0

    def test_ensure_valid_raises_with_missing_directory(self, tmp_path: Path):
        """Test ensure_valid raises with missing directory."""
        non_existent = tmp_path / "does-not-exist"
        manager = EOSDataManager(data_path=non_existent)

        with pytest.raises(EOSDataError):
            manager.ensure_valid()


# =============================================================================
# EOSDataStatus Tests
# =============================================================================


class TestEOSDataStatus:
    """Tests for EOSDataStatus dataclass."""

    def test_to_dict(self, mock_eos_data_path: Path):
        """Test status to_dict serialization."""
        manager = EOSDataManager(data_path=mock_eos_data_path)
        status = manager.validate()

        d = status.to_dict()

        assert "is_valid" in d
        assert "data_path" in d
        assert "version" in d
        assert "files" in d
        assert "fsd_built" in d["files"]
        assert "missing_files" in d


# =============================================================================
# Singleton Tests
# =============================================================================


class TestSingleton:
    """Tests for singleton accessor."""

    def test_get_eos_data_manager_returns_singleton(self):
        """Test that get_eos_data_manager returns singleton."""
        reset_eos_data_manager()

        manager1 = get_eos_data_manager()
        manager2 = get_eos_data_manager()

        assert manager1 is manager2

    def test_reset_eos_data_manager(self):
        """Test that reset clears singleton."""
        manager1 = get_eos_data_manager()
        reset_eos_data_manager()
        manager2 = get_eos_data_manager()

        assert manager1 is not manager2


# =============================================================================
# Constants Tests
# =============================================================================


class TestConstants:
    """Tests for module constants."""

    def test_required_fsd_built_files_list(self):
        """Test REQUIRED_FSD_BUILT_FILES contains expected files."""
        assert "types.json" in REQUIRED_FSD_BUILT_FILES
        assert "dogmaeffects.json" in REQUIRED_FSD_BUILT_FILES
        assert "typedogma.json" in REQUIRED_FSD_BUILT_FILES

    def test_required_fsd_lite_files_list(self):
        """Test REQUIRED_FSD_LITE_FILES contains expected files."""
        assert "fighterabilitiesbytype.json" in REQUIRED_FSD_LITE_FILES

    def test_required_phobos_files_list(self):
        """Test REQUIRED_PHOBOS_FILES contains expected files."""
        assert "metadata.json" in REQUIRED_PHOBOS_FILES

    def test_optional_fsd_built_files_list(self):
        """Test OPTIONAL_FSD_BUILT_FILES contains expected files."""
        assert "requiredskillsfortypes.json" in OPTIONAL_FSD_BUILT_FILES
