"""
ARIA Data Integrity Verification

Provides checksum verification and version pinning for external data sources.
This module helps ensure that downloaded SDE and EOS data hasn't been tampered
with or corrupted during transit.

Security finding: #4 from dev/reviews/SECURITY_000.md
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING

from aria_esi.core.logging import get_logger

if TYPE_CHECKING:
    from typing import Any

logger = get_logger(__name__)

# =============================================================================
# Constants
# =============================================================================

# Path to the data sources manifest, relative to project root
MANIFEST_PATH = Path(__file__).parent.parent.parent.parent / "reference" / "data-sources.json"


# =============================================================================
# Exceptions
# =============================================================================


class IntegrityError(Exception):
    """
    Raised when data integrity verification fails.

    This includes checksum mismatches, missing expected files,
    and other verification failures.
    """

    def __init__(self, message: str, expected: str | None = None, actual: str | None = None):
        """
        Initialize the integrity error.

        Args:
            message: Human-readable error message
            expected: Expected value (e.g., expected checksum)
            actual: Actual value found
        """
        super().__init__(message)
        self.message = message
        self.expected = expected
        self.actual = actual

    def __str__(self) -> str:
        """Return the error message."""
        return self.message


# =============================================================================
# Manifest Loading
# =============================================================================


def load_data_manifest(manifest_path: Path | None = None) -> dict[str, Any]:
    """
    Load the data sources manifest file.

    Args:
        manifest_path: Optional custom path to manifest file.
                       Defaults to reference/data-sources.json.

    Returns:
        Parsed manifest dictionary with schema_version and sources.

    Raises:
        FileNotFoundError: If manifest file doesn't exist
        json.JSONDecodeError: If manifest is invalid JSON
    """
    path = manifest_path or MANIFEST_PATH

    if not path.exists():
        raise FileNotFoundError(f"Data manifest not found: {path}")

    with open(path, encoding="utf-8") as f:
        manifest = json.load(f)

    # Validate schema version
    schema_version = manifest.get("schema_version")
    if schema_version != 1:
        logger.warning(
            "Unknown manifest schema version %s, expected 1",
            schema_version,
        )

    return manifest


def _get_manifest_safe() -> dict[str, Any] | None:
    """
    Safely load manifest, returning None if unavailable.

    This is used by functions that need manifest data but should
    gracefully degrade if the manifest doesn't exist.
    """
    try:
        return load_data_manifest()
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning("Could not load data manifest: %s", e)
        return None


# =============================================================================
# Checksum Functions
# =============================================================================


def compute_sha256(file_path: Path, chunk_size: int = 65536) -> str:
    """
    Compute SHA256 checksum of a file.

    Args:
        file_path: Path to the file to checksum
        chunk_size: Size of chunks to read (default 64KB)

    Returns:
        Lowercase hex-encoded SHA256 hash

    Raises:
        FileNotFoundError: If file doesn't exist
        PermissionError: If file can't be read
    """
    sha256_hash = hashlib.sha256()

    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            sha256_hash.update(chunk)

    return sha256_hash.hexdigest()


def verify_checksum(file_path: Path, expected: str) -> bool:
    """
    Verify a file's SHA256 checksum matches the expected value.

    Args:
        file_path: Path to the file to verify
        expected: Expected SHA256 checksum (lowercase hex)

    Returns:
        True if checksum matches, False otherwise

    Raises:
        FileNotFoundError: If file doesn't exist
    """
    actual = compute_sha256(file_path)
    return actual.lower() == expected.lower()


# =============================================================================
# Break-Glass Functions
# =============================================================================


def is_break_glass_enabled() -> bool:
    """
    Check if break-glass mode is enabled via environment variable.

    Break-glass mode allows bypassing integrity checks for emergency
    situations or CI/testing scenarios.

    Returns:
        True if ARIA_ALLOW_UNPINNED is set to a truthy value
    """
    from .config import get_settings

    return get_settings().is_break_glass_enabled("integrity")


# =============================================================================
# SDE Functions
# =============================================================================


def get_pinned_sde_url() -> tuple[str, str | None]:
    """
    Get the pinned SDE download URL and expected checksum.

    Returns:
        Tuple of (url, expected_checksum). Checksum may be None if
        not yet populated in the manifest.

    Note:
        If manifest is unavailable, returns the latest URL with no checksum.
    """
    manifest = _get_manifest_safe()

    if manifest is None:
        # Fallback to default URL if manifest unavailable
        return ("https://www.fuzzwork.co.uk/dump/sqlite-latest.sqlite.bz2", None)

    sde_config = manifest.get("sources", {}).get("sde", {})
    pinned_version = sde_config.get("pinned_version", "latest")

    if pinned_version == "latest":
        url = sde_config.get(
            "url_latest", "https://www.fuzzwork.co.uk/dump/sqlite-latest.sqlite.bz2"
        )
    else:
        url_template = sde_config.get(
            "url_template", "https://www.fuzzwork.co.uk/dump/sqlite-{version}.sqlite.bz2"
        )
        url = url_template.format(version=pinned_version)

    checksum = sde_config.get("sha256")
    return (url, checksum)


def verify_sde_integrity(
    file_path: Path,
    expected_checksum: str | None = None,
    break_glass: bool = False,
) -> tuple[bool, str]:
    """
    Verify integrity of a downloaded SDE file.

    Args:
        file_path: Path to the downloaded SDE file (compressed or decompressed)
        expected_checksum: Expected SHA256. If None, uses manifest value.
        break_glass: If True, skip verification (always returns success)

    Returns:
        Tuple of (success: bool, actual_checksum: str)

    Raises:
        IntegrityError: If verification fails and break_glass is False
    """
    # Break-glass mode skips verification
    if break_glass or is_break_glass_enabled():
        logger.warning("Break-glass mode enabled, skipping SDE integrity verification")
        actual = compute_sha256(file_path) if file_path.exists() else "unknown"
        return (True, actual)

    # Get expected checksum
    if expected_checksum is None:
        _, expected_checksum = get_pinned_sde_url()

    # If no checksum configured, verification passes (Phase 1 rollout)
    if expected_checksum is None:
        logger.info("No SDE checksum configured in manifest, skipping verification")
        actual = compute_sha256(file_path)
        return (True, actual)

    # Compute and verify
    actual = compute_sha256(file_path)
    if actual.lower() != expected_checksum.lower():
        raise IntegrityError(
            f"SDE checksum mismatch: expected {expected_checksum}, got {actual}",
            expected=expected_checksum,
            actual=actual,
        )

    logger.info("SDE checksum verified: %s", actual[:16] + "...")
    return (True, actual)


# =============================================================================
# EOS Functions
# =============================================================================


def get_pinned_eos_commit() -> str | None:
    """
    Get the pinned EOS/Pyfa commit hash.

    Returns:
        Commit hash string if pinned, None if using HEAD
    """
    manifest = _get_manifest_safe()

    if manifest is None:
        return None

    eos_config = manifest.get("sources", {}).get("eos", {})
    return eos_config.get("pinned_commit")


def get_eos_repository() -> str:
    """
    Get the EOS/Pyfa repository URL.

    Returns:
        Repository URL string
    """
    manifest = _get_manifest_safe()

    if manifest is None:
        return "https://github.com/pyfa-org/Pyfa.git"

    eos_config = manifest.get("sources", {}).get("eos", {})
    return eos_config.get("repository", "https://github.com/pyfa-org/Pyfa.git")


def verify_eos_commit(repo_path: Path, expected_commit: str | None = None) -> tuple[bool, str]:
    """
    Verify that a cloned EOS repository is at the expected commit.

    Args:
        repo_path: Path to the cloned repository
        expected_commit: Expected commit hash. If None, uses manifest value.

    Returns:
        Tuple of (success: bool, actual_commit: str)

    Note:
        This function requires git to be available. If git fails or
        no expected commit is configured, verification passes.
    """
    import subprocess

    # Get actual commit
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        actual = result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.warning("Could not get git commit: %s", e)
        return (True, "unknown")

    # Get expected commit
    if expected_commit is None:
        expected_commit = get_pinned_eos_commit()

    # If no commit configured, verification passes (Phase 1 rollout)
    if expected_commit is None:
        logger.info("No EOS commit pinned in manifest, using HEAD: %s", actual[:12])
        return (True, actual)

    # Check if actual starts with expected (allow short hashes)
    if actual.startswith(expected_commit) or expected_commit.startswith(actual):
        logger.info("EOS commit verified: %s", actual[:12])
        return (True, actual)

    logger.warning(
        "EOS commit mismatch: expected %s, got %s",
        expected_commit[:12],
        actual[:12],
    )
    return (False, actual)


# =============================================================================
# Utility Functions
# =============================================================================


# =============================================================================
# Universe Graph Functions
# =============================================================================


def get_universe_graph_checksum() -> str | None:
    """
    Get the expected checksum for the universe graph from manifest.

    Returns:
        SHA256 checksum string if configured, None otherwise
    """
    manifest = _get_manifest_safe()

    if manifest is None:
        return None

    graph_config = manifest.get("sources", {}).get("universe_graph", {})
    return graph_config.get("sha256")


def verify_universe_graph_integrity(
    file_path: Path,
    expected_checksum: str | None = None,
    break_glass: bool = False,
) -> tuple[bool, str]:
    """
    Verify integrity of the universe graph file.

    Args:
        file_path: Path to universe graph file
        expected_checksum: Expected SHA256. If None, uses manifest value.
        break_glass: If True, skip verification (always returns success)

    Returns:
        Tuple of (success: bool, actual_checksum: str)

    Raises:
        IntegrityError: If verification fails and break_glass is False

    Security:
        This is a critical security control. Checksum verification ensures
        the file hasn't been tampered with before deserialization.
    """
    # Break-glass mode skips verification
    if break_glass or is_break_glass_enabled():
        logger.warning("Break-glass mode enabled, skipping universe graph integrity verification")
        actual = compute_sha256(file_path) if file_path.exists() else "unknown"
        return (True, actual)

    # Get expected checksum
    if expected_checksum is None:
        expected_checksum = get_universe_graph_checksum()

    # If no checksum configured, verification passes with warning
    # This allows gradual rollout - first deploy code, then populate checksum
    if expected_checksum is None:
        logger.warning(
            "No universe graph checksum configured in manifest. "
            "Run 'uv run aria-esi universe --update-checksum' to secure."
        )
        actual = compute_sha256(file_path)
        return (True, actual)

    # Compute and verify before loading the graph
    actual = compute_sha256(file_path)
    if actual.lower() != expected_checksum.lower():
        raise IntegrityError(
            f"Universe graph checksum mismatch!\n"
            f"Expected: {expected_checksum}\n"
            f"Actual:   {actual}\n"
            f"File:     {file_path}\n\n"
            "The universe graph file may have been tampered with or corrupted.\n"
            "If you rebuilt the graph, run 'uv run aria-esi universe --update-checksum'.\n"
            "To bypass (UNSAFE): set ARIA_ALLOW_UNPINNED=1",
            expected=expected_checksum,
            actual=actual,
        )

    logger.info("Universe graph checksum verified: %s", actual[:16] + "...")
    return (True, actual)


def update_universe_graph_checksum(file_path: Path, manifest_path: Path | None = None) -> str:
    """
    Compute and update the universe graph checksum in the manifest.

    This should be called after building a new universe graph file to record
    the known-good checksum.

    Args:
        file_path: Path to universe graph file
        manifest_path: Path to data-sources.json (defaults to standard location)

    Returns:
        The computed SHA256 checksum

    Raises:
        FileNotFoundError: If graph file or manifest doesn't exist
    """
    path = manifest_path or MANIFEST_PATH

    # Compute checksum
    checksum = compute_sha256(file_path)

    # Load existing manifest
    with open(path, encoding="utf-8") as f:
        manifest = json.load(f)

    # Ensure universe_graph section exists
    if "universe_graph" not in manifest.get("sources", {}):
        if "sources" not in manifest:
            manifest["sources"] = {}
        manifest["sources"]["universe_graph"] = {
            "description": "Pre-built universe navigation graph",
        }

    # Update checksum and timestamp
    from datetime import datetime, timezone

    manifest["sources"]["universe_graph"]["sha256"] = checksum
    manifest["sources"]["universe_graph"]["last_verified"] = datetime.now(timezone.utc).isoformat()

    # Write back
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    logger.info("Updated universe graph checksum: %s", checksum[:16] + "...")
    return checksum


def get_integrity_status() -> dict[str, Any]:
    """
    Get overall status of data integrity configuration.

    Returns:
        Dictionary with status information for all data sources
    """
    manifest = _get_manifest_safe()

    status: dict[str, Any] = {
        "manifest_available": manifest is not None,
        "break_glass_enabled": is_break_glass_enabled(),
        "sources": {},
    }

    if manifest:
        status["schema_version"] = manifest.get("schema_version")

        sde = manifest.get("sources", {}).get("sde", {})
        status["sources"]["sde"] = {
            "pinned_version": sde.get("pinned_version"),
            "has_checksum": sde.get("sha256") is not None,
            "last_verified": sde.get("last_verified"),
        }

        eos = manifest.get("sources", {}).get("eos", {})
        status["sources"]["eos"] = {
            "pinned_commit": eos.get("pinned_commit"),
            "last_verified": eos.get("last_verified"),
        }

        universe_graph = manifest.get("sources", {}).get("universe_graph", {})
        status["sources"]["universe_graph"] = {
            "has_checksum": universe_graph.get("sha256") is not None,
            "last_verified": universe_graph.get("last_verified"),
        }

    return status
