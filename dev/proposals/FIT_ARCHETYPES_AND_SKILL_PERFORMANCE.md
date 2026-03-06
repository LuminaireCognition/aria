# Fit Archetypes & Skill Performance

**Status:** Phase 3 Implemented
**Date:** 2026-03-05
**Scope:** `reference/archetypes/`, `.claude/skills/mission-brief/SKILL.md`, `fitting()` MCP dispatcher
**Evidence:** `dev/reviews/exercise-outputs/20260304-223722/` (MANIFEST.md rows 18-19)

---

## Problem

ARIA has two related gaps:

1. **No fit recommendation from scratch.** When a pilot says "fit me a Vexor for L2 missions under 20M," ARIA cannot query a library of proven fits, adapt one to the pilot's skills and budget, and return it validated. The archetype system exists (`reference/archetypes/`) but covers only 11 hulls. Most queries fall through to ad-hoc generation, which is slow and hallucinates module names.

2. **Mission-brief is 6x slower on uncached missions.** Exercise run `20260304-223722` shows 326s uncached vs 52s cached — 13 inference rounds at ~25s each. The cause is structural: lazy data loading, a serial WebFetch waterfall, and sequential fitting validation. Fast skills (abyssal 21.7s, build-cost 29.5s) share a pattern the mission-brief violates: front-load data, avoid WebFetch chains, parallelize tool calls.

These compound: mission-brief's fit generation path reads the archetype index in round 7, the YAML in round 8, the weapon data in round 9 — three rounds that should be zero because all this data is knowable at skill load time.

**Core thesis:** Expand the archetype library so ARIA has fits to recommend. Restructure skill protocols so consuming those fits is fast.

---

## Design

### Archetypes: Curated Templates, Not Computed Fits

The fitting search space is ~10^30 combinations per hull. Precomputation is infeasible. Instead, maintain a curated library of proven fit archetypes — the way experienced players actually theorycraft: start from a template, adapt to constraints.

The existing schema (`reference/archetypes/`) already has the right structure: hull, skill tier, EFT block, damage tuning with faction overrides, skill requirements, upgrade paths. It needs more entries, not a new schema.

**Scale target:** ~1,500-2,000 archetypes covering common hulls across PvE, PvP, exploration, mining, and hauling. With tier variants (t1/meta/t2_budget/t2_optimal per archetype), this produces ~4,000-6,000 index entries. The INDEX.md stays compact — one line per entry, ~200 lines at full scale.

### Why Not More?

| Hull Category | Hulls | Archetypes/Hull | Subtotal |
|---------------|-------|-----------------|----------|
| Frigates | ~60 | 3-5 | ~240 |
| Destroyers | ~16 | 3-5 | ~64 |
| Cruisers | ~50 | 5-8 | ~325 |
| Battlecruisers | ~24 | 5-8 | ~156 |
| Battleships | ~40 | 5-10 | ~300 |
| Industrials | ~20 | 2-3 | ~50 |
| T2/T3/Faction | ~100 | 3-8 | ~500 |
| **Total** | | | **~1,635** |

Manageable as static YAML checked into the repo. The existing directory structure (`hulls/{class}/{hull}/{activity}/{level}/{tier}.yaml`) scales cleanly.

### Skill Performance: Eliminate Rounds, Not Optimize Within Them

Each inference round costs ~25s regardless of payload. The fastest path to performance is fewer rounds.

Three structural changes to mission-brief cut rounds from 13 to 5-6:

**A. Front-load always-needed data into prerequisite_files (+7 files, -3 rounds)**

Currently, `ships.md`, `cache/INDEX.md`, `archetype/INDEX.md`, and 4 weapon JSONs are declared as `data_sources` and loaded lazily across separate rounds. All are needed for every query. Move them to `prerequisite_files` so they load in the single parallel batch in round 1.

Context cost: ~780 additional lines in round 1 (structured reference data). Time saved: ~75s (3 rounds eliminated).

```yaml
# Before: 4 prerequisite_files, 7 data_sources
# After:  11 prerequisite_files, 1 data_source (specific archetype YAML)
prerequisite_files:
  - reference/mechanics/npc_damage_types.md
  - reference/mechanics/drones.json
  - reference/mechanics/missiles.json
  - reference/mechanics/projectile_turrets.json
  - reference/mechanics/laser_turrets.json
  - reference/mechanics/hybrid_turrets.json
  - reference/pve-intel/cache/INDEX.md
  - reference/archetypes/INDEX.md
  - userdata/pilots/{active_pilot}/profile.md
  - userdata/pilots/{active_pilot}/skills.json
  - userdata/pilots/{active_pilot}/ships.md
data_sources:
  - reference/archetypes/{hull_path}     # loaded once hull is identified
```

**B. Streamline intel retrieval (-2-3 rounds)**

Replace the 94-line serial waterfall (extract keywords → check cache → WebFetch search → filter → WebFetch page → write cache → update index → confirm → read cache → present) with:

1. Check `cache/INDEX.md` (already in context) — if hit, read cache file. If the cache file referenced by INDEX is missing or unreadable, treat as a cache miss and fall through to step 2
2. If miss: WebFetch direct URL `wiki.eveuniversity.org/{Name}_(Level_{N})` — one call
3. Extract intel inline from the response — do not write cache during the query
4. If 404: try `Special:Search` as fallback (one additional round)
5. If WebFetch fails with a non-404 error (timeout, 5xx, malformed response): abort intel retrieval for this mission. Present whatever intel is available from the cache or prerequisite data (NPC damage types from `npc_damage_types.md`), flag the missing intel to the user with the failure reason, and continue to the fitting phase. Do not retry within the same query — retries waste a full round (~25s) for transient failures that are unlikely to resolve immediately.

Cache population is removed from the query path entirely. A separate `/cache-populate` command (or batch pass via the exercise runner) handles cache-writing as an explicit, deliberate action — not inline tax on every first lookup. The cache-write-during-query pattern optimizes future queries at the expense of the current one (~25s), and fails entirely in the exercise runner where Write is not in ALLOWED_TOOLS. **Note:** The `/cache-populate` command is out of scope for this proposal — it is referenced here to explain the design rationale for removing cache-writes from the query path, not as a deliverable. A separate proposal will spec the cache population mechanism if needed.

**C. Parallelize fitting validation (-1-2 rounds)**

`fitting(action="calculate_stats")` and `fitting(action="check_requirements")` have no data dependency — both need only the EFT string and pilot skills. Call them as parallel tool calls in a single round.

**Re-validation loop removal is conditional on fit source:**
- **Archetype-sourced fits:** Remove the re-validation loop. Archetype fits are pre-validated; the fitting engine's `calculate_stats` + `check_requirements` still catches issues, which surface as warnings rather than triggering iteration.
- **Ad-hoc fits (no archetype match):** Keep the re-validation loop. Until the archetype library covers a hull, ad-hoc generation is prone to module name hallucination and slot errors that require correction. The re-validation loop is the safety net for these fits.

**Protocol condition:** The re-validation step is skipped if and only if an archetype YAML was successfully read and used as input to the fitting phase. Concretely: the SKILL.md protocol tracks whether round 3 loaded an archetype YAML file. If yes → present fitting results directly after the parallel validation calls (no re-validation loop). If no (INDEX had no match, or INDEX matched but YAML read failed) → treat the fit as ad-hoc and retain the re-validation loop. The condition is on archetype YAML load success, not on INDEX match alone and not on fitting validation outcome.

This distinction matters for Phase 1, where most hulls have no archetype. The round savings from removing re-validation apply only to archetype-sourced fits; ad-hoc fits retain the current 1-2 extra rounds for correctness. As Phase 2 expands archetype coverage, an increasing share of queries benefits from the shorter path. User-provided fits validated via `/fit-check` are a separate skill with its own validation contract.

### Execution Trace: Before and After

*All traces below show success paths. Error/fallback branches (cache-file-miss, WebFetch failure, unparseable response) add 1-2 rounds and are specified in the protocol text (§B), not repeated in the traces.*

**Current uncached mission with fit (13 rounds, ~326s):**

| Round | Action |
|-------|--------|
| 1 | Load SKILL.md + 4 prerequisites |
| 2 | Read `cache/INDEX.md` → miss |
| 3 | WebFetch direct wiki URL |
| 4 | WebFetch search fallback (if 404) |
| 5 | WebFetch actual mission page |
| 6 | Write cache file (blocked in exercise runner) |
| 7 | Read `ships.md` + `archetype/INDEX.md` |
| 8 | Read archetype YAML |
| 9 | Read weapon JSON |
| 10 | Build EFT → `fitting(calculate_stats)` |
| 11 | Review → `fitting(check_requirements)` |
| 12 | Re-validate |
| 13 | Present |

**Proposed uncached mission with archetype fit (5 rounds, ~125s):**

| Round | Action |
|-------|--------|
| 1 | Load SKILL.md + 11 prerequisites (parallel reads) |
| 2 | Cache miss → WebFetch direct wiki URL |
| 3 | Read archetype YAML (path known from INDEX in context) |
| 4 | Build EFT → `calculate_stats` + `check_requirements` in parallel |
| 5 | Present |

**Proposed uncached mission with ad-hoc fit (6-7 rounds, ~150-175s):**

Same as above through round 2, but round 3 builds an ad-hoc fit (no archetype). Rounds 4-5 validate + re-validate (re-validation loop retained for ad-hoc). Still faster than current 13 rounds due to front-loaded prerequisites and streamlined intel retrieval.

**Proposed cached mission with fit (3 rounds, ~75s):**

| Round | Action |
|-------|--------|
| 1 | Load SKILL.md + 11 prerequisites |
| 2 | Read cache file + archetype YAML (parallel) (if cache file read fails → treat as miss, fall through to WebFetch; adds 1-2 rounds) |
| 3 | Build EFT → both fitting calls in parallel → present |

### Archetype Recommendation Flow

For skills that recommend fits (mission-brief, fitting, ship-next, fit-budget):

```
Pilot query (hull, activity, constraints)
        │
        ▼
INDEX.md (in context) ──── filter by hull + activity + level
        │
        ▼
Read archetype YAML ────── get EFT, damage_tuning, skill_requirements
        │
        ▼
Adapt to pilot ─────────── faction hardener swap, drone swap, ammo swap
        │                   skill tier downgrade via reference/archetypes/_shared/module_tiers.yaml
        │                   (upgrade_paths + tier_variant_preference)
        │                   budget filtering via market price
        ▼
Validate ───────────────── calculate_stats + check_requirements (parallel)
        │
        ▼
Present ────────────────── EFT block + fitting engine stats + missing skills
```

The archetype YAML carries everything needed for adaptation: the base EFT, faction-specific overrides (`damage_tuning.overrides`), and the upgrade path for suggesting next steps. No ad-hoc module reasoning required.

---

## Integration Points

| Skill | Current | With This Change |
|-------|---------|-----------------|
| `/mission-brief` | Reads archetype in round 7-8; 13 rounds total | INDEX in context from round 1; 5 rounds (archetype) / 6-7 rounds (ad-hoc) |
| `/fitting` | Analyzes provided fits only | Can recommend fits via archetype query |
| `/fit-check` | Validates one fit | Can suggest archetype alternatives when check fails |
| `/fit-budget` | Downgrades one fit | Selects best-tier archetype directly |
| `/ship-next` | Recommends hull only | Recommends hull + fit together |

New skill (`/fit-recommend`) deferred to Phase 3 — the archetype query logic lives in the fitting engine, and existing skills surface it.

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Stale archetypes after EVE patches | Automated re-validation via fitting engine on SDE updates; `stats.validated_date` flags staleness |
| 11 prerequisite files bloats round-1 context (~1,220 lines) | All structured reference data; well within context budget; 3 fewer rounds (75s) is an unambiguous trade |
| Removing cache-write-during-query leaves uncached missions uncached | Acceptable — cache population is a separate concern, not inline tax on every first lookup |
| Removing re-validation loop passes through a bad fit | Re-validation removed only for archetype-sourced fits (pre-validated); ad-hoc fits retain re-validation loop until archetype coverage displaces them |
| Archetype quality varies | `source` field + validation pipeline gates entry; poor fits get flagged, not recommended. Phase 2 permitted values: `eveuni` (EVE University wiki), `human` (player-submitted EFT), `verified` (validated by experienced theorycrafter). The implementing agent uses `eveuni` for wiki-sourced fits and `human` for player-submitted fits; `verified` is reserved for human review. These are documentation-only in Phase 2 — no test enforcement. Formal `source` validation (enumeration, test enforcement in `test_archetype_integrity.py`) is deferred to Phase 4 when the community submission pipeline requires it |
| INDEX.md grows large at full scale | ~200 lines at 2,000 entries; one-line-per-row table; well within prerequisite budget |
| Archetype selection adds a round when hull is ambiguous | Cross-hull queries (no hull specified) use INDEX in-context reasoning; single-hull queries resolve in zero rounds |

---

## Implementation

### Phase 1: Mission-Brief Round Reduction

Immediate, standalone value. No new data required.

1. Move 7 `data_sources` to `prerequisite_files` in SKILL.md frontmatter
2. Replace 94-line Intel Retrieval Protocol with streamlined version (deferred caching): check cache → direct wiki URL → inline extract → `Special:Search` fallback if 404
3. Rewrite Validation Gate to specify parallel fitting calls; make re-validation conditional on fit source (remove for archetype-sourced, retain for ad-hoc — see §C Protocol condition). The SKILL.md protocol must track whether an archetype YAML was successfully loaded; this boolean governs the re-validation branch
4. **Validate:** Re-run exercise with same queries. Target: uncached < 150s, cached < 80s. Additionally, test the 404 fallback path: include at least one query for a mission name that does not have a direct wiki URL, verifying that the `Special:Search` fallback produces usable intel within +1 round. Spot-check one uncached mission to verify that inline-extracted intel (no cache write) matches the quality of previously cached intel (enemy composition, damage types, recommended tank). Include at least one query for a hull with no archetype to verify ad-hoc generation still works with re-validation loop intact (target: 6-7 rounds). Include at least one query for a hull with an archetype to verify the fit completes in 5 rounds without triggering a re-validation loop (validates the conditional logic, not just the ad-hoc path). **Negative test: cache-write regression guard** — verify that no `Write` tool calls targeting `reference/pve-intel/cache/` occur during any mission-brief query (uncached or cached). Verification mechanism: the exercise runner passes `--allowedTools` to `claude -p`, which prevents disallowed tool calls from executing. Since `Write` is not in `ALLOWED_TOOLS`, any attempt to write cache files will fail visibly in the transcript output. Additionally, review the exercise runner's captured stdout for each query — any `Write` attempt (even a failed one) indicates a protocol regression. In interactive contexts, inspect the conversation transcript directly for `Write` calls targeting cache paths. **WebFetch failure resilience (manual verification)** — this case cannot be reliably triggered in the exercise runner because it requires a server-side failure. Verify manually outside the exercise runner: use a mission-brief query while the wiki is unreachable (e.g., disconnected network, or point at a non-routable host). Verify the skill degrades gracefully (presents available intel from prerequisite data, flags the failure to the user, does not retry, continues to fitting phase). **Unparseable response resilience** — include at least one query where the wiki URL returns HTTP 200 but the page contains no parseable mission intel. Concrete trigger: use mission name `"Enemies Abound"` which maps to a multi-part disambiguation page on the EVE University wiki (`Enemies_Abound_(Level_3)` redirects to a series index, not a single mission briefing). Alternatively, use any mission name that produces a wiki stub or redirect. Verify the same degradation behavior: present available intel from prerequisite data (NPC damage types from `npc_damage_types.md`), flag the missing intel to the user, and continue to the fitting phase

### Phase 2: Archetype Library Expansion (PvE Core)

Build on the existing schema. The base structure (archetype, eft, stats, skill_requirements, damage_tuning) is unchanged; a new optional `roles` field is added. The integrity test suite (`tests/test_archetype_integrity.py`) must be updated to validate `roles` values against the canonical taxonomy.

1. Curate 200-500 archetypes for the most-flown PvE hulls (missions L1-L4, exploration, mining), prioritizing the seed hull list below. **"Curate" means format and validate, not generate.**

   **Seed hull priority list (cover these first, in roughly this order):**

   | Class | Hull | Primary Role |
   |-------|------|-------------|
   | Frigate | Heron | exploration-data, exploration-relic |
   | Frigate | Kestrel | missions-l1 |
   | Frigate | Tristan | missions-l1 |
   | Frigate | Punisher | missions-l1 |
   | Frigate | Venture | mining-ore, mining-gas |
   | Destroyer | Cormorant | missions-l1 |
   | Destroyer | Algos | missions-l1 |
   | Cruiser | Caracal | missions-l2 |
   | Cruiser | Vexor | missions-l2, ratting-anomaly |
   | Cruiser | Gnosis | missions-l2 |
   | Cruiser | Stratios | exploration-combat |
   | Battlecruiser | Drake | missions-l3 |
   | Battlecruiser | Myrmidon | missions-l3 |
   | Battlecruiser | Harbinger | missions-l3 |
   | Battleship | Raven | missions-l4 |
   | Battleship | Dominix | missions-l4, ratting-anomaly |
   | Battleship | Rattlesnake | missions-l4 |
   | Battleship | Praxis | missions-l4 |
   | Industrial | Epithal | hauling-hisec |
   | Industrial | Miasmos | hauling-hisec |
   | Barge | Procurer | mining-ore |
   | Barge | Retriever | mining-ore |

   These 22 hulls cover the most common new-player-to-intermediate PvE progression. The implementing agent must produce at least one archetype per seed hull (at any tier) before expanding to non-seed hulls. This ensures early library queries have a high hit rate on the most-asked-about ships. EFT blocks must be sourced from authoritative references: community-proven fits (EVE University wiki, verified zkillboard patterns, Pyfa community exports), existing game documentation, or human-provided fits from experienced players. The implementing agent's role is to transform sourced EFTs into the archetype YAML schema and validate them through the fitting engine — not to synthesize novel fits from training data. This prevents the module name hallucination problem that motivates the archetype system.

   **Sourcing mechanism:** The implementing agent WebFetches EVE University wiki ship pages (e.g., `wiki.eveuniversity.org/Vexor`) to extract published EFT blocks, then transforms them into archetype YAML. This is the primary source. Human-provided EFT blocks (via issues, PRs, or direct submission) are a secondary source processed identically. The implementation sequence within Phase 2 is: (a) build tooling — schema validation, test updates, INDEX format changes; then (b) populate archetypes using the tooling. Step (a) is a prerequisite for (b) but both are Phase 2 deliverables.

   **EFT extraction rules:** Wiki ship pages often contain multiple fits (e.g., "Basic", "Advanced", "PvP"). The extraction protocol is:
   - **Extract all named EFT blocks** from the page. An EFT block starts with `[Hull Name, Fit Name]` and ends at the next blank line or heading. Each becomes a separate archetype candidate.
   - **Map to tiers:** Use the fit's module meta levels to assign a tier (`t1`, `meta`, `t2_budget`, `t2_optimal`). If two extracted fits map to the same hull/activity/tier, prefer the one with more complete slots (fewer empty).
   - **Skip non-EFT content:** Descriptive text, comparison tables, and partial module lists are not EFT blocks. Only extract content that parses as valid EFT format (fitting engine validation is the gate).
   - **On extraction failure** (page exists but contains no parseable EFT block): log the hull as "no source available" to stdout (a single line: `SKIP {hull}: no parseable EFT block on {url}`) and skip it. Do not generate a fit to fill the gap — the archetype must be sourced, not synthesized.
2. Each archetype: parse through fitting engine, reject validation errors, tag metadata. **Metadata tagging** means adding these top-level fields to each archetype YAML:
   - `source`: One of `eveuni`, `human`, `verified` (see Risks table). Existing 11 archetypes without `source` are exempt (warning, not failure). New archetypes MUST have `source`. Example placement in YAML:
     ```yaml
     archetype:
       hull: Vexor
       skill_tier: meta
       omega_required: false
     source: eveuni
     ```
   - `stats.validated_date`: Already present in existing archetypes; must be set to the date the fitting engine validated the EFT. Format: `YYYY-MM-DD` (ISO 8601 date string, e.g., `"2026-03-05"`), consistent with existing archetypes
3. Expand INDEX.md with new entries
4. Add `roles` field to archetype YAML schema **and** to INDEX.md as a 6th column. In YAML, `roles` is a list of strings (following the existing YAML list convention used by `skill_requirements.required`, `overrides`, etc.). In INDEX.md, roles are comma-separated (no spaces) in a single column. The archetype YAML schema is defined by convention and validated by `tests/test_archetype_integrity.py` — there is no pydantic model or separate schema file. INDEX.md is loaded as a prerequisite file and must support in-context role filtering without loading individual YAMLs. Updated INDEX format:

   ```
   | Hull | Activity | Level | Tier | Roles | Path |
   |------|----------|-------|------|-------|------|
   | Vexor | missions | L2 | meta | missions-l2 | `hulls/cruiser/vexor/pve/missions/l2/meta.yaml` |
   | Drake | missions | L3 | t1 | missions-l3,ratting-anomaly | `hulls/battlecruiser/drake/pve/missions/l3/t1.yaml` |
   ```

   Multiple roles are comma-separated (no spaces) in the Roles column. Entries whose archetype YAML has not been backfilled with `roles` use an empty Roles cell: `| Hull | Activity | Level | Tier | | Path |`. The 6-column regex must accept an empty Roles cell as valid (the consistency test exempts entries with no YAML `roles`, and the INDEX parser treats an empty Roles cell as "no roles assigned"). The `index_entries` fixture regex in `tests/test_archetype_integrity.py` (line 44) must be updated to parse 6 columns, and a new consistency test must verify that YAML `roles` values match the INDEX Roles column.

   Canonical role taxonomy for cross-hull queries:

   | Role | Semantics |
   |------|-----------|
   | `missions-l1` | Level 1 security missions |
   | `missions-l2` | Level 2 security missions |
   | `missions-l3` | Level 3 security missions |
   | `missions-l4` | Level 4 security missions |
   | `exploration-data` | Data site scanning and hacking |
   | `exploration-relic` | Relic site scanning and hacking |
   | `exploration-combat` | Combat exploration (DED, unrated) |
   | `mining-ore` | Ore mining (belts, anomalies) |
   | `mining-gas` | Gas cloud harvesting |
   | `mining-ice` | Ice harvesting |
   | `hauling-hisec` | High-sec cargo transport |
   | `hauling-lowsec` | Low-sec blockade running |
   | `pvp-solo` | Solo PvP engagements |
   | `pvp-fleet-dps` | Fleet PvP damage dealer |
   | `pvp-fleet-logi` | Fleet PvP logistics |
   | `pvp-fleet-tackle` | Fleet PvP tackle/interdictor |
   | `abyssal` | Abyssal Deadspace sites |
   | `ratting-anomaly` | Combat anomaly ratting |
   | `salvaging` | Wreck salvaging |

   Archetypes carry 1-3 roles from this list. Cross-hull queries filter INDEX by role match.

   **Canonical source in code:** Define `VALID_ROLES: set[str]` as a constant in `tests/test_archetype_integrity.py` (alongside the existing `VALID_SKILL_TIERS`). The fitting dispatcher **duplicates** this set as `VALID_ROLES: set[str]` at module level in `fitting.py` (following the `VALID_SKILL_TIERS` pattern) for `role` parameter validation. `src/` does not import from `tests/`. Future taxonomy additions require updating both locations; this is acceptable given the low change frequency of the role taxonomy. Both sites must include a sync comment: `# NOTE: keep in sync with VALID_ROLES in tests/test_archetype_integrity.py` (in fitting.py) and `# NOTE: keep in sync with VALID_ROLES in src/aria_esi/mcp/dispatchers/fitting.py` (in the test file). The proposal text above is the design-time reference; the test constant is the runtime authority
5. Update `tests/test_archetype_integrity.py` to validate the `roles` field:
   - Add `VALID_ROLES: set[str]` constant with the 19 canonical role values (authoritative source for runtime validation)
   - Update `index_entries` fixture regex (line 44) to parse 6 columns: Hull, Activity, Level, Tier, Roles, Path
   - Add consistency test: YAML `roles` values must match the comma-separated Roles column in INDEX.md for each entry
   - New archetypes (added after Phase 2) MUST have `roles` (1-3 values from the canonical taxonomy above)
   - Pre-existing archetypes without `roles` emit a warning, not a failure. **Backfill scope:** The 11 existing archetypes SHOULD be backfilled with `roles` during Phase 2 as part of content work (step 1), since the implementing agent is already touching archetype YAMLs and the role assignment is trivial for known hulls. This is best-effort, not blocking — if an existing archetype's role mapping is ambiguous, skip it and let a human assign later. **Atomicity requirement:** When backfilling `roles` on an existing archetype, the YAML `roles` field and the INDEX.md Roles column must be updated together. The consistency test (YAML roles match INDEX Roles column) applies to all archetypes that have a `roles` field in their YAML — including backfilled ones. An archetype with no `roles` in YAML is exempt from the consistency test (warning path). An archetype with `roles` in YAML but a missing or mismatched Roles column in INDEX fails the consistency test
   - Invalid role values (not in the taxonomy) fail the test with: `"Invalid role '{value}' in {path}, must be one of: {taxonomy}"`
   - `roles` with 0 or >3 entries fail with: `"roles must contain 1-3 values, got {n} in {path}"`
6. Batch validation: each new archetype is validated by the implementing agent invoking `fitting(action="calculate_stats")` with its EFT block inline during creation, reviewing the output for errors before committing the YAML. The agent validates each archetype as it is created — not as a separate post-hoc step. This is not automated CI; automation is deferred to Phase 4. **Acceptance threshold: zero validation failures gate merge.** Every archetype that fails fitting engine validation is either fixed or excluded — no partial-pass batches
7. **Validate:**
   - **Content floor gate:** Phase 2 merge requires at least one archetype per seed hull (22 minimum archetypes across the 22 seed hulls listed above). The 200-500 target is aspirational; 22 is the hard floor. The validate step checks: `grep -c '^|' reference/archetypes/INDEX.md` minus header rows ≥ 33 (11 existing + 22 seed). If a seed hull's EVE University wiki page has no parseable EFT, the hull is exempt from the floor (logged as "no source available" per EFT extraction rules) — count only hulls with committed archetypes
   - Spot-check mission-brief with hulls now covered by archetypes; verify round count stays at 5
   - **INDEX migration test:** Run `uv run pytest tests/test_archetype_integrity.py -n auto` after converting INDEX.md from 5 to 6 columns. All 11 existing archetype entries must pass the updated 6-column regex. This gates the Phase 2 merge — no content work (step b) proceeds until the migrated INDEX and updated test suite pass together
   - **EFT extraction failure negative test:** Attempt ingestion of at least one hull whose EVE University wiki page exists but contains no parseable EFT block. Verify the hull is logged as "no source available" and no archetype YAML is committed for it. This confirms the "skip, don't synthesize" contract from the EFT extraction rules
   - **Roles consistency violation test:** Introduce a deliberate YAML/INDEX roles mismatch on one archetype (e.g., YAML `roles: [missions-l2]` but INDEX Roles column `missions-l3`); verify the consistency test fails with the expected message. Revert the deliberate mismatch before merge

### Phase 3: Cross-Hull Recommendation

Depends on Phase 2 library size. **Hard dependency:** Phase 3's `fitting(action="recommend")` handler parses INDEX.md in 6-column format (with Roles column). This requires the Phase 2 INDEX migration (step 4) and updated test suite (step 5) to be complete. Do not begin Phase 3 implementation until the Phase 2 INDEX migration test passes.

1. Add `fitting(action="recommend")` to the MCP fitting dispatcher (`src/aria_esi/mcp/dispatchers/fitting.py`) following the existing action pattern (`calculate_stats`, `check_requirements`). Add `"recommend"` to `VALID_ACTIONS` and `FittingAction`, then implement the handler function. **`MarketDatabase` access:** The `recommend` handler obtains a `MarketDatabase` instance via `from aria_esi.store.market.database import get_market_database; db = get_market_database()` — the same lazy-import singleton pattern already used in `_resolve_skill_name()` (fitting.py:526). No constructor injection or new initialization pattern is needed. The contract:

   | Parameter | Type | Required | Semantics |
   |-----------|------|----------|-----------|
   | `role` | string | yes | One of the canonical role taxonomy values (e.g., `missions-l2`, `exploration-data`) |
   | `hull` | string | no | Filter to specific hull; omit for cross-hull query |
   | `budget_isk` | integer | no | Maximum total fit cost in ISK; omit for no budget constraint. `budget_isk=0` or negative raises `InvalidParameterError` (`aria_esi.mcp.errors.InvalidParameterError`, already used throughout all MCP dispatchers) (no fit costs 0 ISK) |
   | `skill_tier` | string | no | One of `t1`, `meta`, `t2_budget`, `t2_optimal`; omit to return all tiers |
   | `limit` | integer | no | Max results to return (default: 5, minimum: 1). `limit=0` or negative raises `InvalidParameterError` |

   **Return format:** Object envelope `{"results": [...], "message": null | string}`. The `results` array contains `{hull, path, tier, roles, estimated_cost}` objects sorted by tier (highest first), capped at `limit`. The `roles` field contains the archetype's **full roles list** (e.g., `["missions-l2", "ratting-anomaly"]`), not just the matched role — the caller already knows the queried role and benefits from seeing all activities the fit supports. **Source:** `roles` is parsed from the INDEX.md Roles column (comma-split), not from per-YAML reads — the consistency test guarantees INDEX mirrors YAML, and the handler avoids N YAML reads per recommend call. Each entry has enough metadata for the caller to select and load the full archetype YAML. The envelope is consistent for both success and no-match cases — callers always access `.results` (which may be empty) and optionally check `.message`.

   **Tier sort order:** `t2_optimal > t2_budget > meta > t1`. This ordering is explicit — `VALID_SKILL_TIERS` in tests is a set with no inherent order. The fitting dispatcher defines `TIER_ORDER: list[str] = ["t1", "meta", "t2_budget", "t2_optimal"]` as the canonical ascending sequence; sort descending for results.

   **Cost estimation:** `estimated_cost` is computed in two steps:
   1. **Name → type ID resolution:** Parse the archetype's EFT block via `parse_eft(eft_string)` (`src/aria_esi/fitting/eft_parser.py:439`, returns `ParsedFit` from `src/aria_esi/models/fitting.py:323`) which internally uses `get_market_database()` for type name resolution, returning a `ParsedFit` with `type_id` already resolved on every `ParsedModule` and `ParsedDrone`. Collect all type IDs from `ParsedFit.ship_type_id`, `ParsedFit.modules[*].type_id`, and `ParsedFit.drones[*].type_id`.
   2. **Type ID → price resolution:** Call `MarketDatabase.get_aggregates_batch(type_ids, region_id=10000002)` (`src/aria_esi/store/market/database.py:1110`) to retrieve `CachedAggregate` objects for The Forge (Jita). Sum `CachedAggregate.sell_min` across all items. **Note:** `TypeInfo` does not contain price data — it holds only SDE metadata (`type_id`, `type_name`, `group_id`, `category_id`, `market_group_id`, `volume`). Prices live in `CachedAggregate`. No MCP-within-MCP call is needed; the handler accesses `MarketDatabase` directly via `get_market_database()` — the same lazy-import singleton pattern already used in the fitting dispatcher's `_resolve_skill_name()` (`src/aria_esi/mcp/dispatchers/fitting.py:526`).

   **`parse_eft()` failure:** If `parse_eft(eft_string)` raises an exception for a given archetype (malformed EFT in a committed YAML), set `estimated_cost` to `null` and include the entry in results normally. A single corrupted archetype should degrade cost display for that entry, not fail the entire recommend call. This is consistent with the market-data-unavailable path. The data integrity issue surfaces via the `null` cost (and the fitting engine's own validation will catch it if the caller loads the YAML for presentation).

   When market data is unavailable for any item (no `CachedAggregate` returned or `sell_min` is `None`), `estimated_cost` is `null` (not a partial sum — either all items are priced or the estimate is null). When `budget_isk` is specified, null-cost entries are **omitted** from results (cannot verify they meet the budget). When `budget_isk` is omitted, null-cost entries are included normally. Cost is computed at query time, not stored in the archetype YAML — prices change; fits don't.

   **Role matching:** The `role` parameter is singular. Matching is "archetype's `roles` list contains this value" (containment check, not equality). An archetype with `roles: [missions-l2, ratting-anomaly]` matches a query for `role="missions-l2"`.

   **Invalid role handling:** If `role` is not in the canonical taxonomy, raise `InvalidParameterError` with: `"Invalid role '{value}', must be one of: {taxonomy}"`. Invalid roles return an error, not an empty array — this distinguishes "no archetypes exist for this valid role" from "the role name is wrong."

   **INDEX.md parsing:** The handler reads `reference/archetypes/INDEX.md` from disk on each call and parses it with a regex matching the pipe-delimited table format — the same pattern used in `tests/test_archetype_integrity.py` `index_entries` fixture (line 43). No caching: INDEX.md is ~200 lines at full scale, and disk reads are sub-millisecond. The parsed rows are filtered in-memory by `role` (containment check against comma-split Roles column), `hull` (exact match), and `skill_tier` (exact match).

   **Path resolution:** The handler resolves `reference/archetypes/INDEX.md` (and archetype YAML paths from INDEX entries) relative to the project root. Use the `_get_project_root()` pattern already established in `src/aria_esi/mcp/dispatchers/sde/tools_easy80.py:168` and `tools_activities.py:78`: walk up from `Path(__file__).resolve()` searching for the `pyproject.toml` marker file, with `Path.cwd()` as fallback. Define this as a private function in the fitting dispatcher (or import from a shared location if one is extracted). Do not use bare relative paths — they break when the MCP server is launched from a non-root working directory.

   **INDEX.md read failure:** If `INDEX.md` is missing or unreadable (file not found, permission error), raise `InvalidParameterError("action", "recommend", "Archetype INDEX.md not found at reference/archetypes/INDEX.md")`. If INDEX.md exists but contains no parseable table rows (empty or malformed), return `{"results": [], "message": "Archetype index is empty or malformed."}`. The distinction: missing file is a deployment/data integrity error (raises exception); empty/malformed content is a degraded-but-functional state (returns empty results).

   **No-match behavior:** Return `{"results": [], "message": "No archetypes match the given constraints."}` when no INDEX entries match the role/hull/tier filters. When entries match the filters but all are excluded because `budget_isk` is specified and every matching archetype has `null` estimated_cost (market data unavailable), return `{"results": [], "message": "Archetypes exist for this role but market data is unavailable to verify budget. Try without a budget constraint."}`. This distinguishes "no fits exist" from "fits exist but costs unknown." The calling skill decides whether to relax constraints or inform the user — no fallback to ad-hoc generation.

2. Build `/fit-recommend` skill with SKILL.md (prerequisite_files: archetypes INDEX + pilot profile/skills; protocol: parse query → call `fitting(action="recommend")` → load top archetype YAML → present EFT + stats). Register the skill in `.claude/skills/_index.json` following the existing entry schema (name, description, model, category, triggers, path, prerequisite_files, required_tools). Example: `fit-recommend vexor --role missions-l2 --budget 15m`

   **No-match output:** When `fitting(action="recommend")` returns empty results, `/fit-recommend` presents the `message` field to the user and suggests broadening constraints (e.g., "Try removing the budget filter" or "Try a different role"). No fallback to ad-hoc fit generation — the skill's purpose is archetype recommendation, not fit synthesis.

   **YAML load failure:** When a calling skill loads an archetype YAML from a `path` returned by `fitting(action="recommend")` and the file is missing or malformed (deleted after indexing, corrupt YAML), the calling skill treats this as a no-match: present a message indicating the archetype could not be loaded, suggest the user try a different tier or role, and do not fall back to ad-hoc generation. This is a data integrity issue (stale INDEX), not a query error — the skill should not mask it by generating an ad-hoc fit.
3. Integrate with `/ship-next` for hull + fit combined recommendations. **Integration contract:** ship-next currently recommends hulls based on pilot skills and activity preference. With archetypes available, after selecting the recommended hull, ship-next resolves the activity to a canonical role and calls `fitting(action="recommend", role=<resolved_role>, hull=<recommended_hull>, limit=1)` to attach a starter fit. The output appends an "Example Fit" section with the archetype's EFT block and estimated cost. This augments the existing hull recommendation — if no archetype exists for the hull, ship-next presents the hull recommendation alone (current behavior). No parameter changes to the `/ship-next` skill itself; the archetype lookup is internal to the skill protocol.

   **Activity → role mapping:** ship-next currently accepts three activity labels: `missions`, `exploration`, and `mining` (confirmed from `ship-next/SKILL.md` command syntax, lines 31-33). The mapping table below covers these three plus four forward-looking labels (`hauling`, `pvp`, `abyssal`, `ratting`) that ship-next does not yet support. The implementing agent maps only the labels that exist in ship-next at implementation time; unrecognized activity labels fall through to current behavior (hull recommendation without fit). The mapping rule is: **select the highest-tier archetype role for the recommended hull from INDEX.md**. Concretely:

   | ship-next activity | Resolution rule |
   |--------------------|-----------------|
   | `missions` | Filter INDEX by hull; select the highest mission level present (e.g., if Drake has `missions-l3` and `missions-l4`, use `missions-l4`) |
   | `exploration` | Use `exploration-data` (safest default); if hull has only `exploration-combat`, use that |
   | `mining` | Use `mining-ore` (most common); if hull has only `mining-gas` or `mining-ice`, use that |
   | `hauling` | Use `hauling-hisec`; if hull has only `hauling-lowsec`, use that |
   | `pvp` | Use `pvp-solo` for solo-oriented hulls; `pvp-fleet-dps` for fleet hulls. Determined by hull's available roles in INDEX |
   | `abyssal` | Direct mapping: `abyssal` |
   | `ratting` | Direct mapping: `ratting-anomaly` |

   The rule is: prefer the most capable variant the hull supports. When multiple roles match, INDEX filtering returns all — ship-next picks the first result (highest tier). If the activity shorthand has no INDEX matches for the hull, skip the fit recommendation (current behavior)
4. **Validate:**
   - Query `fitting(action="recommend")` with a role that has ≥3 archetypes; verify correct filtering and sort order
   - Query with an impossible budget constraint; verify empty result with message
   - Query with `hull` + `role` combined filter; verify intersection filtering works
   - Query with an invalid `role` value (not in taxonomy); verify `InvalidParameterError`, not empty array
   - Query with `limit=2` when ≥3 results exist; verify truncation. Query with `limit=10` when only 2 exist; verify all returned without error
   - Verify `estimated_cost` is `null` (not absent) when market data is unavailable for any module in the fit
   - Query with `budget_isk=0`; verify `InvalidParameterError` (consistent with `limit=0` treatment). Query with `budget_isk=-1`; verify same `InvalidParameterError`
   - Query with `limit=0`; verify `InvalidParameterError`. Query with `limit=-1`; verify same `InvalidParameterError`
   - Query with `budget_isk` specified when some archetypes have null `estimated_cost`; verify null-cost entries are omitted from results
   - Simulate an archetype YAML load failure (recommend returns a valid path, but the YAML is missing/malformed); verify the calling skill presents a data integrity message and does not fall back to ad-hoc generation
   - Simulate a `parse_eft()` failure for one archetype (malformed EFT block in committed YAML) while other archetypes are valid; verify the malformed entry has `estimated_cost = null` and other entries have valid costs; verify the recommend call succeeds (does not raise an exception)
   - Query with `budget_isk` specified when ALL matching archetypes have `null` estimated_cost (market data entirely unavailable); verify the distinct message "Archetypes exist for this role but market data is unavailable to verify budget." is returned, not the generic "No archetypes match" message
5. **Deferred:** Activity-based scoring functions (maximize DPS for missions, align time for exploration, etc.) — requires a scoring model spec; will be addressed in a follow-on proposal once library size validates the approach

### Phase 4: PvP & Community Pipeline *(follow-on proposal)*

Out of scope for this proposal. Listed here as directional intent — a separate proposal with concrete specs (CI platform, submission schema, rejection criteria, SDE update triggers) will be written once Phase 2-3 validate the approach.

Goals for the follow-on:
1. Expand archetypes to PvP solo, PvP fleet, and niche roles
2. Fit submission format with automated validation CI
3. Automated patch re-validation as CI job on SDE updates
4. `last_validated` staleness warnings in recommendations

---

## Decision Record

**Rejected:** Brute-force fit precomputation. ~10^30 combinations per hull; infeasible at any scale.

**Rejected:** Cache-write-during-query in mission-brief. Optimizes future at the expense of current; fails in exercise runner; adds 1-2 rounds.

**Chosen:** Curated archetypes + front-loaded prerequisite consumption. Mirrors how experienced players theorycraft. Produces ~5,000 index entries (vs 10^32). Existing schema works; needs entries, not redesign. Round reduction is independently valuable and compounds with library growth.

**Deferred:** AI-driven fit generation. Novel fit synthesis adds complexity without clear benefit over curated archetypes. Revisit if the library proves insufficient.

**Deferred:** Combined `calculate_stats + check_requirements` MCP action. Would save one round but requires fitting tool changes. Parallel calls achieve the same result at the skill protocol level.
