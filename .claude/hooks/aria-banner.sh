#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# ARIA Banner Display (Manual Use)
# ═══════════════════════════════════════════════════════════════════
# Displays the ARIA ASCII art banner in the terminal.
#
# Usage:
#   .claude/hooks/aria-banner.sh           # Show startup banner
#   .claude/hooks/aria-banner.sh --minimal # Show compact status
#
# Note: The SessionStart hook outputs JSON for Claude's context.
#       This script is for users who want to see the banner manually.
# ═══════════════════════════════════════════════════════════════════

set -euo pipefail

# Get project directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
export CLAUDE_PROJECT_DIR="$PROJECT_DIR/.."

# Module directory
MODULE_DIR="$SCRIPT_DIR/aria-boot.d"

# Timestamp
TIMESTAMP=$(date "+%Y.%m.%d %H:%M:%S")

# Source modules (order matters)
source "$MODULE_DIR/pilot-resolution.sh"
source "$MODULE_DIR/persona-detect.sh"
source "$MODULE_DIR/boot-operations.sh"
source "$MODULE_DIR/boot-display.sh"

# Run prerequisite checks
run_prerequisite_checks || true

# Resolve pilot
resolve_pilot_profile

# Check for fresh install
if [ "$PILOT_COUNT" -eq 0 ] && [ -z "$ACTIVE_PILOT_ID" ]; then
    display_fresh_install
    exit 0
fi

# Detect persona
detect_persona

# Run boot operations (for status info)
run_boot_operations_parallel || true

# Display based on argument
case "${1:-}" in
    "--minimal"|"-m")
        display_compact
        ;;
    "--resume"|"-r")
        display_resume
        ;;
    "--clear"|"-c")
        display_clear
        ;;
    *)
        display_startup
        ;;
esac
