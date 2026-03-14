> **Note:** Path disambiguation for *injected* prerequisites is superseded by dynamic context injection (see `PREREQUISITE_INJECTION_PROPOSAL.md`). Injected files are loaded via `` !`cat` `` syntax before the agent runs — no path resolution occurs at runtime. This document applies only to agent-loaded `prerequisite_files` entries.

# Prerequisite File Path Disambiguation — Status

Tracking document for applying the "Prerequisite File Path Disambiguation" standard
(see `dev/docs/CONTRIBUTING_SKILLS.md` §Prerequisite File Path Disambiguation) across all skills.

**Root cause:** Without an explicit `(project-root-relative path, not skill-directory path)`
annotation on file read instructions, the model may attempt to resolve `reference/` paths
relative to `.claude/skills/{name}/` and fail silently, falling back to training data.
Documented in exercise run 20260303-232824 (`exploration` confabulation).

**Required pattern (two elements):**
1. Parenthetical on every read instruction: `(project-root-relative path, not skill-directory path)`
2. Failure instruction: `If a read fails, do not output a blanket failure — check that the path is resolved from the project root (not the skill directory) and retry.`

**Reference implementations:** `abyssal` (line 31), `exploration` (Tool Calls table + line 40).

---

## Completed (2026-03-04)

### `mining-advisory`
- Added parenthetical to Tool Calls table Step 1 (`reference/mechanics/ore_database.md`)
- Added failure instruction after Step 1 note

### `pi`
- Added parenthetical to "Production Chain Query" Step 1 read
- Added parenthetical to "Planet Resource Query" Step 1 read
- Extended hallucination guard with parenthetical on path reference and failure note

### `reactions`
- Fixed short-name reference `fuel_blocks.json` → full path `reference/industry/fuel_blocks.json` with parenthetical
- Added failure instruction

### `skillplan`
- Added new "## Data Gate" section after "## MCP Tool Availability" with explicit read instructions for all 3 prerequisite files:
  - `reference/activities/skill_plans.yaml`
  - `reference/skills/ship_efficacy_rules.yaml`
  - `reference/skills/meta_module_alternatives.yaml`
- Added failure instruction

### `fitting`
- Fixed short-name reference `EFT-FORMAT.md` → `.claude/skills/fitting/EFT-FORMAT.md` with parenthetical
- Added parenthetical to `reference/mechanics/drones.json` in Prerequisites section
- Added parenthetical to `reference/fittings/MODULE_NAMES.md` in Prerequisites section
- Added parenthetical to secondary `reference/mechanics/drones.json` reference in Drone Selection section
- Added failure instruction to Prerequisites section

---

## Remaining Work

> **Protocol-level fix applied (2026-03-04):** Path resolution is now defined upstream in `personas/_shared/skill-loading.md` §1.5 and `CLAUDE.md` §Skill Loading step 3. Per-skill path patching is no longer required — the protocol rule covers all skills, current and future. Remaining items below are optional improvements only.

### `mission-brief` — LOW PRIORITY

`prerequisite_files` declares 4 files but the body has no consolidated Data Gate. References
to these files are scattered across ~12 inline locations without parentheticals:

| Location | Current text | Issue |
|----------|-------------|-------|
| Line 100, 163 | `` `reference/mechanics/npc_damage_types.md` `` | No parenthetical, inline prose only |
| Line 206 | `read \`reference/mechanics/drones.json\`` | No parenthetical |
| Line 207 | `read the weapon JSON (see Weapon JSON Lookup)` | Indirect — no path at all |
| Line 230 | `Read \`reference/mechanics/drones.json → enemy_recommendations.{faction}\`` | Non-standard `→` path notation; no parenthetical |
| Line 231 | `Read the weapon JSON (see Weapon JSON Lookup)` | Indirect — no path at all |

**Recommended fix:** Add a dedicated "## Data Gate" section after the frontmatter/opening,
listing all 4 prerequisite files with parentheticals and a single failure instruction.
Secondary inline references can remain as-is once the gate is in place, since the gate
is the load-time instruction.

**Risk:** Skill is 254 lines and highly tuned. Changes are additive (new section only);
existing prose does not need to change.

### `fitting` — data_sources reads (LOW PRIORITY)

The four weapon JSON files and archetype files are `data_sources` (not `prerequisite_files`),
but are referenced as explicit read instructions in the body without parentheticals:

- `reference/mechanics/hybrid_turrets.json`
- `reference/mechanics/projectile_turrets.json`
- `reference/mechanics/laser_turrets.json`
- `reference/mechanics/missiles.json`
- `reference/archetypes/INDEX.md`
- `reference/archetypes/_shared/module_tiers.yaml`

These are loaded on-demand (not at skill entry), so the failure mode is lower severity.
The `data_sources` mechanism may provide clearer path context than `prerequisite_files`,
reducing the actual risk. Monitor for confabulation before treating as urgent.

### `help` — _index.json read (LOW PRIORITY)

Step 1 instructs `Read \`.claude/skills/_index.json\`` (a `data_sources` item) without the
parenthetical. The path starts with `.claude/` making it unambiguous in practice, but it is
not technically compliant. Low actual risk.
