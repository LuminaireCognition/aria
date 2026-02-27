# Skill Review: corp

**Skill path:** `.claude/skills/corp/SKILL.md`
**Review timestamp:** 2026-02-26-2228
**File size:** 13,112 bytes (~3,278 tokens)

## 1. Executive Summary

The corp skill is a CLI-backed ESI query skill at ~3,278 tokens. It is reasonably well-structured with clear subcommand documentation, but contains the now-familiar ESI Availability Check duplication (Pattern B), verbose ASCII response templates for six subcommands, an In-Universe Framing section that duplicates persona system behavior, and a Data Volatility table that restates CLAUDE.md's data volatility protocol.

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | :yellow_circle: | Uses CLI (`uv run aria-esi corp`). No MCP dispatcher covers corp data. CLI is the correct approach. No hallucination guardrail — the skill never states "do not fabricate corp data." |
| Prompt hygiene | :green_circle: | Subcommand reference (lines 68-78) and per-subcommand behavior sections are clear and well-organized. Options tables are concise. |
| Failure handling | :green_circle: | Good coverage with four distinct error cases: NPC Corporation (lines 226-242), Missing Scopes (lines 244-261), Insufficient Role (lines 263-278), Corporation Not Found (lines 280-295). |
| Context window efficiency | :yellow_circle: | Several sections duplicate system-level behaviors. Error handling blocks are individually verbose but collectively reasonable. The biggest waste is the ESI availability check and the In-Universe Framing section. |

## 3. Reduction Inventory

| File | Lines | What | Action | Est. Token Savings |
|------|-------|------|--------|-------------------|
| SKILL.md | 38-66 | ESI Availability Check section | REMOVE | ~200 tokens. Pattern B — system-level behavior. Same section appears in clones, contracts. |
| SKILL.md | 88-117 | Status Dashboard ASCII response template | CONSOLIDATE | ~200 tokens. Replace with a structural list of dashboard sections. |
| SKILL.md | 133-153 | Corp Info ASCII response template | CONSOLIDATE | ~140 tokens. Merge into the subcommand description as a brief format note. |
| SKILL.md | 166-188 | Corp Wallet ASCII response template | CONSOLIDATE | ~150 tokens. Same approach — brief format note. |
| SKILL.md | 226-295 | Four error handling ASCII blocks (NPC Corp, Missing Scopes, Insufficient Role, Corp Not Found) | CONSOLIDATE | ~400 tokens. Reduce each to 2-3 line imperative instructions. The ASCII art framing adds no steering value. |
| SKILL.md | 297-308 | Data Volatility table | REMOVE | ~100 tokens. Pattern B — data volatility is a system-level protocol defined in CLAUDE.md and `PROTOCOLS.md`. The wallet timestamp instruction (line 308) is the only skill-specific part; keep that as one sentence. |
| SKILL.md | 310-320 | Scopes Required table | REMOVE | ~80 tokens. Duplicates frontmatter `esi_scopes` (lines 14-19). The subcommand-to-scope mapping is mildly useful but already implicit in the error handling. |
| SKILL.md | 322-329 | In-Universe Framing section | REMOVE | ~70 tokens. Pattern B — persona framing is handled by the persona system. Skills should not carry their own RP flavor text mappings. |
| SKILL.md | 331-337 | Behavior Notes section | CONSOLIDATE | ~50 tokens. "Graceful Degradation" (line 332) duplicates line 119. Other notes are generic. |
| SKILL.md | 339-345 | ESI Documentation Reference section | REMOVE | ~60 tokens. Developer reference, not runtime steering. The URLs are for human developers, not Claude. |

**Total estimated savings: ~1,450 tokens (~44% reduction)**

## 4. Specific Findings

### High Severity

**H1. ESI Availability Check duplicates CLAUDE.md (Pattern B)**
- File: `SKILL.md`, lines 38-66
- This is the third skill in this batch with an identical ESI availability check section. It is system-level behavior handled by the session hook.
- **Action:** REMOVE entirely.

**H2. No hallucination guardrail for corp data**
- The skill never explicitly states that all corporation data must come from the CLI response. There is a path where Claude could fill in missing fields (member count, CEO name, tax rate) from training data if the CLI returns partial data.
- **Action:** ADD a one-line guardrail: "All corp data fields must come from CLI output. If a field is missing, display 'N/A' — never fill from memory."

### Medium Severity

**M1. In-Universe Framing re-implements persona system (Pattern B)**
- File: `SKILL.md`, lines 322-329
- Maps subcommands to RP flavor text ("Corporate queries = Accessing NEOCOM corporate interface"). The persona system handles RP framing based on `rp_level`.
- **Action:** REMOVE.

**M2. Data Volatility table restates system protocol (Pattern B)**
- File: `SKILL.md`, lines 297-308
- CLAUDE.md's Data Volatility section and `PROTOCOLS.md` already define volatility tiers. The only skill-specific value is "wallet data requires timestamps."
- **Action:** REMOVE table. Keep one sentence: "Wallet data is volatile — always include query timestamp."

**M3. Six ASCII response templates**
- File: `SKILL.md`, lines 88-117, 133-153, 166-188, 226-295
- Status Dashboard, Corp Info, Corp Wallet, and four error templates.
- **Action:** CONSOLIDATE. Replace format templates with structural descriptions. Reduce error templates to imperative instructions.

### Low Severity

**L1. Scopes Required table duplicates frontmatter**
- File: `SKILL.md`, lines 310-320
- **Action:** REMOVE.

**L2. ESI Documentation Reference is developer-facing**
- File: `SKILL.md`, lines 339-345
- URLs to `esi.evetech.net` and `developers.eveonline.com` are for human developers.
- **Action:** REMOVE.

**L3. Behavior Notes partially redundant**
- File: `SKILL.md`, lines 331-337
- "Graceful Degradation" (line 332) restates line 119. "Public Info Always Works" (line 333) restates line 25.
- **Action:** REMOVE redundant notes; keep any unique behavioral instructions.

## 5. Prioritized Recommendations

1. **REMOVE** ESI Availability Check (lines 38-66). System-level behavior. (~200 tokens)
2. **ADD** one-line hallucination guardrail for corp data fields.
3. **CONSOLIDATE** ASCII response templates into structural descriptions (lines 88-188). (~490 tokens)
4. **CONSOLIDATE** error handling blocks to imperative instructions (lines 226-295). (~400 tokens)
5. **REMOVE** In-Universe Framing section (lines 322-329). Persona system handles this. (~70 tokens)
6. **REMOVE** Data Volatility table (lines 297-308). Keep one sentence about wallet timestamps. (~80 tokens)
7. **REMOVE** Scopes Required table (lines 310-320). Duplicates frontmatter. (~80 tokens)
8. **REMOVE** ESI Documentation Reference (lines 339-345). Developer docs. (~60 tokens)
