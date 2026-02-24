# ARIA Skill Test Results (clones) - 2026-02-23

**Test scope:** 1 skill (MED ESI, previously untested)
**Pilot:** Federation Navy Suwayyah (2123984364) - Gallente, aria-mk4 persona, rp_level: off
**Method:** 2 sub-agents via Task tool (one per exercise query)
**Code state:** Post-commit 9d062774 (skill-testing-cleanup branch)
**MCP dispatchers available:** All 8 (universe, market, sde, skills, fitting, status, killmails, pilot)
**Preflight:** PASS (ok: true, no missing sources or scopes)

## Execution Summary

| # | Query | Variant | Calls | Eff% | Outcome | Notes |
|---|-------|---------|------:|-----:|---------|-------|
| 1 | Medical clone + implant risk | `clones` (full) | 2 | 100 | SUCCESS | status + CLI clones |
| 2 | Jump clone cooldown check | `jump-clones` | 1 | 100 | SUCCESS | Single CLI call |

**Totals:** 2/2 SUCCESS
**Aggregate calls:** 3 | **Aggregate efficiency:** 100%

---

## Per-Query Results

### 1. Full clone status (MED ESI)
**Query:** "Where is my medical clone and what implants will I lose if I get podded?"
**Variant:** `clones` (full status)
**Calls:** 2 | **Efficiency:** 100%

1. MCP status() → system health check
2. Bash: `uv run python -m aria_esi clones` → full clone + implant data

**Data returned:**
- Medical clone: Sortet V - Moon 1 - Federation Navy Assembly Plant (0.6 sec)
- Jump clones: 0
- Jump cooldown: Available (not on cooldown)
- Active implants: 5 attribute enhancers (slots 1-5)
  - Slot 1: Limited Ocular Filter (+1 Perception)
  - Slot 2: Limited Memory Augmentation (+1 Memory)
  - Slot 3: Limited Neural Boost - Beta (+1 Willpower)
  - Slot 4: Limited Cybernetic Subprocessor (+1 Intelligence)
  - Slot 5: Limited Social Adaptation Chip - Beta (+1 Charisma)

**Response quality:** Complete. Included implant loss warning, safety tip about creating jump clones before risky operations, and Infomorph Psychology skill reference.

---

### 2. Jump clone cooldown check (MED ESI)
**Query:** "Can I jump clone right now or am I on cooldown?"
**Variant:** `jump-clones`
**Calls:** 1 | **Efficiency:** 100%

1. Bash: `uv run python -m aria_esi jump-clones` → jump clone status

**Data returned:**
- Jump clone count: 0
- Jump available: true
- Cooldown remaining: null (no active cooldown)
- Last jump: null (never jumped)

**Response quality:** Complete. Answered cooldown question directly, included Infomorph Psychology skill requirements for creating jump clones (L1-L5 progression).

---

## Verification Anchors

These values can be checked against future runs to detect regressions:

| Field | Value | Stability |
|-------|-------|-----------|
| Medical clone location | Sortet V - Moon 1 - Federation Navy Assembly Plant | Stable (unless manually changed) |
| Medical clone system sec | 0.6 | Static |
| Jump clone count | 0 | Changes if pilot trains Infomorph Psychology |
| Active implant count | 5 | Changes if pod loss or manual removal |
| Implant slots occupied | 1, 2, 3, 4, 5 | Changes with implant swaps |
| Hardwiring slots (6-10) | Empty | Changes if hardwirings installed |
| Jump cooldown active | No | Changes after a jump clone swap |
| CLI command used | `aria-esi clones` / `aria-esi jump-clones` | Stable (API) |

## Issues Found

None. Both queries executed cleanly with optimal call counts.

## Notes

- This skill was previously categorized as "MED ESI, out of scope" in the NONE/LOW testing rounds
- ESI scopes `esi-clones.read_clones.v1` and `esi-clones.read_implants.v1` both authenticated successfully
- The `aria-esi clones` CLI returns all data (medical clone, jump clones, implants) in a single call
- The `aria-esi jump-clones` variant correctly filters to just jump clone + cooldown status
- No MCP dispatcher needed — clone data is pure ESI, served via CLI
