#!/usr/bin/env bash
# skill-enforcer.sh — UserPromptSubmit hook
#
# When a prompt starts with /<skill-name>, clears the stale skill-gate
# marker and injects additionalContext requiring the Skill tool first.
# Non-slash prompts: no-op. The PreToolUse gate handles enforcement.

set -euo pipefail

input="$(cat)"

read -r prompt < <(echo "$input" | python3 -c "import json,sys; print(json.load(sys.stdin).get('prompt',''))")
read -r session_id < <(echo "$input" | python3 -c "import json,sys; print(json.load(sys.stdin).get('session_id',''))")

if [[ "$prompt" =~ ^/([a-z][a-z0-9-]*) ]]; then
    skill_name="${BASH_REMATCH[1]}"

    # Clear stale marker so the Skill tool's PreToolUse re-creates it fresh
    if [[ -n "$session_id" && "$session_id" != "null" ]]; then
      rm -f "/tmp/claude-skill-gate-${session_id}"
    fi

    jq -n --arg skill "$skill_name" '{
      hookSpecificOutput: {
        hookEventName: "UserPromptSubmit",
        additionalContext: ("SKILL ENFORCEMENT: The user invoked /\($skill). You MUST call the Skill tool with skill=\"\($skill)\" BEFORE using any other tool (Read, Glob, Grep, MCP, etc). Do NOT bypass the Skill tool by reading skill files directly. This is a blocking requirement from the skill-enforcer hook.")
      }
    }'
else
    echo '{}'
fi
