#!/bin/bash
# UserPromptSubmit hook: reset skill-gate marker at start of each turn.
# This ensures the skill gate is re-evaluated per turn, not per session.
INPUT=$(cat)
SID=$(echo "$INPUT" | jq -r '.session_id // empty')
if [[ -n "$SID" && "$SID" != "null" ]]; then
  rm -f "/tmp/claude-skill-gate-${SID}"
fi
exit 0
