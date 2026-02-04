#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# ARIA Boot Sequence Hook
# ═══════════════════════════════════════════════════════════════════
# Displays when Claude Code session starts in this project.
# V2 multi-pilot structure with modular architecture.
#
# Pilot Selection Priority:
#   1. ARIA_PILOT environment variable
#   2. .aria-config.json → active_pilot
#   3. Auto-select if single pilot exists
#   4. Display selection prompt if multiple pilots
#
# Module Structure:
#   aria-boot.d/
#   ├── pilot-resolution.sh  - Pilot detection and selection
#   ├── persona-detect.sh    - Faction-based AI persona mapping
#   ├── boot-operations.sh   - Validation, ESI sync, context assembly
#   └── boot-display.sh      - All display/output functions
# ═══════════════════════════════════════════════════════════════════

# ───────────────────────────────────────────────────────────────────
# Error Handling
# ───────────────────────────────────────────────────────────────────

# Exit on error, undefined variable, or pipe failure
set -euo pipefail

# Trap errors and display location
trap 'echo "ARIA boot error in ${BASH_SOURCE[0]:-unknown}:${LINENO:-unknown}" >&2' ERR

# ───────────────────────────────────────────────────────────────────
# Initialization
# ───────────────────────────────────────────────────────────────────

# Read JSON from stdin (must be first - before any other command reads stdin)
INPUT=$(cat)

# Parse source field (startup, resume, clear, compact)
SOURCE=$(echo "$INPUT" | grep -o '"source":"[^"]*"' | cut -d'"' -f4 2>/dev/null || echo "startup")

# Get current time for timestamp
TIMESTAMP=$(date "+%Y.%m.%d %H:%M:%S")

# Get project directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
export CLAUDE_PROJECT_DIR="$PROJECT_DIR/.."

# Module directory
MODULE_DIR="$SCRIPT_DIR/aria-boot.d"

# ───────────────────────────────────────────────────────────────────
# Source Modules
# ───────────────────────────────────────────────────────────────────

# Source each module in dependency order
# Note: Variables set in modules are available after sourcing

if [ -f "$MODULE_DIR/pilot-resolution.sh" ]; then
    source "$MODULE_DIR/pilot-resolution.sh"
else
    echo "ERROR: Missing module: pilot-resolution.sh"
    exit 1
fi

if [ -f "$MODULE_DIR/persona-detect.sh" ]; then
    source "$MODULE_DIR/persona-detect.sh"
else
    echo "ERROR: Missing module: persona-detect.sh"
    exit 1
fi

if [ -f "$MODULE_DIR/boot-operations.sh" ]; then
    source "$MODULE_DIR/boot-operations.sh"
else
    echo "ERROR: Missing module: boot-operations.sh"
    exit 1
fi

if [ -f "$MODULE_DIR/boot-display.sh" ]; then
    source "$MODULE_DIR/boot-display.sh"
else
    echo "ERROR: Missing module: boot-display.sh"
    exit 1
fi

# ───────────────────────────────────────────────────────────────────
# Main Execution
# ───────────────────────────────────────────────────────────────────

# Step 1: Run prerequisite checks (Python, uv, config syntax)
# This runs before pilot resolution to catch environment issues early
run_prerequisite_checks || {
    # Critical errors found - display and exit
    echo "═══════════════════════════════════════════════════════════════════"
    echo "ARIA BOOT VALIDATION FAILED"
    echo "───────────────────────────────────────────────────────────────────"
    get_validation_summary
    echo "═══════════════════════════════════════════════════════════════════"
    exit 1
}

# Step 2: Resolve pilot profile (handles v2 multi-pilot detection)
resolve_pilot_profile

# Step 2b: Check for fresh install (no pilots configured)
# This must happen BEFORE persona detection and boot operations
if [ "$PILOT_COUNT" -eq 0 ] && [ -z "$ACTIVE_PILOT_ID" ]; then
    # Fresh install detected - output JSON context and exit cleanly
    output_fresh_install_json
    exit 0
fi

# Step 3: Detect AI persona from faction
detect_persona

# Step 4: Run security preflight, validation, ESI sync, and context assembly
# Security violations block boot entirely (SECURITY_000.md Quick Win #2)
if ! run_boot_operations_parallel; then
    # Security violations found - display and exit
    echo "═══════════════════════════════════════════════════════════════════"
    echo "ARIA BOOT BLOCKED: SECURITY VIOLATION"
    echo "───────────────────────────────────────────────────────────────────"
    echo "Unsafe paths detected in persona configuration."
    echo ""
    get_validation_summary
    echo ""
    echo "This may indicate a compromised profile or malicious persona_context."
    echo "Review the paths in your profile.md and regenerate with:"
    echo "  uv run aria-esi persona-context"
    echo "═══════════════════════════════════════════════════════════════════"
    exit 1
fi

# Step 5: Output structured JSON context for Claude
# Note: SessionStart hook stdout goes to Claude's context, not the terminal.
# JSON is more efficient than ASCII art for LLM consumption.
output_json_context "$SOURCE"

exit 0
