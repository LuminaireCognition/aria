# Skill Review: price

**Skill path:** `.claude/skills/price/`
**Review timestamp:** 2026-02-26-2228
**Files:** `SKILL.md` (310 lines, ~2,398 tokens)

## 1. Executive Summary

The price skill is a market-data skill that describes both CLI and ESI approaches but notably does not reference the MCP `market(action="prices")` or `market(action="orders")` dispatchers that are the preferred data source per CLAUDE.md. The skill spends ~100 lines on JSON response format documentation (L124-195) for a CLI tool, while MCP tools return structured data directly. The persona overlay section (L302-311) duplicates the general skill-loading mechanism already defined in CLAUDE.md. Overall, this is a moderately bloated skill that would benefit most from MCP-first migration and removal of CLI-oriented JSON schemas.

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | :red_circle: | **Critical gap.** The skill documents ESI endpoints (L46-59) and CLI commands (L234-249) but never mentions `market(action="prices")` or `market(action="orders")`, which are the MCP-first approach per CLAUDE.md. The MCP dispatchers should be the primary path. |
| Prompt hygiene | :yellow_circle: | No "do not assume/recall" guardrail. The experience adaptation section (L207-232) includes a "veteran" format that could encourage Claude to generate terse price data from memory rather than fetching it. |
| Failure handling | :green_circle: | Good coverage: item not found (L162-170), no market data (L172-180), no regional orders (L182-195), NES items (L197-205). Each error case is handled explicitly. |
| Context window efficiency | :yellow_circle: | JSON response format (L124-156) and three error JSON blocks (L162-195) are verbose. The trade hub station IDs table (L282-292) is static reference data. Two response format templates (standard + RP) where one suffices. |

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 124-156 | Full JSON output format example. Claude doesn't need to know the JSON schema when MCP returns structured data directly. | **REMOVE** | ~250 tokens |
| `SKILL.md` | 160-195 | Three error JSON response blocks. Should be imperative instructions, not JSON templates. | **CONSOLIDATE** to 3-4 imperative lines per error case | ~200 tokens |
| `SKILL.md` | 100-122 | RP formatted ASCII-box response template. Verbose alternative to the standard markdown format (L62-98). | **REMOVE** -- keep markdown format only, persona overlays handle RP | ~180 tokens |
| `SKILL.md` | 46-59 | ESI endpoint documentation. Implementation detail that doesn't help Claude respond. Pattern (D) -- explains the "how" behind the data source. | **REMOVE** | ~100 tokens |
| `SKILL.md` | 282-292 | Trade hub station IDs table. Static data that the MCP dispatcher already handles (station filtering). | **REMOVE** | ~80 tokens |
| `SKILL.md` | 302-311 | Persona adaptation section. Duplicates CLAUDE.md's skill-loading mechanism for overlays. Pattern (B). | **REMOVE** | ~60 tokens |
| `SKILL.md` | 207-232 | Experience-based adaptation examples. Two full response examples (new player: 8 lines, veteran: 2 lines). Could be 2-line instructions. | **CONSOLIDATE** to brief instructions | ~120 tokens |
| `SKILL.md` | 234-249 | Script command section with CLI examples. If MCP is primary, this becomes fallback documentation. | **CONSOLIDATE** to a 2-line note | ~80 tokens |
| `SKILL.md` | 251-258 | Self-sufficiency integration section. Niche edge case. | **REMOVE** | ~60 tokens |

**Total estimated savings: ~1,130 tokens (~47% reduction)**

## 4. Specific Findings

### High Severity

**H1. No MCP dispatcher integration -- skill is stuck on CLI/ESI model**
- File: `SKILL.md`, entire implementation section
- The skill describes ESI endpoints (L46-59) and CLI commands (L234-249) but never references `market(action="prices")` or `market(action="orders")`, which are documented in CLAUDE.md as the primary market data interface. This is the most impactful finding: the skill should lead with MCP, fall back to CLI.
- **Action:** **Modify** the implementation section to use MCP dispatchers as primary:
  ```
  1. Use market(action="prices", items=["<item>"], region="<hub>") for price data
  2. Use market(action="orders", item="<item>", region="<hub>") for order book
  3. Fallback: uv run aria-esi price "<item>" [--region]
  ```

**H2. JSON response format documentation is dead weight with MCP**
- File: `SKILL.md`, L124-156
- If the skill uses MCP dispatchers, Claude receives structured data directly -- it doesn't need to know what the CLI's JSON schema looks like.
- **Action:** **Remove** the entire JSON output format section.

### Medium Severity

**M1. ESI endpoint documentation is implementation noise**
- File: `SKILL.md`, L46-59
- Pattern (D): Documents endpoint paths, authentication levels, and cache timers. This is "how the data source works" rather than "what to do with the data." The MCP layer abstracts this.
- **Action:** **Remove**. If cache timing is important for user-facing disclaimers, add one line: "Market data is cached up to 5 minutes for regional orders, 1 hour for global prices."

**M2. Duplicate response templates (standard + RP)**
- File: `SKILL.md`, L62-98 (standard) and L100-122 (RP)
- Two full response templates for the same data. The persona overlay system handles RP adaptation; the base skill shouldn't carry two formats.
- **Action:** **Remove** RP template (L100-122). The paria overlay already exists for pirate framing.

**M3. Trade hub station IDs table is static reference**
- File: `SKILL.md`, L282-292
- The MCP dispatcher handles station filtering internally. Including station IDs in the skill is Pattern (A) -- reference data that belongs elsewhere.
- **Action:** **Remove**.

**M4. Persona adaptation section duplicates CLAUDE.md**
- File: `SKILL.md`, L302-311
- Pattern (B): The skill-loading mechanism in CLAUDE.md already handles overlay loading. This section restates it.
- **Action:** **Remove**.

### Low Severity

**L1. Experience adaptation examples are verbose**
- File: `SKILL.md`, L207-232
- Two full response examples (new player + veteran). Could be two-line instructions: "For new players, explain spread concept and suggest regional lookup. For veterans, use single-line compact format."
- **Action:** **Consolidate**.

**L2. Self-sufficiency section is thin**
- File: `SKILL.md`, L251-258
- Describes behavior for `market_trading: false` pilots. The DO NOT section (L293-299) already says "DO NOT recommend selling." This is partial Pattern (G).
- **Action:** **Remove** the self-sufficiency section; the DO NOT line covers it.

## 5. Prioritized Recommendations

1. **Modify** implementation to use MCP `market()` dispatchers as primary data source -- critical grounding improvement.
2. **Remove** JSON output format (L124-156) and ESI endpoint documentation (L46-59) -- saves ~350 tokens, no longer needed with MCP.
3. **Remove** RP response template (L100-122) -- persona overlay handles this, saves ~180 tokens.
4. **Consolidate** error handling from JSON blocks to imperative instructions (L160-195) -- saves ~200 tokens.
5. **Remove** trade hub station IDs (L282-292), persona adaptation (L302-311), self-sufficiency (L251-258) -- saves ~200 tokens.
6. **Add** "do not recall/assume prices" guardrail -- critical for a market data skill.
