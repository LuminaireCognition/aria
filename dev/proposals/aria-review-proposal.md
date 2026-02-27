# aria-review: Implementation Proposal

## What This Is

A Claude Code skill that maintains a library of standardized review prompts and dispatches them against targets (skills, codebases, files). The user invokes it as:

```
/aria-review <prompt-name> <target>
/aria-review skill-review mission-brief
/aria-review skill-review ALL
```

Claude is the template engine. There is no Jinja2, no Python renderer, no build step. Templates declare their variable contracts in YAML front-matter, Claude reads the contracts, resolves the variables dynamically, and executes the rendered prompt.

---

## Directory Structure

Create this under the project's skill directory:

```
aria-review/
├── SKILL.md                        # Dispatcher: command parsing, orchestration
├── catalog.md                      # Prompt registry — maps names to templates
├── prompts/
│   └── skill-review.md             # First template: skill audit
└── lib/
    └── conventions.md              # Shared output rules (persistence, formatting)
```

Four concerns, four files (plus the template). Each has a single responsibility.

---

## File 1: SKILL.md

This is the dispatcher. It handles command parsing and orchestration. It contains **zero** review logic — all analysis criteria live in the templates.

### Front-matter

```yaml
---
name: aria-review
description: >
  Run standardized review prompts against skills, codebases, and other targets.
  Use when the user wants to audit, review, or analyze a skill or code directory
  using a named review template. Supports individual targets and ALL for batch execution.
---
```

### Content

The SKILL.md must instruct Claude to follow this exact dispatch sequence:

**Step 1 — Parse the command.** Extract `prompt-name` and `target` from the user's input. If either is missing, read `catalog.md` and present available prompts with descriptions so the user can choose.

**Step 2 — Catalog lookup.** Read `catalog.md` in the skill's directory. Find the entry matching `prompt-name`. If no match exists, list available prompts and ask the user to clarify.

**Step 3 — Read the template.** Load `prompts/<prompt-name>.md`. Parse the YAML front-matter to understand the variable contract.

**Step 4 — Read shared conventions.** Load `lib/conventions.md` for persistence rules and output standards that apply to all reviews.

**Step 5 — Resolve variables.** Process each variable declared in the template's front-matter, in dependency order:

| Source type | Meaning | How to resolve |
|-------------|---------|----------------|
| `argument` | Supplied by the user's target argument | Parse from the command. If the argument is a bare name rather than a path, search common skill locations to find a match. |
| `resolve` | Derived dynamically | Read the `resolve_from` hint and use judgment. This may involve reading files, inspecting metadata, or listing directories. |
| `static` | Fixed expression | Evaluate the expression. May reference other already-resolved variables using `{{VAR}}` syntax. |

**Step 6 — Handle ALL.** If `target` is `ALL`:
1. Read the template's `target_type` from front-matter to know what to scan for.
2. Discover all matching targets (e.g., for `target_type: skill`, find all directories containing a SKILL.md).
3. Capture `RUN_TS` once for the entire batch.
4. Execute the template once per target, each writing to its own file within the shared `REVIEW_DIR`.
5. After all reviews complete, write `${REVIEW_DIR}/index.md` summarizing all findings.

**Step 7 — Execute.** Follow the fully rendered prompt. Write results to the paths specified by the resolved variables.

### Key rules to state in SKILL.md

- Do not embed review logic here. This file is the dispatcher only.
- Read the template front-matter before resolving anything.
- Capture `RUN_TS` exactly once per invocation, at the start. Never regenerate mid-run.
- Never overwrite files from previous runs. Each run produces an immutable timestamped directory.

---

## File 2: catalog.md

This is the routing layer. The dispatcher reads it to map prompt names to template files. It is the only file that changes when a new template is added.

### Format

```markdown
# aria-review Prompt Catalog

This file is the single source of truth for available review templates.
The dispatcher reads this to route commands.

---

## skill-review

- **Template**: `prompts/skill-review.md`
- **Description**: End-to-end skill audit. Primary focus on data grounding
  discipline (MCP-first enforcement, prompt hygiene, failure handling,
  context efficiency). Secondary focus on dead weight identification
  with a bias toward removal. Produces a reduction inventory with
  estimated token savings.
- **Target type**: `skill` (a directory containing SKILL.md)
- **Arguments**: `<skill-path-or-name>` or `ALL`
- **Examples**:
  - `/aria-review skill-review mission-brief`
  - `/aria-review skill-review /path/to/skills/mission-brief`
  - `/aria-review skill-review ALL`

---

<!-- To add a new template:
     1. Create prompts/<name>.md with YAML front-matter and prompt body
     2. Add an entry here following the format above
     3. Done — SKILL.md does not need to change -->
```

### Extensibility contract

Adding a new review type requires exactly two touches:
1. Create `prompts/<name>.md` with front-matter and body.
2. Add an entry to `catalog.md`.

SKILL.md never changes for new templates.

---

## File 3: lib/conventions.md

Shared rules that apply to every review template. The dispatcher injects these; templates should not duplicate them.

### Content to include

**Persistence rules:**
- Base path: `./dev/reviews/`
- Run directory: `./dev/reviews/${RUN_TS}/` where `RUN_TS` is `%Y-%m-%d-%H%M`, captured once at launch
- File naming: `${TARGET_SLUG}-<template-name>.md` (e.g., `mission-brief-skill-review.md`)
- Immutability: never overwrite or modify files from previous runs

**Batch run rules (ALL):**
- All targets share a single `RUN_TS` and `REVIEW_DIR`
- Each target gets its own review file within the shared directory
- After all individual reviews, write `${REVIEW_DIR}/index.md` containing: run metadata, a table of all targets with top-level findings, cross-cutting themes, and broadly applicable recommendations

**Output standards:**
- Executive summary first: every review opens with 2–3 sentences on the most important finding
- File paths and line references required: "The prompt could be clearer" is not a finding; "Lines 42–58 of SKILL.md repeat the MCP-first instruction from lines 12–15" is
- Actionable recommendations: every finding ends with a concrete action — add, modify, or **remove**. "Consider improving" is not an action.
- Bias toward removal: when uncertain whether something earns its token cost, recommend removal. Keeping requires justification.

**Timestamp discipline:**
- Capture `RUN_TS=$(date +%Y-%m-%d-%H%M)` once at the very start
- Use this value everywhere; do not call `date` again mid-run

---

## File 4: prompts/skill-review.md

The first template. This is a complete, self-contained review prompt with a YAML front-matter variable contract.

### Front-matter contract

```yaml
---
name: skill-review
description: End-to-end audit of a Claude Code skill with grounding discipline focus
target_type: skill
target_required: true
variables:
  SKILL_PATH:
    description: Absolute or relative path to the skill directory
    source: argument
    resolve_hint: >
      If the argument is a bare name (e.g., "mission-brief") rather than a path,
      search common skill locations: ./skills/, /mnt/skills/, and the project root.
      Resolve to the first directory found that contains a SKILL.md.
  SKILL_NAME:
    description: Human-readable skill name
    source: resolve
    resolve_from: >
      Read {{SKILL_PATH}}/SKILL.md. Use the first H1 heading (# ...) as the name.
      If no H1 exists, check YAML front-matter for a 'name' field.
      Fall back to the directory basename of {{SKILL_PATH}}.
  SKILL_SLUG:
    description: Filesystem-safe identifier for output files
    source: resolve
    resolve_from: >
      Take {{SKILL_NAME}}, lowercase it, replace spaces and special characters
      with hyphens, strip anything that isn't a-z, 0-9, or hyphen.
  RUN_TS:
    description: Timestamp of analysis launch
    source: static
    value: "$(date +%Y-%m-%d-%H%M)"
  REVIEW_DIR:
    description: Output directory for this run
    source: static
    value: "./dev/reviews/{{RUN_TS}}"
---
```

Note: `SKILL_NAME` is resolved dynamically from the target's own metadata. It is never hardcoded and never passed as an argument.

### Prompt body

The body uses `{{VARIABLE}}` placeholders throughout. After resolution, it becomes the prompt Claude executes. The body must contain:

**Guiding principle** (stated up front, before any analysis):
> Shorter skills steer better. Every instruction, example, and code path must justify its token cost. If something isn't clearly pulling its weight, recommend removal — don't just note it as "could be improved." The default disposition for anything questionable is *cut it*; keeping something requires justification, not the other way around.

**Setup:** `mkdir -p "{{REVIEW_DIR}}"` and state the output file path.

**Scope:** Read and assess everything the skill ships at `{{SKILL_PATH}}`: SKILL.md and documentation, all supporting code, MCP integration points, context management, configuration and metadata. Start by listing the full file tree so nothing is missed.

**Primary evaluation axis — Data grounding discipline:**

The #1 failure mode for MCP-backed skills is allowing Claude to fill gaps with training-data recall instead of querying MCP services for verifiable data. Evaluate these four areas:

1. **MCP-first enforcement** — Does the skill instruct Claude to fetch data from MCP tools before generating content? Are there "do not assume/recall" guardrails? Identify paths where Claude could bypass MCP and fall back to parametric memory.

2. **Prompt hygiene** — Are instructions unambiguous about what must come from MCP vs. what Claude can infer? Look for vague language that gives wiggle room to hallucinate.

3. **Failure handling** — When MCP data is missing or incomplete, does the skill instruct Claude to surface the gap transparently rather than silently confabulate?

4. **Context window efficiency** — Is MCP data injected cleanly? Identify redundancies, over-fetching, or prompt sections that consume tokens without proportionally improving output. For each, state whether it should be trimmed, restructured, or removed entirely.

If the skill does not use MCP, note this and reframe the axis around its actual data sources. The principle is the same: fetched data over recalled data.

**Secondary axis — Dead weight and noise:**

Actively look for content that should be removed or consolidated:
- Dead code paths (unreachable branches, commented-out blocks, unused helpers)
- Redundant instructions that say the same thing in different ways
- Defensive prompt language addressing failure modes that can't actually occur
- Overly verbose examples where a terse one would steer equally well
- Any section where removing it would NOT degrade output quality
- Vestigial references to renamed or removed components

Flag each with **REMOVE** or **CONSOLIDATE**, not just a note.

**Secondary axis — Code quality:**
- Modularity and maintainability
- Prompt structure and clarity (would a fresh Claude Code instance follow this reliably on first read?)
- Edge cases and robustness

**Output format** (sections in the review file):

1. **Executive Summary** — 2–3 sentences, lead with the most important finding. State the resolved skill name and path.

2. **Grounding Discipline Scorecard** — Table rating each of the 4 grounding items 🟢 / 🟡 / 🔴 with explanation. Adapt row labels if the skill isn't MCP-backed.

3. **Reduction Inventory** — Flat list of every file/section/block recommended for removal or trimming. Each entry: file path and line range, what it is, **REMOVE** or **CONSOLIDATE**, estimated token savings. This section must be non-empty.

4. **Specific Findings** — Detailed findings with file paths and line references, grouped by severity.

5. **Prioritized Recommendations** — Ordered by impact. Lead with changes that most improve grounding or reduce noise. Each labeled add, modify, or **remove**.

---

## Design Decisions

These are the key choices and their rationale, for context during implementation.

**Claude as the template engine.** Templates declare contracts; Claude resolves them. This is more powerful than string interpolation (Claude can read files, search directories, make fallback decisions) and has zero dependencies.

**`{{VARIABLE}}` syntax instead of `${VAR}`.** Visual distinction from bash variables prevents confusion when templates contain bash snippets. This is a convention for Claude to recognize and replace, not a language to parse.

**YAML front-matter as the contract.** Self-documenting, readable as raw markdown, no separate schema file. The `resolve_from` hints are natural language instructions for Claude, not code.

**Catalog as a separate file.** Keeps the dispatcher (SKILL.md) stable. New templates never require dispatcher changes. The catalog is the only file that knows what exists.

**Conventions extracted to lib/.** Prevents duplication across templates. Persistence rules, formatting standards, and timestamp discipline live in one place.

**No validation layer.** A malformed template fails at Claude runtime, not at a compile step. This is an acceptable tradeoff for zero machinery. Claude will surface errors clearly when it reads a broken front-matter contract.

---

## Implementation Sequence

Build in this order:

1. **Create the directory structure** — `aria-review/`, `prompts/`, `lib/`
2. **Write `lib/conventions.md`** — shared rules first, since everything references them
3. **Write `prompts/skill-review.md`** — the first template, with full front-matter and body
4. **Write `catalog.md`** — register the skill-review template
5. **Write `SKILL.md`** — the dispatcher, referencing catalog and conventions
6. **Test against a real skill** — run `/aria-review skill-review <some-skill>` and verify the full flow: dispatch → resolve → execute → persist
7. **Test ALL** — run against multiple skills and verify index generation

---

## Future Templates

These are planned but not part of the initial implementation. Listing them here to validate that the architecture accommodates them without dispatcher changes:

- `code-audit` — Pure code quality review targeting any directory or file
- `prompt-audit` — Analyzes prompt text for steering efficiency and token waste
- `mcp-audit` — Focused review of MCP integration patterns across a project

Each requires only: a new `prompts/<name>.md` and a new entry in `catalog.md`.
