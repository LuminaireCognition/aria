#!/usr/bin/env bash
set -euo pipefail

cd /workspace

# Quick validation — do not re-download anything
if [ -f "userdata/config.json" ] && command -v uv &>/dev/null; then
    echo "ARIA environment ready."
else
    echo "ARIA environment ready (run ./aria-init to configure your pilot)."
fi
