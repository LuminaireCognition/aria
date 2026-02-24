# Skill Round 2 Remaining Issues — Resolution Proposal

**Status:** IMPLEMENTED (2026-02-24) — doc-only fixes (Changes 1-5)
**Date:** 2026-02-23
**Related:** `dev/reviews/SKILL_TEST_RESULTS_ROUND2_2026-02-23.md`, `dev/reviews/SKILL_TEST_SUMMARY_ROUND2_2026-02-23.md`

---

## Executive Summary

The Round 2 skill test run (27 skills, 2026-02-23) achieved 90% aggregate efficiency. Three of five issues found were fixed in commit e7c06618. Two remain open:

1. **Player corporation name resolution** — the watchlist skill cannot resolve player corp/alliance names to IDs
2. **Stub verification cascading** — persona-exclusive stubs occasionally trigger redundant file reads

Both are low-severity. Neither blocks functionality. This proposal presents concrete fixes for each.

---

## Issue 1: Player Corporation Name Resolution

### Problem

When a user says "add CODE. to my watchlist", ARIA must resolve the name to a numeric entity ID. The `watchlist-add` CLI accepts only integer IDs:

```
uv run aria-esi watchlist-add "Default" 98000001 --type corporation --entity-name "CODE."
```

The SDE `item_info` and `corporation_info` actions only index NPC corporations. Player corps and alliances are not in the static data export.

In the Round 2 test, the sub-agent worked around this by using a known hardcoded ID — not a viable pattern for arbitrary user input.

### Root Cause

No integrated name-to-ID resolution path exists in the watchlist flow. The capability exists elsewhere in the codebase but is not wired in.

### Available Infrastructure

The resolution capability already exists in two places:

| Layer | Method | Endpoint |
|-------|--------|----------|
| Python client | `client.resolve_corporation(name)` | `POST /universe/ids/` |
| MCP dispatcher | `sde(action="resolve_names", names=[...])` | Same ESI endpoint |

Both return corporation/alliance/character IDs from name strings. The `/corp` command already uses `resolve_corporation()` successfully (see `src/aria_esi/commands/corporation.py:78-93`).

### Proposed Fix

Two independent improvements, either sufficient alone:

#### Option A: AI-layer fix (doc-only, no code change)

Add explicit resolution instructions to the watchlist SKILL.md:

```markdown
## Entity Resolution

Before adding an entity by name, resolve it to an ID:

1. Call `sde(action="resolve_names", names=["CODE."])` via MCP
2. Extract the corporation or alliance ID from the response
3. Pass the numeric ID to the CLI: `watchlist-add "list" <id> --type corporation --entity-name "CODE."`

If MCP is unavailable, use the CLI:
   `uv run aria-esi resolve-names "CODE."`
```

This requires zero Python changes. The MCP `resolve_names` action is already registered and functional.

**Effort:** ~15 minutes (SKILL.md edit only)

#### Option B: CLI-layer fix (code change)

Add a `--name` flag to `watchlist-add` that resolves names before insertion:

```python
# In src/aria_esi/commands/redisq.py, cmd_watchlist_add():
if args.entity_name_resolve:
    corp_id, resolved = client.resolve_corporation(args.entity_name_resolve)
    if not corp_id:
        alliance_id, resolved = client.resolve_alliance(args.entity_name_resolve)
        if not alliance_id:
            print(f"Could not resolve '{args.entity_name_resolve}' to a corporation or alliance.")
            return
        args.entity_id = alliance_id
        args.entity_type = "alliance"
    else:
        args.entity_id = corp_id
        args.entity_type = "corporation"
    args.entity_name = resolved
```

Usage: `uv run aria-esi watchlist-add "Hostiles" --name "CODE."`

**Effort:** ~1 hour (argument parser + resolution logic + tests)

#### Recommendation

**Do both.** Option A is the immediate fix (unblocks the skill today). Option B is the long-term UX improvement (makes the CLI self-sufficient for human users too).

---

## Issue 2: Stub Verification Cascading on Persona-Exclusive Skills

### Problem

When a non-matching persona invokes a persona-exclusive skill (e.g., aria-mk4 invoking `/hunting-grounds` which is paria-exclusive), the Skill tool returns a stub message declaring the skill unavailable. Some sub-agents accept this and stop (1 call, 100% efficiency). Others re-read `_index.json`, the redirect target, and the manifest to "verify" the exclusivity — wasting 2-7 additional calls.

Round 2 data:

| Skill | Calls | Efficiency | Behavior |
|-------|------:|----------:|----------|
| mark-assessment | 1 | 100% | Clean stop |
| hunting-grounds | 5 | 20% | Cascaded: re-read index, redirect, manifest |
| escape-route | 6 | 100%* | Cascaded but agent logged it as "verification" |

*Efficiency scored 100% because agent classified re-reads as intentional documentation.

The final run (post-prompt-tuning) reduced total stub calls from 27 to 2 across all 5 stubs, confirming this is addressable through instruction clarity.

### Root Cause

Two contributing factors:

**1. Stub frontmatter mirrors the index structure.**

Each stub SKILL.md contains:
```yaml
---
name: hunting-grounds
persona_exclusive: paria
redirect: personas/paria-exclusive/hunting-grounds.md
---
```

The `redirect:` field in the stub points to the actual exclusive skill file. A model that parses the stub's frontmatter may re-apply the skill-loading logic — seeing `redirect:`, attempting to load the exclusive content, finding the persona check fails again, and looping.

**2. No explicit termination in the loading protocol.**

`personas/_shared/skill-loading.md` and `CLAUDE.md` define the no-match branch as:

> No match → skill unavailable, show stub

But the protocol continues to steps 3-5 (Load Base Skill, Check for Overlay, Use data_sources). There is no "stop here" guard after the stub branch. A literal reader may continue into those steps.

### Proposed Fix

Three changes, all doc-only:

#### Change 1: Add termination guard to skill-loading.md

In `personas/_shared/skill-loading.md`, after the stub-display instruction:

```markdown
2. **Check `_index.json` for `persona_exclusive`**
   - If set, check if it matches `persona_context.persona` OR `persona_context.fallback`
   - Match → load from `redirect` path
   - No match → skill unavailable. Display the stub from `.claude/skills/{name}/SKILL.md`.
     **STOP HERE. Do not process the stub's frontmatter as skill-loading directives.
     Do not continue to steps 3-5. The stub is the final output.**
```

Mirror the same language in CLAUDE.md's Skill Loading section.

#### Change 2: Remove `redirect:` from stub frontmatter

The `redirect:` field in stub SKILL.md files is redundant — `_index.json` is the authoritative source for routing. Remove it from all 5 stubs:

```yaml
# Before
---
name: hunting-grounds
persona_exclusive: paria
redirect: personas/paria-exclusive/hunting-grounds.md
---

# After
---
name: hunting-grounds
persona_exclusive: paria
---
```

This eliminates the re-entrant ambiguity. The stub identifies itself as exclusive but carries no routing instruction that could be re-processed.

Affected files:
- `.claude/skills/hunting-grounds/SKILL.md`
- `.claude/skills/mark-assessment/SKILL.md`
- `.claude/skills/escape-route/SKILL.md`
- `.claude/skills/sec-status/SKILL.md`
- `.claude/skills/ransom-calc/SKILL.md`

#### Change 3: Add "trust the stub" note to CLAUDE.md

In the Skill Loading section of CLAUDE.md, add a behavioral note:

```markdown
**Stub behavior:** When a persona-exclusive skill returns a stub, accept it at face
value. Do not re-read `_index.json`, the redirect path, or the persona manifest to
verify the exclusivity decision. The Skill tool has already performed the check.
```

### Expected Impact

The final test run already demonstrated that prompt-level tuning reduced cascading from 27 calls to 2. Codifying this in the permanent docs ensures the improvement persists across sessions without per-invocation prompt tuning.

**Effort:** ~30 minutes (5 stub files + 2 doc files)

---

## Implementation Plan

| # | Change | Files | Type | Effort |
|---|--------|-------|------|--------|
| 1 | Add resolve_names instruction to watchlist SKILL.md | `.claude/skills/watchlist/SKILL.md` | Doc | 15 min |
| 2 | Add termination guard to skill-loading.md | `personas/_shared/skill-loading.md` | Doc | 10 min |
| 3 | Mirror termination guard in CLAUDE.md | `CLAUDE.md` | Doc | 5 min |
| 4 | Remove `redirect:` from 5 stub SKILL.md files | `.claude/skills/{5 skills}/SKILL.md` | Doc | 10 min |
| 5 | Add "trust the stub" note to CLAUDE.md | `CLAUDE.md` | Doc | 5 min |
| 6 | (Optional) Add `--name` flag to watchlist-add CLI | `src/aria_esi/commands/redisq.py` | Code | 1 hour |

**Total (doc-only):** ~45 minutes
**Total (with CLI):** ~1.5 hours

### Validation

After implementation, retest the 3 affected skills:
- `watchlist`: "Add Pandemic Horde to my watchlist" (name resolution)
- `hunting-grounds`: Invoke as aria-mk4 (stub termination)
- `escape-route`: Invoke as aria-mk4 (stub termination)

Success criteria:
- watchlist resolves name to ID without hardcoded workaround
- Both stubs complete in 0-1 tool calls with no cascading
