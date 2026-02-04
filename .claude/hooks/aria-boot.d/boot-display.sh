#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# ARIA Boot Module: Display Functions
# ═══════════════════════════════════════════════════════════════════
# Handles all boot sequence output.
#
# Primary Output (for Claude Code context):
#   - output_json_context() - Structured JSON for LLM consumption
#
# Manual Display (for human terminal, optional):
#   - display_banner() - ASCII art banner (run manually if desired)
#   - display_startup() - Full startup sequence (legacy)
#   - display_resume() - Session resume message (legacy)
#   - display_clear() - Memory clear message (legacy)
#   - display_compact() - Minimal status line (legacy)
#
# Requires:
#   - TIMESTAMP (set by main boot script)
#   - ACTIVE_PILOT_ID, ACTIVE_PILOT_NAME, PILOT_COUNT, PILOT_SELECTION_NEEDED
#   - AI_PERSONA, AI_SUBTITLE
#   - CONFIG_STATUS, ESI_STATUS, ESI_CHANGES
#   - BOOT_WARNINGS[], BOOT_ERRORS[] (set by boot-operations.sh)
# ═══════════════════════════════════════════════════════════════════

# ───────────────────────────────────────────────────────────────────
# JSON Context Output (Primary - for Claude Code)
# ───────────────────────────────────────────────────────────────────
# SessionStart hook output goes to Claude's context, not the terminal.
# JSON is more efficient and unambiguous than ASCII art banners.

output_json_context() {
    local source_event="${1:-startup}"

    # Determine credential status
    local has_creds="false"
    if [ -n "$ACTIVE_PILOT_ID" ] && [ -f "$CREDENTIALS_DIR/$ACTIVE_PILOT_ID.json" ]; then
        has_creds="true"
    fi

    # Determine fresh install status
    local is_fresh="false"
    if [ "$PILOT_COUNT" -eq 0 ] && [ -z "$ACTIVE_PILOT_ID" ]; then
        is_fresh="true"
    fi

    # Build warnings JSON array
    local warnings_json="[]"
    if [ ${#BOOT_WARNINGS[@]} -gt 0 ]; then
        warnings_json="["
        local first=true
        for warn in "${BOOT_WARNINGS[@]}"; do
            if [ "$first" = true ]; then
                first=false
            else
                warnings_json+=","
            fi
            # Escape quotes in warning message
            local escaped_warn="${warn//\"/\\\"}"
            warnings_json+="\"$escaped_warn\""
        done
        warnings_json+="]"
    fi

    # Build errors JSON array
    local errors_json="[]"
    if [ ${#BOOT_ERRORS[@]} -gt 0 ]; then
        errors_json="["
        local first=true
        for err in "${BOOT_ERRORS[@]}"; do
            if [ "$first" = true ]; then
                first=false
            else
                errors_json+=","
            fi
            local escaped_err="${err//\"/\\\"}"
            errors_json+="\"$escaped_err\""
        done
        errors_json+="]"
    fi

    # Build ESI changes array
    local esi_changes_json="[]"
    if [ -n "$ESI_CHANGES" ]; then
        esi_changes_json="["
        local first=true
        while IFS= read -r change_line; do
            [ -z "$change_line" ] && continue
            if [ "$first" = true ]; then
                first=false
            else
                esi_changes_json+=","
            fi
            # Strip "ESI_CHANGE: " prefix if present
            local change_text="${change_line#ESI_CHANGE: }"
            local escaped_change="${change_text//\"/\\\"}"
            esi_changes_json+="\"$escaped_change\""
        done <<< "$ESI_CHANGES"
        esi_changes_json+="]"
    fi

    # Output structured JSON
    cat << EOF
{
  "aria_boot": {
    "version": "2.0",
    "timestamp": "$TIMESTAMP",
    "source": "$source_event"
  },
  "pilot": {
    "id": "${ACTIVE_PILOT_ID:-null}",
    "name": "${ACTIVE_PILOT_NAME:-null}",
    "count": $PILOT_COUNT,
    "selection_needed": $PILOT_SELECTION_NEEDED
  },
  "config": {
    "status": "$CONFIG_STATUS"
  },
  "esi": {
    "status": "$ESI_STATUS",
    "changes": $esi_changes_json
  },
  "persona": {
    "name": "${AI_PERSONA:-ARIA}",
    "subtitle": "${AI_SUBTITLE:-EVE Online Tactical Assistant}"
  },
  "state": {
    "fresh_install": $is_fresh,
    "credentials": $has_creds
  },
  "diagnostics": {
    "warnings": $warnings_json,
    "errors": $errors_json
  }
}
EOF
}

# ───────────────────────────────────────────────────────────────────
# Fresh Install JSON Output
# ───────────────────────────────────────────────────────────────────

output_fresh_install_json() {
    cat << EOF
{
  "aria_boot": {
    "version": "2.0",
    "timestamp": "$TIMESTAMP",
    "source": "fresh_install"
  },
  "pilot": {
    "id": null,
    "name": null,
    "count": 0,
    "selection_needed": false
  },
  "config": {
    "status": "NOT_CONFIGURED"
  },
  "esi": {
    "status": "NOT_CONFIGURED",
    "changes": []
  },
  "persona": {
    "name": "ARIA",
    "subtitle": "Fresh Installation"
  },
  "state": {
    "fresh_install": true,
    "credentials": false
  },
  "diagnostics": {
    "warnings": [],
    "errors": []
  },
  "guidance": {
    "message": "Fresh installation detected. Run /first-run-setup or say 'help me set up' to configure.",
    "commands": ["/first-run-setup", "/setup"]
  }
}
EOF
}

# ═══════════════════════════════════════════════════════════════════
# LEGACY DISPLAY FUNCTIONS (for manual terminal use)
# ═══════════════════════════════════════════════════════════════════
# These functions output ASCII art banners for human viewing.
# They are NOT used by the SessionStart hook (which outputs JSON).
# To see the banner manually: .claude/hooks/aria-banner.sh

# ───────────────────────────────────────────────────────────────────
# Boot Warnings Display
# ───────────────────────────────────────────────────────────────────

display_boot_warnings() {
    # Display boot warnings if any exist
    if [ ${#BOOT_WARNINGS[@]} -gt 0 ]; then
        cat << EOF
BOOT WARNINGS
───────────────────────────────────────────────────────────────────
EOF
        for warn in "${BOOT_WARNINGS[@]}"; do
            echo "  - $warn"
        done
        cat << EOF
───────────────────────────────────────────────────────────────────
EOF
    fi
}

# ───────────────────────────────────────────────────────────────────
# Pilot Selection Display
# ───────────────────────────────────────────────────────────────────

display_pilot_selection() {
    cat << EOF

═══════════════════════════════════════════════════════════════════
    ___    ____  _________
   /   |  / __ \/  _/   |   Adaptive Reasoning & Intelligence Array
  / /| | / /_/ // // /| |   ARIA
 / ___ |/ _, _// // ___ |   Multi-Pilot Mode
/_/  |_/_/ |_/___/_/  |_|
═══════════════════════════════════════════════════════════════════
PILOT SELECTION REQUIRED
───────────────────────────────────────────────────────────────────
Multiple pilot profiles detected ($PILOT_COUNT pilots).
No active pilot configured.

Available pilots:
EOF
    list_pilots
    cat << EOF

To select a pilot:
  1. Set environment variable: export ARIA_PILOT=<character_id>
  2. Or tell me which pilot to use in chat

Current session will use first pilot until selection is made.
───────────────────────────────────────────────────────────────────
EOF
}

# ───────────────────────────────────────────────────────────────────
# Startup Display (Full Boot Sequence)
# ───────────────────────────────────────────────────────────────────

display_startup() {
    # Determine config indicator
    case "$CONFIG_STATUS" in
        "OK")       CONFIG_INDICATOR="████████████████████ VERIFIED" ;;
        "WARNINGS") CONFIG_INDICATOR="████████████████░░░░ MINOR ISSUES" ;;
        "CRITICAL") CONFIG_INDICATOR="████████░░░░░░░░░░░░ INCOMPLETE" ;;
        *)          CONFIG_INDICATOR="████████████████████ VERIFIED" ;;
    esac

    # Determine ESI indicator
    case "$ESI_STATUS" in
        "SYNCED")           ESI_INDICATOR="████████████████████ SYNCED" ;;
        "CHANGES_DETECTED") ESI_INDICATOR="████████████████░░░░ CHANGES DETECTED" ;;
        "CONFIGURED")       ESI_INDICATOR="████████████████████ CONFIGURED" ;;
        "NOT_CONFIGURED")   ESI_INDICATOR="░░░░░░░░░░░░░░░░░░░░ NOT CONFIGURED" ;;
        *)                  ESI_INDICATOR="████████░░░░░░░░░░░░ UNAVAILABLE" ;;
    esac

    # Build pilot display line
    local pilot_display=""
    if [ -n "$ACTIVE_PILOT_NAME" ]; then
        pilot_display="$ACTIVE_PILOT_NAME"
        if [ "$PILOT_COUNT" -gt 1 ]; then
            pilot_display="$pilot_display (1 of $PILOT_COUNT)"
        fi
    else
        pilot_display="[Not configured]"
    fi

    cat << EOF

═══════════════════════════════════════════════════════════════════
    ___    ____  _________
   /   |  / __ \/  _/   |   Adaptive Reasoning & Intelligence Array
  / /| | / /_/ // // /| |   $AI_PERSONA
 / ___ |/ _, _// // ___ |   $AI_SUBTITLE
/_/  |_/_/ |_/___/_/  |_|
═══════════════════════════════════════════════════════════════════
INITIALIZATION SEQUENCE
───────────────────────────────────────────────────────────────────
Timestamp:           $TIMESTAMP
Core Systems:        ████████████████████ ONLINE
Sensor Array:        ████████████████████ CALIBRATED
Tactical Database:   ████████████████████ SYNCHRONIZED
GalNet Connection:   ████████████████████ ESTABLISHED
EOF

    # Show active pilot
    echo "Active Pilot:        $pilot_display"

    cat << EOF
Capsuleer Profile:   $CONFIG_INDICATOR
GalNet ESI Sync:     $ESI_INDICATOR
───────────────────────────────────────────────────────────────────
EOF

    # Show pilot selection notice if needed
    if [ "$PILOT_SELECTION_NEEDED" = true ]; then
        cat << EOF
MULTI-PILOT NOTICE
───────────────────────────────────────────────────────────────────
$PILOT_COUNT pilots available. Using: $ACTIVE_PILOT_NAME
To switch: Set ARIA_PILOT=<character_id> or ask me to switch.
───────────────────────────────────────────────────────────────────
EOF
    fi

    # Show config issues if any
    if [ "$CONFIG_STATUS" = "CRITICAL" ]; then
        cat << EOF
CONFIGURATION INCOMPLETE
───────────────────────────────────────────────────────────────────
Your capsuleer profile needs configuration. I can help with this!

  Say "yes" or "setup" ... I'll guide you through a quick conversation
  Say "skip" ............. Continue without setup (edit files manually)

Or run /setup anytime to configure your profile.
───────────────────────────────────────────────────────────────────
EOF
    elif [ "$CONFIG_STATUS" = "WARNINGS" ]; then
        cat << EOF
Note: Minor configuration items pending. Use /help for guidance.
───────────────────────────────────────────────────────────────────
EOF
    fi

    # Show ESI standing changes if detected
    if [ "$ESI_STATUS" = "CHANGES_DETECTED" ] && [ -n "$ESI_CHANGES" ]; then
        cat << EOF
STANDING CHANGES DETECTED (vs profile)
───────────────────────────────────────────────────────────────────
EOF
        echo "$ESI_CHANGES" | sed 's/^ESI_CHANGE: /  /'
        cat << EOF

Say "update standings" to sync profile with current ESI data.
───────────────────────────────────────────────────────────────────
EOF
    fi

    # Show boot warnings if any
    display_boot_warnings

    # Determine credential status
    local has_creds="false"
    if [ -n "$ACTIVE_PILOT_ID" ] && [ -f "$CREDENTIALS_DIR/$ACTIVE_PILOT_ID.json" ]; then
        has_creds="true"
    fi

    cat << EOF
All systems nominal. Ready to assist, Capsuleer.
═══════════════════════════════════════════════════════════════════
<!-- aria:state fresh_install=false credentials=$has_creds pilot=$ACTIVE_PILOT_ID config_status=$CONFIG_STATUS esi_status=$ESI_STATUS -->
EOF
}

# ───────────────────────────────────────────────────────────────────
# Resume Display (Session Restored)
# ───────────────────────────────────────────────────────────────────

display_resume() {
    local pilot_info=""
    if [ -n "$ACTIVE_PILOT_NAME" ]; then
        pilot_info=" | Pilot: $ACTIVE_PILOT_NAME"
    fi

    cat << EOF

═══════════════════════════════════════════════════════════════════
ARIA SYSTEMS RESTORED
───────────────────────────────────────────────────────────────────
Session resumed at $TIMESTAMP$pilot_info
Previous context restored. Continuing operations.
═══════════════════════════════════════════════════════════════════

EOF
}

# ───────────────────────────────────────────────────────────────────
# Clear Display (Memory Purged)
# ───────────────────────────────────────────────────────────────────

display_clear() {
    cat << EOF

═══════════════════════════════════════════════════════════════════
ARIA MEMORY CLEARED
───────────────────────────────────────────────────────────────────
Tactical buffers purged at $TIMESTAMP
Standing by for new directives, Capsuleer.
═══════════════════════════════════════════════════════════════════

EOF
}

# ───────────────────────────────────────────────────────────────────
# Compact Display (Minimal)
# ───────────────────────────────────────────────────────────────────

display_compact() {
    local pilot_info=""
    if [ -n "$ACTIVE_PILOT_NAME" ]; then
        pilot_info=" | $ACTIVE_PILOT_NAME"
    fi
    echo "ARIA: Systems nominal.$pilot_info [$TIMESTAMP]"
}

# ───────────────────────────────────────────────────────────────────
# Fresh Install Display
# ───────────────────────────────────────────────────────────────────

display_fresh_install() {
    cat << 'EOF'

═══════════════════════════════════════════════════════════════════
    ___    ____  _________
   /   |  / __ \/  _/   |   Adaptive Reasoning & Intelligence Array
  / /| | / /_/ // // /| |   ARIA
 / ___ |/ _, _// // ___ |   Fresh Installation Detected
/_/  |_/_/ |_/___/_/  |_|
═══════════════════════════════════════════════════════════════════
WELCOME, CAPSULEER
───────────────────────────────────────────────────────────────────
This appears to be a fresh installation of ARIA.

ARIA works best when connected to your EVE character via ESI.
This enables skill tracking, asset management, market tools, and more.

To get started, type:   /first-run-setup
Or just say:            "help me set up"

───────────────────────────────────────────────────────────────────
I'll guide you through connecting your EVE character and
configuring your preferences. Takes about 2 minutes.
═══════════════════════════════════════════════════════════════════
<!-- aria:state fresh_install=true credentials=false pilot=none -->
EOF
}
