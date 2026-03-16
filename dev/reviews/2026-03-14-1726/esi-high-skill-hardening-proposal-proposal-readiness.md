# Proposal Readiness Review: ESI:MEDIUM/HIGH Skill Hardening

**Proposal:** `dev/proposals/ESI_HIGH_SKILL_HARDENING_PROPOSAL.md`
**Reviewed:** 2026-03-14

---

## 1. Ship Decision

**NOT READY** — The proposal specifies exact prose to insert into three SKILL.md files, but references CLI commands and MCP actions that do not exist in the codebase, and the freshness gate pattern is applied to data types not in the freshness registry.

---

## 2. Blockers

### B1: Fabricated CLI command `skills --summary` (Critical)

**Location:** Pattern 1 (Field → Source Mapping, `pilot` section, line 48), Pattern 2 (Anti-Patterns, `pilot` section, line 111)

**The ambiguity:** The proposal specifies `skills --summary` as the tool call for Total Skill Points. This flag does not exist. `src/aria_esi/commands/skills.py:205` defines `cmd_skills` with no `--summary` argument. The existing `skills` command returns the full skill dict, not a summary total.

**Decision needed:** What CLI command produces total SP? Options: (a) the `skills` CLI returns JSON with a total SP field — specify the JSON path to extract, (b) the `pilot` CLI already returns total SP in its output — verify and use that instead, (c) add a `--summary` flag to the skills CLI. Option (c) is out of scope for this proposal and must be a separate change. The implementing agent cannot choose between (a) and (b) without knowing the CLI output schemas.

### B2: Fabricated MCP action `pilot(action="public_info")` (Critical)

**Location:** Pattern 6 (MCP + CLI Dual-Path, `pilot` section, lines 329-332)

**The ambiguity:** The proposal documents `pilot(action="public_info", character_name="<name>")` as an available MCP path. This action does not exist. The pilot MCP dispatcher (`src/aria_esi/mcp/dispatchers/pilot.py:36-53`) supports exactly: `mail_list`, `mail_read`, `mining_ledger`, `contracts`, `fittings_list`, `lp_offers`, `lp_balance`. There is no `public_info` action.

**Decision needed:** Remove the MCP row for public info from the `pilot` data path table and mark `pilot` as CLI-only for all identity data (consistent with `corp` and `esi-query`). Alternatively, if a `public_info` action should exist, that is a separate MCP dispatcher feature request — not part of this proposal. Including a non-existent MCP action in skill prose will cause the model to attempt calls that fail at runtime.

### B3: `ensure-fresh` registry scope mismatch (Major)

**Location:** Pattern 3 (Freshness Gate, `esi-query` section, lines 210-211)

**The ambiguity:** The `esi-query` freshness gate groups standings and blueprints together as "SEMI-STABLE" and implies both use `ensure-fresh`. The freshness registry (`src/aria_esi/core/freshness.py:41-56`) confirms `standings` and `skills` are registered sections. Blueprints is NOT a registered freshness section. Calling `ensure-fresh blueprints` would raise a `KeyError`.

**Decision needed:** Explicitly enumerate which `esi-query` query types use `ensure-fresh` (standings and skills only) and which are always-live (location, wallet, blueprints). Remove blueprints from the semi-stable freshness gate grouping, or note that a freshness section for blueprints needs to be added first (separate scope).

### B4: NPC Corp detection heuristic is unreliable (Major)

**Location:** Pattern 10 (Positive-Path Early Exit, `corp` section, lines 509-511)

**The ambiguity:** The proposal specifies: "Detection: check if corporation is an NPC corp (corp ID < 2000000 or corp is in the NPC corp list)." The `< 2000000` heuristic is not established anywhere in the codebase. No "NPC corp list" reference file is cited.

**Decision needed:** Specify the exact detection method. The simplest option: remove the detection gate entirely. Let the authenticated CLI calls fail naturally with an "insufficient role" error, which the existing error handling and the new Degraded Mode section (Pattern 4) already cover. The early exit adds complexity for a marginal performance gain (saving 1-2 CLI calls that would fail fast anyway). If detection is wanted, verify whether the `corp info` CLI output includes an `is_npc` field.

---

## 3. Specification Gaps

### G1: `_index.json` update scope undefined

**Location:** Implementation Plan, Phase 2 step 7 (line 568), Phase 3 step 11 (line 577)

The proposal says "Update `_index.json` with new `allowed-tools` values" and "Update `_index.json` with `preferred_max_lines` values." However, `allowed-tools` is a Claude Code frontmatter key — it lives in SKILL.md YAML, not in `_index.json`. The `_index.json` schema has no `allowed_tools` field. `preferred_max_lines` is similarly a frontmatter key. The implementing agent can infer this from inspecting existing skills, but the proposal's explicit mention of `_index.json` updates for these fields is misleading and would cause the agent to add non-standard fields to the index.

**Action:** Remove references to updating `_index.json` for `allowed-tools` and `preferred_max_lines`. These are frontmatter-only changes.

### G2: `pilot` wallet/SP as separate CLI calls vs. single call

**Location:** Pattern 1 (Field → Source Mapping, `pilot` section, lines 47-48)

The field-source mapping lists Wallet Balance and Total Skill Points as requiring separate CLI calls (`wallet` and `skills --summary`). But the current `pilot` SKILL.md runs `pilot` once. It is unclear from the proposal whether the `pilot` CLI output already includes wallet and SP fields, making separate calls unnecessary. The implementing agent would need to check the CLI output schema to decide whether to add two new CLI calls or use existing output fields.

**Action:** Verify CLI output and adjust mapping. If `pilot` CLI returns wallet/SP, map those fields to it. If not, map to the correct separate commands (with valid flags).

### G3: Nested code fences will break markdown rendering

**Location:** Pattern 3 (lines 177-180, 212-215), Pattern 10 (lines 513-521, 537-548)

Multiple proposed insertions contain triple-backtick code blocks nested inside triple-backtick code blocks. The proposal uses the same delimiter (```)  for both the "here is the text to insert" wrapper and the code blocks within the inserted text. A markdown renderer (or the implementing agent) will misparse these. The implementing agent must manually identify the inner vs. outer fences by context.

**Action:** Not a blocker — an experienced implementing agent can resolve this. But the proposal author should use quadruple backticks or indented code blocks for the outer wrappers to make the intent unambiguous.

### G4: No `Sources:` footer specification

The proposal adds field-source mappings and anti-patterns but does not add or update `Sources:` footer rules for the three skills. The shared rules file (`.claude/rules/skills.md`) mandates a Sources footer on all skill output. These three skills don't currently produce consistent footers. A pattern adopted by well-hardened ESI:LOW skills is to specify the footer format in-skill. The implementing agent may or may not add this.

---

## 4. Test Coverage Assessment

The proposal does not include a test matrix — it relies on exercise runner validation. This is appropriate for prompt-only changes (no code is modified).

The validation steps per phase are reasonable:
- **Phase 1:** "Run exercise queries" — sufficient if exercise coverage exists for `pilot`, `corp`, and `esi-query`.
- **Phase 2:** "Simulated scope failures" — not clear whether the exercise runner supports scope simulation. The implementing agent may need to create new exercise query files with explicit scope-failure scenarios.
- **Phase 3-4:** Line count measurement and profile variant testing are achievable through existing exercise infrastructure.

**Untested contract:** The degraded mode tables (Pattern 4) specify exact output strings per missing scope. No validation mechanism verifies these strings are produced. This is inherent to prompt-based skills and acceptable — the strings are guidance, not a contract.

---

## 5. Readiness Checklist

- [ ] **B1:** Replace all occurrences of `skills --summary` with a verified CLI command or JSON path that produces total SP
- [ ] **B2:** Remove `pilot(action="public_info")` from the MCP dual-path table — mark pilot identity data as CLI-only
- [ ] **B3:** Remove `blueprints` from the freshness gate semi-stable group; enumerate exactly which queries use `ensure-fresh` (standings, skills) vs. always-live (location, wallet, blueprints)
- [ ] **B4:** Remove NPC corp detection heuristic or replace with a verified detection method; consider dropping the early exit in favor of existing error handling
- [ ] **G1:** Remove references to updating `_index.json` for `allowed-tools` and `preferred_max_lines` — these are SKILL.md frontmatter-only keys
- [ ] **G2:** Verify `pilot` CLI output schema for wallet/SP fields; adjust field-source mapping accordingly
- [ ] **G3:** Fix nested code fence delimiters so inner/outer blocks are distinguishable
- [ ] All four blockers resolved before handing to implementing agent
