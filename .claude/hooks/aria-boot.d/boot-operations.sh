#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# ARIA Boot Module: Boot Operations
# ═══════════════════════════════════════════════════════════════════
# Handles validation, ESI sync, context assembly, and skill index operations.
#
# Exports:
#   - VALIDATION_OUTPUT, CONFIG_STATUS
#   - ESI_SYNC_OUTPUT, ESI_STATUS, ESI_CHANGES
#   - SECURITY_STATUS, SECURITY_VIOLATIONS[] - Security preflight results
#   - BOOT_WARNINGS[], BOOT_ERRORS[] - Validation results
#   - run_prerequisite_checks() - Validate environment (Python, uv, configs)
#   - get_validation_summary() - Format warnings/errors for display
#   - run_security_validation() - Security preflight (path validation)
#   - run_validation() - Validate pilot configuration
#   - run_esi_sync() - Trigger ESI data sync
#   - run_context_assembly() - Assemble session context
#   - run_skill_index_update() - Regenerate skill index (background)
#
# Requires:
#   - PROJECT_DIR, CLAUDE_PROJECT_DIR (set by main boot script)
#   - ACTIVE_PILOT_ID, ACTIVE_PILOT_DIR (set by pilot-resolution.sh)
# ═══════════════════════════════════════════════════════════════════

# State variables (exported for display module)
VALIDATION_OUTPUT=""
CONFIG_STATUS="OK"
ESI_SYNC_OUTPUT=""
ESI_STATUS="NOT_CONFIGURED"
ESI_CHANGES=""
BOOT_WARNINGS=()
BOOT_ERRORS=()

# ───────────────────────────────────────────────────────────────────
# Path Resolution (with legacy fallback)
# ───────────────────────────────────────────────────────────────────
# Note: CONFIG_FILE, PILOTS_DIR, REGISTRY_FILE are set by pilot-resolution.sh
# This section resolves CREDENTIALS_DIR which is specific to boot-operations.

# Credentials directory: prefer userdata/credentials/, fallback to credentials/
if [ -d "$CLAUDE_PROJECT_DIR/userdata/credentials" ]; then
    CREDENTIALS_DIR="$CLAUDE_PROJECT_DIR/userdata/credentials"
elif [ -d "$CLAUDE_PROJECT_DIR/credentials" ]; then
    CREDENTIALS_DIR="$CLAUDE_PROJECT_DIR/credentials"
else
    CREDENTIALS_DIR="$CLAUDE_PROJECT_DIR/userdata/credentials"  # Default for new installs
fi

# ───────────────────────────────────────────────────────────────────
# Prerequisite Validation (runs early, before other operations)
# ───────────────────────────────────────────────────────────────────

run_prerequisite_checks() {
    # Validates environment prerequisites before boot continues.
    # Populates BOOT_WARNINGS and BOOT_ERRORS arrays.
    # Returns 0 if boot can continue, 1 if critical failure.

    BOOT_WARNINGS=()
    BOOT_ERRORS=()

    # --- Python Version Check ---
    if command -v python3 &>/dev/null; then
        local py_version
        py_version=$(uv run python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "0.0")
        local py_major py_minor
        py_major=$(echo "$py_version" | cut -d. -f1)
        py_minor=$(echo "$py_version" | cut -d. -f2)

        if [ "$py_major" -lt 3 ] || { [ "$py_major" -eq 3 ] && [ "$py_minor" -lt 10 ]; }; then
            BOOT_WARNINGS+=("Python $py_version detected, requires >=3.10")
        fi
    else
        BOOT_WARNINGS+=("Python3 not found in PATH")
    fi

    # --- uv Check ---
    if ! command -v uv &>/dev/null; then
        BOOT_WARNINGS+=("uv not found - Python scripts may fail")
    fi

    # --- Config File Syntax ---
    # Uses CONFIG_FILE from pilot-resolution.sh (prefers userdata/config.json)
    if [ -f "$CONFIG_FILE" ]; then
        if ! uv run python -c "import json; json.load(open('$CONFIG_FILE'))" 2>/dev/null; then
            local config_name
            config_name=$(basename "$CONFIG_FILE")
            BOOT_ERRORS+=("Invalid JSON in $config_name")
        fi
    fi

    # --- Pilot Registry Validation ---
    # Uses REGISTRY_FILE from pilot-resolution.sh (prefers userdata/pilots/_registry.json)
    if [ -f "$REGISTRY_FILE" ]; then
        if ! uv run python -c "import json; json.load(open('$REGISTRY_FILE'))" 2>/dev/null; then
            BOOT_ERRORS+=("Invalid JSON in _registry.json")
        else
            # Check required fields
            local has_pilots
            has_pilots=$(uv run python -c "
import json
with open('$REGISTRY_FILE') as f:
    data = json.load(f)
    if 'pilots' not in data:
        print('missing_pilots')
    elif not isinstance(data['pilots'], list):
        print('pilots_not_list')
    else:
        print('ok')
" 2>/dev/null || echo "error")

            if [ "$has_pilots" = "missing_pilots" ]; then
                BOOT_ERRORS+=("_registry.json missing 'pilots' array")
            elif [ "$has_pilots" = "pilots_not_list" ]; then
                BOOT_ERRORS+=("_registry.json 'pilots' is not an array")
            fi
        fi
    fi

    # --- Credential File Permissions ---
    # Uses CREDENTIALS_DIR (prefers userdata/credentials/)
    if [ -d "$CREDENTIALS_DIR" ]; then
        for cred_file in "$CREDENTIALS_DIR"/*.json; do
            [ -f "$cred_file" ] || continue
            local perms
            perms=$(stat -f "%OLp" "$cred_file" 2>/dev/null || stat -c "%a" "$cred_file" 2>/dev/null || echo "unknown")
            if [ "$perms" != "600" ] && [ "$perms" != "unknown" ]; then
                local basename
                basename=$(basename "$cred_file")
                BOOT_WARNINGS+=("credentials/$basename has permissions $perms (should be 600)")
            fi
        done
    fi

    # --- Required Directories ---
    # Uses PILOTS_DIR from pilot-resolution.sh (prefers userdata/pilots/)
    if [ ! -d "$PILOTS_DIR" ]; then
        BOOT_WARNINGS+=("pilots directory missing (expected: userdata/pilots/)")
    fi

    if [ ! -d "$PROJECT_DIR/scripts" ]; then
        BOOT_WARNINGS+=(".claude/scripts/ directory missing")
    fi

    # --- Virtual Environment ---
    if [ ! -d "$CLAUDE_PROJECT_DIR/.venv" ]; then
        BOOT_WARNINGS+=(".venv/ missing - run 'uv sync'")
    fi

    # Return status: errors are critical, warnings are not
    if [ ${#BOOT_ERRORS[@]} -gt 0 ]; then
        return 1
    fi
    return 0
}

# Helper to get validation summary for display
get_validation_summary() {
    local summary=""

    if [ ${#BOOT_ERRORS[@]} -gt 0 ]; then
        summary+="ERRORS:\n"
        for err in "${BOOT_ERRORS[@]}"; do
            summary+="  - $err\n"
        done
    fi

    if [ ${#BOOT_WARNINGS[@]} -gt 0 ]; then
        if [ -n "$summary" ]; then summary+="\n"; fi
        summary+="WARNINGS:\n"
        for warn in "${BOOT_WARNINGS[@]}"; do
            summary+="  - $warn\n"
        done
    fi

    echo -e "$summary"
}

# ───────────────────────────────────────────────────────────────────
# Persona Artifact Integrity Verification
# ───────────────────────────────────────────────────────────────────
# SECURITY_001.md Finding #2: Verify compiled persona artifacts at boot
# to detect tampering (removed delimiters, injected instructions).

ARTIFACT_STATUS="OK"
ARTIFACT_ISSUES=()

run_artifact_verification() {
    # Verify persona artifact integrity at boot time.
    # Implements SECURITY_001.md Finding #2.
    #
    # Returns 0 if verification passes or artifact doesn't exist (fresh install)
    # Returns 1 if tampering detected (hash mismatch)

    ARTIFACT_STATUS="OK"
    ARTIFACT_ISSUES=()

    # Skip if no pilot configured
    if [ -z "$ACTIVE_PILOT_ID" ]; then
        return 0
    fi

    # Run verify-persona-context and capture JSON output
    local verify_json
    verify_json=$(uv run --quiet aria-esi verify-persona-context 2>/dev/null || echo '{"status":"error"}')

    # Parse verification result using Python
    local verify_result
    verify_result=$(uv run python -c "
import json
import sys

try:
    data = json.loads('''$verify_json''')
except:
    print('parse_error')
    sys.exit(0)

status = data.get('status', 'error')
verification = data.get('verification', {})

if status == 'valid':
    print('OK')
elif status == 'error':
    # Could be missing artifact (fresh install) - not a security issue
    msg = data.get('message', 'Unknown error')
    if 'not found' in msg.lower():
        print('MISSING')
    else:
        print(f'ERROR:{msg}')
elif status == 'integrity_failed':
    # Tampering detected - this is a security issue
    issues = verification.get('issues', [])
    mismatched = verification.get('mismatched_files', [])

    if mismatched:
        print('TAMPERED:' + '|'.join(issues[:5]))  # Limit to 5 issues
    elif not verification.get('artifact_hash_valid', True):
        print('TAMPERED:Artifact integrity hash mismatch')
    else:
        print('TAMPERED:' + '|'.join(issues[:5]) if issues else 'Unknown integrity issue')
else:
    print(f'ERROR:{status}')
" 2>/dev/null || echo "parse_error")

    # Handle results
    case "$verify_result" in
        OK)
            ARTIFACT_STATUS="OK"
            return 0
            ;;
        MISSING)
            # Missing artifact is OK for fresh installs
            ARTIFACT_STATUS="MISSING"
            BOOT_WARNINGS+=("Persona artifact not found - run 'uv run aria-esi persona-context'")
            return 0
            ;;
        parse_error)
            BOOT_WARNINGS+=("Artifact verification: could not parse output")
            return 0
            ;;
        TAMPERED:*)
            ARTIFACT_STATUS="TAMPERED"
            local issues_str="${verify_result#TAMPERED:}"

            # Split by | and add to arrays
            IFS='|' read -ra issues_arr <<< "$issues_str"
            for issue in "${issues_arr[@]}"; do
                if [ -n "$issue" ]; then
                    ARTIFACT_ISSUES+=("$issue")
                    BOOT_ERRORS+=("ARTIFACT TAMPERING: $issue")
                fi
            done
            return 1
            ;;
        ERROR:*)
            local error_msg="${verify_result#ERROR:}"
            BOOT_WARNINGS+=("Artifact verification error: $error_msg")
            return 0
            ;;
        *)
            BOOT_WARNINGS+=("Artifact verification: unexpected result")
            return 0
            ;;
    esac
}

# ───────────────────────────────────────────────────────────────────
# Security Validation (Path Safety Preflight)
# ───────────────────────────────────────────────────────────────────

SECURITY_STATUS="OK"
SECURITY_VIOLATIONS=()

run_security_validation() {
    # Validates persona/overlay/redirect paths for security issues.
    # Implements SECURITY_000.md Quick Win #2: Required preflight check.
    #
    # Security violations (path traversal, absolute paths, out-of-allowlist)
    # are blocking errors. Other issues (staleness, missing files) are warnings.
    #
    # Returns 0 if boot can continue, 1 if security violation found.

    SECURITY_STATUS="OK"
    SECURITY_VIOLATIONS=()

    # Skip if no pilot configured
    if [ -z "$ACTIVE_PILOT_ID" ]; then
        return 0
    fi

    # Run validate-overlays and capture JSON output
    local validation_json
    validation_json=$(uv run --quiet aria-esi validate-overlays 2>/dev/null || echo '{"status":"error"}')

    # Parse security violations using Python (more reliable than jq for complex JSON)
    local security_result
    security_result=$(uv run python -c "
import json
import sys

try:
    data = json.loads('''$validation_json''')
except:
    print('parse_error')
    sys.exit(0)

# Check for security violations (blocking)
results = data.get('results', [])
security_violations = []
other_warnings = []

for result in results:
    validation = result.get('validation', {})
    issues = validation.get('issues', {})

    # Security violations are BLOCKING
    for sec_issue in issues.get('security', []):
        msg = sec_issue.get('message', 'Unknown security issue')
        security_violations.append(msg)

    # Staleness warnings (non-blocking)
    for stale_issue in issues.get('stale', []):
        msg = stale_issue.get('message', 'Stale persona context')
        other_warnings.append(f'STALE: {msg}')

    # Missing file errors (non-blocking - degrade gracefully)
    for err in issues.get('errors', []):
        if err.get('type') == 'missing_persona_file':
            msg = err.get('message', 'Missing persona file')
            other_warnings.append(f'MISSING: {msg}')
        elif err.get('type') == 'missing_exclusive_skill':
            msg = err.get('message', 'Missing exclusive skill')
            other_warnings.append(f'MISSING: {msg}')

# Output format: SECURITY:count|violation1|violation2...
# Then: WARNING:count|warning1|warning2...
if security_violations:
    print('SECURITY:' + str(len(security_violations)) + '|' + '|'.join(security_violations))
if other_warnings:
    print('WARNING:' + str(len(other_warnings)) + '|' + '|'.join(other_warnings))
if not security_violations and not other_warnings:
    print('OK')
" 2>/dev/null || echo "parse_error")

    # Parse the result
    if [ "$security_result" = "parse_error" ]; then
        BOOT_WARNINGS+=("Security validation: could not parse output")
        return 0
    fi

    # Process security violations (blocking)
    if echo "$security_result" | grep -q "^SECURITY:"; then
        SECURITY_STATUS="VIOLATION"
        local sec_line
        sec_line=$(echo "$security_result" | grep "^SECURITY:" | head -1)
        # Extract violations after the count
        local violations_str
        violations_str=$(echo "$sec_line" | cut -d'|' -f2-)

        # Split by | and add to arrays
        IFS='|' read -ra violations_arr <<< "$violations_str"
        for violation in "${violations_arr[@]}"; do
            if [ -n "$violation" ]; then
                SECURITY_VIOLATIONS+=("$violation")
                BOOT_ERRORS+=("SECURITY: $violation")
            fi
        done
    fi

    # Process other warnings (non-blocking)
    if echo "$security_result" | grep -q "^WARNING:"; then
        local warn_line
        warn_line=$(echo "$security_result" | grep "^WARNING:" | head -1)
        local warnings_str
        warnings_str=$(echo "$warn_line" | cut -d'|' -f2-)

        IFS='|' read -ra warnings_arr <<< "$warnings_str"
        for warning in "${warnings_arr[@]}"; do
            if [ -n "$warning" ]; then
                BOOT_WARNINGS+=("$warning")
            fi
        done
    fi

    # Return failure if security violations found
    if [ "$SECURITY_STATUS" = "VIOLATION" ]; then
        return 1
    fi
    return 0
}

# ───────────────────────────────────────────────────────────────────
# Configuration Validation
# ───────────────────────────────────────────────────────────────────

run_validation() {
    VALIDATION_OUTPUT=""
    CONFIG_STATUS="OK"

    # Export pilot directory for validation script
    export ARIA_PILOT_DIR="$ACTIVE_PILOT_DIR"
    export ARIA_PILOT_ID="$ACTIVE_PILOT_ID"

    if [ -x "$PROJECT_DIR/scripts/aria-config-validate" ]; then
        VALIDATION_OUTPUT=$("$PROJECT_DIR/scripts/aria-config-validate" text 2>/dev/null || true)
        CONFIG_STATUS=$(echo "$VALIDATION_OUTPUT" | grep "^CONFIG_STATUS:" | cut -d: -f2 || echo "OK")
    fi

    # If no validator, check profile existence
    if [ -z "$VALIDATION_OUTPUT" ]; then
        if [ ! -f "$PILOT_PROFILE" ]; then
            CONFIG_STATUS="CRITICAL"
        elif grep -q '\[YOUR CHARACTER NAME\]\|\[GALLENTE/CALDARI/MINMATAR/AMARR\]' "$PILOT_PROFILE" 2>/dev/null; then
            CONFIG_STATUS="CRITICAL"
        fi
    fi
}

# ───────────────────────────────────────────────────────────────────
# ESI Synchronization
# ───────────────────────────────────────────────────────────────────

run_esi_sync() {
    ESI_SYNC_OUTPUT=""
    ESI_STATUS="NOT_CONFIGURED"
    ESI_CHANGES=""

    # Export pilot info for ESI sync
    export ARIA_PILOT_DIR="$ACTIVE_PILOT_DIR"
    export ARIA_PILOT_ID="$ACTIVE_PILOT_ID"
    export ARIA_PILOT="$ACTIVE_PILOT_ID"

    if [ -x "$PROJECT_DIR/scripts/aria-boot-sync" ]; then
        ESI_SYNC_OUTPUT=$("$PROJECT_DIR/scripts/aria-boot-sync" --boot 2>/dev/null || true)
        ESI_STATUS=$(echo "$ESI_SYNC_OUTPUT" | grep "^ESI_STATUS:" | cut -d: -f2 | tr -d ' ' || echo "NOT_CONFIGURED")
        ESI_CHANGES=$(echo "$ESI_SYNC_OUTPUT" | grep "^ESI_CHANGE:" || true)
    else
        # Check for credentials to determine ESI status
        # Uses CREDENTIALS_DIR (prefers userdata/credentials/)
        if [ -n "$ACTIVE_PILOT_ID" ]; then
            local creds_file="$CREDENTIALS_DIR/$ACTIVE_PILOT_ID.json"
            if [ -f "$creds_file" ]; then
                ESI_STATUS="CONFIGURED"
            fi
        fi
    fi

    # Launch comprehensive ESI sync in background (non-blocking)
    # This updates ships.md, blueprints.md, and .esi-sync.json
    if [ -n "$ACTIVE_PILOT_ID" ]; then
        local creds_file="$CREDENTIALS_DIR/$ACTIVE_PILOT_ID.json"
        if [ -f "$creds_file" ] && [ -x "$PROJECT_DIR/scripts/aria-esi-sync.py" ]; then
            # Run in background with nohup to survive shell exit
            (nohup uv run --quiet python "$PROJECT_DIR/scripts/aria-esi-sync.py" --quick --quiet >/dev/null 2>&1 &)
        fi
    fi
}

# ───────────────────────────────────────────────────────────────────
# Skill Index Regeneration
# ───────────────────────────────────────────────────────────────────

run_skill_index_update() {
    # Regenerate skill index to pick up any changes to SKILL.md files
    # Runs in background - non-blocking for boot
    local index_script="$PROJECT_DIR/scripts/aria-skill-index.py"
    if [ -f "$index_script" ]; then
        (nohup uv run --quiet python "$index_script" >/dev/null 2>&1 &)
    fi
}

# ───────────────────────────────────────────────────────────────────
# Session Context Assembly
# ───────────────────────────────────────────────────────────────────

run_context_assembly() {
    # Assemble session context from projects (fast, runs synchronously)
    # This generates .session-context.json for conversational awareness
    export ARIA_PILOT_DIR="$ACTIVE_PILOT_DIR"
    export ARIA_PILOT_ID="$ACTIVE_PILOT_ID"
    export ARIA_PILOT="$ACTIVE_PILOT_ID"

    if [ -n "$ACTIVE_PILOT_ID" ] && [ -f "$PROJECT_DIR/scripts/aria-context-assembly.py" ]; then
        uv run --quiet python "$PROJECT_DIR/scripts/aria-context-assembly.py" --quiet 2>/dev/null || true
    fi
}

# ───────────────────────────────────────────────────────────────────
# Parallel Boot Operations
# ───────────────────────────────────────────────────────────────────

run_boot_operations_parallel() {
    # Run security validation, config validation, ESI sync, and context assembly.
    #
    # Strategy:
    # 1. Run artifact integrity verification FIRST (blocking on tampering)
    # 2. Run security validation SECOND (blocking on violations)
    # 3. Start ESI sync in background (longest operation)
    # 4. Run config validation and context assembly in parallel
    #
    # Security violations and artifact tampering block boot entirely.
    # Other issues are warnings.

    # Export pilot info for all operations
    export ARIA_PILOT_DIR="$ACTIVE_PILOT_DIR"
    export ARIA_PILOT_ID="$ACTIVE_PILOT_ID"
    export ARIA_PILOT="$ACTIVE_PILOT_ID"

    # ARTIFACT INTEGRITY: Verify persona artifact hasn't been tampered with
    # This implements SECURITY_001.md Finding #2
    if ! run_artifact_verification; then
        # Tampering detected - these are added to BOOT_ERRORS
        # Return early to let main script handle the error display
        return 1
    fi

    # SECURITY PREFLIGHT: Run security validation (blocking)
    # This implements SECURITY_000.md Quick Win #2
    if ! run_security_validation; then
        # Security violations found - these are added to BOOT_ERRORS
        # Return early to let main script handle the error display
        return 1
    fi

    # Start background operations (non-blocking)
    run_esi_sync
    run_skill_index_update

    # Run config validation and context assembly in parallel
    # Use a subshell and wait to run both concurrently
    {
        run_validation
    } &
    local validation_pid=$!

    {
        # Context assembly (only if pilot exists)
        if [ -n "$ACTIVE_PILOT_ID" ] && [ -f "$PROJECT_DIR/scripts/aria-context-assembly.py" ]; then
            uv run --quiet python "$PROJECT_DIR/scripts/aria-context-assembly.py" --quiet 2>/dev/null || true
        fi
    } &
    local context_pid=$!

    # Wait for both to complete
    wait $validation_pid 2>/dev/null || true
    wait $context_pid 2>/dev/null || true

    return 0
}
