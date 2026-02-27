# Skill Review Prompt

## Setup

Resolve the skill name dynamically from the skill's own SKILL.md, directory name, or manifest — do not hardcode it. If the skill path is ambiguous or passed as an argument, capture it:

```
SKILL_PATH="<path-to-skill>"
```

Then resolve the name:

```
# Prefer the skill's own metadata; fall back to directory name
SKILL_NAME=$(grep -m1 -oP '(?<=^#\s).*' "${SKILL_PATH}/SKILL.md" 2>/dev/null \
  || basename "${SKILL_PATH}")
SKILL_SLUG=$(echo "${SKILL_NAME}" | tr '[:upper:] ' '[:lower:]-' | tr -cd 'a-z0-9-')
RUN_TS=$(date +%Y-%m-%d-%H%M)
REVIEW_DIR="./dev/reviews/${RUN_TS}"
mkdir -p "${REVIEW_DIR}"
```

All output files for this review must be written to `${REVIEW_DIR}/`. Use the timestamp captured at launch — do not regenerate it mid-run.

## Objective

Review the skill at `${SKILL_PATH}` end-to-end and write findings to `${REVIEW_DIR}/${SKILL_SLUG}-review.md`.

**Guiding principle: Shorter skills steer better.** Every instruction, example, and code path must justify its token cost. If something isn't clearly pulling its weight, recommend removal — don't just note it as "could be improved." The default disposition for anything questionable is *cut it*; keeping something requires justification, not the other way around.

## Scope

Read and assess everything the skill ships:

- SKILL.md and any supporting markdown or documentation
- All supporting code (helpers, templates, formatters, scripts)
- MCP integration points (tool calls, data fetching, response handling)
- Context management (how context is built, passed, and constrained)
- Any configuration, manifests, or metadata files

Start by listing the full file tree of the skill directory so the review is comprehensive and nothing is missed.

## Primary Evaluation Axis: Data Grounding Discipline

The #1 failure mode for MCP-backed skills is allowing Claude to fill gaps with training-data recall instead of querying local MCP services for verifiable data. Hallucinated details destroy output quality and user trust. Evaluate specifically:

1. **MCP-first enforcement** — Does the skill explicitly instruct Claude to fetch data from MCP tools before generating content? Are there clear "do not assume/recall" guardrails? Identify any paths where Claude could bypass MCP and fall back to parametric memory.

2. **Prompt hygiene** — Are instructions unambiguous about what must come from MCP vs. what Claude can reasonably infer? Look for vague language that gives Claude wiggle room to hallucinate.

3. **Failure handling** — When MCP data is missing or incomplete, does the skill instruct Claude to surface the gap transparently rather than silently confabulate?

4. **Context window efficiency** — Is retrieved MCP data being injected cleanly? Identify specific redundancies, over-fetching, or prompt sections that consume tokens without proportionally improving output. For each, state whether it should be trimmed, restructured, or removed entirely.

If the skill under review does not use MCP, note this and reframe the grounding axis around whatever its primary data sources are (files, APIs, user input, etc.). The principle is the same: fetched data over recalled data.

## Secondary Axes

### Dead Weight and Noise

Actively look for content that should be **removed or consolidated**, not just improved. This includes:

- Dead code paths (unreachable branches, commented-out blocks, unused helpers)
- Redundant instructions that say the same thing in different ways (dilutes steering)
- Defensive prompt language that addresses failure modes that can't actually occur
- Overly verbose examples where a terse one would steer equally well
- Any section where removing it would NOT degrade output quality
- Vestigial references to renamed or removed components

Flag each with a clear **REMOVE** or **CONSOLIDATE** recommendation, not just a note.

### Code Quality

- Modularity and maintainability
- Prompt structure and clarity (would a fresh Claude Code instance follow this reliably on first read?)
- Edge cases and robustness

## Output Format

Write the review to `${REVIEW_DIR}/${SKILL_SLUG}-review.md` with the following sections:

### 1. Executive Summary
2–3 sentences. Lead with the most important finding. State the resolved skill name and path.

### 2. Grounding Discipline Scorecard
Rate each of the 4 grounding items 🟢 / 🟡 / 🔴 with a brief explanation.

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | | |
| Prompt hygiene | | |
| Failure handling | | |
| Context window efficiency | | |

If the skill is not MCP-backed, adapt the row labels to match its actual data source pattern and note the substitution.

### 3. Reduction Inventory
A flat list of every file, section, or block recommended for removal or significant trimming. For each entry:
- File path and line range
- What it is
- Recommendation: **REMOVE** or **CONSOLIDATE**
- Estimated token savings (rough is fine)

Bias toward removal. This section should be non-empty — every skill has fat to cut.

### 4. Specific Findings
Detailed findings with file paths and line references. Group by severity.

### 5. Prioritized Recommendations
Ordered by impact. Lead with the changes that most improve grounding discipline or most reduce noise. For each, state whether the action is *add*, *modify*, or **remove**.

## File Persistence

All artifacts from this run live in `${REVIEW_DIR}/`:

```
${REVIEW_DIR}/
├── ${SKILL_SLUG}-review.md    # Primary review document
└── raw-notes.md               # (Optional) Working notes if the review is complex
```

Do not overwrite files from previous runs. Each run is immutable once written.
