"""
EOS Data Management.

Handles data validation, paths, and version management for EOS fitting calculations.
The EOS library requires JSON data files in a specific directory structure.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ..core.config import get_settings
from ..core.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

# =============================================================================
# Constants
# =============================================================================

# Required files for EOS to function
REQUIRED_FSD_BUILT_FILES = [
    "types.json",
    "groups.json",
    "categories.json",
    "dogmaattributes.json",
    "dogmaeffects.json",
    "typedogma.json",
]

OPTIONAL_FSD_BUILT_FILES = [
    "requiredskillsfortypes.json",
]

REQUIRED_FSD_LITE_FILES = [
    "fighterabilitiesbytype.json",  # Can be empty {}
]

OPTIONAL_FSD_LITE_FILES = [
    "dbuffcollections.json",
    "clonegrades.json",
]

REQUIRED_PHOBOS_FILES = [
    "metadata.json",
]


# =============================================================================
# Exceptions
# =============================================================================


class EOSDataError(Exception):
    """Raised when EOS data is missing or invalid."""

    def __init__(self, message: str, missing_files: list[str] | None = None):
        super().__init__(message)
        self.missing_files = missing_files or []


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class EOSDataStatus:
    """Status of EOS data files."""

    is_valid: bool
    data_path: Path
    version: str | None
    fsd_built_files: list[str]
    fsd_lite_files: list[str]
    phobos_files: list[str]
    missing_files: list[str]
    total_records: int
    error_message: str | None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "is_valid": self.is_valid,
            "data_path": str(self.data_path),
            "version": self.version,
            "files": {
                "fsd_built": self.fsd_built_files,
                "fsd_lite": self.fsd_lite_files,
                "phobos": self.phobos_files,
            },
            "missing_files": self.missing_files,
            "total_records": self.total_records,
            "error_message": self.error_message,
        }


# =============================================================================
# Data Manager
# =============================================================================


class EOSDataManager:
    """
    Manages EOS data files and validation.

    Provides methods to check data status, validate files, and get paths
    for EOS initialization.
    """

    def __init__(self, data_path: Path | str | None = None):
        """
        Initialize the data manager.

        Args:
            data_path: Path to EOS data directory. Defaults to {instance_root}/cache/eos-data
        """
        if data_path is None:
            data_path = get_settings().eos_data_path
        self.data_path = Path(data_path)
        self._status_cache: EOSDataStatus | None = None
        self._lock = threading.Lock()

    @property
    def fsd_built_path(self) -> Path:
        """Path to fsd_built directory."""
        return self.data_path / "fsd_built"

    @property
    def fsd_lite_path(self) -> Path:
        """Path to fsd_lite directory."""
        return self.data_path / "fsd_lite"

    @property
    def phobos_path(self) -> Path:
        """Path to phobos directory."""
        return self.data_path / "phobos"

    @property
    def cache_path(self) -> Path:
        """Path to EOS cache file."""
        return self.data_path / "eos-cache.json.bz2"

    def validate(self) -> EOSDataStatus:
        """
        Validate EOS data files and return status.

        Returns:
            EOSDataStatus with validation results
        """
        with self._lock:
            # Check if data directory exists
            if not self.data_path.exists():
                return EOSDataStatus(
                    is_valid=False,
                    data_path=self.data_path,
                    version=None,
                    fsd_built_files=[],
                    fsd_lite_files=[],
                    phobos_files=[],
                    missing_files=["(data directory does not exist)"],
                    total_records=0,
                    error_message=f"EOS data directory not found: {self.data_path}",
                )

            missing_files = []
            fsd_built_files = []
            fsd_lite_files = []
            phobos_files = []
            total_records = 0

            # Check fsd_built files
            for filename in REQUIRED_FSD_BUILT_FILES:
                filepath = self.fsd_built_path / filename
                if filepath.exists():
                    fsd_built_files.append(filename)
                    # Count records for types.json
                    if filename == "types.json":
                        try:
                            with open(filepath) as f:
                                data = json.load(f)
                                total_records = len(data)
                        except Exception:
                            pass
                else:
                    missing_files.append(f"fsd_built/{filename}")

            # Check optional fsd_built files
            for filename in OPTIONAL_FSD_BUILT_FILES:
                filepath = self.fsd_built_path / filename
                if filepath.exists():
                    fsd_built_files.append(filename)

            # Check fsd_lite files
            for filename in REQUIRED_FSD_LITE_FILES:
                filepath = self.fsd_lite_path / filename
                if filepath.exists():
                    fsd_lite_files.append(filename)
                else:
                    missing_files.append(f"fsd_lite/{filename}")

            # Check optional fsd_lite files
            for filename in OPTIONAL_FSD_LITE_FILES:
                filepath = self.fsd_lite_path / filename
                if filepath.exists():
                    fsd_lite_files.append(filename)

            # Check phobos files
            for filename in REQUIRED_PHOBOS_FILES:
                filepath = self.phobos_path / filename
                if filepath.exists():
                    phobos_files.append(filename)
                else:
                    missing_files.append(f"phobos/{filename}")

            # Get version from metadata
            version = self._get_version()

            is_valid = len(missing_files) == 0

            status = EOSDataStatus(
                is_valid=is_valid,
                data_path=self.data_path,
                version=version,
                fsd_built_files=fsd_built_files,
                fsd_lite_files=fsd_lite_files,
                phobos_files=phobos_files,
                missing_files=missing_files,
                total_records=total_records,
                error_message=None if is_valid else f"Missing required files: {missing_files}",
            )

            self._status_cache = status
            return status

    def _get_version(self) -> str | None:
        """Get data version from metadata.json."""
        metadata_path = self.phobos_path / "metadata.json"
        if not metadata_path.exists():
            return None

        try:
            with open(metadata_path) as f:
                data = json.load(f)
                # Metadata is a list of dicts with field_name/field_value
                for item in data:
                    if item.get("field_name") == "client_build":
                        return str(item.get("field_value"))
        except Exception as e:
            logger.warning("Failed to read metadata.json: %s", e)

        return None

    def ensure_valid(self) -> None:
        """
        Ensure EOS data is valid, raising an error if not.

        Raises:
            EOSDataError: If data is missing or invalid
        """
        status = self.validate()
        if not status.is_valid:
            raise EOSDataError(
                f"EOS data is not valid: {status.error_message}",
                missing_files=status.missing_files,
            )

    def get_status(self) -> EOSDataStatus:
        """
        Get cached status or validate if not cached.

        Returns:
            EOSDataStatus with validation results
        """
        if self._status_cache is None:
            return self.validate()
        return self._status_cache

    def invalidate_cache(self) -> None:
        """Invalidate the cached status."""
        with self._lock:
            self._status_cache = None


# =============================================================================
# Singleton Accessor
# =============================================================================

_eos_data_manager: EOSDataManager | None = None
_manager_lock = threading.Lock()


def get_eos_data_manager() -> EOSDataManager:
    """Get the singleton EOS data manager."""
    global _eos_data_manager
    if _eos_data_manager is None:
        with _manager_lock:
            if _eos_data_manager is None:
                manager = EOSDataManager()
                _eos_data_manager = manager
    return _eos_data_manager


def reset_eos_data_manager() -> None:
    """Reset the singleton (for testing)."""
    global _eos_data_manager
    with _manager_lock:
        _eos_data_manager = None
