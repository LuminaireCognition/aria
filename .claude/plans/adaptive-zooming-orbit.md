# Plan: Implement Exercise Run 20260308-204547 Recommendations

## Context

Exercise run tested 47 queries across 24 ESI:NONE skills. All queries routed correctly and MCP tools were used effectively, but the review surfaced 5 critical issues and 7 high-ROI improvements around stat provenance, emoji usage, route priority, and brevity discipline. This plan implements R1-R11 from `dev/reviews/exercise-outputs/20260308-204547/RECOMMENDATIONS.md`.

---

## R1. Label estimated stats with `(est.)` suffix — P0

**Files:**
- `.claude/skills/fitting/SKILL.md`
- `.claude/skills/mark-assessment/SKILL.md`

**fitting/SKILL.md** — Add to the `## Rules` section (after line 129):
```
- When presenting DPS, EHP, or HP values that are calculated or estimated rather than returned directly by the fitting engine tool, suffix with `(est.)`. Example: `DPS: ~124 (est.) | EHP: ~12,500 (est.)`. Stats returned by `fitting(action="calculate_stats")` do not need the suffix.
```

**mark-assessment/SKILL.md** — Add to the `HALLUCINATION GUARD` block (after line 48):
```
When presenting DPS, EHP, or HP values that are computed from base stats or estimated rather than returned directly by `fitting(action="calculate_stats")`, suffix with `(est.)`. Example: `EHP: ~14,000 (est.)`. The response format template line for Tank should read: `Tank: {ehp} EHP (est.) {(base hull — actual depends on fit)}` when no user fit is provided.
```

Also update the response format template (line 86) from:
```
  Tank: {ehp} EHP {(fitted) or (base hull — actual depends on fit)}
```
to:
```
  Tank: {ehp} EHP {(fitted) or (est.) (base hull — actual depends on fit)}
```

---

## R2. Verify abyssal NPC damage splits — P0

**Files:**
- `.claude/skills/abyssal/SKILL.md` (lines 39-46, inline weather table)
- `reference/mechanics/abyssal_deadspace.json` (source of truth)

**Finding:** The JSON `_meta.notes` already says "Damage profiles are approximate." The inline table in SKILL.md shows only the top 2 damage types per weather (e.g., "EM 50%, Thermal 30%") which matches the JSON data. The C3 issue was about NPC *faction* damage splits (Triglavian, Drifter) being stated as exact 50/50 in exercise output.

**Change:** Add a note below the weather table (after line 47):
```
> **Note:** NPC damage profiles are approximate and vary by NPC variant within each weather type. Do not state splits as exact ratios.
```

No change needed to `abyssal_deadspace.json` — its `_meta` already caveats this.

---

## R3. Verify mission damage profiles — P0

**Files:**
- `reference/mechanics/npc_damage_types.md`
- `.claude/skills/mission-brief/SKILL.md`

**Finding:** `npc_damage_types.md` lists EoM as "EM / Therm" dealt, "Kin > EM/Therm" to deal. Gone Berserk L3 reportedly showed "Kin primary / Therm secondary" which was flagged as "atypical." EoM missions can have mixed waves (mercenaries, drones) which shift the profile. The reference data is correct for the faction overall.

**Change in mission-brief/SKILL.md:** Add a note in the damage profile section (near the hardener swap logic ~line 182):
```
> **Mixed-wave missions:** Some missions (e.g., Gone Berserk) feature mixed NPC factions (EoM + mercenaries + drones). When the PVE intel cache shows a damage profile that differs from the primary faction's reference data, present the mission-specific profile without flagging it as "atypical" — mission-specific data takes priority over faction defaults.
```

No change to `npc_damage_types.md` — the faction-level data is correct.

---

## R4. Fix route skill safe-mode priority — P0

**File:** `.claude/skills/route/SKILL.md`

**Change:** Add a new section after the Flags table (after line 44), before "Avoiding Systems":

```markdown
### Safe-Mode Intent Detection

When the user's query contains "safe", "safest", "secure", or "safely", use `mode="safe"` as the **primary** route. Show the shortest route as a brief alternative ("Shortest alternative: N jumps via [key system]"). Do not bury the safe route in prose while presenting the shortest route as the primary result.
```

---

## R5. Strip emoji from skill outputs — P1

**Files to edit** (16 files use emoji, but only those in skill output templates/rules need fixing):

| File | Emoji | Replacement |
|------|-------|-------------|
| `gatecamp/SKILL.md` | `⚠️` (5x in output format + watchlist + chokepoint) | `[!]` |
| `killmail/SKILL.md` | `⚠️` (1x in CONTEXT section of output format) | `[!]` |
| `orient/SKILL.md` | `⚠️` (2x in hallucination guard + FW output), `✅`/`✓`/`❌` (anti-patterns) | `[!]` for warnings in output templates; keep `✅`/`❌` in anti-pattern docs (these are internal skill docs, not user-facing output) |
| `mark-assessment/SKILL.md` | `✅`/`❌` (anti-patterns only) | Keep — internal docs, not output |
| `hunting-grounds/SKILL.md` | `✅`/`❌` (anti-patterns only) | Keep — internal docs, not output |

**Decision:** Only replace emoji that appear in **output format templates** or **user-facing response sections**. Anti-pattern tables (`❌ WRONG / ✅ RIGHT`) are internal skill documentation and don't reach the user — leave those alone.

**Specific edits:**
- `gatecamp/SKILL.md` lines 61, 66, 83, 111, 147: `⚠️` → `[!]`
- `killmail/SKILL.md` line 69: `⚠️` → `[!]`
- `orient/SKILL.md` line 147: `⚠️` → `[!]`

---

## R6. Add data provenance footers — P1

**Approach:** Option 3 from recommendations — path-scoped rule in `.claude/rules/skills.md`.

**New file:** `.claude/rules/skills.md`
```yaml
---
paths:
  - ".claude/skills/**"
---

# Skill Output Provenance

When producing skill output, append a `Sources:` footer showing data origin. Format:

```
Sources: universe(route, activity) | market(prices) | SDE: item_info | Ref: npc_damage_types.md
```

Rules:
- List each MCP dispatcher call made (action names only)
- List reference files consulted from `prerequisite_files`
- Omit pilot profile reads (assumed)
- Keep to one line
```

---

## R7. Add per-skill line budgets — P1

**Approach:** Add `max_lines` as a custom frontmatter field in each SKILL.md. Only override the defaults — skills that fit the standard 30-line budget don't need the field.

**Files to edit (non-standard budgets only):**

| Skill | `max_lines` | Rationale |
|-------|------------|-----------|
| `price/SKILL.md` | 15 | Compact data lookup |
| `journal/SKILL.md` | 15 | Compact data lookup |
| `wallet-journal/SKILL.md` | 20 | Tabular financial data |
| `orient/SKILL.md` | 45 | Multi-section tactical intel |
| `threat-assessment/SKILL.md` | 45 | Multi-section tactical intel |
| `exploration/SKILL.md` | 50 | Reference-heavy guidance |
| `help/SKILL.md` | 80 | Command listing |
| `mission-brief/SKILL.md` | 45 | Streaming multi-phase output |
| `hunting-grounds/SKILL.md` | 45 | Multi-system analysis |
| `fitting/SKILL.md` | 50 | EFT block + stats + notes |

**Change:** Add `max_lines: N` to YAML frontmatter of each skill above.

Also add a brief note to the provenance rule file (`.claude/rules/skills.md`) so the line budget is respected:
```
If a skill declares `max_lines` in its frontmatter, target that line count instead of the global 30-line default.
```

---

## R8. Coordinate with argument-hint — P1

**No additional work.** The remediation proposal already specifies `argument-hint` for all user-facing skills, and several are already applied. This recommendation is a coordination note, not a code change.

---

## R9. Normalize watchlist names — P2

**File:** `.claude/skills/watchlist/SKILL.md`

**Change:** Add after the CLI Commands section (after line 43):

```markdown
## Name Normalization

When listing watchlists, perform case-insensitive deduplication. If multiple lists differ only by case (e.g., "Default" and "default"), warn the user:

```
[!] Duplicate watchlist names detected (case mismatch): "Default" and "default"
    Consider merging with: uv run aria-esi watchlist-delete "default"
```
```

---

## R10. Require coalition data citations — P2

**File:** `.claude/skills/hunting-grounds/SKILL.md`

**Change:** Add to the `### Output Constraints` section (after line 83):

```markdown
- When referencing sovereignty or coalition territory, cite the data source (e.g., "sovereignty via ESI/DOTLAN") or disclaim: "Coalition boundaries are approximate and may be outdated." Never state coalition membership as established fact without a tool-sourced `sovereignty` or `territory_analysis` response backing it.
```

---

## R11. Apply allowed-tools — P2 (coordinate with remediation Phase 4)

**Files:**
- `.claude/skills/fitting/SKILL.md` — add `allowed-tools`
- `.claude/skills/mark-assessment/SKILL.md` — already has `allowed-tools` ✓
- `.claude/skills/route/SKILL.md` — already has `allowed-tools` ✓

**Change for fitting/SKILL.md:** Add to frontmatter:
```yaml
allowed-tools: [Read, Grep, Glob, "mcp__aria-universe__fitting", "mcp__aria-universe__sde", "mcp__aria-universe__market", "mcp__aria-universe__pilot"]
```

Fitting needs `fitting` (calculate_stats, hull_stats), `sde` (item_info for module verification), `market` (for price checks when relevant), and `pilot` (fittings_list for exports).

---

## Verification

1. **R1 (est. suffix):** Re-read fitting and mark-assessment SKILL.md to confirm new rules are present
2. **R2 (abyssal):** Re-read abyssal SKILL.md to confirm approximation note added
3. **R3 (mission):** Re-read mission-brief SKILL.md to confirm mixed-wave note added
4. **R4 (route):** Re-read route SKILL.md to confirm safe-mode intent detection section
5. **R5 (emoji):** `grep -r '⚠️\|✅\|✓\|📌\|🔴\|🟢\|🟡' .claude/skills/*/SKILL.md` — verify remaining emoji are only in anti-pattern docs
6. **R6 (provenance):** Verify `.claude/rules/skills.md` exists with correct `paths:` scope
7. **R7 (line budgets):** Spot-check 3 skills for `max_lines` in frontmatter
8. **R9 (watchlist):** Re-read watchlist SKILL.md for normalization section
9. **R10 (coalition):** Re-read hunting-grounds SKILL.md for citation rule
10. **R11 (allowed-tools):** Re-read fitting SKILL.md frontmatter for allowed-tools

## File Change Summary

| File | Changes |
|------|---------|
| `.claude/skills/fitting/SKILL.md` | Add est. suffix rule, `allowed-tools`, `max_lines: 50` |
| `.claude/skills/mark-assessment/SKILL.md` | Add est. suffix rule + update response template |
| `.claude/skills/abyssal/SKILL.md` | Add approximation note to NPC damage profiles |
| `.claude/skills/mission-brief/SKILL.md` | Add mixed-wave note, `max_lines: 45` |
| `.claude/skills/route/SKILL.md` | Add safe-mode intent detection section |
| `.claude/skills/gatecamp/SKILL.md` | Replace `⚠️` → `[!]` in output templates |
| `.claude/skills/killmail/SKILL.md` | Replace `⚠️` → `[!]` in output template |
| `.claude/skills/orient/SKILL.md` | Replace `⚠️` → `[!]` in output template, `max_lines: 45` |
| `.claude/skills/watchlist/SKILL.md` | Add name normalization section |
| `.claude/skills/hunting-grounds/SKILL.md` | Add coalition citation rule, `max_lines: 45` |
| `.claude/skills/threat-assessment/SKILL.md` | `max_lines: 45` |
| `.claude/skills/exploration/SKILL.md` | `max_lines: 50` |
| `.claude/skills/help/SKILL.md` | `max_lines: 80` |
| `.claude/skills/price/SKILL.md` | `max_lines: 15` |
| `.claude/skills/journal/SKILL.md` | `max_lines: 15` |
| `.claude/skills/wallet-journal/SKILL.md` | `max_lines: 20` |
| `.claude/rules/skills.md` | **New file** — provenance footer + line budget rule |
