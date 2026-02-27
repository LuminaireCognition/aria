# Skill Review: contracts

**Skill path:** `.claude/skills/contracts/SKILL.md`
**Review timestamp:** 2026-02-26-2228
**File size:** 14,999 bytes (~3,750 tokens)

## 1. Executive Summary

The contracts skill is a CLI-backed ESI query skill at ~3,750 tokens. Over half the file is consumed by verbose ASCII-art response templates (five distinct format blocks) and full JSON response structure examples that serve as documentation rather than steering. The skill also duplicates CLAUDE.md's ESI availability check and read-only limitation messaging, and includes inlined reference data for contract types and statuses that could be in a reference file.

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | :yellow_circle: | Uses CLI (`uv run python -m aria_esi contracts`). No MCP pilot action covers contracts. CLI is the correct approach. However, there is no "do not assume/recall" guardrail for contract data — Claude could fabricate contract details if the CLI fails silently. |
| Prompt hygiene | :green_circle: | Commands and options are clearly documented (lines 98-127). The read-only limitation (lines 19-35) is explicit. |
| Failure handling | :green_circle: | Good coverage: ESI unavailable (lines 73-96), missing scope (lines 362-376), and ESI not configured (lines 347-361) all have actionable fallback messages. |
| Context window efficiency | :red_circle: | Five ASCII response format templates (~1,200 tokens), two full JSON response structures (~600 tokens), courier risk assessment block, auction monitoring block, and self-sufficiency context all consume tokens without proportional steering value. |

## 3. Reduction Inventory

| File | Lines | What | Action | Est. Token Savings |
|------|-------|------|--------|-------------------|
| SKILL.md | 19-35 | "CRITICAL: Read-Only Limitation" section | REMOVE | ~150 tokens. Pattern B — ESI read-only limitation is stated in CLAUDE.md's "ESI Capability Boundaries" table. Restating it here with a full "ARIA CANNOT" list is pure noise. |
| SKILL.md | 37-59 | Contract Types + Contract Statuses reference tables | CONSOLIDATE | ~180 tokens. Pattern A — these are static game data. Move to `reference/mechanics/contract_types.json` if needed, or simply trust the CLI output to provide this context. |
| SKILL.md | 61-71 | ESI Requirement section | REMOVE | ~80 tokens. Duplicates frontmatter `esi_scopes` (line 14) and the error handling section (lines 362-376). |
| SKILL.md | 73-96 | ESI Availability Check section | REMOVE | ~180 tokens. Pattern B — system-level behavior duplicated from CLAUDE.md session hook handling. |
| SKILL.md | 129-214 | Two full JSON Response Structures (Contract List + Contract Detail) | REMOVE | ~600 tokens. These document the CLI's JSON output format. Claude does not need to know the exact JSON schema to format the response — it receives the actual JSON at runtime. This is developer documentation, not steering. |
| SKILL.md | 216-235 | Standard Display response template | CONSOLIDATE | ~150 tokens. Keep a 3-line structural description instead of the full markdown example. |
| SKILL.md | 237-294 | Formatted Version + No Contracts Display (two ASCII templates) | CONSOLIDATE | ~400 tokens. Merge into a compact format description with key sections noted. |
| SKILL.md | 296-321 | Courier Contract Guidance + Courier Risk Assessment block | CONSOLIDATE | ~200 tokens. The risk assessment ASCII block is verbose. Reduce to imperative instructions: "For courier contracts, assess route security and ISK/jump ratio." |
| SKILL.md | 323-343 | Auction Monitoring ASCII block | REMOVE | ~150 tokens. This is a response template for a narrow edge case (auction with bids). The standard format description is sufficient. |
| SKILL.md | 345-376 | Error Handling: ESI Not Configured + Missing Scope (two ASCII blocks) | CONSOLIDATE | ~200 tokens. Reduce to 3-line imperative instructions per case. |
| SKILL.md | 389-396 | Cross-References table | REMOVE | ~60 tokens. Generic cross-references handled by CLAUDE.md command suggestion system. |
| SKILL.md | 398-404 | Self-Sufficiency Context section | REMOVE | ~60 tokens. Pilot playstyle awareness comes from the pilot profile, not hardcoded skill instructions. |

**Total estimated savings: ~2,410 tokens (~64% reduction)**

## 4. Specific Findings

### High Severity

**H1. JSON Response Structures are developer documentation, not steering (lines 129-214)**
- Two complete JSON examples totaling ~600 tokens document what the CLI returns. Claude receives the actual JSON at runtime — it does not need a schema ahead of time. This is the single largest waste in the file.
- **Action:** REMOVE entirely.

**H2. ESI read-only limitation restated from CLAUDE.md (Pattern B)**
- File: `SKILL.md`, lines 19-35
- CLAUDE.md's "ESI Capability Boundaries" table already states: "ARIA cannot: Place buy/sell orders... Interact with EVE client."
- The contracts skill adds a 15-line section with "CRITICAL" header restating this for the contracts domain.
- **Action:** REMOVE. If the read-only reminder is needed, one sentence suffices: "Remind the pilot that contract actions (accept, create, cancel) require in-game action."

**H3. ESI Availability Check duplicates CLAUDE.md (Pattern B)**
- File: `SKILL.md`, lines 73-96
- Same pattern seen in clones and corp skills.
- **Action:** REMOVE entirely.

### Medium Severity

**M1. Five ASCII response templates are excessive**
- File: `SKILL.md`, lines 216-294, 306-321, 323-343
- Standard display, formatted version, no-contracts display, courier risk assessment, auction monitoring — five distinct format blocks.
- **Action:** CONSOLIDATE to one structural description covering the key sections (summary, outstanding, in-progress, completed) with format notes for RP level variation.

**M2. Inlined contract type and status reference tables**
- File: `SKILL.md`, lines 37-59
- Static game data that could drift. The CLI returns actual status strings.
- **Action:** CONSOLIDATE. Keep a brief note that contract types include item_exchange, courier, auction, loan. Remove the full status table — the CLI output is self-documenting.

### Low Severity

**L1. Cross-References table is generic**
- File: `SKILL.md`, lines 389-396
- **Action:** REMOVE.

**L2. Self-Sufficiency Context is profile-driven**
- File: `SKILL.md`, lines 398-404
- **Action:** REMOVE. The pilot profile already communicates this.

**L3. Duplicate ESI scope documentation**
- Lines 14 (frontmatter), 61-71 (ESI Requirement section), 362-376 (Missing Scope error) all cover the same scope.
- **Action:** REMOVE lines 61-71.

## 5. Prioritized Recommendations

1. **REMOVE** JSON Response Structures (lines 129-214). Developer documentation, not steering. (~600 tokens)
2. **REMOVE** ESI read-only limitation section (lines 19-35). Duplicates CLAUDE.md. (~150 tokens)
3. **REMOVE** ESI Availability Check (lines 73-96). System-level behavior. (~180 tokens)
4. **CONSOLIDATE** five ASCII response templates into one compact format description. (~700 tokens)
5. **REMOVE** Auction Monitoring block (lines 323-343). Edge case template. (~150 tokens)
6. **CONSOLIDATE** error handling blocks to imperative instructions. (~200 tokens)
7. **REMOVE** Cross-References table and Self-Sufficiency Context. (~120 tokens)
8. **REMOVE** ESI Requirement section (lines 61-71). Duplicates frontmatter. (~80 tokens)
