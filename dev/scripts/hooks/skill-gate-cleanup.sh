#!/bin/bash
# SessionEnd hook: clean up skill-gate marker file.
INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty')
if [[ -n "$SESSION_ID" && "$SESSION_ID" != "null" ]]; then
  rm -f "/tmp/claude-skill-gate-${SESSION_ID}"
fi
exit 0
