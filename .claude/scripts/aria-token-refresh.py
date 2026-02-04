#!/usr/bin/env python3
"""
ARIA Token Refresh Module
═══════════════════════════════════════════════════════════════════
Maintains GalNet authentication by refreshing EVE SSO tokens.

Usage:
    python aria-token-refresh.py              # Refresh if expired/expiring soon
    python aria-token-refresh.py --force      # Force refresh regardless of expiry
    python aria-token-refresh.py --check      # Just check status, don't refresh
    python aria-token-refresh.py --quiet      # Minimal output (for cron)
    python aria-token-refresh.py --hook       # Read hook JSON from stdin (Claude Code integration)

Exit codes:
    0 - Success (token valid or refreshed)
    1 - Error (refresh failed, credentials missing, etc.)
    2 - Token expired and refresh failed (blocking error for hooks)

No external dependencies - uses only Python standard library.
═══════════════════════════════════════════════════════════════════
"""

import argparse
import json
import os
import shutil
import stat
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Import keyring backend with graceful fallback
try:
    # When running from scripts directory, add to path
    sys.path.insert(0, str(Path(__file__).parent))
    from aria_esi.core.keyring_backend import (
        KEYRING_BACKEND,
        get_keyring_status,
        is_keyring_enabled,
        load_from_keyring,
        store_in_keyring,
    )

    KEYRING_IMPORT_OK = True
except ImportError:
    KEYRING_IMPORT_OK = False

    def is_keyring_enabled():
        return False

    def store_in_keyring(char_id, data):
        return False

    def load_from_keyring(char_id):
        return None

    def get_keyring_status():
        return {"available": False, "reason": "keyring_backend not found"}

    KEYRING_BACKEND = None

# Configuration
TOKEN_ENDPOINT = "https://login.eveonline.com/v2/oauth/token"
REFRESH_BUFFER_MINUTES = 5  # Refresh if expiring within this many minutes
CREDENTIALS_DIR = "userdata/credentials"
CONFIG_FILENAME = "userdata/config.json"


# ARIA-style output formatting
def aria_print(message: str, level: str = "info", quiet: bool = False):
    """Print messages in ARIA style."""
    if quiet and level == "info":
        return

    prefixes = {
        "info": "ARIA:",
        "warn": "ARIA WARNING:",
        "error": "ARIA ALERT:",
        "success": "ARIA:",
        "debug": "ARIA [DEBUG]:",
    }
    prefix = prefixes.get(level, "ARIA:")
    print(f"{prefix} {message}", file=sys.stderr if level == "error" else sys.stdout)


def get_project_root() -> Path:
    """Find the ARIA project root directory."""
    # Check environment variable first
    env_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_dir:
        return Path(env_dir)

    # Check relative to script location
    script_dir = Path(__file__).parent
    if script_dir.name == "scripts":
        project_root = script_dir.parent.parent  # .claude/scripts -> project root
        if (project_root / "CLAUDE.md").exists():
            return project_root

    # Check current directory
    cwd = Path.cwd()
    if (cwd / "CLAUDE.md").exists():
        return cwd

    # Default to script-relative path
    return Path(__file__).parent.parent.parent


def get_active_pilot_id(project_root: Path) -> str:
    """Get the active pilot ID from environment or config."""
    # Priority 1: Environment variable
    pilot_id = os.environ.get("ARIA_PILOT")
    if pilot_id:
        return pilot_id

    # Priority 2: Config file
    config_path = project_root / CONFIG_FILENAME
    if config_path.exists():
        try:
            with open(config_path) as f:
                config = json.load(f)
            pilot_id = config.get("active_pilot")
            if pilot_id:
                return str(pilot_id)
        except (OSError, json.JSONDecodeError):
            pass

    # Priority 3: First credential file in directory
    creds_dir = project_root / CREDENTIALS_DIR
    if creds_dir.exists():
        cred_files = list(creds_dir.glob("*.json"))
        if cred_files:
            # Extract pilot ID from filename (e.g., "1234567890.json")
            return cred_files[0].stem

    return ""


def find_credentials_file(pilot_id: str = None) -> Path:
    """
    Locate the credentials file (V2 structure).

    Args:
        pilot_id: Optional specific pilot ID

    Returns:
        Path to credentials file, or None if not found
    """
    project_root = get_project_root()
    creds_dir = project_root / CREDENTIALS_DIR

    if pilot_id:
        # Specific pilot requested
        creds_path = creds_dir / f"{pilot_id}.json"
        if creds_path.exists():
            return creds_path.resolve()
    else:
        # Use active pilot
        active_id = get_active_pilot_id(project_root)
        if active_id:
            creds_path = creds_dir / f"{active_id}.json"
            if creds_path.exists():
                return creds_path.resolve()

        # Fallback to first credential file
        cred_files = list(creds_dir.glob("*.json"))
        if cred_files:
            return cred_files[0].resolve()

    return None


def load_credentials(creds_path: Path, use_keyring: bool = True) -> tuple[dict, str]:
    """
    Load credentials with keyring priority, falling back to file.

    Args:
        creds_path: Path to the credentials file
        use_keyring: If True, try keyring first

    Returns:
        Tuple of (credentials dict, source string "keyring" or "file")

    Raises:
        ValueError: If credentials cannot be loaded or are invalid
    """
    pilot_id = creds_path.stem  # Extract pilot ID from filename

    # Try keyring first if enabled
    if use_keyring and is_keyring_enabled():
        keyring_creds = load_from_keyring(pilot_id)
        if keyring_creds:
            # Validate keyring credentials have required fields
            required = ["client_id", "refresh_token"]
            missing = [f for f in required if not keyring_creds.get(f)]
            if not missing:
                return keyring_creds, "keyring"
            # If keyring data is incomplete, fall through to file

    # Fall back to file
    try:
        with open(creds_path) as f:
            creds = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in credentials file: {e}")
    except OSError as e:
        raise ValueError(f"Cannot read credentials file: {e}")

    # Validate required fields
    required = ["client_id", "refresh_token"]
    missing = [f for f in required if not creds.get(f) or creds.get(f, "").startswith("YOUR_")]

    if missing:
        raise ValueError(f"Missing or unconfigured fields: {', '.join(missing)}")

    return creds, "file"


def parse_token_expiry(creds: dict) -> datetime:
    """Parse the token expiry timestamp."""
    expiry_str = creds.get("token_expiry", "")

    if not expiry_str:
        # No expiry set, assume expired
        return datetime.now(timezone.utc) - timedelta(hours=1)

    # Handle various ISO 8601 formats
    formats = [
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(expiry_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue

    # If we can't parse, assume expired
    return datetime.now(timezone.utc) - timedelta(hours=1)


def is_token_valid(
    creds: dict, buffer_minutes: int = REFRESH_BUFFER_MINUTES
) -> tuple[bool, datetime, timedelta]:
    """
    Check if the token is still valid.

    Returns:
        (is_valid, expiry_time, time_remaining)
    """
    expiry = parse_token_expiry(creds)
    now = datetime.now(timezone.utc)
    remaining = expiry - now
    buffer = timedelta(minutes=buffer_minutes)

    is_valid = remaining > buffer
    return is_valid, expiry, remaining


def refresh_token(creds: dict) -> dict:
    """
    Refresh the access token using the refresh token.

    Returns:
        Dict with new token data from EVE SSO
    """
    # Build the refresh request
    data = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "refresh_token": creds["refresh_token"],
            "client_id": creds["client_id"],
        }
    ).encode("utf-8")

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "User-Agent": "ARIA-TokenRefresh/1.0 (Claude Code Integration)",
    }

    # If client_secret is present (confidential app), include it
    if creds.get("client_secret"):
        import base64

        auth_string = f"{creds['client_id']}:{creds['client_secret']}"
        auth_bytes = base64.b64encode(auth_string.encode("utf-8")).decode("utf-8")
        headers["Authorization"] = f"Basic {auth_bytes}"

    request = urllib.request.Request(TOKEN_ENDPOINT, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else "No details"
        raise RuntimeError(f"Token refresh failed (HTTP {e.code}): {error_body}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error during token refresh: {e.reason}")
    except json.JSONDecodeError:
        raise RuntimeError("Invalid JSON response from EVE SSO")

    return response_data


def save_credentials(creds_path: Path, creds: dict, use_keyring: bool = True):
    """
    Save credentials with keyring priority, always updating file.

    Args:
        creds_path: Path to the credentials file
        creds: Credentials dict to save
        use_keyring: If True, also save to keyring
    """
    pilot_id = creds_path.stem  # Extract pilot ID from filename

    # Try to save to keyring first
    if use_keyring and is_keyring_enabled():
        store_in_keyring(pilot_id, creds)

    # Always save to file as well (atomic write)
    temp_path = creds_path.with_suffix(".json.tmp")

    try:
        with open(temp_path, "w") as f:
            json.dump(creds, f, indent=2)

        # Set secure permissions (owner read/write only) before moving
        # This prevents race conditions where file is briefly world-readable
        os.chmod(temp_path, stat.S_IRUSR | stat.S_IWUSR)  # 0o600

        # Atomic rename
        shutil.move(str(temp_path), str(creds_path))
    except OSError as e:
        # Clean up temp file if it exists
        if temp_path.exists():
            temp_path.unlink()
        raise RuntimeError(f"Failed to save credentials: {e}")


def update_credentials_with_new_tokens(creds: dict, token_response: dict) -> dict:
    """Merge new token data into existing credentials."""
    now = datetime.now(timezone.utc)

    # Calculate expiry time
    expires_in = token_response.get("expires_in", 1199)  # Default ~20 minutes
    expiry = now + timedelta(seconds=expires_in)

    # Update credentials
    creds["access_token"] = token_response["access_token"]
    creds["token_expiry"] = expiry.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Refresh token may be rotated
    if "refresh_token" in token_response:
        creds["refresh_token"] = token_response["refresh_token"]

    # Store last refresh time for debugging
    creds["_last_refresh"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    return creds


def format_timedelta(td: timedelta) -> str:
    """Format a timedelta for human reading."""
    total_seconds = int(td.total_seconds())

    if total_seconds < 0:
        return "EXPIRED"

    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"


def print_status_report(
    creds: dict, is_valid: bool, expiry: datetime, remaining: timedelta, quiet: bool = False
):
    """Print ARIA-style status report."""
    if quiet:
        return

    char_name = creds.get("character_name", "Unknown")

    print("═══════════════════════════════════════════════════════════════════")
    print("ARIA GALNET AUTHENTICATION STATUS")
    print("───────────────────────────────────────────────────────────────────")
    print(f"Capsuleer:      {char_name}")
    print(f"Token Status:   {'VALID' if is_valid else 'EXPIRED/EXPIRING'}")
    print(f"Expires:        {expiry.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Time Remaining: {format_timedelta(remaining)}")
    print("═══════════════════════════════════════════════════════════════════")


def handle_hook_mode():
    """
    Handle execution as a Claude Code hook.
    Reads hook JSON from stdin, performs refresh if needed.
    """
    try:
        json.load(sys.stdin)
    except json.JSONDecodeError:
        # Not valid hook input, but that's okay
        pass

    # We're being called as a hook - be quiet and just ensure token is valid
    return main_logic(force=False, check_only=False, quiet=True)


def main_logic(
    force: bool = False, check_only: bool = False, quiet: bool = False, use_keyring: bool = True
) -> int:
    """
    Main token refresh logic.

    Args:
        force: Force refresh even if token is valid
        check_only: Only check status, don't refresh
        quiet: Minimal output
        use_keyring: Use keyring for storage (default True)

    Returns:
        Exit code (0 = success, 1 = error, 2 = blocking error)
    """
    # Find credentials file
    creds_path = find_credentials_file()

    if creds_path is None:
        aria_print(
            f"Credentials file not found. Expected: {CREDENTIALS_DIR}/<character_id>.json",
            "error",
            quiet,
        )
        aria_print(
            "Run the OAuth setup wizard: uv run aria-esi auth", "info", quiet
        )
        return 1

    aria_print(f"Credentials located: {creds_path}", "debug" if quiet else "info", quiet)

    # Load credentials (try keyring first, fall back to file)
    try:
        creds, creds_source = load_credentials(creds_path, use_keyring=use_keyring)
        if not quiet:
            aria_print(f"Credentials loaded from: {creds_source}", "info", quiet)
    except ValueError as e:
        aria_print(str(e), "error", quiet)
        return 1

    # Check token validity
    is_valid, expiry, remaining = is_token_valid(creds)

    # Print status if not quiet
    if not quiet:
        print_status_report(creds, is_valid, expiry, remaining, quiet)

    # Check-only mode
    if check_only:
        if is_valid:
            aria_print(f"Token valid for {format_timedelta(remaining)}", "success", quiet)
            return 0
        else:
            aria_print("Token expired or expiring soon", "warn", quiet)
            return 1

    # Determine if refresh is needed
    needs_refresh = force or not is_valid

    if not needs_refresh:
        aria_print(
            f"Token valid. No refresh needed. Expires in {format_timedelta(remaining)}",
            "success",
            quiet,
        )
        return 0

    # Perform refresh
    if force:
        aria_print("Force refresh requested. Initiating GalNet re-authentication...", "info", quiet)
    else:
        aria_print(
            "Token expired or expiring. Initiating GalNet re-authentication...", "info", quiet
        )

    try:
        token_response = refresh_token(creds)
    except RuntimeError as e:
        aria_print(f"Token refresh failed: {e}", "error", quiet)
        aria_print("Manual re-authorization may be required via EVE SSO.", "warn", quiet)
        return 2  # Blocking error for hooks

    # Update and save credentials
    updated_creds = update_credentials_with_new_tokens(creds, token_response)

    try:
        save_credentials(creds_path, updated_creds, use_keyring=use_keyring)
    except RuntimeError as e:
        aria_print(str(e), "error", quiet)
        return 1

    # Report success
    _, new_expiry, new_remaining = is_token_valid(updated_creds)
    aria_print(
        f"GalNet authentication refreshed. Valid for {format_timedelta(new_remaining)}",
        "success",
        quiet,
    )

    if not quiet:
        print("───────────────────────────────────────────────────────────────────")
        print(f"New expiry: {new_expiry.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print("Credentials file updated.")
        print("═══════════════════════════════════════════════════════════════════")

    return 0


def main():
    """Entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description="ARIA Token Refresh Module - Maintain EVE SSO authentication",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    Check and refresh if needed
  %(prog)s --force            Force refresh even if token is valid
  %(prog)s --check            Just check status, don't refresh
  %(prog)s --quiet            Minimal output (for cron jobs)
  %(prog)s --hook             Claude Code hook mode (reads stdin)

Exit codes:
  0 - Success
  1 - Error (missing credentials, config issues)
  2 - Blocking error (token refresh failed, needs manual intervention)
        """,
    )

    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force token refresh even if current token is valid",
    )

    parser.add_argument(
        "--check", "-c", action="store_true", help="Only check token status, don't refresh"
    )

    parser.add_argument(
        "--quiet", "-q", action="store_true", help="Minimal output (suitable for cron)"
    )

    parser.add_argument(
        "--hook", action="store_true", help="Run in Claude Code hook mode (reads JSON from stdin)"
    )

    parser.add_argument(
        "--no-keyring", action="store_true", help="Disable keyring storage, use file storage only"
    )

    args = parser.parse_args()

    # Respect ARIA_NO_KEYRING environment variable
    use_keyring = not args.no_keyring and os.environ.get("ARIA_NO_KEYRING", "").lower() not in (
        "1",
        "true",
        "yes",
    )

    # Hook mode
    if args.hook:
        sys.exit(handle_hook_mode())

    # Normal mode
    sys.exit(
        main_logic(
            force=args.force, check_only=args.check, quiet=args.quiet, use_keyring=use_keyring
        )
    )


if __name__ == "__main__":
    main()
