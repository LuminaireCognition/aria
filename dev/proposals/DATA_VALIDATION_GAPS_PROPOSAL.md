# Closing Data Validation Gaps

## Current State

ARIA manages ~120 reference files, 50 skill definitions, 6 persona directories, and structured pilot data — all feeding directly into LLM context. Three validators exist today:

| Validator | Coverage | Trigger |
|-----------|----------|---------|
| `validate-reference-data.py` | 6 files: `npc_damage_types.md`, `faction_tuning.yaml`, `INDEX.md`, `missions/*.md`, `drones.json`, `missiles.json` | Pre-commit on `reference/`, weekly CI |
| `validate-archetype-modules.py` | Archetype YAML EFT blocks + `module_tiers.yaml` + `damage_tuning` overrides (item names → SDE) | Pre-commit on `reference/archetypes/` |
| `validate-archetype-rigs.py` | Archetype YAML rig sections (SDE existence + hull-class sizing) | Pre-commit on `reference/archetypes/` |

These validators are well-built and catch real bugs (the EoM damage incident, 11 invalid module names). But they cover a narrow slice of the data surface.

## Gap Analysis

### Gap 1: Skill Index Integrity (HIGH — zero validation today)

The skill system is the primary interface between the LLM and reference data. `_index.json` declares 50 skills with `prerequisite_files`, `data_sources`, `required_tools`, `triggers`, `esi_scopes`, and `path` fields. None of these references are validated.

**Known issue found during analysis:** `reference/pve-intel/cache/INDEX.md` is declared as a prerequisite for `mission-brief` but does not exist.

**What breaks without validation:**
- A typo in `prerequisite_files` silently skips a blocking data gate → hallucination from training data
- A renamed skill directory breaks `path` → skill fails to load
- Duplicate `triggers` across skills → unpredictable skill dispatch
- `required_tools` referencing non-existent MCP actions → exercise-validate false positives
- `_index.json` drifting from SKILL.md frontmatter → conflicting metadata

**Proposed checks:**

| Check | Rule | Severity |
|-------|------|----------|
| `prerequisite_files_exist` | Every path in `prerequisite_files` resolves to a file | FAIL |
| `skill_path_exists` | `path` field points to existing SKILL.md | FAIL |
| `skill_directory_exists` | `directory` field is a real directory under `.claude/skills/` | FAIL |
| `data_sources_syntax` | Non-templated `data_sources` paths exist; templated ones (`{active_pilot}`) follow valid patterns | FAIL / WARN |
| `trigger_uniqueness` | No trigger phrase appears in more than one skill | FAIL |
| `frontmatter_sync` | SKILL.md frontmatter `prerequisite_files` matches `_index.json` entry | WARN |
| `category_enum` | `category` is one of: `tactical`, `operations`, `financial`, `identity`, `industry`, `system` | FAIL |
| `model_enum` | `model` is one of: `haiku`, `sonnet`, `opus` | FAIL |
| `required_tools_format` | `required_tools` entries follow `dispatcher.action` format | WARN |
| `esi_scopes_format` | `esi_scopes` entries match `esi-*.v1` pattern | WARN |

**Implementation:** Single script `dev/scripts/validate-skill-index.py` (~300 LOC). No external dependencies — pure file existence and JSON/YAML parsing.

---

### Gap 2: Structured Reference Data (HIGH — 30+ JSON/YAML files with zero schema validation)

The `reference/` tree contains ~35 structured data files (JSON/YAML) that skills load as prerequisite context. Only 5 of these are validated. The rest have no schema enforcement, no cross-referencing, and no staleness tracking.

**Files with highest risk (directly drive skill output):**

| File | Size | Skills Using It | Risk |
|------|------|-----------------|------|
| `abyssal_deadspace.json` | 14.6K | `/abyssal` | Wrong weather effects → wrong fit advice |
| `fuel_blocks.json` | 4.5K | `/reactions` | Wrong recipes → incorrect cost calculations |
| `planetary-interaction.json` | 12.8K | `/pi` | Wrong P1→P4 chains → bad colony advice |
| `chokepoints.json` | 4.0K | `/threat-assessment`, `/hunting-grounds` | Wrong system IDs → missed gatecamps |
| `epic_arcs.json` | 5.7K | `/standings` | Wrong standing thresholds → bad faction planning |
| `security_status.json` | 3.8K | `/sec-status` | Wrong penalty thresholds → dangerous advice |
| `standings_thresholds.json` | 6.4K | `/standings` | Wrong agent access levels → wasted time |
| `hybrid_turrets.json` | 7.6K | `/mission-brief`, `/fitting` | Wrong DPS/range → bad fit choices |
| `laser_turrets.json` | 7.8K | `/mission-brief`, `/fitting` | Same |
| `projectile_turrets.json` | 6.6K | `/mission-brief`, `/fitting` | Same |
| `skill_plans.yaml` | — | `/skillplan` | Wrong training paths → wasted SP |
| `ship_efficacy_rules.yaml` | — | `/skillplan` | Wrong bonuses → bad ship recommendations |
| `breakpoint_skills.yaml` | — | `/skillplan` | Wrong breakpoints → incomplete training |
| `meta_module_alternatives.yaml` | — | `/skillplan` | Wrong substitutions → over/under-fitting |
| `skill_tiers.yaml` | — | `/fit-recommend`, `/fit-budget` | Wrong tier definitions → wrong archetypes |

**Proposed checks (two tiers):**

**Tier A — Schema validation (offline, fast):**
- JSON/YAML files parse without error
- Required top-level keys present (per-file schema)
- `_meta.last_verified` exists and is valid ISO date
- `_meta.last_verified` is within 90-day staleness window
- Nested structures match expected shapes (e.g., `fuel_blocks.json` entries have `materials`, `output_quantity`, `time`)

**Tier B — SDE cross-reference (requires `cache/aria.db`):**
- Item names in turret/weapon JSON files resolve in SDE `invTypes`
- System IDs in `chokepoints.json` resolve in SDE `mapSolarSystems`
- Skill names in `skill_plans.yaml`, `breakpoint_skills.yaml`, `ship_efficacy_rules.yaml` resolve in SDE
- Station IDs in `trade_hubs.json` resolve in SDE `staStations`
- Corporation IDs in `npc_corporations.json` resolve in SDE `crpNPCCorporations`

**Implementation:** Extend existing `validate-reference-data.py` with a `--schema` pass, or create `validate-reference-schemas.py` (~400 LOC). SDE cross-reference checks are gated on `cache/aria.db` presence (SKIP if missing, like existing validators).

---

### Gap 3: Archetype Structural Integrity (MEDIUM — partially covered)

Module names and rig sizing are validated. But archetype YAML files have broader structural requirements that go unchecked:

| Check | Rule | Current Status |
|-------|------|----------------|
| Module names exist in SDE | Item resolution | **Covered** |
| Rig sizing matches hull class | Small/Medium/Large | **Covered** |
| `archetype.hull` matches directory path | Hull name consistency | **Not checked** |
| `archetype.skill_tier` is valid enum | `t1`, `meta`, `t2` | **Not checked** |
| `roles` values are from defined set | Consistent role taxonomy | **Not checked** |
| `damage_tuning.default_damage` is valid | `kinetic`, `thermal`, `em`, `explosive` | **Not checked** |
| `damage_tuning.tank_profile` matches `faction_tuning.yaml` keys | Profile name agreement | **Not checked** |
| `upgrade_path.next_tier` forms valid chain | `t1 → meta → t2`, no loops | **Not checked** |
| `stats.validated_date` is recent | Staleness | **Not checked** |
| INDEX.md paths resolve to files | Broken links in lookup table | **Not checked** |
| Faction override names match `npc_damage_types.md` | Faction name normalization | **Not checked** |

**Implementation:** Add checks to existing `validate-archetype-modules.py` or a new `validate-archetype-structure.py` (~250 LOC).

---

### Gap 4: Persona & Overlay Integrity (MEDIUM — zero validation today)

Personas drive voice, tone, and skill overlay loading. A broken persona path or missing overlay causes silent fallback to base behavior — the user gets ARIA instead of their configured persona with no error.

**What needs validation:**

| Check | Rule | Severity |
|-------|------|----------|
| `manifest.yaml` exists | Every `personas/*/` has one | FAIL |
| Required manifest fields | `name`, `subtitle`, `directory`, `factions`, `address`, `greeting` | FAIL |
| `manifest.directory` matches actual directory name | Self-referential consistency | FAIL |
| `manifest.factions` values are valid | Known faction names | WARN |
| `voice.md` exists | Every persona has a voice file | FAIL |
| Skill overlays referenced exist | `skill-overlays/{name}.md` for each declared overlay | FAIL |
| `rp_level` values valid | `off`, `on`, `full` — not deprecated `lite` | FAIL |
| Shared resources exist | `_shared/empire/`, `_shared/pirate/` have expected files | WARN |
| Compiled artifact not stale | `.persona-context-compiled.json` timestamp vs source file mtimes | WARN |

**Implementation:** `dev/scripts/validate-personas.py` (~200 LOC). Pure filesystem checks.

---

### Gap 5: Cross-File Reference Integrity (MEDIUM — emergent from gaps 1-4)

Many data relationships span multiple files. Individual validators check one file at a time. Cross-file consistency requires a holistic pass:

| Relationship | Source | Target | Current |
|-------------|--------|--------|---------|
| Skill `prerequisite_files` → reference files | `_index.json` | `reference/**` | **Not checked** |
| Archetype INDEX → YAML files | `archetypes/INDEX.md` | `hulls/**/*.yaml` | **Not checked** |
| Faction names in archetypes → `npc_damage_types.md` | `damage_tuning.overrides` keys | Faction names | **Not checked** |
| `skill_tiers.yaml` module expectations → `module_tiers.yaml` | Category references | Upgrade paths | **Not checked** |
| `data-sources.json` pinned versions → actual SDE/EOS | Pinned SHA/tag | Remote repository | **Checked in data-health.yml** |

These cross-file checks can be distributed into the relevant validators (Gap 1 validator handles prerequisite resolution, Gap 3 handles archetype cross-refs).

---

### Gap 6: MCP Policy Consistency (LOW — config validation)

`reference/mcp-policy.json` defines access control for MCP tools. `exercise-validate.py` already does an optional policy pre-flight. But the policy itself is never validated against the actual MCP tool inventory or the `required_tools` declared in skills.

**Proposed checks:**
- Every `required_tools` action in `_index.json` has a corresponding policy entry
- Policy `allowed_actions` reference valid dispatcher.action pairs
- No orphaned policy entries (actions defined in policy but used by no skill)

**Implementation:** Fold into skill-index validator as an optional `--policy` pass.

---

## Implementation Plan

### Phase 1: Skill Index Validator (highest impact, simplest)

**Script:** `dev/scripts/validate-skill-index.py`
**Estimated size:** ~300 LOC
**Dependencies:** None (JSON parsing + filesystem)
**Trigger:** Pre-commit on `.claude/skills/` changes

Core checks:
1. Parse `_index.json`, validate schema basics (count matches array length, enums valid)
2. For each skill: verify `path` exists, `directory` exists, all `prerequisite_files` exist
3. Collect all triggers, detect duplicates
4. Optionally sync-check SKILL.md frontmatter vs index entry

This catches the known missing-file bug (`pve-intel/cache/INDEX.md`) and prevents future drift.

### Phase 2: Reference Schema Validator

**Script:** `dev/scripts/validate-reference-schemas.py`
**Estimated size:** ~400 LOC
**Dependencies:** `cache/aria.db` for SDE checks (optional, SKIP if missing)
**Trigger:** Pre-commit on `reference/` changes (alongside existing `validate-reference-data.py`)

Schema definitions can be inline dicts — no need for a JSON Schema library. Each file gets a shape check:

```python
SCHEMAS = {
    "fuel_blocks.json": {
        "required_keys": ["fuel_blocks", "_meta"],
        "entry_shape": {"materials": list, "output_quantity": int, "time_seconds": int},
    },
    "chokepoints.json": {
        "required_keys": ["systems", "_meta"],
        "entry_shape": {"system_id": int, "name": str, "security": float},
    },
    # ...
}
```

SDE cross-reference is a second pass that validates item/system/skill names against the database.

### Phase 3: Archetype Structure + Persona Validators

**Scripts:** Extend existing archetype validators + new `validate-personas.py`
**Estimated size:** ~250 LOC each
**Trigger:** Pre-commit on respective directories

### Phase 4: Cross-File Reference Pass

Integrate cross-file checks into the validators from phases 1-3 rather than building a separate tool. Each validator already loads its domain — adding cross-references is incremental:

- Skill-index validator: check prerequisite_files exist (already in Phase 1)
- Archetype validator: check INDEX.md paths resolve, faction names normalized
- Reference schema validator: check skill names, item names, system IDs against SDE

---

## Pre-commit & CI Integration

```yaml
# .pre-commit-config.yaml additions
- id: skill-index-check
  name: Skill index validation
  entry: uv run python3 dev/scripts/validate-skill-index.py
  language: system
  files: ^\.claude/skills/
  pass_filenames: false

- id: reference-schema-check
  name: Reference schema validation
  entry: uv run python3 dev/scripts/validate-reference-schemas.py
  language: system
  files: ^reference/
  pass_filenames: false

- id: persona-check
  name: Persona validation
  entry: uv run python3 dev/scripts/validate-personas.py
  language: system
  files: ^personas/
  pass_filenames: false
```

**CI (`data-health.yml`):** Add skill-index and reference-schema checks to the weekly scheduled run. These are lightweight and need no external dependencies.

---

## Coverage Impact

| Category | Files | Current Coverage | After Proposal |
|----------|-------|-----------------|----------------|
| Skill definitions | 50 skills + index | 0% | **100%** (index integrity, path resolution, trigger uniqueness) |
| Reference mechanics (JSON/YAML) | ~35 files | 14% (5/35) | **85%** (schema + SDE cross-ref for 30 additional files) |
| Reference mechanics (Markdown) | ~10 files | 30% | 30% (markdown content validation is scope for external validators) |
| Archetype fitting YAML | ~40 files | Module names + rig sizing | **+structural integrity** (hull consistency, tier chains, faction names) |
| Archetype shared configs | 3 files | 2/3 (`module_tiers`, `faction_tuning`) | **3/3** (`skill_tiers.yaml` added) |
| Persona definitions | 6 personas | 0% | **100%** (manifest, voice, overlay existence) |
| Cross-file references | ~100 links | 0% | **~80%** (prerequisite paths, INDEX links, faction name normalization) |
| MCP policy | 1 file | Optional pre-flight only | **Skill-aligned** (required_tools coverage) |

**Overall structured data coverage: ~15% → ~85%**

---

## What Remains Out of Scope

- **External validation** (wiki fetching): Already proposed in `REFERENCE_DATA_VALIDATION_PROPOSAL.md` Phase 2. Complementary, not duplicate.
- **Fitting engine validation** (CPU/PG/cap): Requires EOS or fitting MCP tool. Covered by exercise runner.
- **Pilot data validation**: Pilot profiles are user-edited and ESI-synced. Validating their structure is lower-value since the boot hooks already handle missing fields gracefully.
- **Auto-remediation**: Validators report, humans fix. Same principle as existing validators.
- **Markdown prose validation**: Content quality of `.md` reference docs is not machine-verifiable. The exercise-validate system handles output quality.

## Priority

| Phase | Effort | Impact | Blocks |
|-------|--------|--------|--------|
| Phase 1: Skill index | Low (~300 LOC) | HIGH — prevents silent skill breakage | Nothing |
| Phase 2: Reference schemas | Medium (~400 LOC) | HIGH — covers 30 unvalidated data files | Nothing |
| Phase 3: Archetype + persona | Medium (~500 LOC) | MEDIUM — structural integrity | Nothing |
| Phase 4: Cross-file refs | Low (incremental) | MEDIUM — emergent consistency | Phases 1-3 |

Phase 1 is the single highest-value item: it's small, has zero dependencies, and directly prevents the class of bug where a renamed or deleted file silently breaks a skill's data gate — causing the LLM to fall back on training data without any signal.
