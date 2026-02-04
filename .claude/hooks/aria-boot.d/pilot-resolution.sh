#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# ARIA Boot Module: Pilot Resolution
# ═══════════════════════════════════════════════════════════════════
# Handles V2 multi-pilot structure detection and pilot selection.
#
# Exports:
#   - ACTIVE_PILOT_ID, ACTIVE_PILOT_NAME, ACTIVE_PILOT_DIR
#   - PILOT_PROFILE, PILOT_COUNT, PILOT_SELECTION_NEEDED
#   - resolve_pilot_profile() - Main entry point
#   - list_pilots() - For selection display
#
# Requires:
#   - CLAUDE_PROJECT_DIR (set by main boot script)
# ═══════════════════════════════════════════════════════════════════

# State variables (exported for other modules)
ACTIVE_PILOT_ID=""
ACTIVE_PILOT_NAME=""
ACTIVE_PILOT_DIR=""
PILOT_PROFILE=""
PILOT_COUNT=0
PILOT_SELECTION_NEEDED=false

# ───────────────────────────────────────────────────────────────────
# Path Resolution (with legacy fallback)
# ───────────────────────────────────────────────────────────────────
# New structure: userdata/{config.json, pilots/, credentials/, sessions/}
# Legacy structure: .aria-config.json, pilots/, credentials/, sessions/

# Config file: prefer userdata/config.json, fallback to .aria-config.json
if [ -f "$CLAUDE_PROJECT_DIR/userdata/config.json" ]; then
    CONFIG_FILE="$CLAUDE_PROJECT_DIR/userdata/config.json"
elif [ -f "$CLAUDE_PROJECT_DIR/.aria-config.json" ]; then
    CONFIG_FILE="$CLAUDE_PROJECT_DIR/.aria-config.json"
else
    CONFIG_FILE="$CLAUDE_PROJECT_DIR/userdata/config.json"  # Default for new installs
fi

# Pilots directory: prefer userdata/pilots/, fallback to pilots/
if [ -d "$CLAUDE_PROJECT_DIR/userdata/pilots" ]; then
    PILOTS_DIR="$CLAUDE_PROJECT_DIR/userdata/pilots"
elif [ -d "$CLAUDE_PROJECT_DIR/pilots" ]; then
    PILOTS_DIR="$CLAUDE_PROJECT_DIR/pilots"
else
    PILOTS_DIR="$CLAUDE_PROJECT_DIR/userdata/pilots"  # Default for new installs
fi

REGISTRY_FILE="$PILOTS_DIR/_registry.json"

# ───────────────────────────────────────────────────────────────────
# JSON Parsing Helpers (no jq dependency)
# ───────────────────────────────────────────────────────────────────

json_get() {
    local json="$1"
    local key="$2"
    echo "$json" | grep -o "\"$key\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" | head -1 | cut -d'"' -f4
}

json_get_number() {
    local json="$1"
    local key="$2"
    echo "$json" | grep -o "\"$key\"[[:space:]]*:[[:space:]]*[0-9]*" | head -1 | grep -o '[0-9]*$'
}

# ───────────────────────────────────────────────────────────────────
# Pilot Registry Functions
# ───────────────────────────────────────────────────────────────────

count_pilots() {
    if [ ! -f "$REGISTRY_FILE" ]; then
        echo 0
        return
    fi
    # Count "character_id" occurrences as proxy for pilot count
    grep -c '"character_id"' "$REGISTRY_FILE" 2>/dev/null || echo 0
}

get_pilot_info() {
    local char_id="$1"
    if [ ! -f "$REGISTRY_FILE" ]; then
        return 1
    fi

    # Use awk to extract the pilot block - more reliable for nested JSON
    local pilot_data
    pilot_data=$(awk -v id="$char_id" '
        BEGIN { found=0; brace_count=0; pilot_text=""; capturing=0 }
        # Start capturing when we see an opening brace (potential pilot object)
        /{/ && !capturing {
            brace_count = 0
            pilot_text = ""
            capturing = 1
        }
        capturing {
            pilot_text = pilot_text $0 "\n"
            # Count braces in this line
            for (i=1; i<=length($0); i++) {
                c = substr($0, i, 1)
                if (c == "{") brace_count++
                if (c == "}") brace_count--
            }
            # Check if we completed an object
            if (brace_count == 0) {
                # Check if this object contains our character_id
                if (pilot_text ~ "\"character_id\"[[:space:]]*:[[:space:]]*\"" id "\"") {
                    print pilot_text
                    exit
                }
                # Reset for next object
                capturing = 0
                pilot_text = ""
            }
        }
    ' "$REGISTRY_FILE")

    # If awk approach fails, try simpler line-by-line search
    if [ -z "$pilot_data" ]; then
        # Fallback: search for character_id line and extract nearby fields
        local found_id=false
        local char_name=""
        local dir_name=""
        local faction=""

        while IFS= read -r line; do
            if echo "$line" | grep -q "\"character_id\".*\"$char_id\""; then
                found_id=true
            fi
            if [ "$found_id" = true ]; then
                if echo "$line" | grep -q '"character_name"'; then
                    char_name=$(echo "$line" | grep -o '"character_name"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4)
                fi
                if echo "$line" | grep -q '"directory"'; then
                    dir_name=$(echo "$line" | grep -o '"directory"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4)
                fi
                if echo "$line" | grep -q '"faction"'; then
                    faction=$(echo "$line" | grep -o '"faction"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4)
                fi
                # Stop at closing brace (end of pilot object)
                if echo "$line" | grep -q '^[[:space:]]*}'; then
                    break
                fi
            fi
        done < "$REGISTRY_FILE"

        if [ -n "$char_name" ]; then
            ACTIVE_PILOT_NAME="$char_name"
            if [ -n "$dir_name" ] && [ -d "$PILOTS_DIR/$dir_name" ]; then
                ACTIVE_PILOT_DIR="$PILOTS_DIR/$dir_name"
                return 0
            fi
        fi
        return 1
    fi

    ACTIVE_PILOT_NAME=$(json_get "$pilot_data" "character_name")
    local dir_name
    dir_name=$(json_get "$pilot_data" "directory")

    if [ -n "$dir_name" ] && [ -d "$PILOTS_DIR/$dir_name" ]; then
        ACTIVE_PILOT_DIR="$PILOTS_DIR/$dir_name"
        return 0
    fi

    return 1
}

get_first_pilot() {
    if [ ! -f "$REGISTRY_FILE" ]; then
        return 1
    fi

    local registry
    registry=$(cat "$REGISTRY_FILE")

    # Get first character_id
    local first_id
    first_id=$(echo "$registry" | grep -o '"character_id"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | cut -d'"' -f4)

    if [ -n "$first_id" ]; then
        ACTIVE_PILOT_ID="$first_id"
        get_pilot_info "$first_id"
        return $?
    fi

    return 1
}

list_pilots() {
    if [ ! -f "$REGISTRY_FILE" ]; then
        return
    fi

    local registry
    registry=$(cat "$REGISTRY_FILE")

    # Extract all pilot entries
    local index=1
    echo "$registry" | grep -o '{[^}]*"character_id"[^}]*}' | while read -r pilot_block; do
        local char_id char_name faction
        char_id=$(json_get "$pilot_block" "character_id")
        char_name=$(json_get "$pilot_block" "character_name")
        faction=$(json_get "$pilot_block" "faction")

        if [ -n "$char_id" ] && [ -n "$char_name" ]; then
            echo "  [$index] $char_name ($faction) - ID: $char_id"
            index=$((index + 1))
        fi
    done
}

# ───────────────────────────────────────────────────────────────────
# Main Resolution Logic
# ───────────────────────────────────────────────────────────────────

resolve_v2_pilot() {
    PILOT_COUNT=$(count_pilots)

    # Priority 1: Environment variable
    if [ -n "${ARIA_PILOT:-}" ]; then
        ACTIVE_PILOT_ID="${ARIA_PILOT:-}"
        if get_pilot_info "$ACTIVE_PILOT_ID"; then
            return 0
        else
            # Environment variable set but pilot not found
            ACTIVE_PILOT_ID=""
        fi
    fi

    # Priority 2: Config file active_pilot
    if [ -f "$CONFIG_FILE" ]; then
        local config_pilot
        config_pilot=$(json_get "$(cat "$CONFIG_FILE")" "active_pilot")
        if [ -n "$config_pilot" ]; then
            ACTIVE_PILOT_ID="$config_pilot"
            if get_pilot_info "$ACTIVE_PILOT_ID"; then
                return 0
            fi
        fi
    fi

    # Priority 3: Auto-select if single pilot
    if [ "$PILOT_COUNT" -eq 1 ]; then
        if get_first_pilot; then
            return 0
        fi
    fi

    # Priority 4: Multiple pilots, none selected - need user selection
    if [ "$PILOT_COUNT" -gt 1 ]; then
        PILOT_SELECTION_NEEDED=true
        # Still try to get first pilot for display purposes
        get_first_pilot
        return 1
    fi

    # No pilots found
    return 1
}

resolve_pilot_profile() {
    # Call resolve_v2_pilot but don't let it fail the script
    # Fresh installs will have PILOT_COUNT=0 and empty ACTIVE_PILOT_ID
    resolve_v2_pilot || true

    if [ -n "$ACTIVE_PILOT_DIR" ]; then
        PILOT_PROFILE="$ACTIVE_PILOT_DIR/profile.md"
    fi
}
