# aria-review Shared Conventions

These rules apply to every review template. The dispatcher loads this file once per invocation. Templates must not duplicate these rules.

## Persistence

- **Base path:** `./dev/reviews/`
- **Run directory:** `./dev/reviews/${RUN_TS}/` where `RUN_TS` is `%Y-%m-%d-%H%M`, captured once at launch
- **File naming:** `${TARGET_SLUG}-<template-name>.md` (e.g., `mission-brief-skill-review.md`)
- **Immutability:** Never overwrite or modify files from previous runs. Each run produces an immutable timestamped directory.

## Batch Runs (ALL)

When target is `ALL`:

1. All targets share a single `RUN_TS` and `REVIEW_DIR`
2. Each target gets its own review file within the shared directory
3. After all individual reviews, write `${REVIEW_DIR}/index.md` containing:
   - Run metadata (timestamp, template used, target count)
   - Table of all targets with top-level findings
   - Cross-cutting themes
   - Broadly applicable recommendations

## Output Standards

- **Executive summary first:** Every review opens with 2-3 sentences on the most important finding
- **File paths and line references required:** "The prompt could be clearer" is not a finding; "Lines 42-58 of SKILL.md repeat the MCP-first instruction from lines 12-15" is
- **Actionable recommendations:** Every finding ends with a concrete action — add, modify, or **remove**. "Consider improving" is not an action.
- **Bias toward removal:** When uncertain whether something earns its token cost, recommend removal. Keeping requires justification.

## Timestamp Discipline

- Capture `RUN_TS=$(date +%Y-%m-%d-%H%M)` once at the very start of the invocation
- Use this value everywhere — do not call `date` again mid-run
- For batch runs, capture once before the first target
