"""
ARIA Keyring Backend

Cross-platform credential storage using system keychains.

This module provides secure credential storage (Tier II security):
- macOS: Keychain
- Linux: Secret Service (GNOME Keyring / KWallet)
- Windows: Credential Manager

If no functional keyring backend is available (e.g., headless server
without D-Bus), ARIA falls back to file-based storage with 0600
permissions (Tier I security) with a warning.

Set ARIA_NO_KEYRING=1 to suppress security warnings on headless systems.
"""

import json
import os
import sys
import warnings
from typing import Optional, Union

# Service name for keyring storage
# All ARIA credentials are stored under this service
KEYRING_SERVICE = "aria-eve-online"

# Track if we've already warned about keyring unavailability
_KEYRING_WARNING_ISSUED = False

# Module-level type declarations for conditional assignments
KEYRING_AVAILABLE: bool
KEYRING_BACKEND: Optional[str]
KEYRING_REASON: Optional[str]

# Attempt to import keyring with graceful fallback
try:
    import keyring
    from keyring.errors import KeyringError

    # Test that keyring is functional (not just importable)
    # Some systems have keyring installed but no backend available
    _backend = keyring.get_keyring()
    _backend_name = _backend.__class__.__name__

    # Check for known non-functional backends
    if "fail" in _backend_name.lower() or "null" in _backend_name.lower():
        KEYRING_AVAILABLE = False
        KEYRING_BACKEND = None
        KEYRING_REASON = f"No functional keyring backend ({_backend_name})"
    else:
        KEYRING_AVAILABLE = True
        KEYRING_BACKEND = _backend_name
        KEYRING_REASON = None

except ImportError:
    KEYRING_AVAILABLE = False
    KEYRING_BACKEND = None
    KEYRING_REASON = "keyring package not installed (pip install aria[secure])"
    KeyringError = Exception  # type: ignore[assignment]  # Fallback for type hints

except Exception as e:
    KEYRING_AVAILABLE = False
    KEYRING_BACKEND = None
    KEYRING_REASON = f"Keyring initialization failed: {e}"
    KeyringError = Exception  # type: ignore[assignment]  # Fallback for type hints


def _warn_keyring_unavailable() -> None:
    """
    Issue a one-time warning when keyring is unavailable.

    This warning helps users understand they're falling back to
    less secure file-based storage and how to fix it.
    """
    global _KEYRING_WARNING_ISSUED

    # Only warn once per session
    if _KEYRING_WARNING_ISSUED:
        return

    # Don't warn if user has explicitly disabled keyring
    if os.environ.get("ARIA_NO_KEYRING", "").lower() in ("1", "true", "yes"):
        return

    _KEYRING_WARNING_ISSUED = True

    warnings.warn(
        f"SECURITY: Keyring backend unavailable ({KEYRING_REASON}). "
        "Credentials will be stored in plaintext JSON files with 0600 permissions. "
        "For enhanced security, install a system keyring backend "
        "(GNOME Keyring, KWallet, or SecretService on Linux). "
        "Set ARIA_NO_KEYRING=1 to suppress this warning.",
        UserWarning,
        stacklevel=3,
    )


def is_keyring_enabled() -> bool:
    """
    Check if keyring storage is available and enabled.

    Returns False if:
    - keyring package is not installed
    - No functional backend is available
    - ARIA_NO_KEYRING environment variable is set
    - Running in a headless/CI environment without D-Bus

    Returns:
        True if keyring can be used for credential storage
    """
    from .config import is_keyring_disabled

    if is_keyring_disabled():
        return False

    return KEYRING_AVAILABLE


def get_keyring_status() -> dict:
    """
    Get detailed status about keyring availability.

    Returns:
        Dict with keys:
        - available: bool - whether keyring can be used
        - backend: str - backend name (e.g., "Keychain", "SecretService")
        - reason: str - why keyring is unavailable (if applicable)
        - enabled: bool - whether keyring is enabled (respects ARIA_NO_KEYRING)
    """
    from .config import is_keyring_disabled

    return {
        "available": KEYRING_AVAILABLE,
        "backend": KEYRING_BACKEND,
        "reason": KEYRING_REASON,
        "enabled": is_keyring_enabled(),
        "env_disabled": is_keyring_disabled(),
    }


class KeyringCredentialStore:
    """
    Secure credential storage using system keyring.

    Stores the complete credential JSON as the password value,
    with the character_id as the username/key.

    This allows storing all credential fields (tokens, scopes, metadata)
    in a single keyring entry per character.
    """

    def __init__(self, service: str = KEYRING_SERVICE):
        """
        Initialize the keyring store.

        Args:
            service: The service name to use in keyring (default: aria-eve-online)
        """
        self.service = service

    def is_available(self) -> bool:
        """Check if keyring storage is available and enabled."""
        return is_keyring_enabled()

    def get_credentials(self, character_id: Union[str, int]) -> Optional[dict]:
        """
        Retrieve credentials from keyring.

        Args:
            character_id: The EVE character ID

        Returns:
            Credential dict if found, None otherwise
        """
        if not is_keyring_enabled():
            return None

        try:
            stored = keyring.get_password(self.service, str(character_id))
            if stored:
                data = json.loads(stored)
                # Ensure we got a dict (credentials should always be stored as JSON objects)
                if isinstance(data, dict):
                    return data
                return None
        except (json.JSONDecodeError, KeyringError):
            pass

        return None

    def set_credentials(self, character_id: Union[str, int], credentials: dict) -> bool:
        """
        Store credentials in keyring.

        Args:
            character_id: The EVE character ID
            credentials: The full credential dict to store

        Returns:
            True if stored successfully, False otherwise
        """
        if not is_keyring_enabled():
            return False

        try:
            # Serialize credentials to JSON
            creds_json = json.dumps(credentials, indent=None, separators=(",", ":"))
            keyring.set_password(self.service, str(character_id), creds_json)
            return True
        except KeyringError as e:
            # Log the error but don't crash - fall back to file storage
            print(f"WARNING: Failed to store credentials in keyring: {e}", file=sys.stderr)
            return False

    def delete_credentials(self, character_id: Union[str, int]) -> bool:
        """
        Delete credentials from keyring.

        Args:
            character_id: The EVE character ID

        Returns:
            True if deleted successfully (or not found), False on error
        """
        if not is_keyring_enabled():
            return False

        try:
            keyring.delete_password(self.service, str(character_id))
            return True
        except keyring.errors.PasswordDeleteError:
            # Password didn't exist - that's fine
            return True
        except KeyringError as e:
            print(f"WARNING: Failed to delete credentials from keyring: {e}", file=sys.stderr)
            return False

    def has_credentials(self, character_id: Union[str, int]) -> bool:
        """
        Check if credentials exist in keyring.

        Args:
            character_id: The EVE character ID

        Returns:
            True if credentials exist in keyring
        """
        return self.get_credentials(character_id) is not None


# Module-level singleton for convenience
_default_store: Optional[KeyringCredentialStore] = None


def get_keyring_store() -> KeyringCredentialStore:
    """
    Get the default keyring credential store.

    Returns:
        KeyringCredentialStore instance
    """
    global _default_store
    if _default_store is None:
        _default_store = KeyringCredentialStore()
    return _default_store


def reset_keyring_store() -> None:
    """Reset the keyring store singleton (for testing)."""
    global _default_store
    _default_store = None


def store_in_keyring(character_id: Union[str, int], credentials: dict) -> bool:
    """
    Convenience function to store credentials in keyring.

    Args:
        character_id: The EVE character ID
        credentials: The credential dict

    Returns:
        True if stored successfully
    """
    return get_keyring_store().set_credentials(character_id, credentials)


def load_from_keyring(character_id: Union[str, int]) -> Optional[dict]:
    """
    Convenience function to load credentials from keyring.

    Args:
        character_id: The EVE character ID

    Returns:
        Credential dict if found
    """
    return get_keyring_store().get_credentials(character_id)


def delete_from_keyring(character_id: Union[str, int]) -> bool:
    """
    Convenience function to delete credentials from keyring.

    Args:
        character_id: The EVE character ID

    Returns:
        True if deleted successfully
    """
    return get_keyring_store().delete_credentials(character_id)
