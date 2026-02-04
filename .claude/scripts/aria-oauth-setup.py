#!/usr/bin/env python3
"""
ARIA OAuth Setup Wizard
═══════════════════════════════════════════════════════════════════
Interactive setup for EVE Online ESI authentication.

This script:
1. Starts a local HTTP server to receive the OAuth callback
2. Opens your browser to EVE's authorization page
3. Automatically captures the authorization code
4. Exchanges it for access/refresh tokens
5. Saves credentials to credentials/{character_id}.json (V2 multi-pilot structure)

Usage:
    python aria-oauth-setup.py           # Automatic mode (recommended)
    python aria-oauth-setup.py --manual  # Manual copy-paste mode

No external dependencies - uses only Python standard library.
═══════════════════════════════════════════════════════════════════
"""

import argparse
import base64
import hashlib
import json
import os
import secrets
import socket
import stat
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# Import keyring backend with graceful fallback
# Note: aria_esi is available when run via `uv run` (recommended)
# Falls back gracefully to file-based storage if import fails
try:
    from aria_esi.core.keyring_backend import (
        KEYRING_BACKEND,
        get_keyring_status,
        is_keyring_enabled,
        store_in_keyring,
    )

    KEYRING_IMPORT_OK = True
except ImportError:
    KEYRING_IMPORT_OK = False

    def is_keyring_enabled():
        return False

    def store_in_keyring(char_id, data):
        return False

    def get_keyring_status():
        return {"available": False, "reason": "keyring_backend not found"}

    KEYRING_BACKEND = None

# EVE SSO endpoints
AUTH_URL = "https://login.eveonline.com/v2/oauth/authorize"
TOKEN_URL = "https://login.eveonline.com/v2/oauth/token"
VERIFY_URL = "https://esi.evetech.net/verify/"

# Server configuration
DEFAULT_PORT = 8421  # ARIA's port (A=4, R=18, I=9, A=1 -> 8421)
CALLBACK_TIMEOUT = 300  # 5 minutes to complete authorization

# Default scopes for ARIA (can be customized)
DEFAULT_SCOPES = [
    "esi-location.read_location.v1",
    "esi-location.read_ship_type.v1",
    "esi-skills.read_skills.v1",
    "esi-skills.read_skillqueue.v1",
    "esi-characters.read_standings.v1",
    "esi-characters.read_blueprints.v1",
    "esi-characters.read_loyalty.v1",
    "esi-clones.read_clones.v1",
    "esi-clones.read_implants.v1",
    "esi-killmails.read_killmails.v1",
    "esi-contracts.read_character_contracts.v1",
    "esi-characters.read_agents_research.v1",
    "esi-markets.read_character_orders.v1",
    "esi-fittings.read_fittings.v1",
    "esi-mail.read_mail.v1",
    "esi-wallet.read_character_wallet.v1",
    "esi-assets.read_assets.v1",
    "esi-industry.read_character_mining.v1",
    "esi-industry.read_character_jobs.v1",
]

# Scope descriptions for user selection
SCOPE_INFO = {
    "esi-location.read_location.v1": "Current solar system location",
    "esi-location.read_ship_type.v1": "Current ship type",
    "esi-location.read_online.v1": "Online/offline status",
    "esi-skills.read_skills.v1": "Skill points and trained skills",
    "esi-skills.read_skillqueue.v1": "Skill training queue",
    "esi-characters.read_standings.v1": "Faction/corp standings",
    "esi-characters.read_blueprints.v1": "Owned blueprints (BPOs/BPCs)",
    "esi-characters.read_loyalty.v1": "Loyalty Points balances",
    "esi-clones.read_clones.v1": "Clone locations and jump clones",
    "esi-clones.read_implants.v1": "Active implants",
    "esi-killmails.read_killmails.v1": "Kill and loss history",
    "esi-contracts.read_character_contracts.v1": "Personal contracts (item exchange, courier, auction)",
    "esi-characters.read_agents_research.v1": "Research agent partnerships and RP",
    "esi-markets.read_character_orders.v1": "Market buy/sell orders",
    "esi-fittings.read_fittings.v1": "Saved ship fittings",
    "esi-wallet.read_character_wallet.v1": "ISK balance",
    "esi-assets.read_assets.v1": "Items and assets",
    "esi-industry.read_character_mining.v1": "Mining ledger",
    "esi-industry.read_character_jobs.v1": "Industry jobs",
    "esi-characters.read_contacts.v1": "Contact list",
    "esi-mail.read_mail.v1": "EVE mail",
}

# Corporation scopes (CEO/Director only)
CORP_SCOPES = [
    "esi-wallet.read_corporation_wallets.v1",
    "esi-assets.read_corporation_assets.v1",
    "esi-corporations.read_blueprints.v1",
    "esi-industry.read_corporation_jobs.v1",
    "esi-corporations.read_standings.v1",
    "esi-corporations.read_divisions.v1",
]

CORP_SCOPE_INFO = {
    "esi-wallet.read_corporation_wallets.v1": "Corp wallet and journal",
    "esi-assets.read_corporation_assets.v1": "Corp hangar inventory",
    "esi-corporations.read_blueprints.v1": "Corp blueprint library",
    "esi-industry.read_corporation_jobs.v1": "Corp manufacturing/research",
    "esi-corporations.read_standings.v1": "Corp faction standings",
    "esi-corporations.read_divisions.v1": "Corp division names",
}

# Global to store the authorization result
auth_result = {"code": None, "state": None, "error": None}
server_ready = threading.Event()
callback_received = threading.Event()


# HTML Templates
SUCCESS_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>ARIA - Authorization Complete</title>
    <style>
        body {
            background: #0a0a12;
            color: #00ff9d;
            font-family: 'Courier New', monospace;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
        }
        .container {
            text-align: center;
            border: 2px solid #00ff9d;
            padding: 40px;
            max-width: 600px;
            background: rgba(0, 255, 157, 0.05);
        }
        h1 {
            color: #00ff9d;
            text-shadow: 0 0 10px #00ff9d;
            margin-bottom: 10px;
        }
        .subtitle {
            color: #888;
            margin-bottom: 30px;
        }
        .status {
            font-size: 1.2em;
            margin: 20px 0;
        }
        .checkmark {
            font-size: 3em;
            margin: 20px 0;
        }
        .instruction {
            color: #aaa;
            margin-top: 30px;
            font-size: 0.9em;
        }
        .divider {
            border-top: 1px solid #333;
            margin: 20px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="checkmark">✓</div>
        <h1>ARIA</h1>
        <div class="subtitle">Adaptive Reasoning & Intelligence Array</div>
        <div class="divider"></div>
        <div class="status">GalNet Authentication Successful</div>
        <p>Authorization code received and verified.</p>
        <p>Capsuleer identity confirmed: <strong>{character}</strong></p>
        <div class="divider"></div>
        <p class="instruction">You may close this browser tab.<br>Return to your terminal to complete setup.</p>
    </div>
</body>
</html>"""

ERROR_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>ARIA - Authorization Failed</title>
    <style>
        body {
            background: #0a0a12;
            color: #ff4444;
            font-family: 'Courier New', monospace;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
        }
        .container {
            text-align: center;
            border: 2px solid #ff4444;
            padding: 40px;
            max-width: 600px;
            background: rgba(255, 68, 68, 0.05);
        }
        h1 { color: #ff4444; }
        .error { margin: 20px 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>ARIA - Authorization Failed</h1>
        <div class="error">{error}</div>
        <p>Please close this tab and try again.</p>
    </div>
</body>
</html>"""


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler for OAuth callback."""

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass

    def do_GET(self):
        """Handle GET request (OAuth callback)."""
        global auth_result

        # Parse the callback URL
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path != "/callback":
            self.send_error(404, "Not Found")
            return

        params = urllib.parse.parse_qs(parsed.query)

        # Check for errors
        if "error" in params:
            error_msg = params.get("error_description", params["error"])[0]
            auth_result["error"] = error_msg
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(ERROR_HTML.format(error=error_msg).encode())
            callback_received.set()
            return

        # Extract code and state
        if "code" not in params:
            auth_result["error"] = "No authorization code received"
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(ERROR_HTML.format(error="No authorization code in callback").encode())
            callback_received.set()
            return

        auth_result["code"] = params["code"][0]
        auth_result["state"] = params.get("state", [None])[0]

        # Send success response (character name will be filled later, show placeholder)
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

        # Simple success page - we don't have character name yet
        success_html = SUCCESS_HTML.replace("{character}", "Verifying...")
        self.wfile.write(success_html.encode())

        callback_received.set()


def find_available_port(start_port: int = DEFAULT_PORT) -> int:
    """Find an available port starting from start_port."""
    for port in range(start_port, start_port + 100):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("localhost", port))
                return port
        except OSError:
            continue
    raise RuntimeError("Could not find an available port")


def run_callback_server(port: int):
    """Run the OAuth callback server."""
    server = HTTPServer(("localhost", port), OAuthCallbackHandler)
    server.timeout = 1  # Check for shutdown every second

    server_ready.set()

    while not callback_received.is_set():
        server.handle_request()

    # Give the response time to be sent
    time.sleep(0.5)
    server.server_close()


def print_header(text: str):
    """Print a formatted header."""
    print()
    print("═" * 70)
    print(f"  {text}")
    print("═" * 70)


def print_section(text: str):
    """Print a section divider."""
    print()
    print("─" * 70)
    print(f"  {text}")
    print("─" * 70)


def print_aria(message: str):
    """Print in ARIA style."""
    print(f"\nARIA: {message}")


def get_project_root() -> Path:
    """Find the project root directory."""
    if os.environ.get("CLAUDE_PROJECT_DIR"):
        return Path(os.environ["CLAUDE_PROJECT_DIR"])
    script_path = Path(__file__).resolve()
    return script_path.parent.parent.parent


def update_pilot_registry(project_root: Path, character_id: int, character_name: str):
    """Update the pilot registry with new character info."""
    # V2 structure: userdata/pilots/_registry.json
    registry_path = project_root / "userdata" / "pilots" / "_registry.json"

    # Load existing registry or create new
    if registry_path.exists():
        try:
            with open(registry_path) as f:
                registry = json.load(f)
        except (OSError, json.JSONDecodeError):
            registry = {"schema_version": "1.0", "pilots": []}
    else:
        registry = {"schema_version": "1.0", "pilots": []}

    # Check if pilot already exists
    existing = next(
        (p for p in registry.get("pilots", []) if str(p.get("character_id")) == str(character_id)),
        None,
    )

    if existing:
        # Update existing entry
        existing["character_name"] = character_name
        existing["last_active"] = datetime.now(timezone.utc).isoformat()
    else:
        # Generate slug from character name
        slug = character_name.lower().replace(" ", "_")
        slug = "".join(c for c in slug if c.isalnum() or c == "_")[:32]

        # Add new pilot entry
        registry.setdefault("pilots", []).append(
            {
                "character_id": str(character_id),
                "character_name": character_name,
                "directory": f"{character_id}_{slug}",
                "faction": "Unknown",  # Will be set during profile setup
                "account_tag": "main",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "last_active": datetime.now(timezone.utc).isoformat(),
            }
        )

    # Save registry
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    with open(registry_path, "w") as f:
        json.dump(registry, f, indent=2)


def update_config(project_root: Path, character_id: int):
    """Update the config to set active pilot if not already set."""
    # V2 structure: userdata/config.json
    config_path = project_root / "userdata" / "config.json"

    if config_path.exists():
        try:
            with open(config_path) as f:
                config = json.load(f)
        except (OSError, json.JSONDecodeError):
            config = {}
    else:
        config = {}

    # Only set active_pilot if not already configured
    if not config.get("active_pilot"):
        config["active_pilot"] = str(character_id)

    # Ensure version is set
    config["version"] = config.get("version", "2.0")
    config.setdefault(
        "settings",
        {"boot_greeting": True, "auto_refresh_tokens": True, "token_refresh_buffer_minutes": 10},
    )

    # Ensure parent directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)


def generate_pkce_pair() -> tuple[str, str]:
    """Generate PKCE code verifier and challenge."""
    code_verifier = secrets.token_urlsafe(32)
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return code_verifier, code_challenge


def save_credentials_secure(creds_path: Path, credentials: dict, use_keyring: bool = True):
    """
    Save credentials with keyring priority, falling back to file.

    Security Model (Two-Tier):
        Tier II: keyring available → System keychain (best)
        Tier I:  Default → Plaintext JSON with 0600 permissions

    Args:
        creds_path: Path to save credentials file (always saved as backup)
        credentials: Credential dict to save
        use_keyring: If True, try keyring first (default True)
    """
    character_id = credentials.get("character_id")
    keyring_saved = False

    # Tier II: Try keyring first
    if use_keyring and is_keyring_enabled() and character_id:
        keyring_saved = store_in_keyring(character_id, credentials)
        if keyring_saved:
            print_aria(f"✓ Credentials stored securely in system keyring (Tier II: {KEYRING_BACKEND})")

    # Tier I: Always save to file as backup/fallback
    with open(creds_path, "w") as f:
        json.dump(credentials, f, indent=2)

    # Set secure permissions: owner read/write only (0600)
    os.chmod(creds_path, stat.S_IRUSR | stat.S_IWUSR)

    if not keyring_saved:
        print_aria("⚠ Credentials stored in plaintext file (Tier I: 0600 permissions)")
        keyring_status = get_keyring_status()
        if keyring_status.get("reason"):
            print(f"      Keyring unavailable: {keyring_status['reason']}")
        print("      For enhanced security, install a system keyring backend.")
        print("      Run: uv run aria-esi migrate-keyring --info")


def build_auth_url(
    client_id: str, scopes: list[str], state: str, code_challenge: str, callback_url: str
) -> str:
    """Build the OAuth authorization URL."""
    params = {
        "response_type": "code",
        "redirect_uri": callback_url,
        "client_id": client_id,
        "scope": " ".join(scopes),
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{AUTH_URL}?{urllib.parse.urlencode(params)}"


def exchange_code_for_tokens(
    client_id: str, code: str, code_verifier: str, callback_url: str
) -> dict:
    """Exchange authorization code for access and refresh tokens."""
    data = urllib.parse.urlencode(
        {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "code_verifier": code_verifier,
            "redirect_uri": callback_url,
        }
    ).encode("utf-8")

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "User-Agent": "ARIA-OAuthSetup/1.0",
    }

    request = urllib.request.Request(TOKEN_URL, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else "No details"
        raise RuntimeError(f"Token exchange failed (HTTP {e.code}): {error_body}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error: {e.reason}")


def verify_token(access_token: str) -> dict:
    """Verify the access token and get character info."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "User-Agent": "ARIA-OAuthSetup/1.0",
    }

    request = urllib.request.Request(VERIFY_URL, headers=headers, method="GET")

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else "No details"
        raise RuntimeError(f"Token verification failed (HTTP {e.code}): {error_body}")


def extract_code_from_callback(callback_input: str) -> str:
    """Extract the authorization code from callback URL or direct input."""
    if not callback_input.startswith("http"):
        return callback_input.strip()

    parsed = urllib.parse.urlparse(callback_input)
    params = urllib.parse.parse_qs(parsed.query)

    if "code" in params:
        return params["code"][0]

    raise ValueError("Could not find 'code' parameter in the URL")


def select_scopes() -> list[str]:
    """Interactive scope selection."""
    print_section("SCOPE SELECTION")
    print("\nAvailable scopes (ARIA recommends all marked with ✓):\n")

    all_scopes = list(SCOPE_INFO.keys())

    for i, scope in enumerate(all_scopes, 1):
        short_name = scope.split(".")[-2]
        desc = SCOPE_INFO[scope]
        default = "✓" if scope in DEFAULT_SCOPES else " "
        print(f"  [{default}] {i:2}. {short_name:<25} - {desc}")

    print("\nOptions:")
    print("  [Enter]     Use recommended scopes (marked with ✓)")
    print("  [A]         Select all scopes")
    print("  [1,3,5]     Select specific scopes by number")

    choice = input("\nYour choice: ").strip().lower()

    if not choice:
        return DEFAULT_SCOPES
    elif choice == "a":
        return all_scopes
    else:
        try:
            indices = [int(x.strip()) for x in choice.split(",")]
            return [all_scopes[i - 1] for i in indices if 1 <= i <= len(all_scopes)]
        except (ValueError, IndexError):
            print("Invalid selection, using defaults")
            return DEFAULT_SCOPES


def get_character_corporation(access_token: str, character_id: int) -> dict:
    """Get corporation info for a character."""
    # Get character's corporation ID
    char_url = f"https://esi.evetech.net/latest/characters/{character_id}/?datasource=tranquility"
    try:
        with urllib.request.urlopen(char_url, timeout=30) as resp:
            char_info = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None

    corp_id = char_info.get("corporation_id")
    if not corp_id:
        return None

    # Get corporation details
    corp_url = f"https://esi.evetech.net/latest/corporations/{corp_id}/?datasource=tranquility"
    try:
        with urllib.request.urlopen(corp_url, timeout=30) as resp:
            corp_info = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None

    return {
        "corporation_id": corp_id,
        "corporation_name": corp_info.get("name", "Unknown"),
        "ticker": corp_info.get("ticker", ""),
        "member_count": corp_info.get("member_count", 0),
        "ceo_id": corp_info.get("ceo_id"),
        "is_player_corp": corp_id >= 2000000,  # NPC corps have lower IDs
    }


def select_corp_scopes(corp_info: dict, character_id: int) -> list[str]:
    """Offer corporation scope selection if in a player corp."""
    if not corp_info or not corp_info.get("is_player_corp"):
        print_section("CORPORATION SCOPES")
        print("""
You are currently in an NPC corporation.

Corporation management features require membership in a player corporation.
Skipping corporation scope selection.
""")
        return []

    is_ceo = corp_info.get("ceo_id") == character_id

    print_section("CORPORATION SCOPES (Optional)")
    print(f"""
Player corporation detected: {corp_info["corporation_name"]} [{corp_info["ticker"]}]
{"You are the CEO of this corporation." if is_ceo else "You are a member of this corporation."}

If you are CEO or Director, you can authorize corporation data access.
This enables /corp commands for wallet, assets, blueprints, and industry jobs.

NOTE: These scopes only work if you have the required corp roles.
      Regular members should skip this section.
""")

    print("Corporation scopes available:\n")
    for i, scope in enumerate(CORP_SCOPES, 1):
        short_name = scope.split(".")[-2]
        desc = CORP_SCOPE_INFO.get(scope, "")
        print(f"  {i:2}. {short_name:<30} - {desc}")

    print("\nOptions:")
    print("  [Enter]     Skip (don't add corp scopes)")
    print("  [Y]         Add all corporation scopes")
    print("  [1,3,5]     Select specific scopes by number")

    choice = input("\nAdd corporation scopes? ").strip().lower()

    if not choice:
        print_aria("Skipping corporation scopes.")
        return []
    elif choice in ("y", "yes", "a", "all"):
        print_aria("Adding all corporation scopes.")
        return CORP_SCOPES.copy()
    else:
        try:
            indices = [int(x.strip()) for x in choice.split(",")]
            selected = [CORP_SCOPES[i - 1] for i in indices if 1 <= i <= len(CORP_SCOPES)]
            print_aria(f"Adding {len(selected)} corporation scope(s).")
            return selected
        except (ValueError, IndexError):
            print("Invalid selection, skipping corp scopes")
            return []


def ask_corp_scopes() -> list[str]:
    """Ask user about corporation scopes before OAuth flow."""
    print_section("CORPORATION SCOPES (Optional)")
    print("""
If you are CEO or Director of a player corporation, you can also
authorize corporation data access. This enables the /corp command
for wallet, assets, blueprints, and industry job management.

NOTE: These scopes only work if you have the required corp roles.
      NPC corporation members or regular corp members should skip this.
      You can always re-run this wizard later to add corp scopes.
""")

    print("Corporation scopes available:\n")
    for i, scope in enumerate(CORP_SCOPES, 1):
        short_name = scope.split(".")[-2]
        desc = CORP_SCOPE_INFO.get(scope, "")
        print(f"  {i:2}. {short_name:<30} - {desc}")

    print("\nOptions:")
    print("  [Enter]     Skip (don't add corp scopes)")
    print("  [Y]         Add all corporation scopes")
    print("  [1,3,5]     Select specific scopes by number")

    choice = input("\nAdd corporation scopes? ").strip().lower()

    if not choice:
        print_aria("Skipping corporation scopes.")
        return []
    elif choice in ("y", "yes", "a", "all"):
        print_aria("Adding all corporation scopes.")
        return CORP_SCOPES.copy()
    else:
        try:
            indices = [int(x.strip()) for x in choice.split(",")]
            selected = [CORP_SCOPES[i - 1] for i in indices if 1 <= i <= len(CORP_SCOPES)]
            if selected:
                print_aria(f"Adding {len(selected)} corporation scope(s).")
            return selected
        except (ValueError, IndexError):
            print("Invalid selection, skipping corp scopes")
            return []


def run_automatic_flow(client_id: str, scopes: list[str]) -> dict:
    """Run the OAuth flow with automatic callback handling."""
    global auth_result
    auth_result = {"code": None, "state": None, "error": None}
    callback_received.clear()
    server_ready.clear()

    # Find an available port
    try:
        port = find_available_port()
    except RuntimeError as e:
        raise RuntimeError(f"Could not start callback server: {e}")

    callback_url = f"http://localhost:{port}/callback"

    # Generate PKCE and state
    state = secrets.token_urlsafe(16)
    code_verifier, code_challenge = generate_pkce_pair()

    # Start the callback server in a background thread
    server_thread = threading.Thread(target=run_callback_server, args=(port,), daemon=True)
    server_thread.start()

    # Wait for server to be ready
    server_ready.wait(timeout=5)

    # Build and display the auth URL
    auth_url = build_auth_url(client_id, scopes, state, code_challenge, callback_url)

    print_section("AUTHORIZATION")
    print(f"""
ARIA is starting a local server on port {port} to receive the callback.

Your browser will open to EVE Online's login page.
After you authorize, you'll be redirected back automatically.
""")

    input("Press Enter to open your browser...")

    # Open browser
    print_aria("Opening browser for EVE SSO authentication...")
    webbrowser.open(auth_url)

    print_aria(f"Waiting for authorization (timeout: {CALLBACK_TIMEOUT // 60} minutes)...")
    print("      Complete the authorization in your browser.")

    # Wait for callback
    if not callback_received.wait(timeout=CALLBACK_TIMEOUT):
        raise RuntimeError("Authorization timed out. Please try again.")

    # Check for errors
    if auth_result["error"]:
        raise RuntimeError(f"Authorization failed: {auth_result['error']}")

    if not auth_result["code"]:
        raise RuntimeError("No authorization code received")

    # Verify state
    if auth_result["state"] != state:
        raise RuntimeError("State mismatch - possible CSRF attack")

    print_aria("Authorization code received!")

    # Exchange code for tokens
    print_aria("Exchanging authorization code for tokens...")

    token_response = exchange_code_for_tokens(
        client_id, auth_result["code"], code_verifier, callback_url
    )

    return token_response


def run_manual_flow(client_id: str, scopes: list[str]) -> dict:
    """Run the OAuth flow with manual copy-paste."""
    callback_url = "http://localhost/callback"

    state = secrets.token_urlsafe(16)
    code_verifier, code_challenge = generate_pkce_pair()

    auth_url = build_auth_url(client_id, scopes, state, code_challenge, callback_url)

    print_section("AUTHORIZATION (Manual Mode)")
    print(f"""
Open this URL in your browser:

{auth_url}

After authorizing, you'll be redirected to a page that won't load.
Copy the ENTIRE URL from your browser's address bar and paste it below.
""")

    open_browser = input("Open URL in browser automatically? [Y/n]: ").strip().lower()
    if open_browser != "n":
        webbrowser.open(auth_url)

    print()
    callback_input = input("Paste the callback URL (or just the code): ").strip()

    if not callback_input:
        raise RuntimeError("No callback URL provided")

    code = extract_code_from_callback(callback_input)

    print_aria("Exchanging authorization code for tokens...")

    token_response = exchange_code_for_tokens(client_id, code, code_verifier, callback_url)

    return token_response


def main():
    """Main setup wizard."""
    parser = argparse.ArgumentParser(description="ARIA OAuth Setup Wizard")
    parser.add_argument(
        "--manual", action="store_true", help="Use manual copy-paste mode instead of local server"
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

    print_header("ARIA GALNET AUTHENTICATION SETUP WIZARD")

    print_aria("Initiating EVE SSO integration sequence.")
    print_aria("This wizard will connect ARIA to your EVE Online character data.")

    # Step 1: Get client_id
    print_section("STEP 1: EVE DEVELOPER APPLICATION")

    print("""
Before proceeding, you need an EVE Developer application.

If you haven't created one yet:
  1. Go to: https://developers.eveonline.com/
  2. Log in with your EVE Online account
  3. Click 'Manage Applications' → 'Create New Application'
  4. Fill in:
     • Name: ARIA Integration
     • Description: Personal ship AI assistant
     • Connection Type: Authentication & API Access
     • Callback URL: http://localhost:8421/callback
     • Scopes: Select all you want (you'll choose again here)
  5. Click 'Create Application'
  6. Copy your Client ID
""")

    open_browser = input("Open EVE Developers website? [Y/n]: ").strip().lower()
    if open_browser != "n":
        webbrowser.open("https://developers.eveonline.com/")

    print()
    client_id = input("Enter your Client ID: ").strip()

    if not client_id:
        print_aria("Error: Client ID is required.")
        sys.exit(1)

    # Step 2: Select scopes
    scopes = select_scopes()
    print(f"\nSelected {len(scopes)} personal scopes.")

    # Step 2b: Corporation scopes (optional)
    corp_scopes = ask_corp_scopes()
    if corp_scopes:
        scopes = scopes + corp_scopes
        print(f"Total scopes: {len(scopes)} (including {len(corp_scopes)} corporation scopes)")

    # Step 3: OAuth flow
    try:
        if args.manual:
            token_response = run_manual_flow(client_id, scopes)
        else:
            token_response = run_automatic_flow(client_id, scopes)
    except RuntimeError as e:
        print_aria(f"Error: {e}")
        sys.exit(1)

    access_token = token_response.get("access_token")
    refresh_token = token_response.get("refresh_token")
    expires_in = token_response.get("expires_in", 1199)

    if not access_token or not refresh_token:
        print_aria("Error: Invalid token response")
        sys.exit(1)

    # Step 4: Verify and get character info
    print_aria("Verifying identity with GalNet...")

    try:
        char_info = verify_token(access_token)
    except RuntimeError as e:
        print_aria(f"Error: {e}")
        sys.exit(1)

    character_id = char_info.get("CharacterID")
    character_name = char_info.get("CharacterName")

    print_aria(f"Identity confirmed: {character_name} (ID: {character_id})")

    # Step 5: Check corporation status
    print_aria("Checking corporation status...")
    corp_info = get_character_corporation(access_token, character_id)
    if corp_info:
        if corp_info.get("is_player_corp"):
            print_aria(
                f"Player corporation: {corp_info['corporation_name']} [{corp_info['ticker']}]"
            )
        else:
            print_aria(f"NPC corporation: {corp_info['corporation_name']}")

    # Determine if corp scopes were authorized
    has_corp_scopes = any(s in CORP_SCOPES for s in scopes)

    # Step 6: Save credentials
    print_section("SAVING CREDENTIALS")

    expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    credentials = {
        "client_id": client_id,
        "character_id": character_id,
        "character_name": character_name,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_expiry": expiry.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scopes": scopes,
        "corp_authorized": has_corp_scopes,
        "_created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "_note": "Generated by ARIA OAuth Setup Wizard",
    }

    # Add corp info if available
    if corp_info:
        credentials["corporation_id"] = corp_info.get("corporation_id")
        credentials["corporation_name"] = corp_info.get("corporation_name")

    project_root = get_project_root()

    # V2 structure: userdata/credentials/{character_id}.json
    creds_dir = project_root / "userdata" / "credentials"
    creds_dir.mkdir(parents=True, exist_ok=True)
    creds_path = creds_dir / f"{character_id}.json"

    if creds_path.exists():
        overwrite = (
            input(f"\nCredentials for {character_name} already exist. Overwrite? [y/N]: ")
            .strip()
            .lower()
        )
        if overwrite != "y":
            print_aria("Keeping existing credentials.")
        else:
            save_credentials_secure(creds_path, credentials, use_keyring=use_keyring)
            print_aria(f"Credentials updated: credentials/{character_id}.json")
    else:
        save_credentials_secure(creds_path, credentials, use_keyring=use_keyring)
        print_aria(f"Credentials saved: credentials/{character_id}.json")

    # Update registry and config
    update_pilot_registry(project_root, character_id, character_name)
    update_config(project_root, character_id)
    print_aria("Pilot registry updated.")

    # Success!
    print_header("SETUP COMPLETE")

    # Determine storage info for display
    keyring_status = get_keyring_status()
    if use_keyring and keyring_status.get("available"):
        storage_line = f"System keyring ({KEYRING_BACKEND})"
    else:
        storage_line = "File-based (0600 permissions)"

    print(f"""
╔════════════════════════════════════════════════════════════════════╗
║                 ARIA GALNET INTEGRATION ACTIVE                     ║
╠════════════════════════════════════════════════════════════════════╣
║                                                                    ║
║  Capsuleer:     {character_name:<48} ║
║  Character ID:  {str(character_id):<48} ║
║  Scopes:        {str(len(scopes)) + " permissions granted":<48} ║
║  Token Expiry:  {expiry.strftime("%Y-%m-%d %H:%M:%S UTC"):<48} ║
║  Storage:       {storage_line:<48} ║
║                                                                    ║
╠════════════════════════════════════════════════════════════════════╣
║  Credentials:   {creds_path.name:<48} ║
╚════════════════════════════════════════════════════════════════════╝

NEXT STEPS:

  1. Return to Claude Code and verify with:
     /aria-status

  2. Set up automatic token refresh (recommended):

     WINDOWS (Task Scheduler):
       • Open Task Scheduler → Create Basic Task
       • Name: "ARIA Token Refresh"
       • Trigger: Daily, repeat every 15 minutes
       • Action: Start a program
       • Program: uv
       • Arguments: run python .claude/scripts/aria-refresh --quiet
       • Start in: {project_root}

     MACOS/LINUX (crontab):
       crontab -e
       # Add: */15 * * * * cd {project_root} && uv run python .claude/scripts/aria-refresh --quiet

  3. Start using ARIA! Try /help to see available commands.
""")

    print_aria("GalNet integration complete. Return to Claude Code and say /aria-status")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nARIA: Setup cancelled.")
        sys.exit(1)
