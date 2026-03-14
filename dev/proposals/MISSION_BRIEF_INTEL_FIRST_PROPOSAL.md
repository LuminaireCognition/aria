# Mission Brief: Intel-Only Default

## Problem

`/mission-brief` delays actionable intel while generating a ship fit the pilot didn't ask for.

The current flow is: read pilot data → fetch wiki → select archetype → adapt fit → call `fitting(calculate_stats)` + `fitting(check_requirements)` → render everything. The fitting engine MCP calls are the slowest step, and the entire response is blocked behind them. A pilot who just accepted a mission and wants to know "what do they deal, what's the blitz" has to wait for fit generation and validation they may not need.

Additionally, the fitting pipeline dominates the skill's token budget:

| Category | Files | Injected bytes |
|----------|-------|----------------|
| Intel-only | `npc_damage_types.md`, PVE indexes | ~5 KB |
| Fitting-only | 5 weapon JSONs, archetype INDEX, `faction_tuning.yaml`, tank summary | ~46 KB |

Over 90% of the injected prerequisite data exists to support fitting. Removing it from the default path cuts prompt token cost by ~12K tokens per invocation.

## Proposed Change

**Make fitting opt-in.** By default, `/mission-brief` delivers intel only. A `--fit` flag adds fitting back for pilots who want it.

### Default flow (no `--fit`)

1. Read `profile.md` (for RP level, constraints) — `skills.json` and `ships.md` are NOT read
2. Fetch mission intel (cache → wiki → faction fallback)
3. Render intel-only response immediately

### With `--fit` flag

1. Read all three pilot prerequisite files (profile, skills, ships) — same as today
2. Fetch mission intel
3. Read fitting reference data at runtime (archetypes, faction tuning, weapon JSONs)
4. Select archetype, adapt fit, validate via fitting MCP
5. Render full response (intel + fit)

### Argument Parsing

Current `argument-hint` is `<mission_name> [--level N]`. Change to `<mission_name> [--level N] [--fit]`.

The `--fit` flag is positional-insensitive: `/mission-brief Recon 3 --fit` and `/mission-brief --fit Recon 3` both work. Parsing is simple string matching — if `--fit` appears anywhere in the argument string, enable fitting mode.

## SKILL.md Changes

### Frontmatter

**Remove from `injected_prerequisites`** (fitting-only data):
- `reference/mechanics/drones.json`
- `reference/mechanics/missiles.json`
- `reference/mechanics/projectile_turrets.json`
- `reference/mechanics/laser_turrets.json`
- `reference/mechanics/hybrid_turrets.json`
- `reference/archetypes/INDEX.md`
- `reference/archetypes/_shared/faction_tuning.yaml`

**Keep in `injected_prerequisites`** (needed for intel):
- `reference/mechanics/npc_damage_types.md`
- `reference/pve-intel/INDEX.md`
- `reference/pve-intel/missions/INDEX.md`

**Move to `data_sources`** (agent reads at runtime only when `--fit` is present):
- `reference/archetypes/INDEX.md`
- `reference/archetypes/_shared/faction_tuning.yaml`
- `reference/mechanics/drones.json`
- `reference/mechanics/missiles.json`
- `reference/mechanics/projectile_turrets.json`
- `reference/mechanics/laser_turrets.json`
- `reference/mechanics/hybrid_turrets.json`

No new frontmatter keys are introduced. This uses the existing `data_sources` mechanism — the agent reads these files at runtime when the `--fit` flag is present, just as it already reads archetype hull files on demand. Prose instructions in the Protocol section gate when these reads happen.

**Simplify `prerequisite_files`:**
- Default: only `userdata/pilots/{active_pilot}/profile.md`
- With `--fit`: add `skills.json` and `ships.md`

**Keep `allowed-tools` unchanged.** `mcp__aria-universe__fitting` remains in the list. The prose instructions gate when the agent calls it — without `--fit`, the fitting sections are skipped entirely, so the tool is never invoked. This avoids introducing conditional frontmatter values, which the skill-loading system does not support.

**Update `preferred_max_lines`:** Change from `45` to `25`. The Protocol section specifies that `--fit` responses target 45 lines instead.

**Update `argument-hint`:** `<mission_name> [--level N] [--fit]`

### Protocol Section

Replace:

> **Intel first, fitting second.** Present Quick Reference, Spawns, Blitz, and Tactical Notes immediately from prerequisite data and wiki. Append the Mission Fit after fitting engine validation.

With:

> **Intel only by default.** Present Quick Reference, Spawns, Blitz, and Tactical Notes from prerequisite data and wiki. Fitting is opt-in via `--fit` flag — without it, skip all fitting sections entirely and do not read fitting reference data.
>
> **With `--fit`:** Read `skills.json`, `ships.md`, and all fitting `data_sources` before generating output. Target 45 lines instead of the default 25.

### Spawn Data Guard

Update the fallback language. Replace:

> "Proceed directly to fitting"

With:

> "End the response" (intel-only mode) or "Proceed directly to fitting" (with `--fit`)

The guard itself is unchanged — just the terminal action adapts to the active mode.

### Tank Hardener Reference

The current `!` injection (`!uv run python3 ... tank_summary.py`) executes at skill-load time and cannot be conditionally skipped. Replace the `!` injection with a runtime instruction:

> **When `--fit` is present:** Run `uv run python3 ${CLAUDE_SKILL_DIR}/scripts/tank_summary.py` via Bash and use the output as the tank hardener reference.

Remove the `!` line from the Injected Reference Data section. This is consistent with the Option B approach — all fitting data is loaded at runtime, not injected.

### Response Format

**Default (intel-only):**

1. **Quick Reference** — table: Tank, Deal, EWAR, Objective
2. **Blitz** — numbered steps (omit if unavailable)
3. **Spawns** — wave structure with distances and triggers
4. **Tactical Notes** — EWAR warnings, special mechanics (omit if trivial)

**With `--fit`:**

1. **Quick Reference** — table: Tank, Deal, EWAR, Objective
2. **Mission Fit** — single adapted EFT block in code fence
3. **Blitz** — numbered steps (omit if unavailable)
4. **Spawns** — wave structure with distances and triggers
5. **Tactical Notes** — EWAR warnings, special mechanics (omit if trivial)

### Sections to Gate Behind `--fit`

The following sections become conditional (only rendered when `--fit` is passed):
- Pilot Data Gate (skills.json + ships.md reads)
- Ship Roster Check
- Archetype Selection
- Fit Adaptation
- Fitting Validation
- Tank Hardener Reference (runtime `tank_summary.py` call)
- Runtime reads for weapon JSONs, archetype INDEX, faction_tuning.yaml

### Injected Reference Data Section

Remove all `!cat` injections for fitting-only files. The section retains only:
- `!cat reference/mechanics/npc_damage_types.md`
- `!cat reference/pve-intel/INDEX.md`
- `!cat reference/pve-intel/missions/INDEX.md`

### Line Budget

Default intel-only responses should target **20–25 lines** (down from 45). With `--fit`, target **45 lines** (same as today). The `preferred_max_lines` frontmatter value changes to `25`; the `--fit` override is specified in Protocol prose.

### Suggested Followup

When rendering an intel-only response, append a one-liner after the Sources footer:

> `Tip: /mission-brief <name> --fit for a tailored ship fitting`

This teaches the pilot about the opt-in flag without cluttering the intel.

## Impact

| Metric | Before | After (default) | After (--fit) |
|--------|--------|-----------------|---------------|
| Injected tokens | ~12K | ~1.3K | ~1.3K + runtime reads |
| MCP tool calls | 2 (fitting) | 0 | 2 |
| Prerequisite file reads | 3 | 1 | 3 + data_sources |
| Response latency | High (fitting-bound) | Low (wiki-bound) | Same as before |
| Response lines | 30–45 | 20–25 | 30–45 |

Note: with `--fit`, injected token cost drops to ~1.3K (only intel data is injected) but total context is similar to today since fitting data is loaded via runtime `Read` calls instead.

## What This Does NOT Change

- **Fitting skill is unaffected.** `/fitting` continues to work independently for dedicated fit requests.
- **Intel retrieval is unchanged.** Cache → wiki → faction fallback flow stays the same.
- **Spawn Data Guard is unchanged.** The no-fabrication rule still applies; only the fallback terminal action adapts to the active mode.
- **`--fit` behavior is identical to today's default.** No fitting logic is removed, only gated.
- **Skill-loading infrastructure is unchanged.** No new frontmatter keys, no conditional injection mechanism. All gating is prose-driven using existing `data_sources` and runtime `Read` patterns.

## Migration

No user-facing migration needed. The change is backwards-compatible:
- Pilots who never used `--fit` get faster, leaner briefs
- Pilots who want fits add `--fit` and get the same output as before
- The `/fitting` skill remains the primary entry point for dedicated fitting work

## Routing Hint Update

Add to the CLAUDE.md routing table:

| User says | Invoke |
|-----------|--------|
| "brief me on [mission]", "what's the blitz for [mission]" | `/mission-brief` (intel-only default) |
| "fit for [mission]", "fitting for [mission]" | `/mission-brief --fit` or `/fitting` |
