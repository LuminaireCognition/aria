#!/usr/bin/env python3
"""
ARIA Credential Watcher
═══════════════════════════════════════════════════════════════════
Polls for credential file creation and outputs when found.
Used by first-run-setup skill for background OAuth detection.

Usage:
    python aria-credential-watch.py [--timeout 300]

Outputs JSON when credentials are found:
    {"status": "found", "character_id": "12345", "file": "path/to/file.json"}

Or on timeout:
    {"status": "timeout", "waited_seconds": 300}
"""

import argparse
import json
import sys
import time
from pathlib import Path


def get_project_root() -> Path:
    """Find the project root directory."""
    script_path = Path(__file__).resolve()
    return script_path.parent.parent.parent


def find_credentials(creds_dir: Path) -> tuple[str, Path] | None:
    """Check for credential files, return (character_id, path) or None."""
    if not creds_dir.exists():
        return None

    for cred_file in creds_dir.glob("*.json"):
        # Skip any non-credential files
        if cred_file.stem.isdigit():
            return (cred_file.stem, cred_file)

    return None


def main():
    parser = argparse.ArgumentParser(description="Watch for credential file creation")
    parser.add_argument("--timeout", type=int, default=300, help="Timeout in seconds (default: 300)")
    parser.add_argument("--interval", type=int, default=5, help="Poll interval in seconds (default: 5)")
    args = parser.parse_args()

    project_root = get_project_root()
    creds_dir = project_root / "userdata" / "credentials"

    # Record existing credentials to detect NEW ones
    existing = set()
    if creds_dir.exists():
        existing = {f.stem for f in creds_dir.glob("*.json") if f.stem.isdigit()}

    start_time = time.time()

    # Print startup message to stderr (not captured as result)
    print(f"Watching for credentials in {creds_dir}...", file=sys.stderr)
    print(f"Timeout: {args.timeout}s, Interval: {args.interval}s", file=sys.stderr)
    if existing:
        print(f"Existing credentials (will ignore): {existing}", file=sys.stderr)

    while True:
        elapsed = time.time() - start_time

        if elapsed > args.timeout:
            result = {
                "status": "timeout",
                "waited_seconds": int(elapsed),
                "message": "No new credentials detected"
            }
            print(json.dumps(result))
            sys.exit(1)

        # Check for new credentials
        if creds_dir.exists():
            for cred_file in creds_dir.glob("*.json"):
                if cred_file.stem.isdigit() and cred_file.stem not in existing:
                    # New credential file found!
                    result = {
                        "status": "found",
                        "character_id": cred_file.stem,
                        "file": str(cred_file),
                        "waited_seconds": int(elapsed)
                    }
                    print(json.dumps(result))
                    sys.exit(0)

        # Progress indicator every 30 seconds
        if int(elapsed) % 30 == 0 and int(elapsed) > 0:
            print(f"Still watching... ({int(elapsed)}s elapsed)", file=sys.stderr)

        time.sleep(args.interval)


if __name__ == "__main__":
    main()
