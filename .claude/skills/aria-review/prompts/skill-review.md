---
name: skill-review
description: End-to-end audit of a Claude Code skill with grounding discipline focus
target_type: skill
target_required: true
references:
  - dev/decisions/ADR-006-skill-context-ownership.md
  - dev/docs/SKILL_MIGRATION_GUIDE.md
variables:
  SKILL_PATH:
    description: Absolute or relative path to the skill directory
    source: argument
    resolve_hint: >
      If the argument is a bare name (e.g., "mission-brief") rather than a path,
      search .claude/skills/ for a directory matching that name.
      Resolve to the first directory found that contains a SKILL.md.
  SKILL_NAME:
    description: Human-readable skill name
    source: resolve
    resolve_from: >
      Read {{SKILL_PATH}}/SKILL.md. Extract the 'name' field from YAML front-matter.
      If no front-matter, use the first H1 heading (# ...).
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

# Skill Review

## Setup

```bash
mkdir -p "{{REVIEW_DIR}}"
```

Write findings to `{{REVIEW_DIR}}/{{SKILL_SLUG}}-skill-review.md`.

**Guiding principle: Shorter skills steer better.** Every instruction, example, and code path must justify its token cost. If something isn't clearly pulling its weight, recommend removal — don't just note it as "could be improved." The default disposition for anything questionable is *cut it*; keeping something requires justification, not the other way around.

## Scope

Read and assess everything the skill ships at `{{SKILL_PATH}}`:

- SKILL.md and any supporting markdown or documentation
- All supporting code (helpers, templates, formatters, scripts)
- MCP integration points (tool calls, data fetching, response handling)
- Context management (how context is built, passed, and constrained)
- Any configuration, manifests, or metadata files

Start by listing the full file tree of the skill directory so the review is comprehensive and nothing is missed.

## Primary Evaluation Axis: Data Grounding Discipline

The #1 failure mode for MCP-backed skills is allowing Claude to fill gaps with training-data recall instead of querying MCP services for verifiable data. Hallucinated details destroy output quality and user trust. Evaluate:

1. **MCP-first enforcement** — Does the skill instruct Claude to fetch data from MCP tools before generating content? Are there "do not assume/recall" guardrails? Identify paths where Claude could bypass MCP and fall back to parametric memory.

2. **Prompt hygiene** — Are instructions unambiguous about what must come from MCP vs. what Claude can infer? Look for vague language that gives wiggle room to hallucinate.

3. **Failure handling** — When MCP data is missing or incomplete, does the skill instruct Claude to surface the gap transparently rather than silently confabulate?

4. **Context window efficiency** — Is MCP data injected cleanly? Identify redundancies, over-fetching, or prompt sections that consume tokens without proportionally improving output. For each, state whether it should be trimmed, restructured, or removed entirely.

If the skill does not use MCP, note this and reframe the axis around its actual data sources. The principle is the same: fetched data over recalled data.

## Secondary Axes

### Dead Weight and Noise

Apply the ownership rules and named patterns (A–G) from the loaded references. Actively look for content that should be removed or consolidated:

- **(A)** Inlined reference data that duplicates declared `prerequisite_files`
- **(B)** Duplicated CLAUDE.md behaviors (pilot resolution, persona loading, MCP usage)
- **(C)** Skill-specific protocols stranded in CLAUDE.md (flag for move-in)
- **(D)** "Why X?" justification prose adjacent to protocols
- **(E)** ASCII flowcharts convertible to numbered lists
- **(F)** Checkbox-style checklists convertible to imperative steps
- **(G)** Duplicate sections within the same file
- Dead code paths (unreachable branches, commented-out blocks, unused helpers)
- Redundant instructions that say the same thing in different ways
- Defensive prompt language addressing failure modes that can't actually occur
- Overly verbose examples where a terse one would steer equally well
- Any section where removing it would NOT degrade output quality
- Vestigial references to renamed or removed components

Flag each with **REMOVE** or **CONSOLIDATE**, not just a note.

### Code Quality

- Modularity and maintainability
- Prompt structure and clarity (would a fresh Claude Code instance follow this reliably on first read?)
- Edge cases and robustness

## Output Format

Write to `{{REVIEW_DIR}}/{{SKILL_SLUG}}-skill-review.md` with these sections:

### 1. Executive Summary
2-3 sentences. Lead with the most important finding. State the resolved skill name and path.

### 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | | |
| Prompt hygiene | | |
| Failure handling | | |
| Context window efficiency | | |

Rate each 🟢 / 🟡 / 🔴. If the skill isn't MCP-backed, adapt row labels to match its actual data source pattern and note the substitution.

### 3. Reduction Inventory
Flat list of every file, section, or block recommended for removal or trimming. Each entry:
- File path and line range
- What it is
- **REMOVE** or **CONSOLIDATE**
- Estimated token savings (rough is fine)

This section must be non-empty — every skill has fat to cut.

### 4. Specific Findings
Detailed findings with file paths and line references. Group by severity.

### 5. Prioritized Recommendations
Ordered by impact. Lead with changes that most improve grounding or reduce noise. Each labeled add, modify, or **remove**.
