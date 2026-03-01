# Mission-Brief Skill Review

**Date:** 2026-02-26
**Reviewer:** ARIA development (Claude Code)
**Scope:** End-to-end review of `/mission-brief` skill — SKILL.md, supporting code, data pipeline, context management

---

## Executive Summary

The mission-brief skill is one of the most thoroughly documented skills in the ARIA system, with strong architectural decisions around cache-first data retrieval and explicit validation checklists for drones, ammo, and gear tiers. However, it has a critical structural gap: the weapon/drone reference files that the SKILL.md repeatedly marks as **"CRITICAL: MUST read"** are listed only in `data_sources` (contextual, advisory) rather than `prerequisite_files` (mandatory gate). This means the skill loading system does not enforce pre-reading them before output generation, creating a path where Claude can skip the reference lookups and fall back to training data for damage types, drone names, and ammo recommendations — exactly the failure mode the checklists were designed to prevent.

---

## Grounding Discipline Scorecard

### 1. MCP-First Enforcement — 🟡 Yellow

**What works:**
- The skill correctly identifies that mission intel does **not** come from MCP tools — it uses a local cache + EVE University Wiki pipeline, which is appropriate since mission wave/spawn data is static content not exposed by ESI or SDE.
- The cache-first pattern (SKILL.md:340-404) is structurally sound: cache → wiki fetch → write cache → read from cache → present. The "never present raw WebFetch data" rule (line 341-343, 396) prevents a common failure mode.
- Drone/ammo validation protocols (lines 627-741) correctly point to local JSON reference files as ground truth and include explicit checklists.

**What's weak:**
- **No MCP validation of fitting recommendations.** The skill generates EFT fits (lines 81-115) but never calls `fitting(action="calculate_stats")` to validate them. The `fitting` skill's `_index.json` entry has `requires_eos_validation: true`, but mission-brief doesn't inherit or reference this requirement. A mission fit could have CPU/PG overflows, invalid module names, or slot conflicts that go undetected.
- **No SDE verification of module names.** The fit adaptation rules (lines 97-103) say to swap hardeners and drones, but there's no instruction to verify module names via `sde(action="item_info")` before presenting. The DATA_VERIFICATION.md doc (lines 62-83) explicitly requires this for all fitting recommendations.
- The faction damage data is duplicated between `npc_damage_types.md` and the inline tables in SKILL.md (lines 634-641, 673-679, 689-694). If the reference file is updated, the SKILL.md inline tables could drift and become a competing source of truth.

### 2. Prompt Hygiene — 🟡 Yellow

**What works:**
- The disambiguation protocol (lines 180-292) is excellent — it explicitly says "never assume" faction or level, and provides a structured AskUserQuestion flow with damage profiles to help identification.
- The zero-results clarification protocol (lines 484-526) has a strong "NEVER guess" directive with clear fallback behavior.
- WebFetch prompts (lines 450-471) are specific extraction prompts, not open-ended, reducing the risk of the LLM inventing data from the wiki response.
- The keyword extraction rules (lines 316-334) prevent search-breaking additions like "mission" or "Level X".

**What's weak:**
- **Lines 98-103 ("Fit Adaptation Rules") give Claude significant creative latitude.** "Swap hardeners to match enemy damage profile" and "Swap drones to match enemy weakness" are correct instructions, but they assume Claude will consult the reference files first. There's no inline gate like "STOP — have you read drones.json? If not, read it now." The validation checklists exist later (lines 643-653, 723-735) but are 500+ lines away from the fit adaptation instructions, creating a structural gap where Claude may reach the adaptation rules, generate a fit, and never scroll down to the checklists.
- **The cache file template (lines 530-580) includes HTML comments as instructions** (e.g., `<!-- REQUIRED: Look up reference/mechanics/drones.json -->`). These comments are guidance for the agent when reading cached data, but they're easy to skip since they look like metadata rather than blocking instructions.
- **Experience-level adaptation (lines 157-167, 760-774) is entirely inference-based.** There's no reference data for what constitutes "new" vs "veteran" responses — Claude must decide how to abbreviate spawns or omit EWAR warnings based on judgment. This is acceptable for presentation style but creates edge cases where important tactical warnings (e.g., warp disruptors) could be omitted for "veteran" pilots.

### 3. Failure Handling — 🟢 Green

**What works:**
- The error handling table (lines 473-482) covers all major failure modes: 0 variants, wiki unavailable, multiple variants, cache miss, cache write failure, and nonexistent level/faction combos.
- The "Cache write fails → Report error, do NOT present raw WebFetch data" rule (line 481) is critical and correctly implemented.
- The zero-results protocol (lines 484-526) is particularly strong — it refuses to guess, asks for clarification with region-appropriate faction options, and clearly labels generic faction guidance as such.
- The wiki-unavailable fallback (line 478) correctly degrades to faction quick reference rather than inventing data.

**What's weak:**
- **No staleness detection for cached data.** Cache files have no TTL, version marker, or game-patch indicator. A cache entry written before a game balance patch could contain outdated wave compositions or EWAR changes. The README.md says `rm -rf cache/` is safe, but there's no mechanism to flag when cached data might be stale.
- **WebFetch failure modes beyond "wiki unavailable" aren't covered.** What if WebFetch returns a disambiguation page instead of a mission page? What if the wiki page exists but has no wave data (stub article)? The skill doesn't distinguish between "no data found" and "partial/unreliable data found."

### 4. Context Window Efficiency — 🟢 Green

**What works:**
- The `data_sources` list (9 files) is well-curated — only files directly needed for mission briefing are listed.
- The "What NOT to Include" table (lines 146-156) actively constrains output size, preventing bloat.
- The brevity target (line 743: "20-30 lines total") is specific and enforced through the response format structure.
- The persona overlay (118 lines) is compact and additive, not redundant with the base skill.
- Cache files use a compact template (lines 530-580) that stores only actionable intel, not raw wiki prose.

**What's weak:**
- **The SKILL.md itself is 799 lines.** While comprehensive, this is a significant context load. The validation checklists for drones (lines 627-654), missiles (lines 660-680), projectiles (lines 682-694), lasers (lines 696-708), and hybrids (lines 709-735) contain substantial inline tables that duplicate data already in the JSON reference files. These inline tables serve as "quick reference during generation" but cost ~150 lines of context that could be saved if the skill simply said "consult the JSON file."
- **The inline drone damage table (lines 634-641) duplicates `drones.json` → `enemy_recommendations`** almost verbatim. If the JSON is the authoritative source, the inline table is redundant context. Same for missile damage types (lines 673-679) duplicating `missiles.json`.

---

## Specific Findings

### F1: `prerequisite_files` is empty — Critical grounding gap

**File:** `.claude/skills/_index.json:793`
**Severity:** High

```json
"prerequisite_files": [],
```

The SKILL.md contains six "CRITICAL: MUST read" directives for reference files:
- `reference/mechanics/drones.json` (line 629)
- `reference/mechanics/missiles.json` (line 669)
- `reference/mechanics/projectile_turrets.json` (line 685)
- `reference/mechanics/laser_turrets.json` (line 697)
- `reference/mechanics/hybrid_turrets.json` (line 710)
- `reference/mechanics/npc_damage_types.md` (line 170)

But none are in `prerequisite_files`. Per CLAUDE.md's skill loading protocol, `prerequisite_files` is a **"MANDATORY GATE"** — the agent must read all listed files before producing any output. The `data_sources` list where these files currently live is described as **"Contextual files to read when relevant"** — a weaker, advisory directive.

Compare with the `fitting` skill which correctly lists `drones.json` in `prerequisite_files` (line 418). The `mission-brief` skill generates fittings too, but lacks this enforcement.

**Recommendation:** Move at minimum `drones.json`, `npc_damage_types.md`, and the pilot's weapon-appropriate JSON file into `prerequisite_files`. This converts the "CRITICAL: MUST read" prose directives into structurally enforced gates.

**Counterargument:** Loading all 5 weapon JSONs as prerequisites would add ~700 lines of context even when the pilot only uses one weapon type. A compromise: add `npc_damage_types.md` and `drones.json` as prerequisites (needed for every brief), and keep weapon JSONs in `data_sources` with a stronger directive to read the relevant one based on the pilot's weapon system.

### F2: No EOS fitting validation

**File:** `.claude/skills/mission-brief/SKILL.md:81-115`
**Severity:** Medium

The skill generates EFT fits for every mission brief but never validates them through `fitting(action="calculate_stats")`. The DATA_VERIFICATION.md protocol (lines 201-207) requires all fitting recommendations to pass EOS validation. The `fitting` skill has `requires_eos_validation: true` in its index entry; mission-brief does not.

This means a mission-adapted fit could:
- Use an invalid module name (e.g., "Armor Thermal Hardener I" instead of the correct "Thermal Armor Hardener I")
- Exceed CPU/powergrid
- Place modules in wrong slots
- Include modules that don't exist

**Recommendation:** Add a step between fit adaptation and presentation: "Validate the adapted fit via `fitting(action="calculate_stats")`. If validation fails, fix the fit and re-validate. Never present an unvalidated fit."

### F3: Inline duplicate data tables waste context

**File:** `.claude/skills/mission-brief/SKILL.md:634-641, 673-679, 689-694`
**Severity:** Low

The drone damage table (lines 634-641) is a subset of `drones.json → enemy_recommendations`. The missile damage table (lines 673-679) is a subset of `missiles.json → enemy_recommendations`. The projectile table (lines 689-694) duplicates `projectile_turrets.json`.

These inline tables exist as "guardrails in case Claude doesn't read the JSON," but they also:
1. Consume ~80 lines of context window
2. Can drift from the JSON source of truth
3. Create ambiguity about which is authoritative

**Recommendation:** Replace inline tables with a single directive: "The JSON file is the authoritative source. Do not use these inline tables as a substitute for reading the file." Or remove the inline tables entirely and rely on the prerequisite gate (see F1).

### F4: Cache has no staleness mechanism

**File:** `reference/pve-intel/cache/*.md`
**Severity:** Low

Cache files include a `Source:` URL but no timestamp, game version, or TTL. After a game patch that changes mission spawns or EWAR, cached data silently becomes incorrect. The README.md (line 17) acknowledges `rm -rf cache/` is safe, but there's no proactive staleness detection.

**Recommendation:** Add a `Cached:` timestamp line to the cache template. Optionally, add a check in the cache-read step: "If cached data is older than 90 days, re-fetch from wiki." This is low priority since mission data rarely changes, but it prevents long-term drift.

### F5: No SDE module name verification for fit adaptation

**File:** `.claude/skills/mission-brief/SKILL.md:97-103`
**Severity:** Medium

The fit adaptation rules say "Swap hardeners to match enemy damage profile" but don't require verifying the replacement module name via `sde(action="item_info")`. EVE module naming is notoriously inconsistent (e.g., "Armor EM Hardener I" vs "EM Armor Hardener I" — the latter is the correct SDE name). Without SDE verification, Claude will generate module names from training data, which may use outdated or incorrect naming conventions.

**Recommendation:** Add to fit adaptation rules: "Before including any module in the EFT output, verify its exact name via `sde(action='item_info')` or cross-reference with `reference/fittings/MODULE_NAMES.md`."

### F6: Validation checklists are far from the instructions they gate

**File:** `.claude/skills/mission-brief/SKILL.md:97-103 vs 627-735`
**Severity:** Low

The fit adaptation rules appear at lines 97-103. The drone validation checklist appears at lines 627-654. That's a 530-line gap. In practice, Claude processes the SKILL.md sequentially and may generate the fit at line ~100 without reaching the validation checklists at line ~650, especially if the skill context is compressed.

**Recommendation:** Move a compact summary of the validation requirement immediately after the fit adaptation rules (line 103):

```markdown
**VALIDATION GATE:** Before presenting any fit, complete the Drone Validation (§Drone Recommendation Validation) and Ammo Validation (§Weapon Ammo Recommendation Validation) checklists below. Do not present a fit without completing both checklists.
```

### F7: PARIA overlay response format diverges from base format

**File:** `personas/paria/skill-overlays/mission-brief.md:20-38`
**Severity:** Low (design choice)

The PARIA overlay defines a completely different response format (ASCII box art with `═══` borders) that doesn't match the base skill's structured format (Quick Reference table → EFT → Blitz → Spawns → Tactical). The PARIA format omits the EFT fit section, the blitz steps, and the spawn details — replacing them with a looser "ENGAGEMENT NOTES" section.

This may be intentional (pirate persona is more casual), but it means PARIA briefings lose the structured data that makes empire briefings actionable.

**Recommendation:** Consider whether PARIA should maintain the same information hierarchy (just with different framing) or intentionally provide less structured data. Document the intent explicitly.

### F8: Test infrastructure is placeholder-only

**File:** `tests/skills/test_semantic.py:351-372`
**Severity:** Medium

The two primary test methods (`test_mission_brief_factual_accuracy` and `test_mission_brief_completeness`) both `pytest.skip()` with "Pending skill invocation framework integration." Only the infrastructure tests (config loading, weight validation) actually execute. The sample response test (`test_mission_brief_with_sample_response`) requires `deepeval` + API key, making it effectively skip in CI.

This means there is **no automated verification** that the mission-brief skill produces grounded output. The G-Eval framework and ground truth data exist but are unused.

**Recommendation:** At minimum, create a deterministic test that validates the cache-first pipeline works (cache miss → fetch → cache write → cache read) without requiring LLM evaluation. The semantic tests can remain gated behind `deepeval`.

### F9: WebFetch disambiguation page handling is implicit

**File:** `.claude/skills/mission-brief/SKILL.md:440-448`
**Severity:** Low

The direct URL shortcut (line 441-448) says "If the page returns 404 or a disambiguation page, fall back to Special:Search." But it doesn't explain how to detect a disambiguation page. MediaWiki disambiguation pages have specific markers (`class="disambig"`, category links), but the skill relies on Claude recognizing them from the WebFetch markdown response.

**Recommendation:** Add a WebFetch prompt specifically for the direct URL path: "If this page is a disambiguation page (contains a list of similarly-named articles), return 'DISAMBIGUATION' and the list of linked pages. Otherwise, extract mission intel."

---

## Prioritized Recommendations

| Priority | Finding | Action | Effort |
|----------|---------|--------|--------|
| **P0** | F1: Empty `prerequisite_files` | Add `npc_damage_types.md` and `drones.json` to prerequisite_files | 5 min |
| **P1** | F2: No EOS fitting validation | Add `fitting(action="calculate_stats")` step after fit generation | 15 min |
| **P1** | F5: No SDE module name verification | Add module name verification directive to fit adaptation rules | 10 min |
| **P1** | F6: Validation checklists far from fit rules | Add forward-reference gate after line 103 | 5 min |
| **P2** | F8: Placeholder tests | Create deterministic cache pipeline test | 1-2 hrs |
| **P2** | F3: Inline duplicate tables | Remove inline tables, rely on prerequisite gate | 15 min |
| **P3** | F4: No cache staleness | Add `Cached:` timestamp to template | 10 min |
| **P3** | F7: PARIA format divergence | Document intent, optionally align | 30 min |
| **P3** | F9: Disambiguation detection | Add specific WebFetch prompt for direct URL path | 10 min |

---

## Architecture Notes

**What's well-designed:**
- The cache-first pattern is the right architectural choice for mission data. It creates a local source of truth, prevents repeated wiki fetches, and ensures data is reviewed before presentation.
- The wiki-only external source restriction is a strong security boundary — it limits prompt injection surface to a single, trusted source.
- The disambiguation protocol with damage profiles is excellent UX — it helps pilots identify the correct mission variant without requiring exact faction names.
- The experience-level adaptation table is a clean way to vary verbosity without changing structure.
- The `data_sources` enumeration in `_index.json` makes the skill's data dependencies explicit and auditable.

**Structural concern:**
The skill is trying to do two complex things: (1) retrieve and cache mission intel, and (2) generate adapted ship fittings. The fitting generation is essentially a subset of the `/fitting` skill but without the same validation infrastructure. Consider whether mission-brief should delegate fitting generation to the fitting skill (or at least share its validation requirements) rather than implementing its own fit adaptation logic.
