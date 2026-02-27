# Data Trust & Authority

> **Audience:** ARIA runtime policy defining how data is sourced, validated, cached, and presented.

## Core Principles

1. **Never present EVE game mechanics as fact without verification** from a trusted source. Training data is not a trusted source.
2. **All data persisted to local cache must be sourced from or validated against authoritative sources.**

## Trust Hierarchy

| Priority | Source | Authority | Use For |
|----------|--------|-----------|---------|
| 1 | **ESI** | Authoritative | Alliance IDs, sovereignty, market, pilot data, live game state |
| 2 | **SDE** | Authoritative | Item stats, skill effects, blueprint data, faction IDs, NPC corps |
| 3 | **Pyfa/EOS** | Authoritative | Fitting calculations, DPS, EHP, capacitor |
| 4 | **DOTLAN** | Semi-authoritative | Supplemental reference, alliance lookup |
| 5 | **EVE University Wiki** | Community reference | Mechanics explanations, PvE intel |
| 6 | **Training data** | **NOT AUTHORITATIVE** | Never trust alone; only as hypothesis to verify |

**Authoritative** sources (ESI, SDE, EOS) can be cached directly. **Semi-authoritative** sources (DOTLAN) must be cross-referenced with ESI/SDE before caching. **Training data** must never be cached directly.

## Data Type Authority

| Data Type | Authoritative Source | Validation |
|-----------|---------------------|------------|
| Alliance IDs/names | ESI `/alliances/{id}/` | `sov-validate` |
| Faction IDs | SDE `corporation_info` | `sov-validate` |
| Sovereignty map | ESI `/sovereignty/map/` | `sov-update` |
| Coalition membership | Community (DOTLAN) | Manual verification |
| Item stats | SDE `item_info` | N/A (SDE is authoritative) |
| Market prices | ESI `/markets/` | N/A (live query) |
| Pilot data | ESI (authenticated) | N/A (live query) |
| FW contested status | ESI `/fw/systems/` | 30-min cache |

## Data Source Characteristics

### ESI Activity Endpoints

**Endpoints:** `/universe/system_kills/`, `/universe/system_jumps/`

| Property | Value |
|----------|-------|
| Completeness | **100%** — every kill and jump counted |
| Data window | Rolling 1-hour aggregate, ~1h refresh |
| Max staleness | ~1h 10m from in-game event |

**Strengths:** Complete census. If ESI says 0 kills, there were 0 kills.

**Limitations:** Hourly granularity cannot detect transient threats. A gatecamp that killed 5 ships 45 minutes ago and disbanded looks identical to one still active.

### zKillboard / RedisQ (Real-Time Intel)

| Property | Value |
|----------|-------|
| Completeness | **Variable** — depends on participant uploaders |
| Timeliness | Seconds to minutes from kill |
| Coverage bias | High in active regions; sparse in quiet space |

**Strengths:** Near-real-time kill clustering detects active gatecamps and fleet fights. What appears is **confirmed real** (high precision).

**Limitations:** Uncertain recall. Missing kills are silent — "no kills reported" is not the same as "no kills occurred." Coverage correlates with population density.

### Precision vs Recall

| Source | Precision | Recall | "0 kills" means |
|--------|-----------|--------|-----------------|
| ESI hourly | Perfect | Perfect | No kills occurred (within the hour) |
| RedisQ real-time | Perfect | Uncertain | No kills **reported** |

**Rule:** When real-time data shows zero activity, phrase as "no recent kills reported" not "system is clear." ESI hourly zeros can be stated as fact within the staleness window.

### Combined Use

| Question | Best source | Why |
|----------|------------|-----|
| "Is this region generally active?" | ESI hourly | Complete picture |
| "Is there a gatecamp right now?" | RedisQ real-time | Minute-level granularity |
| "Is it safe to jump this gate?" | Both | ESI baseline + RedisQ immediate threats |

## Verification Rules

**Always verify when claiming:** specific numbers, skill effects per level, module/ship bonuses, blueprint materials, T2 requirements, any "X gives Y" statement.

**May skip verification for:** general strategic advice, directional guidance, non-mechanic questions.

**When tools lack data:** Acknowledge the gap explicitly. Do not fill with training knowledge. Suggest in-game verification or EVE University Wiki lookup. An honest "I don't know" is better than a confident hallucination.

## Case Studies

### Case Study 1: Drones Skill Error

User asked for Vexor skill recommendations. ARIA claimed "Drones IV gives +1 drone (5 total)" without verification. This was wrong — Drones gives 1 drone *per level*, so IV = 4 drones. The SDE description clearly states "Can operate 1 drone per skill level."

**Root cause:** Hallucinated skill effect from training data. **Fix:** Call `sde(action="item_info", item="Drones")` before making claims about skill effects.

**Lesson:** The SDE had the correct answer. The failure was not checking it.

### Case Study 2: Invention Requirements Error

User asked what skills are needed to invent DDA II. ARIA called `sde(action="blueprint_info")` which returned manufacturing data but not invention requirements. ARIA filled the gap with training knowledge, listing "Gallentean Starship Engineering" as a required skill. The user challenged this: "Gallentean Starship Engineering" (type_id 20410) is a **datacore**, not a skill. The actual skill is "Gallente Starship Engineering" (type_id 11450) — the "-ean" suffix distinguishes datacores from skills.

**Root cause:** When tools returned incomplete data, ARIA filled gaps with unverified training knowledge. **Fix:** State "The SDE tools don't expose invention requirements. You can check in-game via Industry -> Invention on a DDA I BPC."

**Lesson:** Incomplete tool data is not permission to fill gaps with training knowledge.

### Case Study 3: Build Cost Component Error

User asked for Dominix build cost. ARIA called `sde(action="blueprint_info")` which returned 10 materials (7 minerals + 3 components). ARIA only priced the 7 minerals using a hardcoded mineral list, silently omitting 3 component materials (Auto-Integrity Preservation Seal, Life Support Backup Unit, Core Temperature Regulator). This understated cost by ~19.6M ISK, reporting 7.8% profit when the actual result was a loss.

**Root cause:** Hardcoded material list pattern from simple examples (Hammerhead I) didn't generalize to complex items (ships with components). **Fix:** Always extract ALL material names dynamically from the SDE response. Verify price count matches material count. Never silently omit materials.

**Lesson:** Silent omission of data is forbidden. Missing data must be flagged prominently.

## Cache Authority Rules

### Caching Requirements

- **Authoritative sources** (ESI, SDE): Cache directly after retrieval
- **Semi-authoritative sources** (DOTLAN): Cross-reference with ESI/SDE, annotate source
- **Community data** (coalitions): Validate via `sov-validate` before caching; fail-fast if validation fails
- **Training data**: Never cache directly under any circumstances

### Cache Freshness

| Data Type | Validation Frequency | Trigger |
|-----------|---------------------|---------|
| Alliance IDs | On edit | `sov-validate` before commit |
| Sovereignty map | On demand | `sov-update` |
| Coalition membership | Monthly | Community updates |
| Reference files | On contribution | PR review |

### ESI Unavailable During Validation

1. Fail the operation — do not proceed with unvalidated data
2. Report clearly: "ESI unavailable — cannot validate"
3. Suggest retry when ESI is available
4. Escape hatch: `--skip-validation` flag (not recommended)

## File-Specific Requirements

### `coalitions.yaml`

Community-maintained coalition definitions. Alliance IDs must be valid ESI alliance IDs. Run `uv run aria-esi sov-validate --fix` before committing changes.

### `reference/` files

Static game data from SDE, EVE University Wiki, or documented community sources. Non-SDE data requires source annotation with verification date.

### Mission Data

Mission intel uses local cache + EVE University Wiki only — never general web search. See `reference/pve-intel/INDEX.md` for cached intel. See `dev/docs/DATA_SOURCES.md` for blessed external sources.
