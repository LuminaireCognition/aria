"""
ARIA Path Security

Centralized path validation to prevent directory traversal attacks.

Security finding: P0 #2 from dev/reviews/PYTHON_REVIEW_2026-01.md
"""

from __future__ import annotations

import re
from pathlib import Path

from aria_esi.core.logging import get_logger

logger = get_logger(__name__)

# =============================================================================
# Constants
# =============================================================================

# Allowlisted directory prefixes for persona/overlay/redirect paths
# Only paths starting with these prefixes are permitted
PERSONA_ALLOWED_PREFIXES = (
    "personas/",
    ".claude/skills/",
)

# Allowlisted file extensions for persona files
# Only files with these extensions can be loaded as persona content
ALLOWED_EXTENSIONS = frozenset({".md", ".yaml", ".json"})

# Default maximum file size for persona files (100KB)
DEFAULT_MAX_FILE_SIZE = 100_000

# EVE character IDs are numeric (max ~20 digits for int64)
PILOT_ID_PATTERN = re.compile(r"^\d{1,20}$")


# =============================================================================
# Exceptions
# =============================================================================


class PathValidationError(Exception):
    """
    Raised when path validation fails.

    Includes the invalid path and reason for rejection.
    """

    def __init__(self, message: str, path: str | None = None, reason: str | None = None):
        """
        Initialize the path validation error.

        Args:
            message: Human-readable error message
            path: The path that failed validation
            reason: Specific reason for rejection
        """
        super().__init__(message)
        self.message = message
        self.path = path
        self.reason = reason

    def __str__(self) -> str:
        """Return the error message."""
        return self.message


# =============================================================================
# Break-Glass Functions
# =============================================================================


def is_break_glass_enabled() -> bool:
    """
    Check if break-glass mode is enabled via environment variable.

    Break-glass mode allows bypassing path validation for emergency
    situations, debugging, or CI/testing scenarios.

    Returns:
        True if ARIA_ALLOW_UNSAFE_PATHS is set to a truthy value

    Warning:
        Enabling this bypasses critical security controls. Only use
        in controlled environments.
    """
    from .config import get_settings

    return get_settings().is_break_glass_enabled("paths")


# =============================================================================
# Path Validation Functions
# =============================================================================


def validate_path(
    path: str,
    base_path: Path,
    allowed_prefixes: tuple[str, ...],
    check_symlinks: bool = True,
) -> tuple[bool, str | None]:
    """
    Validate that a path is safe to load.

    Ensures:
    - Path is relative (not absolute)
    - Path doesn't contain traversal components (..)
    - Path starts with an allowed prefix
    - Canonicalized path stays within allowed boundaries
    - Symlinks don't escape allowed boundaries (optional)

    Args:
        path: The relative path to validate
        base_path: Project root path
        allowed_prefixes: Tuple of allowed path prefixes
        check_symlinks: Whether to resolve symlinks and verify containment

    Returns:
        Tuple of (is_safe, error_message)
        If safe, error_message is None
    """
    # Break-glass mode bypasses all validation
    if is_break_glass_enabled():
        logger.warning("Break-glass mode enabled, bypassing path validation for: %s", path)
        return True, None

    # Reject None or empty paths
    if not path:
        return False, "Empty path"

    # Reject absolute paths (Unix and Windows style)
    if path.startswith("/") or (len(path) > 1 and path[1] == ":"):
        return False, f"Absolute paths not allowed: {path}"

    # Reject path traversal components
    path_parts = Path(path).parts
    if ".." in path_parts:
        return False, f"Path traversal not allowed: {path}"

    # Check allowlist prefix
    if not any(path.startswith(prefix) for prefix in allowed_prefixes):
        return False, f"Path not in allowlist (must start with {allowed_prefixes}): {path}"

    # If symlink checking is enabled, canonicalize and verify containment
    if check_symlinks:
        try:
            resolved = (base_path / path).resolve()
            resolved_base = base_path.resolve()

            # Ensure resolved path is under base_path (catches symlink escapes)
            try:
                resolved.relative_to(resolved_base)
            except ValueError:
                return False, f"Path escapes project root: {path}"

            # Extra check: verify resolved path matches an allowed prefix
            rel_to_base = str(resolved.relative_to(resolved_base))
            if not any(rel_to_base.startswith(prefix.rstrip("/")) for prefix in allowed_prefixes):
                return False, f"Resolved path not in allowlist: {path} -> {rel_to_base}"

        except Exception as e:
            return False, f"Path validation error: {path}: {e}"

    return True, None


def validate_persona_path(path: str, base_path: Path) -> tuple[bool, str | None]:
    """
    Validate a persona file path.

    Wrapper around validate_path() with persona-specific allowed prefixes.

    Args:
        path: The relative path to validate
        base_path: Project root path

    Returns:
        Tuple of (is_safe, error_message)
    """
    return validate_path(path, base_path, PERSONA_ALLOWED_PREFIXES)


def validate_pilot_id(pilot_id: str | None) -> tuple[bool, str | None]:
    """
    Validate that a pilot ID is in the expected format.

    EVE Online character IDs are numeric strings. This prevents
    path traversal via malformed pilot IDs like "../../../etc/passwd".

    Args:
        pilot_id: The pilot ID string to validate

    Returns:
        Tuple of (is_valid, error_message)
        If valid, error_message is None

    Examples:
        >>> validate_pilot_id("2123984364")
        (True, None)
        >>> validate_pilot_id("../../../etc/passwd")
        (False, "Invalid pilot ID format (must be numeric): ../../../etc/passwd")
        >>> validate_pilot_id("")
        (False, "Empty pilot ID")
    """
    # Break-glass mode bypasses validation
    if is_break_glass_enabled():
        logger.warning("Break-glass mode enabled, bypassing pilot_id validation for: %s", pilot_id)
        return True, None

    # Reject None or empty
    if not pilot_id:
        return False, "Empty pilot ID"

    # Must match numeric pattern
    if not PILOT_ID_PATTERN.match(pilot_id):
        return False, f"Invalid pilot ID format (must be numeric): {pilot_id}"

    return True, None


def validate_persona_file_path(
    path: str,
    base_path: Path,
    allowed_extensions: frozenset[str] | None = None,
) -> tuple[bool, str | None]:
    """
    Validate a persona file path with extension allowlist.

    Combines directory prefix validation with file extension checking
    to prevent loading of arbitrary file types (.py, .sh, executables, etc.).

    Security finding: SEC-001/SEC-002 from dev/planning/REMEDIATION_BACKLOG.md

    Args:
        path: The relative path to validate
        base_path: Project root path
        allowed_extensions: Optional custom extension set (defaults to ALLOWED_EXTENSIONS)

    Returns:
        Tuple of (is_safe, error_message)
        If safe, error_message is None

    Examples:
        >>> validate_persona_file_path("personas/paria/voice.md", Path("/project"))
        (True, None)
        >>> validate_persona_file_path("personas/paria/script.py", Path("/project"))
        (False, "Extension not allowed...")
    """
    # First do standard persona path validation
    is_safe, error = validate_persona_path(path, base_path)
    if not is_safe:
        return is_safe, error

    # Check file extension
    ext = Path(path).suffix.lower()
    exts = allowed_extensions or ALLOWED_EXTENSIONS

    if ext not in exts:
        return False, f"Extension not allowed (must be one of {sorted(exts)}): {path}"

    return True, None


def safe_read_persona_file(
    path: str,
    base_path: Path,
    max_size_bytes: int | None = None,
    allowed_extensions: frozenset[str] | None = None,
) -> tuple[str | None, str | None]:
    """
    Safely read a persona file with full validation and size limits.

    Performs path validation, extension checking, and size limiting before
    reading file content. Use this for all persona/overlay file loading.

    Security finding: SEC-001/SEC-002 from dev/planning/REMEDIATION_BACKLOG.md

    Args:
        path: The relative path to read
        base_path: Project root path
        max_size_bytes: Maximum file size in bytes (defaults to DEFAULT_MAX_FILE_SIZE)
        allowed_extensions: Optional custom extension set (defaults to ALLOWED_EXTENSIONS)

    Returns:
        Tuple of (content, error_message)
        If successful, error_message is None
        If failed, content is None

    Examples:
        >>> content, err = safe_read_persona_file("personas/paria/voice.md", Path("/project"))
        >>> if err:
        ...     print(f"Failed: {err}")
        ... else:
        ...     print(f"Loaded {len(content)} bytes")
    """
    max_size = max_size_bytes or DEFAULT_MAX_FILE_SIZE

    # Validate path and extension
    is_safe, error = validate_persona_file_path(path, base_path, allowed_extensions)
    if not is_safe:
        logger.warning("Rejected unsafe persona file path: %s - %s", path, error)
        return None, error

    # Build full path and check existence
    full_path = base_path / path

    if not full_path.exists():
        return None, f"File not found: {path}"

    if not full_path.is_file():
        return None, f"Not a file: {path}"

    # Check file size before reading
    try:
        file_size = full_path.stat().st_size
        if file_size > max_size:
            return None, f"File too large ({file_size} bytes, max {max_size}): {path}"
    except OSError as e:
        return None, f"Cannot stat file: {path}: {e}"

    # Read file content
    try:
        content = full_path.read_text(encoding="utf-8")
        return content, None
    except UnicodeDecodeError as e:
        return None, f"File is not valid UTF-8: {path}: {e}"
    except OSError as e:
        return None, f"Cannot read file: {path}: {e}"
