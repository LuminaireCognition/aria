---
name: proposal
description: Implementation readiness review for proposals
target_type: proposal
target_required: true
variables:
  PROPOSAL_PATH:
    description: Path to the proposal markdown file
    source: argument
    resolve_hint: >
      If the argument is a bare name (e.g., "CONTEXT_EFFICIENCY_PROPOSAL"),
      search dev/proposals/ for a file matching that name with .md extension.
      Resolve to the first match found.
  PROPOSAL_SLUG:
    description: Filesystem-safe identifier for output files
    source: resolve
    resolve_from: >
      Take the basename of {{PROPOSAL_PATH}} without extension, lowercase it,
      replace spaces and special characters with hyphens.
  RUN_TS:
    description: Timestamp of analysis launch
    source: static
    value: "$(date +%Y-%m-%d-%H%M)"
  REVIEW_DIR:
    description: Output directory for this run
    source: static
    value: "./dev/reviews/{{RUN_TS}}"
---

# Proposal Implementation Readiness Review

## Setup

```bash
mkdir -p "{{REVIEW_DIR}}"
```

Write findings to `{{REVIEW_DIR}}/{{PROPOSAL_SLUG}}-proposal-readiness.md`.

## Scope

- Proposal: `{{PROPOSAL_PATH}}`

Read the full proposal before producing any output.

## Goal

Determine whether a capable AI coding agent with full codebase access could
implement this proposal in 1-2 iterations with minimal ambiguity.

## Calibration

What the implementing agent CAN do without specification:
- Read existing code and follow established patterns
- Write method bodies from a signature, docstring, and behavioral contract
- Write SQL/queries from table schemas and stated intent
- Handle standard edge cases (null, empty, type errors) unless the correct
  behavior is genuinely non-obvious for the domain
- Write test implementations from a test matrix (name + what it proves)
- Perform mechanical migrations ("replace constant X with registry call Y")

What the implementing agent CANNOT do without specification:
- Choose between meaningfully different architectural approaches
- Know which behavioral changes are intentional vs. accidental
- Decide migration ordering when phases have implicit dependencies
- Resolve domain-specific ambiguity (e.g., "should this include tank skills?")

## Standards

- Be strict on AMBIGUITY — flag cases where multiple valid interpretations
  lead to meaningfully different implementations.
- Be lenient on COMPLETENESS — do not penalize missing detail that the agent
  can infer from the codebase or from standard engineering practice.
- Treat missing DECISIONS as defects. Do not treat missing CODE as a defect.
- If you infer intent, label it explicitly as inference.

### Proposal format expectations (STP style)

- Proposals should define signatures, contracts, and decisions — not method bodies.
- Full implementations in the proposal are acceptable as illustrative examples
  but should not be required for readiness.
- A proposal that specifies `resolve_skill_ids(names: list[str]) -> dict[str, int]`
  with error semantics and preconditions is READY even without the SQL query body.

## Deliverables

Write to `{{REVIEW_DIR}}/{{PROPOSAL_SLUG}}-proposal-readiness.md` with these
sections in this exact order:

### 1. Ship Decision
- `READY` or `NOT READY`
- One-sentence rationale.

### 2. Blockers (max 5, ranked by severity)
- Issues where the implementing agent would have to GUESS between meaningfully
  different outcomes. Only include issues that, if guessed wrong, cause incorrect
  behavior, regressions, or blocked implementation.
- For each item:
  - Severity: `Critical` (wrong guess causes bugs) or `Major` (wrong guess
    causes rework but not incorrect behavior)
  - Location: section heading or quoted phrase from proposal
  - The ambiguity: what are the multiple valid interpretations?
  - The decision needed: what must the proposal author clarify?

### 3. Specification Gaps
- Missing behavioral contracts that the agent cannot infer from the codebase:
  - Undocumented error semantics (what exception, when?)
  - Unclear return type or ordering guarantees
  - Missing decision records (why approach A over B?)
  - Implicit phase dependencies not stated
- Do NOT flag:
  - Standard null/empty handling
  - Threading behavior that follows existing module patterns
  - Implementation details derivable from function signatures
  - Edge cases with obviously correct handling

### 4. Test Coverage Assessment
- Does the proposal's test matrix cover the stated behavioral contracts?
- Identify UNTESTED CONTRACTS, not missing test code.
- A test matrix entry like `test_missing_name_raises | SDEResolutionError on
  unknown skill` is sufficient — the agent writes the implementation.

### 5. Readiness Checklist
- Max 10 items. Checkbox list of what must be true before implementation starts.
- Each item should be a concrete, verifiable condition.
- Prioritize by: blocks implementation > causes bugs > causes rework.

## Exclusions

Do NOT include:
- Proposed edits or replacement text (the proposal author fixes blockers)
- Full test plans, test code, or fixture implementations
- Edge cases with domain-obvious handling
- Implementation suggestions for code that follows existing patterns
- Commentary on proposal length, style, or organization

## Review Constraints

- Do not invent architecture beyond what is necessary to remove ambiguity.
- Do not rewrite the whole proposal.
- Prefer precise, actionable corrections over broad advice.
- If no issues exist in a category, explicitly say `None found`.
- Total review output should be concise — aim for signal density over coverage.
