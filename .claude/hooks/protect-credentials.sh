#!/bin/bash
# Block Bash commands that read credential files
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if echo "$COMMAND" | grep -qE '\.(env|env\.local)\b|userdata/credentials/'; then
  echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Credential file access blocked by hook"}}'
  exit 0
fi

exit 0
