#!/usr/bin/env python3
"""
ARIA ESI Sync — Thin wrapper

Delegates to: uv run aria-esi esi-sync / sync-status

Kept for backward compatibility with manual invocations.
The actual implementation lives in src/aria_esi/commands/sync_esi.py.
"""

import subprocess
import sys


def main():
    cmd = ["uv", "run", "--quiet", "aria-esi"]
    args = sys.argv[1:]

    if "--status" in args:
        args.remove("--status")
        cmd.append("sync-status")
    else:
        cmd.append("esi-sync")

    cmd.extend(args)
    sys.exit(subprocess.run(cmd).returncode)


if __name__ == "__main__":
    main()
