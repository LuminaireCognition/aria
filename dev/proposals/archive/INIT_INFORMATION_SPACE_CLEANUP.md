# Init Information Space Cleanup

**Status:** IMPLEMENTED (2026-02-22)
**Related:** `aria-init`, `.claude/scripts/aria-oauth-setup.py`, boot hook, `aria-esi persona-context`

---

## Executive Summary

The two onboarding scripts (`aria-init` and `aria-oauth-setup.py`) populate an information space with coherence issues: a duplicate file that causes wrong reads, a missing section that blocks boot, dead templates, and redundant reference data baked into pilot files. This proposal addresses all six issues in priority order.

**Severity breakdown:**
- 3 active friction items (cause errors or maintenance traps today)
- 3 context budget waste items (drag on session quality as the project grows)

---

## Problem Inventory

### P1: Active Friction

#### 1. Duplicate `blueprints.md`

`aria-init` writes identical content to two paths:

```
userdata/pilots/{id}/blueprints.md           ← orphaned copy
userdata/pilots/{id}/industry/blueprints.md  ← ESI sync target
```

ESI sync (`aria-esi-sync.py:530`) writes to `industry/blueprints.md`. Any skill or command that reads `blueprints.md` from the pilot root gets stale data. The root copy is never updated after init.

**Impact:** Wrong blueprint data served to skills that resolve from pilot root.

#### 2. No `persona_context` after init

`aria-init` generates `profile.md` without a `persona_context` YAML section. That section is only added by `aria-esi persona-context` during the seed phase. If seeding is skipped (`--skip-seed`), fails, or the user runs OAuth before seeding:

1. `profile.md` has no `persona_context` block
2. `.persona-context-compiled.json` doesn't exist
3. Boot hook's artifact verification returns `integrity_failed` (fixed to `missing` in current branch)
4. Boot either blocks or warns, depending on the fix state

**Impact:** Was the direct cause of the `SessionStart:startup hook error` investigated in this session.

#### 3. Templates exist but aren't used

`aria-init` validates that 7 template files exist in `templates/` (lines 310-325) but never reads them. All content is generated from inline heredocs in `generate_*` functions. The templates are dead code that:

- Must be kept in sync with heredoc output (they aren't)
- Cause init to fail if deleted (prerequisite check)
- Mislead contributors into thinking init uses template substitution

**Impact:** Maintenance trap. False prerequisite failure if templates are cleaned up.

### P2: Context Budget Waste

#### 4. Reference data baked into pilot files

`missions.md` contains a hardcoded faction damage profile table (6 factions, ~40 lines). This same data exists in `reference/pve-intel/INDEX.md` (git-tracked, authoritative, already loaded by `/mission-brief`). The per-pilot copy:

- Is never updated after init
- Duplicates authoritative reference data
- Costs context tokens when missions.md is loaded by skills

**Impact:** ~40 lines of redundant context per skill invocation that reads missions.md.

#### 5. Redundancy across pilot files

The same information appears in multiple init-generated files:

| Data | Files Where It Appears |
|------|------------------------|
| Faction alignment | `profile.md`, `operations.md` |
| Ship roster | `operations.md`, `ships.md` |
| Standing tables | `profile.md`, `missions.md` |
| Mission corporation | `profile.md`, `operations.md`, `missions.md` |
| Target pirates | `profile.md`, `operations.md` |

Once ESI sync runs, standings and ships come from ESI. The init copies are scaffolding that persists indefinitely.

**Note:** `profile.md` and `operations.md` are loaded at session start (per CLAUDE.md directives 2-3). The other files are loaded on-demand by skills. The session-start files have the highest context cost.

#### 6. Content that ESI immediately replaces

For authenticated pilots (the common path after OAuth), ESI sync overwrites on first boot:

| Init File | ESI Replacement | Latency |
|-----------|-----------------|---------|
| `ships.md` | Asset-based ship roster | First boot sync |
| `industry/blueprints.md` | Blueprint API data | First boot sync |
| Standing tables in `profile.md` | `/esi-query standings` | On-demand |

The init-generated content in these sections serves as a template for the window between `aria-init` and first ESI sync — typically seconds to minutes.

---

## Proposed Changes

### Phase 1: Fix Active Friction (low risk, high value)

#### 1a. Remove root-level `blueprints.md` from init

**Change:** In `aria-init`, remove the line that creates `$DATA_DIR/blueprints.md`. Only `$INDUSTRY_DIR/blueprints.md` should be generated.

**Files modified:**
- `aria-init`: Remove root blueprints generation (it's already generated via `generate_blueprint_library` which writes to `$INDUSTRY_DIR/blueprints.md`)

**Cleanup:** Delete existing orphaned copies:
```bash
# For each pilot directory
rm -f userdata/pilots/*/blueprints.md
```

**Verification:** `aria-init --test` should not create `blueprints.md` at pilot root.

#### 1b. Inject minimal `persona_context` stub during init

**Change:** After generating `profile.md`, append a minimal `persona_context` section based on the selected faction. This ensures the boot hook always finds what it needs, even without seeding.

Add to `aria-init` after `generate_pilot_profile`:

```bash
inject_persona_context_stub() {
    local faction="$1"
    local profile_path="$2"

    # Map faction to persona branch and name
    local branch="empire"
    local persona=""
    case "$faction" in
        GALLENTE) persona="aria-mk4" ;;
        CALDARI)  persona="aura-c" ;;
        MINMATAR) persona="vind" ;;
        AMARR)    persona="throne" ;;
    esac

    cat >> "$profile_path" << EOF

## Persona Context

<!--
  AUTO-GENERATED by aria-init. Regenerate with: uv run aria-esi persona-context
-->

\`\`\`yaml
persona_context:
  branch: ${branch}
  persona: ${persona}
  fallback: null
  rp_level: "off"
  files: []
  skill_overlay_path: personas/${persona}/skill-overlays
  overlay_fallback_path: null
\`\`\`
EOF
}
```

With `rp_level: "off"` and `files: []`, the boot hook will find a valid (if empty) persona context. Running `aria-esi persona-context` later upgrades it to the full version.

**Boot hook impact:** The artifact verification should treat `files: []` as valid-but-empty, not as missing. Verify this path works.

#### 1c. Remove template prerequisite check

**Change:** Remove the template validation from `check_prerequisites()` (lines 303-327) and delete the `templates/` directory.

**Alternative:** If templates are intended for future use (e.g., user-customizable init output), keep them but remove the prerequisite check and add a `TODO` comment. This proposal recommends deletion since the heredocs are the source of truth and have diverged.

**Files modified:**
- `aria-init`: Remove lines 303-327 from `check_prerequisites()`
- Delete `templates/` directory (or mark as deprecated)

### Phase 2: Reduce Context Waste (low risk, moderate value)

#### 2a. Remove faction damage profiles from `missions.md`

**Change:** Replace the "Mission Notes by Faction" section (~40 lines) with a pointer:

```markdown
## Mission Notes by Faction

See `reference/pve-intel/INDEX.md` for faction damage profiles and EWAR.
Use `/mission-brief` for detailed mission intel.
```

**Rationale:** The authoritative data is already in `reference/pve-intel/INDEX.md`. Skills that need it (`/mission-brief`) already load from there. The per-pilot copy is never updated and costs context tokens.

#### 2b. Deduplicate faction/standing data across files

**Change:** Establish clear ownership for each data category:

| Data | Owner File | Remove From |
|------|-----------|-------------|
| Faction alignment | `profile.md` | `operations.md` (section "Faction Alignment") |
| Ship roster | `operations.md` | `ships.md` (merge into operations or keep ships.md as sole owner) |
| Standing tables | `profile.md` | `missions.md` (section "Standing Progress") |
| Mission corporation | `profile.md` | `operations.md`, `missions.md` (reference profile instead) |

**Approach:** For each removed section, add a one-line pointer: `See profile.md for faction alignment and standings.`

**Session-start files** (`profile.md`, `operations.md`) should contain the canonical version. Demand-loaded files should reference, not duplicate.

#### 2c. Slim down ESI-replaced content in init output

**Change:** For sections that ESI sync will overwrite, generate minimal placeholders instead of elaborate scaffolding:

**`ships.md` before:**
```markdown
### Mining Frigate
- **Hull:** Venture
- **Name:** -
- **Role:** Mining operations
... (30+ lines of fitting details)
```

**`ships.md` after:**
```markdown
## Ship Roster

*Updated automatically by ESI sync. Run `/esi-query` to refresh.*

| Ship | Class | Role | Station |
|------|-------|------|---------|
```

This reduces init output size without losing structure. ESI sync populates the table.

---

## Migration

### For existing installations

Phase 1 changes are backward-compatible:

- **1a:** Delete orphaned `blueprints.md` files. No code reads from pilot root for blueprints.
- **1b:** Run `uv run aria-esi persona-context` to generate full context (existing workflow). The stub is only needed for new installs.
- **1c:** No migration needed. Templates are unused.

Phase 2 changes affect existing pilot files:

- **2a-c:** Existing files are not modified. Changes only affect new `aria-init` runs. Existing users can manually slim their files or re-run init with backup.

### Rollout order

1. **Phase 1a** — Immediate. No risk. Fixes active data confusion.
2. **Phase 1b** — Immediate. Fixes boot failure for `--skip-seed` path.
3. **Phase 1c** — Immediate. Removes dead code.
4. **Phase 2a** — Next session. Low risk, clear win.
5. **Phase 2b-c** — Can be deferred. Requires care to not break skills that parse specific markdown structure.

---

## Out of Scope

- **Refactoring `aria-init` to use templates:** If templates are revived, that's a separate proposal. This proposal addresses the current state where they're dead code.
- **Restructuring the pilot directory layout:** The `{id}_{slug}/` convention works. No change proposed.
- **ESI sync improvements:** How sync populates files is a separate concern.
- **Boot hook architecture:** The `missing` vs `integrity_failed` fix is handled in the current branch, not this proposal.

---

## Success Criteria

1. `aria-init --skip-seed` produces a bootable installation (no startup hook error)
2. No duplicate `blueprints.md` at pilot root after init
3. `aria-init` runs successfully without `templates/` directory
4. Faction damage profiles appear exactly once in the information space (in `reference/`)
5. Standing tables appear exactly once per pilot (in `profile.md`)
