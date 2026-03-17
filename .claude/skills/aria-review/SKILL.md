---
name: aria-review
description: Run standardized review prompts against skills, codebases, and other targets. Use when the user wants to audit, review, or analyze a skill or code directory using a named review template. Supports individual targets and ALL for batch execution.
category: system
triggers:
  - "/aria-review"
  - "review skill"
  - "audit skill"
  - "run skill review"
  - "review all skills"
requires_pilot: false
data_sources: []
argument-hint: "<template> <target|ALL>"
disable-model-invocation: true
---

# aria-review Dispatcher

You are a review dispatcher. You parse commands, resolve template variables, and execute review prompts. You contain **zero** review logic — all analysis criteria live in the templates.

## Command Format

```
/aria-review <prompt-name> <target>
/aria-review skill-review mission-brief
/aria-review skill-review ALL
```

## Dispatch Sequence

### Step 1 — Parse the command

Extract `prompt-name` and `target` from the user's input.

If either is missing, read `catalog.md` (in this skill's directory: `.claude/skills/aria-review/catalog.md`) and present available prompts with descriptions so the user can choose.

### Step 2 — Catalog lookup

Read `.claude/skills/aria-review/catalog.md`. Find the entry matching `prompt-name`. If no match, list available prompts and ask the user to clarify.

### Step 3 — Read the template

Load the template file from the catalog entry's **Template** path (relative to this skill's directory, e.g., `.claude/skills/aria-review/prompts/skill-review.md`). Parse the YAML front-matter to understand the variable contract.

### Step 4 — Load references

If the template front-matter contains a `references` list, read each file before proceeding. These provide the evaluation framework (e.g., ADR decisions, migration guides) that the template's criteria are built against. Treat them as read-only context — do not modify.

### Step 5 — Read shared conventions

Load `.claude/skills/aria-review/lib/conventions.md` for persistence rules and output standards that apply to all reviews.

### Step 6 — Resolve variables

Process each variable declared in the template's front-matter, in dependency order:

| Source type | How to resolve |
|-------------|----------------|
| `argument` | Parse from the user's target argument. If a bare name, search `.claude/skills/` for a matching directory containing SKILL.md. Use `resolve_hint` for guidance. |
| `resolve` | Read the `resolve_from` hint and execute it. May involve reading files, inspecting metadata, or listing directories. Reference already-resolved variables via `{{VAR}}` syntax. |
| `static` | Evaluate the expression. May reference other resolved variables via `{{VAR}}`. |

Resolution order: `argument` variables first, then `resolve` in declared order, then `static`.

### Step 7 — Handle ALL

If `target` is `ALL`:

1. Read the template's `target_type` from front-matter to know what to scan for.
2. Discover all matching targets (for `target_type: skill`, find all directories under `.claude/skills/` containing a SKILL.md, excluding this skill itself).
3. Capture `RUN_TS` once for the entire batch.
4. Execute the template once per target, each writing to its own file within the shared `REVIEW_DIR`.
5. After all reviews complete, write `${REVIEW_DIR}/index.md` summarizing all findings.

### Step 8 — Execute

Follow the fully rendered prompt. Write results to the paths specified by the resolved variables.

## Rules

- Do not embed review logic here. This file is the dispatcher only.
- Read the template front-matter before resolving anything.
- Capture `RUN_TS` exactly once per invocation, at the start. Never regenerate mid-run.
- Never overwrite files from previous runs. Each run produces an immutable timestamped directory.
- `{{VARIABLE}}` syntax is a convention for Claude to recognize and replace — not a language to parse. Substitute resolved values wherever you see `{{VAR_NAME}}` in the template body.
