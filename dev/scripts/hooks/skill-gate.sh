#!/bin/bash
# PreToolUse hook: block data tool calls until the Skill tool has been invoked.
#
# Marker: /tmp/claude-skill-gate-{session_id}
#   Created by Phase 1 when the Skill tool fires.
#   Cleared per-turn by skill-gate-cleanup-turn.sh (UserPromptSubmit).
#   Cleared on exit by skill-gate-cleanup.sh (SessionEnd).
INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty')

if [[ -z "$SESSION_ID" || "$SESSION_ID" == "null" ]]; then
  exit 0
fi

MARKER="/tmp/claude-skill-gate-${SESSION_ID}"

# Phase 1: Record Skill tool invocation
if [[ "$TOOL_NAME" == "Skill" ]]; then
  touch "$MARKER"
  exit 0
fi

# Phase 2: Always allow read-only and schema-resolution tools
case "$TOOL_NAME" in
  Read|Glob|Grep|ToolSearch|WebFetch|WebSearch) exit 0 ;;
esac

# Phase 3: If Skill marker exists, allow everything
if [[ -f "$MARKER" ]]; then
  exit 0
fi

# Phase 4: Block data tools — Skill not yet invoked
case "$TOOL_NAME" in
  Bash)
    COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
    if echo "$COMMAND" | grep -qE '(uv run )?aria-esi\b'; then
      # Exempt disable-model-invocation skills (load inline via /command)
      if echo "$COMMAND" | grep -qE 'watchlist-|journal|sync-wars'; then
        exit 0
      fi
      # Build skill hint based on CLI subcommand
      HINT=""
      if echo "$COMMAND" | grep -qE '\bskills\b'; then
        HINT=" Try /skillqueue, /fit-check, /ship-next, or /isk-compare."
      elif echo "$COMMAND" | grep -qE '\bstandings\b'; then
        HINT=" Try /standings."
      elif echo "$COMMAND" | grep -qE '\bwallet\b'; then
        HINT=" Try /fit-check, /fit-budget, or /ship-next."
      elif echo "$COMMAND" | grep -qE '\bclones\b'; then
        HINT=" Try /clones."
      fi
      echo "SKILL-GATE-BLOCK: Invoke the Skill tool for the relevant skill before using aria-esi CLI.${HINT}" >&2
      exit 2
    fi
    exit 0
    ;;
  mcp__aria-universe__fitting)
    # Exempt resolve_names — read-only SDE name lookup, no confabulation risk
    if echo "$INPUT" | jq -r '.tool_input // empty' | grep -q '"resolve_names"'; then
      exit 0
    fi
    echo "SKILL-GATE-BLOCK: Invoke the Skill tool for the relevant skill before calling ${TOOL_NAME}. Try /fit-check or /fit-budget." >&2
    exit 2
    ;;
  mcp__aria-universe__skills)
    echo "SKILL-GATE-BLOCK: Invoke the Skill tool for the relevant skill before calling ${TOOL_NAME}. Try /skillqueue, /ship-next, or /isk-compare." >&2
    exit 2
    ;;
  mcp__aria-universe__market)
    echo "SKILL-GATE-BLOCK: Invoke the Skill tool for the relevant skill before calling ${TOOL_NAME}. Try /fit-check, /fit-budget, /price, or /build-cost." >&2
    exit 2
    ;;
  mcp__*)
    # Exempt resolve_names — read-only SDE name lookup, no confabulation risk
    if echo "$INPUT" | jq -r '.tool_input // empty' | grep -q '"resolve_names"'; then
      exit 0
    fi
    echo "SKILL-GATE-BLOCK: Invoke the Skill tool for the relevant skill before calling ${TOOL_NAME}." >&2
    exit 2
    ;;
  Agent)
    echo "SKILL-GATE-BLOCK: Invoke the Skill tool for the relevant skill before delegating to an Agent." >&2
    exit 2
    ;;
  *)
    exit 0
    ;;
esac
