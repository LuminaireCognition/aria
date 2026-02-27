# Skill Review: orders

**Skill path:** `.claude/skills/orders/`
**Review timestamp:** 2026-02-26-2228
**Files:** `SKILL.md` (335 lines, ~2,948 tokens)

## 1. Executive Summary

The orders skill is an ESI-backed CLI skill with no MCP integration -- it relies entirely on `uv run aria-esi orders` for data. The skill is heavily padded with verbose JSON response examples, duplicate RP-formatted response templates, and redundant ESI/read-only warnings already covered by CLAUDE.md. Approximately 40% of the token budget is spent on example JSON payloads and ASCII-box response templates that provide marginal steering value.

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | N/A (CLI-backed) | Uses `uv run aria-esi orders` for all data. No MCP market dispatcher used despite availability. Could use `market(action="orders")` for the pilot's own orders if supported. Currently acceptable since this is personal ESI data. |
| Prompt hygiene | :yellow_circle: | Clear that data comes from ESI, but no explicit "do not assume/recall" guardrail. Claude could fill in order details if ESI fails without being told not to. |
| Failure handling | :green_circle: | Good ESI unavailability check (L56-78), missing scope handler (L290-303), empty response handler (L258-270). Multiple error paths covered. |
| Context window efficiency | :red_circle: | Extremely bloated. Two full JSON response examples (L98-158, L161-171), three ASCII-box response templates (L227-256, L258-270, L277-288, L290-303), and verbose field-by-field documentation that a model doesn't need. |

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 19-32 | Read-only limitation section. CLAUDE.md already has the ESI read-only table (Session Init). | **REMOVE** | ~120 tokens |
| `SKILL.md` | 34-42 | Data volatility section. Duplicates CLAUDE.md "Data Volatility" section. Pattern (B). | **REMOVE** | ~80 tokens |
| `SKILL.md` | 44-53 | ESI Requirement section with setup instructions. Duplicated again in error handling L277-303. Pattern (G). | **CONSOLIDATE** into error handling only | ~80 tokens |
| `SKILL.md` | 98-158 | Full JSON response example (active orders). Verbose example teaching Claude a response structure it already gets from the CLI tool output. | **REMOVE** | ~500 tokens |
| `SKILL.md` | 161-171 | Order history JSON response example. | **REMOVE** | ~80 tokens |
| `SKILL.md` | 174-190 | Empty response JSON example. | **REMOVE** | ~120 tokens |
| `SKILL.md` | 192-200 | Order range values table. Static EVE reference data that Claude can infer from context or that the CLI output already includes. | **REMOVE** | ~60 tokens |
| `SKILL.md` | 227-256 | RP-formatted ASCII-box response template (30 lines). Verbose. One template is sufficient. | **CONSOLIDATE** with standard display (keep one format) | ~250 tokens |
| `SKILL.md` | 258-270 | No-orders ASCII-box display. | **CONSOLIDATE** into a one-line instruction | ~80 tokens |
| `SKILL.md` | 277-303 | Two separate error ASCII-box templates (ESI not configured + missing scope). Duplicate of L44-53. Pattern (G). | **CONSOLIDATE** into 2-3 lines of imperative instructions | ~200 tokens |
| `SKILL.md` | 321-327 | Self-sufficiency context. Niche edge case unlikely to justify token cost. | **REMOVE** | ~50 tokens |

**Total estimated savings: ~1,620 tokens (~55% reduction)**

## 4. Specific Findings

### High Severity

**H1. No MCP integration despite market dispatcher availability**
- File: `SKILL.md`, L82-84
- The skill uses `uv run aria-esi orders` exclusively. While this is ESI-authenticated personal data, the skill should note that this is intentional (personal orders require ESI auth, not available via public market MCP).
- **Action:** Add a one-line note explaining why CLI is used instead of MCP (authenticated endpoint).

**H2. Massive JSON response examples consume ~700 tokens for zero steering value**
- File: `SKILL.md`, L98-190
- Three full JSON blocks document the CLI's output format. Claude doesn't need to know the exact JSON schema -- it needs to know how to present the data to the user. The CLI already returns structured data.
- **Action:** **Remove** all JSON examples. Replace with a 2-line note: "The CLI returns JSON with order details (type, price, volume, fill%, location, expiry). Present using the response format below."

**H3. Duplicate content between ESI Requirement (L44-53) and Error Handling (L277-303)**
- File: `SKILL.md`, L44-53 and L277-303
- Pattern (G): The setup command `uv run python .claude/scripts/aria-oauth-setup.py` appears in both sections with identical messaging.
- **Action:** **Remove** L44-53 entirely. Keep error handling section as the single location for auth failure messaging.

### Medium Severity

**M1. Read-only limitation section duplicates CLAUDE.md**
- File: `SKILL.md`, L19-32
- Pattern (B): CLAUDE.md's "ESI Capability Boundaries" table already covers this. The skill restates it with a bullet list.
- **Action:** **Remove** L19-32. Replace with one line: "If user asks to place/modify orders, explain this requires the Market window (Alt+R)."

**M2. Data volatility section duplicates CLAUDE.md**
- File: `SKILL.md`, L34-42
- Pattern (B): CLAUDE.md's "Data Volatility" section already covers semi-stable data handling.
- **Action:** **Remove** L34-42.

**M3. Two response format templates where one suffices**
- File: `SKILL.md`, L203-256
- The skill has both a "Standard Display" (markdown table) and "Formatted Version" (ASCII boxes). The formatted version is 30 lines of box-drawing characters. One format is sufficient -- the persona overlay system handles RP styling.
- **Action:** **Remove** the ASCII-box formatted version (L227-256). Keep the markdown table format.

### Low Severity

**L1. Self-sufficiency section is speculative**
- File: `SKILL.md`, L321-327
- Describes edge-case behavior for `market_trading: false` pilots. This is thin enough to not justify dedicated section.
- **Action:** **Remove**.

**L2. Missing "do not assume" guardrail**
- File: `SKILL.md` (absent)
- No explicit instruction preventing Claude from fabricating order data if the CLI fails or returns empty.
- **Action:** Add: "Present only data returned by the CLI. If the command fails or returns empty, say so -- do not fabricate order details."

## 5. Prioritized Recommendations

1. **Remove** JSON response examples (L98-190) -- eliminates ~700 tokens of dead weight. Replace with a 2-line summary of what the CLI returns.
2. **Remove** duplicate read-only (L19-32), volatility (L34-42), and ESI requirement (L44-53) sections -- Pattern (B)/(G), saves ~280 tokens.
3. **Consolidate** error handling templates (L277-303) from ASCII boxes to imperative instructions -- saves ~200 tokens.
4. **Remove** ASCII-box RP response template (L227-256) -- keep only the markdown table format, saves ~250 tokens.
5. **Add** a "do not fabricate" guardrail (1 line).
6. **Add** a note explaining why CLI is used instead of MCP (authenticated data).
