# AI Runtime Instructions

These documents are read by the LLM (Claude) during ARIA sessions. They are **not intended for human readers** during normal use — they contain rules and protocols that guide ARIA's behavior.

They are referenced by `CLAUDE.md` and loaded into the AI's context at session start.

## Why These Are Separate

These files were originally in `docs/` alongside user guides. They've been moved here because:

1. Users browsing `docs/` don't need to see AI behavior rules
2. Developers modifying these files should understand they affect AI behavior, not user-facing documentation
3. Clear separation prevents accidental edits that could change ARIA's runtime behavior
