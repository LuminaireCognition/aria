"""
ARIA ESI Authentication

Credential resolution and token management for ESI API access.

Security Model (Two-Tier):
    Tier II: keyring installed → System keychain (macOS/Linux/Windows)
    Tier I:  Default → Plaintext JSON with 0600 permissions

Install keyring for enhanced security: pip install aria[secure]

Security: Path validation added per dev/reviews/PYTHON_REVIEW_2026-01.md P0 #2
"""

import json
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional, Union

from .constants import CORP_SCOPES, PLAYER_CORP_MIN_ID
from .keyring_backend import (
    KEYRING_AVAILABLE,
    _warn_keyring_unavailable,
    get_keyring_status,
    is_keyring_enabled,
    load_from_keyring,
    store_in_keyring,
)
from .logging import get_logger
from .path_security import validate_pilot_id

# Module logger
_logger = get_logger(__name__)

# Security: Acceptable file permission modes for credentials
# Owner read/write (0o600) or owner read-only (0o400)
SECURE_FILE_MODES = {0o600, 0o400}


def _debug_log(message: str) -> None:
    """
    Log debug message using structured logging.

    Set ARIA_LOG_LEVEL=DEBUG or ARIA_DEBUG=1 to enable.
    """
    _logger.debug(message)


def _check_credentials_permissions(credentials_file: Path) -> None:
    """
    Check if credentials file has secure permissions.

    Warns to stderr if file is readable by group or others.
    Only checks on Unix-like systems (Linux, macOS).
    """
    # Skip on Windows - different permission model
    if sys.platform == "win32":
        return

    try:
        file_stat = credentials_file.stat()
        mode = stat.S_IMODE(file_stat.st_mode)

        # Check if group or others have any permissions
        if mode & (stat.S_IRWXG | stat.S_IRWXO):
            print(
                f"WARNING: Credentials file has insecure permissions ({oct(mode)}): "
                f"{credentials_file}\n"
                f"  Recommended: chmod 600 {credentials_file}",
                file=sys.stderr,
            )
    except OSError:
        pass  # If we can't stat the file, skip the check


class CredentialsError(Exception):
    """Exception raised for credential-related errors."""

    def __init__(
        self, message: str, action: Optional[str] = None, command: Optional[str] = None
    ) -> None:
        self.message = message
        self.action = action
        self.command = command
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Convert error to JSON-serializable dict."""
        result: dict[str, Any] = {"error": "credentials_error", "message": self.message}
        if self.action:
            result["action"] = self.action
        if self.command:
            result["command"] = self.command
        return result


class Credentials:
    """
    ESI credentials container and resolver.

    Handles credential resolution following priority order:
    1. ARIA_PILOT environment variable
    2. active_pilot in userdata/config.json
    3. First credentials file in userdata/credentials/ directory

    Usage:
        creds = Credentials.resolve()
        if creds:
            client = ESIClient(token=creds.access_token)
            char_id = creds.character_id
    """

    def __init__(
        self,
        credentials_file: Optional[Path],
        character_id: int,
        access_token: str,
        refresh_token: Optional[str] = None,
        token_expiry: Optional[str] = None,
        scopes: Optional[list[str]] = None,
        storage_source: str = "file",
    ) -> None:
        self.credentials_file: Optional[Path] = credentials_file
        self.character_id: int = character_id
        self.access_token: str = access_token
        self.refresh_token: Optional[str] = refresh_token
        self.token_expiry: Optional[str] = token_expiry
        self.scopes: list[str] = scopes or []
        self.storage_source: str = storage_source  # "keyring" or "file"

    @classmethod
    def from_file(cls, credentials_file: Path) -> "Credentials":
        """
        Load credentials from a JSON file.

        Args:
            credentials_file: Path to credentials JSON file

        Returns:
            Credentials instance

        Raises:
            CredentialsError: If file cannot be read or parsed
        """
        try:
            with open(credentials_file) as f:
                data = json.load(f)
        except FileNotFoundError:
            raise CredentialsError(
                f"Credentials file not found: {credentials_file}",
                action="Run the OAuth setup wizard",
                command="python3 .claude/scripts/aria-oauth-setup.py",
            )
        except json.JSONDecodeError as e:
            raise CredentialsError(f"Invalid credentials JSON: {e}")

        required_fields = ["character_id", "access_token"]
        for field in required_fields:
            if field not in data:
                raise CredentialsError(
                    f"Missing required field '{field}' in credentials",
                    action="Re-run OAuth setup",
                    command="python3 .claude/scripts/aria-oauth-setup.py",
                )

        # Security check: warn if credentials file has insecure permissions
        _check_credentials_permissions(credentials_file)

        return cls(
            credentials_file=credentials_file,
            character_id=data["character_id"],
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            token_expiry=data.get("token_expiry"),
            scopes=data.get("scopes", []),
            storage_source="file",
        )

    @classmethod
    def from_keyring(
        cls, character_id: Union[str, int], credentials_file: Optional[Path] = None
    ) -> Optional["Credentials"]:
        """
        Load credentials from system keyring.

        Args:
            character_id: The EVE character ID
            credentials_file: Optional path to associate with credentials
                            (used for fallback operations)

        Returns:
            Credentials instance if found in keyring, None otherwise
        """
        if not is_keyring_enabled():
            return None

        data = load_from_keyring(character_id)
        if not data:
            return None

        # Validate required fields
        required_fields = ["character_id", "access_token"]
        for field in required_fields:
            if field not in data:
                return None  # Invalid keyring data, will fall back to file

        return cls(
            credentials_file=credentials_file,
            character_id=data["character_id"],
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            token_expiry=data.get("token_expiry"),
            scopes=data.get("scopes", []),
            storage_source="keyring",
        )

    @classmethod
    def from_storage(cls, character_id: Union[str, int], credentials_file: Path) -> "Credentials":
        """
        Load credentials with keyring priority, falling back to file.

        This is the preferred method for loading credentials. It implements
        the two-tier security model:
            1. Try keyring (Tier II) if available
            2. Fall back to file (Tier I) if keyring unavailable or empty

        Args:
            character_id: The EVE character ID
            credentials_file: Path to the file-based credentials

        Returns:
            Credentials instance

        Raises:
            CredentialsError: If no credentials found in either location
        """
        # Tier II: Try keyring first
        creds = cls.from_keyring(character_id, credentials_file)
        if creds:
            return creds

        # Warn if keyring is installed but no backend available
        # (This helps users understand why they're falling back to file storage)
        if not KEYRING_AVAILABLE and is_keyring_enabled():
            # is_keyring_enabled() returns False when no backend, so this branch
            # won't fire. We need to check KEYRING_AVAILABLE directly.
            pass

        # Issue warning if falling back to file when keyring should be available
        if not is_keyring_enabled() and KEYRING_AVAILABLE is False:
            _warn_keyring_unavailable()

        # Tier I: Fall back to file
        return cls.from_file(credentials_file)

    def save_to_keyring(self) -> bool:
        """
        Save current credentials to system keyring.

        Returns:
            True if saved successfully, False otherwise
        """
        if not is_keyring_enabled():
            return False

        # Build credential dict
        data = {
            "character_id": self.character_id,
            "access_token": self.access_token,
        }
        if self.refresh_token:
            data["refresh_token"] = self.refresh_token
        if self.token_expiry:
            data["token_expiry"] = self.token_expiry
        if self.scopes:
            data["scopes"] = self.scopes

        success = store_in_keyring(self.character_id, data)
        if success:
            self.storage_source = "keyring"
        return success

    def get_full_data(self) -> dict[str, Any]:
        """
        Get the full credential data as a dictionary.

        Useful for saving or migration operations.

        Returns:
            Dict with all credential fields
        """
        data: dict[str, Any] = {
            "character_id": self.character_id,
            "access_token": self.access_token,
        }
        if self.refresh_token:
            data["refresh_token"] = self.refresh_token
        if self.token_expiry:
            data["token_expiry"] = self.token_expiry
        if self.scopes:
            data["scopes"] = self.scopes
        return data

    @classmethod
    def resolve(cls, project_dir: Optional[Path] = None) -> Optional["Credentials"]:
        """
        Resolve credentials following priority order.

        Priority:
        1. ARIA_PILOT environment variable
        2. active_pilot in userdata/config.json
        3. First credentials file in userdata/credentials/

        Args:
            project_dir: Project root directory (defaults to auto-detect)

        Returns:
            Credentials instance, or None if no credentials found
        """
        if project_dir is None:
            project_dir = cls._find_project_dir()

        if project_dir is None:
            _debug_log("Could not find project directory")
            return None

        _debug_log(f"Project directory: {project_dir}")

        # Credential and config paths
        creds_dir = project_dir / "userdata" / "credentials"
        config_file = project_dir / "userdata" / "config.json"

        # Priority 1: ARIA_PILOT environment variable (via centralized config)
        from .config import get_settings

        pilot_id = get_settings().pilot
        if pilot_id:
            # Security: Validate pilot_id format to prevent path traversal
            is_valid, error = validate_pilot_id(pilot_id)
            if not is_valid:
                _debug_log(f"Invalid ARIA_PILOT rejected: {error}")
                pilot_id = None  # Skip to next priority
            else:
                _debug_log(f"Using ARIA_PILOT env var: {pilot_id}")
                creds_file = creds_dir / f"{pilot_id}.json"
                # Try keyring first, then file
                creds = cls.from_keyring(pilot_id, creds_file)
                if creds:
                    _debug_log("Loaded from keyring (ARIA_PILOT)")
                    return creds
                if creds_file.exists():
                    _debug_log(f"Loaded from file (ARIA_PILOT): {creds_file}")
                    return cls.from_file(creds_file)

        # Priority 2: Config file active_pilot
        if config_file.exists():
            _debug_log(f"Reading config file: {config_file}")
            try:
                with open(config_file) as f:
                    config = json.load(f)
                pilot_id = config.get("active_pilot")
                if pilot_id:
                    # Security: Validate pilot_id format to prevent path traversal
                    is_valid, error = validate_pilot_id(pilot_id)
                    if not is_valid:
                        _debug_log(f"Invalid active_pilot in config rejected: {error}")
                        pilot_id = None  # Skip to next priority
                    else:
                        _debug_log(f"Using active_pilot from config: {pilot_id}")
                        creds_file = creds_dir / f"{pilot_id}.json"
                        # Try keyring first, then file
                        creds = cls.from_keyring(pilot_id, creds_file)
                        if creds:
                            _debug_log("Loaded from keyring (config)")
                            return creds
                        if creds_file.exists():
                            _debug_log(f"Loaded from file (config): {creds_file}")
                            return cls.from_file(creds_file)
            except json.JSONDecodeError as e:
                _debug_log(f"Config file JSON parse error: {config_file}: {e}")
            except OSError as e:
                _debug_log(f"Config file read error: {config_file}: {e}")

        # Priority 3: First credentials file in directory
        if creds_dir.exists():
            _debug_log(f"Scanning credentials directory: {creds_dir}")
            for creds_file in sorted(creds_dir.glob("*.json")):
                if creds_file.is_file():
                    # Extract pilot ID from filename
                    pilot_id = creds_file.stem
                    _debug_log(f"Found credentials file: {creds_file}")
                    # Try keyring first, then file
                    creds = cls.from_keyring(pilot_id, creds_file)
                    if creds:
                        _debug_log("Loaded from keyring (scan)")
                        return creds
                    _debug_log(f"Loaded from file (scan): {creds_file}")
                    return cls.from_file(creds_file)

        _debug_log("No credentials found")
        return None

    @staticmethod
    def _find_project_dir() -> Optional[Path]:
        """
        Auto-detect project directory.

        Looks for project markers starting from script location and walking up.
        Looks for userdata/ directory or pyproject.toml.

        Returns:
            Project directory Path, or None if not found
        """
        # Start from the script's location
        current = Path(__file__).resolve().parent

        # Walk up looking for project markers
        for _ in range(10):  # Max 10 levels up
            if (current / "userdata").is_dir():
                return current
            if (current / "pyproject.toml").exists():
                return current

            parent = current.parent
            if parent == current:
                break
            current = parent

        return None

    def has_scope(self, scope: str) -> bool:
        """
        Check if credentials include a specific scope.

        Args:
            scope: ESI scope string (e.g., "esi-wallet.read_corporation_wallets.v1")

        Returns:
            True if scope is authorized
        """
        return scope in self.scopes

    def has_any_corp_scope(self) -> bool:
        """
        Check if any corporation scopes are authorized.

        Returns:
            True if any corp scope is present
        """
        return any(self.has_scope(scope) for scope in CORP_SCOPES)

    def require_scope(self, scope: str) -> None:
        """
        Require a specific scope, raising error if missing.

        Args:
            scope: Required ESI scope

        Raises:
            CredentialsError: If scope is not authorized
        """
        if not self.has_scope(scope):
            raise CredentialsError(
                f"Missing required scope: {scope}",
                action="Re-run OAuth setup with additional scopes",
                command="python3 .claude/scripts/aria-oauth-setup.py",
            )

    def get_personal_scopes(self) -> list[str]:
        """Get list of personal (non-corporation) scopes."""
        return [s for s in self.scopes if "corporation" not in s]

    def get_corp_scopes(self) -> list[str]:
        """Get list of corporation scopes."""
        return [s for s in self.scopes if "corporation" in s]

    def refresh_if_needed(self, script_dir: Optional[Path] = None) -> bool:
        """
        Refresh access token if needed using aria-token-refresh.py.

        Args:
            script_dir: Directory containing aria-token-refresh.py

        Returns:
            True if refresh was attempted (may or may not have succeeded)
        """
        if script_dir is None:
            script_dir = Path(__file__).resolve().parent.parent

        refresh_script = script_dir / "aria-token-refresh.py"
        if not refresh_script.exists():
            return False

        if self.credentials_file is None:
            return False

        try:
            subprocess.run(
                ["python3", str(refresh_script), "--quiet"], capture_output=True, timeout=30
            )
            # Reload credentials after refresh
            new_creds = self.from_file(self.credentials_file)
            self.access_token = new_creds.access_token
            self.token_expiry = new_creds.token_expiry
            return True
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            return False


def get_credentials(
    project_dir: Optional[Path] = None, require: bool = True
) -> Optional[Credentials]:
    """
    Convenience function to get resolved credentials.

    Args:
        project_dir: Project root directory (defaults to auto-detect)
        require: If True, raise error when credentials not found

    Returns:
        Credentials instance

    Raises:
        CredentialsError: If require=True and no credentials found
    """
    creds = Credentials.resolve(project_dir)
    if creds is None and require:
        raise CredentialsError(
            "No credentials found",
            action="Run the OAuth setup wizard",
            command="python3 .claude/scripts/aria-oauth-setup.py",
        )
    return creds


def get_authenticated_client() -> tuple["ESIClient", Credentials]:
    """
    Get an authenticated ESI client with valid credentials.

    Convenience function that resolves credentials, refreshes the token
    if needed, and returns a ready-to-use client.

    Returns:
        Tuple of (ESIClient, Credentials)

    Raises:
        CredentialsError: If no credentials found
    """
    from .client import ESIClient  # Local import to avoid circular dependency

    creds = get_credentials(require=True)
    if creds is None:
        raise CredentialsError("No credentials found")
    creds.refresh_if_needed()
    client = ESIClient(token=creds.access_token)
    return client, creds


# Type alias for forward reference
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import ESIClient


def get_pilot_directory(project_dir: Optional[Path] = None) -> Optional[Path]:
    """
    Get the active pilot's data directory.

    Args:
        project_dir: Project root directory

    Returns:
        Path to pilot directory (e.g., userdata/pilots/12345_name/), or None
    """
    if project_dir is None:
        project_dir = Credentials._find_project_dir()

    if project_dir is None:
        return None

    # Get active pilot ID via centralized config
    from .config import get_settings

    pilot_id = get_settings().pilot

    # Security: Validate pilot_id from env var
    if pilot_id:
        is_valid, error = validate_pilot_id(pilot_id)
        if not is_valid:
            _debug_log(f"Invalid ARIA_PILOT in get_pilot_directory rejected: {error}")
            pilot_id = None

    if not pilot_id:
        # Check config file
        config_file = project_dir / "userdata" / "config.json"

        if config_file.exists():
            try:
                with open(config_file) as f:
                    config = json.load(f)
                pilot_id = config.get("active_pilot")
                # Security: Validate pilot_id from config
                if pilot_id:
                    is_valid, error = validate_pilot_id(pilot_id)
                    if not is_valid:
                        _debug_log(f"Invalid active_pilot in get_pilot_directory rejected: {error}")
                        pilot_id = None
            except json.JSONDecodeError as e:
                _debug_log(f"Config file JSON parse error: {config_file}: {e}")
            except OSError as e:
                _debug_log(f"Config file read error: {config_file}: {e}")

    if not pilot_id:
        return None

    # Find pilot directory
    pilots_dir = project_dir / "userdata" / "pilots"

    if pilots_dir.exists():
        for d in pilots_dir.iterdir():
            if d.is_dir() and d.name.startswith(pilot_id):
                return d

    return None


def is_player_corp(corporation_id: int) -> bool:
    """
    Check if a corporation ID is a player corporation.

    NPC corporations have IDs below PLAYER_CORP_MIN_ID.

    Args:
        corporation_id: Corporation ID

    Returns:
        True if player corp, False if NPC corp
    """
    return corporation_id >= PLAYER_CORP_MIN_ID


def migrate_credentials_to_keyring(
    project_dir: Optional[Path] = None, pilot_id: Optional[str] = None, delete_file: bool = False
) -> dict[str, Any]:
    """
    Migrate file-based credentials to system keyring.

    This function reads credentials from JSON files and stores them
    in the system keyring for enhanced security.

    Args:
        project_dir: Project root directory (auto-detected if None)
        pilot_id: Specific pilot ID to migrate (all if None)
        delete_file: If True, delete the file after successful migration

    Returns:
        Dict with migration results:
        - migrated: List of pilot IDs successfully migrated
        - skipped: List of pilot IDs already in keyring
        - failed: List of pilot IDs that failed
        - keyring_status: Keyring availability info
    """

    result: dict[str, Any] = {
        "migrated": [],
        "skipped": [],
        "failed": [],
        "keyring_status": get_keyring_status(),
    }

    if not is_keyring_enabled():
        result["error"] = "Keyring not available"
        return result

    if project_dir is None:
        project_dir = Credentials._find_project_dir()

    if project_dir is None:
        result["error"] = "Could not find project directory"
        return result

    creds_dir = project_dir / "userdata" / "credentials"

    if not creds_dir.exists():
        result["error"] = f"Credentials directory not found: {creds_dir}"
        return result

    # Determine which files to migrate
    if pilot_id:
        # Security: Validate pilot_id format to prevent path traversal
        is_valid, error = validate_pilot_id(pilot_id)
        if not is_valid:
            result["error"] = f"Invalid pilot_id: {error}"
            return result
        files_to_migrate = [creds_dir / f"{pilot_id}.json"]
    else:
        files_to_migrate = list(creds_dir.glob("*.json"))

    for creds_file in files_to_migrate:
        if not creds_file.exists():
            continue

        current_pilot_id = creds_file.stem

        # Check if already in keyring
        existing = load_from_keyring(current_pilot_id)
        if existing:
            result["skipped"].append(current_pilot_id)
            continue

        # Load from file and migrate
        try:
            with open(creds_file) as f:
                data = json.load(f)

            if store_in_keyring(current_pilot_id, data):
                result["migrated"].append(current_pilot_id)

                if delete_file:
                    creds_file.unlink()
            else:
                result["failed"].append(current_pilot_id)

        except (OSError, json.JSONDecodeError) as e:
            result["failed"].append(f"{current_pilot_id}: {e}")

    return result


def get_credential_storage_info(project_dir: Optional[Path] = None) -> dict[str, Any]:
    """
    Get information about credential storage status.

    Args:
        project_dir: Project root directory

    Returns:
        Dict with storage info for each pilot
    """
    from .keyring_backend import get_keyring_store

    if project_dir is None:
        project_dir = Credentials._find_project_dir()

    info: dict[str, Any] = {
        "keyring": get_keyring_status(),
        "pilots": [],
    }

    if project_dir is None:
        return info

    creds_dir = project_dir / "userdata" / "credentials"

    if not creds_dir.exists():
        return info

    store = get_keyring_store()

    for creds_file in sorted(creds_dir.glob("*.json")):
        pilot_id = creds_file.stem
        pilot_info = {
            "pilot_id": pilot_id,
            "file_exists": True,
            "in_keyring": store.has_credentials(pilot_id) if store.is_available() else False,
        }

        # Try to get character name from file
        try:
            with open(creds_file) as f:
                data = json.load(f)
                pilot_info["character_name"] = data.get("character_name", "Unknown")
        except (OSError, json.JSONDecodeError):
            pilot_info["character_name"] = "Unknown"

        info["pilots"].append(pilot_info)

    return info
