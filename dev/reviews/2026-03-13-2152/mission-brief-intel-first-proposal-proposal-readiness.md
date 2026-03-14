# Proposal Readiness Review: MISSION_BRIEF_INTEL_FIRST_PROPOSAL

**Reviewed:** 2026-03-13-2152
**Proposal:** `dev/proposals/MISSION_BRIEF_INTEL_FIRST_PROPOSAL.md`

## 1. Ship Decision

**READY** — The proposal is well-scoped, specifies exact frontmatter changes, section gating, and response format for both modes. An implementing agent can execute this with minimal ambiguity.

## 2. Blockers

### 2.1 — "Conditional prerequisites" is a new frontmatter concept with no existing mechanism

- **Severity:** Major
- **Location:** "Move to conditional prerequisites (loaded only when `--fit` is present)" (SKILL.md Changes → Frontmatter)
- **Ambiguity:** The skill-loading system (`personas/_shared/skill-loading.md`, CLAUDE.md § Skill Loading) has no concept of "conditional prerequisites." `injected_prerequisites` are compiled at skill-load time via `!cat` injection — they're baked into the prompt before the agent even sees the arguments. Two valid interpretations:
  1. Introduce a new `conditional_prerequisites` frontmatter key with flag-based gating logic (requires changes to the skill-loading documentation and any tooling that processes frontmatter)
  2. Move the fitting data out of `injected_prerequisites` entirely and add prose instructions in the SKILL.md body telling the agent to `Read` those files only when `--fit` is present (no infrastructure change needed)
- **Decision needed:** Which mechanism? Option 2 is simpler and consistent with how `data_sources` already work (agent-loaded, not injected). Option 1 requires defining the conditional prerequisite contract across the skill system.

### 2.2 — `allowed-tools` gating semantics undefined

- **Severity:** Major
- **Location:** "Update `allowed-tools`: Default: remove `mcp__aria-universe__fitting` from the list"
- **Ambiguity:** `allowed-tools` in frontmatter is a static declaration read at skill load time. The proposal says to conditionally include/exclude `mcp__aria-universe__fitting` based on `--fit`, but doesn't specify _how_. Two interpretations:
  1. Two separate `allowed-tools` lists in frontmatter (no existing precedent for conditional frontmatter values)
  2. Keep `fitting` in `allowed-tools` but rely on prompt instructions to not call it without `--fit` (simpler, but the tool remains technically available)
- **Decision needed:** Should the gating be enforced at the frontmatter/infrastructure level, or is prompt-level instruction sufficient? Given that skill-gate hooks enforce tool access, this has real behavioral implications.

## 3. Specification Gaps

### 3.1 — Spawn Data Guard under intel-only mode

The current Spawn Data Guard (SKILL.md:57-64) says "Proceed directly to fitting" as the fallback. Under intel-only mode, this terminal action is invalid. The proposal doesn't specify replacement language. **Inference:** the guard should say "End response" instead, but this should be stated explicitly since the guard is a safety-critical anti-hallucination mechanism.

### 3.2 — `preferred_max_lines` handling

The proposal specifies "20–25 lines" for intel-only and "45 lines" for `--fit` (Lines 115-116). The current frontmatter has `preferred_max_lines: 45`. The proposal doesn't state whether to change this value to 25 or keep it at 45 with prose override. Minor, but the implementing agent needs to pick one.

### 3.3 — Tank Hardener Reference script

Line 99 of current SKILL.md runs `tank_summary.py` via `!` injection. The proposal lists "Tank Hardener Reference (the `tank_summary.py` output)" as gated behind `--fit` (Line 110), but doesn't address how to conditionally skip an `!` command injection. `!` commands execute at skill-load time, not at runtime. Same underlying issue as Blocker 2.1 — injected content can't be conditionally gated without changing the injection mechanism or moving it to a runtime `Read`.

## 4. Test Coverage Assessment

The proposal contains no test matrix. However, this is a prompt-engineering change (SKILL.md edits), not a code change — there are no functions to unit test. The behavioral contracts are:

- **Intel-only default:** no fitting MCP calls, no skills.json/ships.md reads, 20-25 line response → verifiable by manual invocation
- **`--fit` parity:** identical to current behavior → verifiable by comparison
- **Argument parsing:** `--fit` detected anywhere in argument string → trivial

No untested contracts that warrant a test matrix.

## 5. Readiness Checklist

- [x] Intel-only response format fully specified (sections, order, line budget)
- [x] `--fit` response format matches current behavior
- [x] Argument parsing semantics defined (positional-insensitive `--fit`)
- [x] Files to remove from `injected_prerequisites` enumerated
- [x] Files to keep in `injected_prerequisites` enumerated
- [x] Impact metrics quantified
- [x] Migration path defined (backwards-compatible)
- [ ] **Decide conditional prerequisite mechanism:** new frontmatter key vs. runtime `Read` with prose gating (Blocker 2.1)
- [ ] **Decide `allowed-tools` gating:** infrastructure-level vs. prompt-level (Blocker 2.2)
- [ ] **Update Spawn Data Guard fallback** for intel-only mode (Gap 3.1)
