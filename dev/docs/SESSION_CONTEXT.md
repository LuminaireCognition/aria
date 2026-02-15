# Session Context Protocol

At session start, ARIA automatically loads conversational context from active projects. This enables natural references like "the new corp" without explicit file paths.

## How It Works

1. **Boot hook runs** `aria-context-assembly.py`
2. **Script generates** `.session-context.json` in the pilot directory
3. **ARIA reads** this file for project awareness

## What ARIA Should Do

**At session start (after reading pilot profile):**
1. Read `.session-context.json` from `userdata/pilots/{active_pilot}/`
2. Note active projects and their aliases
3. Recognize natural language references during conversation

## Session Context File Structure

```json
{
  "active_projects": [
    {
      "name": "Horadric Acquisitions",
      "file": "horadric-acquisitions.md",
      "status": "Planning",
      "phase": "Phase 1: Prerequisites",
      "aliases": ["the new corp", "corp project"],
      "summary": "Establish player corporation in New Eden",
      "next_steps": ["Train Corporation Management I", "Accumulate 1.6M ISK"]
    }
  ],
  "alias_map": {
    "the new corp": "Horadric Acquisitions",
    "corp project": "Horadric Acquisitions"
  }
}
```

## Conversational Awareness

When a capsuleer references a project by alias:
- "How's the new corp coming along?" → Look up "the new corp" in alias_map → Horadric Acquisitions
- "What's next for corp project?" → Same mapping

**If no match found:** Ask for clarification naturally.

## Adding Aliases to Projects

Project files support an `**Aliases:**` field:

```markdown
# Project: Horadric Acquisitions

**Status:** Planning
**Aliases:** the new corp, corp project, horadric
**Target:** Found player corporation
```

Aliases are case-insensitive and parsed at boot.
