# Unified Fit Sources: Eve Workbench Integration Proposal

**Status:** ⛔ **BLOCKED — EFFORT STOPPED**  
**Date:** 2026-02-05  
**Blocked Date:** 2026-02-06  
**Focus:** Architecture validation and capability assessment  
**Last Review:** 2026-02-06 (Phase 0 validation failed — Eve Workbench v2.0 auth requirements)

---

## Document History

| Date | Event |
|------|-------|
| 2026-02-05 | Proposal created, architecture decisions locked |
| 2026-02-06 | **Phase 0 executed** — discovered Eve Workbench v2.0 requires developer authentication |
| 2026-02-06 | **Effort stopped** — Phase B/C cancelled, proposal updated with blocker documentation |

---

## ⚠️ CRITICAL BLOCKER: Phase 0 Failure

**Eve Workbench integration is NOT VIABLE** due to authentication requirements discovered during Phase 0 API validation.

### What Changed

Eve Workbench launched **version 2.0 in April 2025** with a completely rebuilt API architecture:
- New Angular frontend with separate WebAPI backend
- **Authentication now REQUIRED** — no anonymous access
- Developer must register to obtain Client ID and API Key

### Root Cause

Per current Eve Workbench API documentation (https://devblog.eveworkbench.com/docs/api/):

> "To get access you will have to request developer access which allows you to create an application to retrieve the Client ID and API Key."

This contradicts the proposal's core assumption (G0-1) that anonymous access would work.

### Why This Kills the Integration

| Requirement | Reality | Impact |
|-------------|---------|--------|
| Each ARIA user queries Workbench | Each user needs developer registration | Unacceptable friction |
| Single proxy service | Centralized auth creates operational/legal risk | Not viable |
| ESI-style OAuth | Manual developer approval process | Not scalable |

**Conclusion:** Asking every ARIA user to go through Eve Workbench's developer approval process (likely via Discord interview) is unacceptable. Unlike ESI OAuth (standard for EVE tools), this creates a massive barrier to entry.

### Evidence

See `dev/evidence/phase0_workbench_validation.md` for:
- API endpoint test results (404 / HTML responses)
- Documentation references
- Eve Workbench 2.0 changelog analysis

### Recommendation

**CANCEL Eve Workbench integration.** Proceed with:
1. **Phase A:** FitSource protocol + Archetype/ESI adapters only
2. **Future consideration:** User-pasted EFT imports from Workbench (no API)
3. **Alternative:** Partner with sources offering OAuth or public APIs

---

## Original Proposal (Retained for Reference)

*The following sections document the architecture as designed, but should be considered obsolete for the Eve Workbench component.*

---

## Executive Summary

**⛔ UPDATE 2026-02-06: This proposal is BLOCKED. The Eve Workbench component is not viable due to v2.0 authentication requirements. See "CRITICAL BLOCKER" section above.**

This proposal originally intended to integrate Eve Workbench as a third fit source alongside existing ESI personal fittings and local archetypes. The goal was to reduce the burden of manually curating archetype fits by leveraging Eve Workbench's community-scored fits, while preserving the structured archetype system for core use cases.

**Original core question:** Can we match pilots with "the best fit they can fly" by combining:
1. **Local Archetypes** - Curated, tier-specific, faction-tunable reference fits
2. **ESI Personal Fittings** - Player's own saved fits from the EVE client
3. ~~**Eve Workbench** - Community-uploaded fits with scoring/ratings~~ ⛔ **REMOVED — auth barrier unacceptable**

**Revised scope:** FitSource protocol supporting Archetype + ESI Personal only

### v1 Scope Decisions

The following scope decisions were made during the 2026-02-05 review to reduce complexity and preserve extensibility. Each decision resolves a specific architecture review finding.

| Decision | Rationale | Resolved Finding |
|----------|-----------|------------------|
| **Grouped-by-source output** (no blended ranking) | Cross-source scores are incomparable; no empirical data to calibrate | RF-3 |
| **No cross-source deduplication** | Requires parse-first normalization pipeline; grouped display handles naturally | RF-5 |
| **No on-demand EFT expansion** | Only score EFT-cached items; fixed top-N per source is sufficient | Review item 3 |
| **omega_required=True for all non-archetype fits** | Alpha cap data not in SDE; no reliable source without maintenance burden | RF-4 |
| **FitSource protocol** (not monolithic UnifiedFit) | Sources have fundamentally different capabilities; protocol keeps engine source-agnostic | RF-2 |
| **Archetype source wraps existing select_fits()** | Preserves tank selection, faction tuning, tier ranking as a black box | RF-6 |
| **Defer cost estimation** | Compute only for user-selected fit, or skip entirely until market data is available | Review item 6 |
| **Defer MCP integration** | CLI first until data model stabilizes | Review item 7 |
| **Hull-only search for Workbench** | Activity tag mapping is optional when user explicitly provides tags; no mandatory mapping maintenance | Review item 5 |

---

## Problem Statement

### Current State

The archetype system is sophisticated but requires significant manual curation:

| Hull | Activity | Tiers | Tank Variants | Total Files |
|------|----------|-------|---------------|-------------|
| Vexor | L2 missions | 3 | 1 | 3 |
| Vexor | L3 missions | 3 | 2 | 6 |
| Myrmidon | L3 missions | 2 | 2 | 4 |
| ... | ... | ... | ... | ... |

Each file requires:
- Manual EFT creation and validation
- Skill requirement extraction
- Stats caching via EOS
- Faction tuning overrides
- Ongoing maintenance as game balance changes

**Scale problem:** EVE has ~300+ combat-viable hulls across 6+ ship classes. Full coverage with 4 tiers x 2 tank variants x 3 activity types = thousands of files.

### Eve Workbench Opportunity

Eve Workbench hosts community-uploaded fits with:
- User ratings/scores (popularity, votes)
- Hull filtering (`typeId` parameter)
- Tag-based search
- EFT export endpoint

**Key insight:** Instead of curating every fit ourselves, we could query Eve Workbench for highly-rated fits matching the pilot's hull, then filter by pilot skills.

---

## Proposed Architecture

### FitSource Protocol

Each fit source is a plugin that implements a minimal protocol. The selection engine is source-agnostic — it queries registered sources and presents grouped results.

```python
from typing import Protocol
from dataclasses import dataclass, field

class FitSource(Protocol):
    """Each source handles its own loading, caching, and scoring."""
    name: str  # "archetype", "esi_personal", "eve_workbench"

    def query(self, hull: str, activity: str | None) -> list["FitCandidate"]:
        """Return candidates for this hull/activity, pre-scored by this source's logic."""
        ...

    def is_available(self) -> bool:
        """Whether this source can be queried (credentials, connectivity, etc.)."""
        ...

@dataclass
class FitCandidate:
    """Minimal common representation. Sources own their internal complexity."""
    source: str
    source_id: str
    hull_name: str
    fit_name: str
    eft: str  # EFT format string (must be populated; metadata-only entries are not candidates)
    quality_score: float  # 0.0-1.0, normalized within source
    tags: list[str] = field(default_factory=list)

    # Populated by selection engine (not by source):
    can_fly: bool = False
    missing_skills: list[str] = field(default_factory=list)
    omega_required: bool = True  # Conservative default for non-archetype sources
```

### Source Registry

Sources are registered via config, enabling incremental rollout:

```json
// userdata/config.json
{
  "fit_sources": {
    "enabled_sources": ["archetype", "esi_personal"],
    "eve_workbench": {
      "enabled": false,
      "min_votes": 3,
      "max_candidates_per_hull": 50,
      "top_n_eft_fetch": 15
    }
  }
}
```

Adding Workbench later requires only `"enabled_sources": ["archetype", "esi_personal", "eve_workbench"]` — no conditional logic in the selector.

**Display ordering:** Sources are presented in the order they appear in `enabled_sources`. No separate priority field — list order is the single source of truth.

### Source Capabilities

Each source has different capabilities. The protocol keeps these internal:

| Capability | Archetype | ESI Personal | Eve Workbench |
|------------|-----------|-------------|---------------|
| Quality scoring | Tier mapping (internal) | Fixed 0.6 (no signal) | Bayesian-adjusted votes |
| Activity filtering | Directory structure | None | Tags (optional) |
| Faction tuning | Yes (internal) | No | No |
| Upgrade paths | Yes (internal) | No | No |
| Tank selection | Yes (internal) | No | No |
| Omega derivation | Explicit in YAML | Default True (v1) | Default True (v1) |
| Cost estimation | Deferred | Deferred | Deferred |

**Key design choice:** The archetype `FitSource` wraps the existing `select_fits()` as a black box. All archetype-specific logic (tank variant discovery, meta.yaml parsing, tier priority, damage matching, faction tuning) runs inside the adapter. The selection engine never touches archetype internals.

### Grouped Output Model

Results are presented **grouped by source**, sorted within each group by quality score. No cross-source ranking in v1.

```python
@dataclass
class SourceGroup:
    """Results from a single source, split by flyability."""
    flyable: list[FitCandidate]   # Sorted by quality_score descending
    trainable: list[FitCandidate] # Sorted by quality_score descending

@dataclass
class FitSearchResult:
    """Container for grouped fit search results."""
    groups: list[tuple[str, SourceGroup]]  # (source_name, group) ordered by config list position
    query_hull: str
    query_activity: str | None
    sources_queried: list[str]
    sources_unavailable: list[str]  # Sources that failed or were disabled
```

**Why grouped instead of blended?** The scoring systems across sources are fundamentally incomparable:
- **Archetype:** Hardcoded tier mapping (t1=0.5, t2=0.85) — an ordinal scale set by the developer
- **ESI Personal:** Fixed 0.6 — no signal at all
- **Workbench:** Bayesian-adjusted community votes — a noisy popularity signal

Blended ranking implies fine-grained quality distinctions that don't exist. Grouped output is more honest with the user and avoids the maintenance burden of tuning magic numbers.

**Future:** Blended ranking can be added behind a `--blended` flag once real usage data provides calibration input. The `FitSource` protocol supports this — a cross-source comparator would consume `quality_score` from each `FitCandidate`.

---

## Eve Workbench API Analysis

### Available Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/latest/fits` | GET | List fits with filters |
| `/latest/fits/:fitid` | GET | Get fit details |
| `/latest/fits/:fitid/eft` | GET | Export fit as EFT |

### Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `typeId` | int | Filter by ship type ID (from SDE) |
| `tags` | string | Comma/semicolon separated tags |

### Hull Name Resolution

User-supplied hull names must be resolved to EVE type IDs before querying Workbench (`typeId` parameter).

| Step | Method | Example |
|------|--------|---------|
| 1. Primary | SDE `item_info` with fuzzy matching (exact → prefix → contains → Levenshtein ≤3) | `"vexor"` → `Vexor` (type_id 626) |
| 2. Fallback | ESI `/universe/ids/` endpoint | Handles cases SDE fuzzy match misses |
| 3. On failure | Error with suggestions from `find_type_suggestions()` | `"vaxor"` → "Did you mean: Vexor, Vagabond?" |

**Scope:** This resolution applies to Workbench `typeId` queries and ESI lookups. The archetype source uses its own `HULL_CLASS_MAP` with string names and does not require type ID resolution.

### Unknown (Requires Investigation)

> **BLOCKING:** Every item below is a direct dependency for Phase B/C design. Each must be resolved during Phase 0 with documented evidence (observed response JSON, header captures, or ToS excerpts). If observed behavior differs from the assumptions in this proposal, the "Affected Sections" must be revised before implementation begins.

| Item | Impact | Investigation Method | Affected Sections |
|------|--------|---------------------|-------------------|
| Authentication | Can we query anonymously? | Test API without auth | §Authentication Architecture, §Go/No-Go G0-1 |
| Rate limits | How many queries/minute? | Check response headers | §EFT Fetch Strategy (N+1 call budget), §Circuit Breaker, §Go/No-Go G0-3 |
| Score/rating fields | What scoring data is returned? | Inspect response JSON | §Quality Score Derivation (assumes 1–5 star scale), §Within-Source Ordering |
| Tag taxonomy | What tags exist? | Query with common tags | §Activity Matching, §Tag Matching Rules |
| Response pagination | How are large results handled? | Query popular hull type | §EFT Fetch Strategy (top-N selection), §Result Set Limits, §Cache Lifecycle |
| **Content-Type headers** | **Response format for JSON vs EFT endpoints** | **Capture headers from both endpoints** | **§EFT Fetch Strategy (parsing logic)** |
| **Tag format** | **Comma-separated? Multiple params? Case sensitivity?** | **Test various tag query formats** | **§Tag Matching Rules** |
| **Rating scale bounds** | **Is it 1-5? 0-5? 0-100?** | **Inspect min/max values across many fits** | **§Quality Score Derivation** |
| **GUID stability** | **Do fit GUIDs change on updates?** | **Query same fit daily for 1 week** | **§Cache Lifecycle** |
| **Deleted fit behavior** | **404? Empty body? Different error code?** | **Test with known-deleted fit GUID** | **§Error Handling** |

### Proof of Concept Required

Before committing to integration, validate:

```bash
# Test 1: Anonymous access
curl "https://api.eveworkbench.com/latest/fits?typeId=626"  # Vexor

# Test 2: Response structure (what fields exist?)
curl "https://api.eveworkbench.com/latest/fits/SOME_GUID"

# Test 3: EFT export format
curl "https://api.eveworkbench.com/latest/fits/SOME_GUID/eft"

# Test 4: Tag filtering
curl "https://api.eveworkbench.com/latest/fits?typeId=626&tags=pve,missions"
```

**Exit criteria:** Document response schemas, rate limits, and authentication requirements before proceeding. Additionally:
- Confirm whether `/latest/fits` returns rating, votes, and tags inline or requires per-fit detail calls (OQ-1)
- Test pagination behavior on popular hulls — document mechanism and page sizes (OQ-3)
- Verify EFT export format is parseable by existing `extract_skill_requirements` pipeline

---

## Quality Score Derivation

Scores are normalized **within each source** and used for ordering within that source's group. They are never compared across sources.

| Source | Score Derivation | Range | Purpose |
|--------|-----------------|-------|---------|
| Archetype | Tier mapping (t1=0.5, meta=0.7, t2=0.85, t2_optimal=1.0) | 0.5-1.0 | Orders tiers within archetype group |
| ESI Personal | Fixed 0.6 (no quality signal available) | 0.6 | All personal fits rank equally |
| Eve Workbench | Bayesian-adjusted rating from community votes | 0.0-1.0 | Surfaces well-rated community fits |

**Workbench score normalization:**

> **ASSUMPTION (Phase 0 dependent):** This normalization assumes the API returns a numeric rating on a 1–5 scale and an integer vote count per fit. If Phase 0 reveals different scoring fields (e.g., upvote/downvote counts, weighted score, or no rating at all), this normalization and the Bayesian adjustment must be reworked before Phase B. See "Unknown (Requires Investigation)" → Score/rating fields.

```python
# If Workbench returns a 1-5 star rating (ASSUMED — validate in Phase 0)
normalized_score = (workbench_rating - 1) / 4  # Maps 1-5 -> 0.0-1.0

# Bayesian adjustment for low-vote fits (prevents 5-star/1-vote outliers)
PRIOR_VOTES = 5
PRIOR_MEAN = 0.5
adjusted_score = (votes * normalized_score + PRIOR_VOTES * PRIOR_MEAN) / (votes + PRIOR_VOTES)
```

### Within-Source Ordering

Each source sorts its own candidates by `quality_score` descending, with `source_id` as a stable tie-breaker for deterministic output:

```python
candidates.sort(key=lambda f: (-f.quality_score, f.source_id))
```

- **Archetype group:** T2 optimal > T2 > Meta > T1 (tier ordering preserved from existing `select_fits()`). Ties broken by source_id (file path).
- **Personal group:** All at 0.6 — ordered by `source_id` (ESI fitting_id, which is numeric and stable). Recency can replace this as a tie-breaker later if ESI provides timestamps.
- **Workbench group:** Bayesian-adjusted rating descending (well-rated, well-voted fits first). Ties broken by `source_id` (Workbench GUID).

### Score Validation

All `quality_score` values **must** fall within the `[0.0, 1.0]` range. Out-of-range values are clamped and logged as warnings to surface bugs in source adapters or upstream data changes.

```python
def validate_quality_score(score: float, fit_id: str, source: str) -> float:
    """Clamp quality_score to [0.0, 1.0] with warning on out-of-range values."""
    if score < 0.0 or score > 1.0:
        logger.warning(
            "quality_score out of range: clamped %.3f → %.3f for fit %s (source: %s)",
            score, max(0.0, min(1.0, score)), fit_id, source
        )
        return max(0.0, min(1.0, score))
    return score
```

| Scenario | Behavior |
|----------|----------|
| Score within `[0.0, 1.0]` | Passed through unchanged |
| Score < 0.0 | Clamped to `0.0`, `WARNING` logged with fit ID, source name, and original value |
| Score > 1.0 | Clamped to `1.0`, `WARNING` logged with fit ID, source name, and original value |
| Score is `NaN` or non-numeric | Treated as `0.0`, `ERROR` logged — indicates a source adapter bug |

**When applied:** Validation runs inside each `FitSource` adapter's `query()` method, before candidates are returned to the selection engine. This catches issues at the source boundary rather than allowing invalid scores to propagate through sorting and display logic.

**Rationale:** The archetype source uses hardcoded tier mappings (0.5–1.0) which are inherently in-range. ESI personal uses a fixed 0.6. The primary risk is the Workbench source, where upstream API changes (e.g., rating scale change from 1–5 to 0–100) could produce out-of-range normalized scores. Clamping with logging surfaces these issues without crashing.

---

## Omega Derivation

**v1 decision: descoped for non-archetype sources.**

| Source | Omega Derivation | Rationale |
|--------|-----------------|-----------|
| Archetype | Explicit in YAML metadata (`omega_required: true/false`) | Already implemented |
| ESI Personal | Default `omega_required=True` | Conservative; no alpha cap data source |
| Eve Workbench | Default `omega_required=True` | Conservative; no alpha cap data source |

Alpha clone skill restrictions are not in the EVE SDE. They are hardcoded in the EVE client and have been reverse-engineered by community tools (PyFA, EVEMon). Maintaining a reverse-engineered table adds a dependency with no staleness detection.

**Conservative-correct:** Alpha pilots won't be recommended fits they can't fly. The worst case is that some alpha-eligible external fits are hidden — an acceptable tradeoff for v1.

**Future (Phase D):** Source alpha cap table from PyFA data files with a documented refresh process. Implement `derive_omega_required(eft)` checking hull eligibility, module eligibility, and skill caps vs alpha limits.

---

## Activity Matching

**v1 decision: hull-only search by default.** Activity tag mapping is optional — the user can provide tags explicitly, but no mandatory mapping maintenance is required.

### Query Behavior

| User Input | Workbench Query | Filtering |
|------------|----------------|-----------|
| Hull only (`fit search vexor`) | `typeId=626` | None — all fits for hull |
| Hull + tags (`fit search vexor --tags pve,missions`) | `typeId=626` (cache), then local tag filter | User-provided tags matched against fit tags |
| Hull + activity (archetypes only) | N/A — archetypes use directory structure internally | Archetype source handles activity matching |

### Result Set Limits

When querying Workbench without tags, popular hulls may return large result sets. Controls:

1. **Minimum quality threshold:** Discard fits with `votes < 3` (insufficient community signal). **Exception:** When user provides `--tags`, min_votes is NOT applied — see "EFT Fetch Strategy" for rationale.
2. **Result cap:** Keep only top 50 fits by Bayesian-adjusted rating
3. **Both filters applied at cache read time** — cache stores all results, Workbench source applies thresholds before returning candidates

These thresholds are configurable in `userdata/config.json` under `fit_sources.eve_workbench`.

**Future (Phase D):** Add a `reference/fit_sources/tag_mapping.yaml` for automatic activity-to-tag mapping when usage data shows which mappings are valuable.

### Tag Matching Rules

When `--tags` is provided, matching follows these rules:

| Rule | Behavior |
|------|----------|
| Case handling | Case-insensitive (casefolded via Python `str.casefold()` before comparison for proper Unicode handling) |
| Token splitting | Comma/semicolon separated, whitespace trimmed |
| Match type | Exact token match (no substring, no stemming) |
| Logic | OR — fit matches if **any** user tag appears in the fit's tag list |
| Missing tags | Fit with no tags field is treated as empty list (never matches) |
| Synonym expansion | None in v1 (deferred to Phase D tag mapping YAML) |

**Example:** `--tags pve,ratting` matches a fit tagged `["ratting", "nullsec"]` (because `ratting` matches), but does not match `["pvp", "fleet"]`.

---

## Authentication Architecture

### Eve Workbench Authentication

| Mode | Capabilities | Use Case |
|------|--------------|----------|
| Anonymous | Query public fits by typeId/tags | Default, no setup |
| Authenticated | Access private fits, higher rate limits (TBD) | Optional power user |

**Configuration:**
```json
// userdata/config.json
{
  "fit_sources": {
    "eve_workbench": {
      "enabled": true,
      "authenticated": false
    }
  }
}
```

API keys stored in `userdata/credentials/eve_workbench.json` (gitignored, 600 permissions).

### ESI Authentication

Already implemented. Uses existing ESI OAuth flow for `esi-fittings.read_fittings.v1` scope.

---

## Caching Strategy

> **PROVISIONAL DESIGN — BLOCKED ON PHASE 0 EVIDENCE**
>
> The caching strategy and EFT fetch behavior depend on the following falsifiable assumptions. Each must be validated during Phase 0 with documented evidence. If any assumption is false, the indicated design elements must be revised before Phase B implementation begins.
>
> | # | Assumption | Phase 0 Validation | If False → Revise |
> |---|-----------|-------------------|-------------------|
> | C-1 | `/latest/fits` returns rating, votes, and tags **inline** per fit (no per-fit detail call required) | Inspect response JSON for list endpoint | Metadata-first fetch loop; re-evaluate latency budget and call count |
> | C-2 | EFT content is **immutable** for a given fit GUID (edits produce a new GUID) | Fetch same fit twice across 24h+ gap; compare EFT | Add EFT content hash to cache; re-fetch on metadata refresh if hash changes |
> | C-3 | Pagination is **deterministic and stable** (offset/cursor-based, not random sampling) | Query popular hull (Vexor); verify page consistency across two requests | Top-N selection unreliable; may need to fetch all pages or use different ranking strategy |
> | C-4 | EFT export from `/latest/fits/:fitid/eft` is **parseable** by existing `parse_eft()` without adaptation | Fetch 5+ EFTs; run through `parse_eft()`; check for `EFTParseError` | Implement EFT adapter/normalizer before cache pipeline |

### Cache Hierarchy

| Source | Cache Location | TTL | Invalidation |
|--------|---------------|-----|--------------|
| Archetype | Loaded on demand (files) | Infinite | File changes |
| ESI Personal | `userdata/pilots/{pilot}/cache/fittings.json` | 24h | Manual or ESI scope |
| Eve Workbench | `userdata/cache/eve_workbench/{type_id}.json` | 24h | TTL expiry |

### Cache Subdirectory Structure

```
userdata/cache/eve_workbench/
├── 626.json                    # Vexor fits (type_id = 626)
├── 24690.json                  # Drake fits (type_id = 24690)
├── 645.json                    # Dominix fits (type_id = 645)
└── _metadata/                  # Bookkeeping files (not fit data)
    ├── last_refresh.json       # Timestamps of last refresh per type_id
    ├── circuit_breaker.json    # Persistent circuit breaker state (Phase D — in-memory for v1)
    └── fetch_stats.json        # API call counts, cache hit rates for diagnostics
```

| Path | Contents | Managed By |
|------|----------|------------|
| `{type_id}.json` | Fit metadata + cached EFTs for a single hull | Workbench client (write), Workbench source adapter (read) |
| `_metadata/last_refresh.json` | `{"626": "2026-02-05T14:30:00Z", ...}` — last successful API fetch per type_id | Workbench client (updated on successful fetch) |
| `_metadata/fetch_stats.json` | Diagnostic counters: total API calls, cache hits, cache misses, EFT fetch failures | Workbench client (append-only, reset on `refresh-cache --force`) |
| `_metadata/circuit_breaker.json` | Reserved for Phase D persistent circuit breaker state | Not used in v1 (in-memory only) |

**Naming convention:** Fit cache files use the bare `type_id` as filename (e.g., `626.json`). The `_metadata/` prefix with underscore ensures bookkeeping files sort separately and are never confused with fit data (EVE type IDs are always numeric).

**Directory creation:** The cache directory and `_metadata/` subdirectory are created lazily on first write. `refresh-cache --force` deletes all `{type_id}.json` files but preserves `_metadata/`.

### Eve Workbench Cache Structure

**Cache key:** `type_id` only. Cache stores **unfiltered** results. Tag filtering is applied locally after cache read. This avoids cache fragmentation — one API call per hull serves all queries.

```json
// userdata/cache/eve_workbench/626.json (Vexor fits)
{
  "type_id": 626,
  "fetched_at": "2026-02-05T14:30:00Z",
  "fits": [
    {
      "guid": "abc-123",
      "name": "Vexor Ratting Beast",
      "rating": 4.5,
      "votes": 127,
      "tags": ["pve", "ratting"],
      "eft_cached": true,
      "eft": "[Vexor, Vexor Ratting Beast]\n..."
    }
  ]
}
```

### Cache Lifecycle

Cache entries evolve across refreshes. This table defines behavior for each scenario:

| Scenario | Behavior |
|----------|----------|
| **Metadata TTL expires** | Re-fetch `/latest/fits?typeId=X` for fresh metadata |
| **EFTs still in top-N** | Retained and reused (assumes C-2: EFT immutable per fit GUID — Phase 0 must validate) |
| **EFTs dropped from top-N** | Retained in cache but not refreshed; available if re-promoted |
| **New entries in top-N** | EFT fetched on demand |
| **Metadata-only changes** (name/tags/rating) | Cached EFT reused, metadata updated from fresh response |
| **GUID change** | Treated as new fit; new EFT fetch required |
| **Manual invalidation** | `fit refresh-cache --hull vexor --force` or `rm -rf userdata/cache/eve_workbench/` |

### EFT Fetch Strategy

**v1 approach: fixed top-N, no expansion. Tag filtering applies before top-N selection.**

1. **Metadata-first:** `/latest/fits?typeId=X` returns fit metadata (name, rating, votes, tags) without EFT. Cache this.
2. **Pre-filter on metadata:** If user supplied `--tags`, filter to tag-matching fits first (min_votes threshold is **not** applied — see Result Set Limits). If no tags, apply min_votes threshold to discard low-signal fits. Then sort by rating. Select **top N candidates** (N=15 default, configurable) from the filtered set.
3. **Fetch EFT only for top N:** Request `/latest/fits/:fitid/eft` for the top N candidates only.
4. **Cache EFT alongside metadata:** Once fetched, EFT is stored in the cache entry and reused. EFTs fetched for one query are available to subsequent queries regardless of tags.
5. **No expansion:** If the pilot can't fly any of the top N, they get zero Workbench results. Archetype and personal fits still available.

**Tag filtering guarantees:** When `--tags` is provided, the top-N selection operates on the tag-filtered subset, not the overall population. This ensures tag-matching fits get EFTs fetched even if they aren't in the top N overall. Without this, a niche tag like `abyssal` could return zero results despite matching metadata existing in the cache.

**Tag filter vs min_votes interaction:**

| Scenario | User Tags | min_votes Applied? | Rationale |
|----------|-----------|-------------------|-----------|
| Hull-only query | None | Yes (default 3) | Quality floor needed without intent signal |
| Tagged query | Provided | No | User intent overrides quality floor |

```
API calls per uncached hull query:
  1 call:  GET /latest/fits?typeId=X  (metadata for all fits)
  N calls: GET /latest/fits/:fitid/eft (EFT for top N candidates)
  Total:   N+1 calls (typically 16)

Subsequent queries for same hull: 0 API calls (cache hit)
```

**Why no expansion in v1?** On-demand expansion adds a large surface area for rate-limit, caching, and partial-failure bugs. Fixed top-N is predictable: always the same number of API calls, always the same cache behavior. If 15 well-rated fits aren't flyable, the Workbench source simply returns an empty group — the other sources still provide results.

**Future (Phase D):** Add on-demand expansion with rate-limit caps when usage data shows it's needed.

### Cache Warming

For frequently-used hulls, pre-warm cache during:
- Explicit `aria-esi fit refresh-cache` command
- Background task after pilot login (if idle time permits)

**Candidate hulls:** Hulls in pilot's ship roster (from operations.md).

### Circuit Breaker

The Workbench client implements a circuit breaker to prevent cascading failures:

| Parameter | Value |
|-----------|-------|
| Failure threshold | 5 consecutive failures → circuit open |
| Open duration | 5 minutes |
| State storage | In-memory (resets on process restart) |
| Half-open behavior | Probe after 5 minutes; success → closed, failure → restart timer |
| HTTP 429 handling | Triggers backoff but does NOT count as circuit breaker failure |
| Open circuit behavior | Source returns empty result set, marked unavailable, warning in CLI footer |

**Design rationale:** In-memory state is sufficient because the CLI is short-lived. Long-running MCP server processes would need persistent state (Phase D consideration).

---

## Error Taxonomy

API errors from Eve Workbench are classified into categories with distinct handling strategies. Each category maps to a recovery action, circuit breaker interaction, and user-facing message.

### Error Categories

| Category | HTTP Codes / Conditions | Examples |
|----------|------------------------|---------|
| **Client error** | 400, 401, 403, 404, 410, 422 | Bad `typeId`, invalid auth token, deleted fit, malformed query |
| **Server error** | 500, 502, 503, 504 | Workbench API outage, upstream gateway failure |
| **Rate limit** | 429 | Too many requests within window |
| **Network error** | Connection refused, DNS failure, TCP timeout | Workbench unreachable, network partition |
| **Parse error** | 200 with unexpected body | Schema drift, HTML error page returned as 200, truncated JSON, EFT format incompatible with `parse_eft()` |

### Handling Strategy Per Category

| Category | Retry? | Backoff | Circuit Breaker | Cache Fallback | Logging |
|----------|--------|---------|-----------------|----------------|---------|
| **Client 4xx (non-retriable)** | No | N/A | Does NOT increment failure count | No (request is invalid) | `WARNING` with status code and endpoint |
| **Client 404/410 (deleted fit)** | No | N/A | Does NOT increment failure count | Remove stale cache entry if exists | `INFO` — fit no longer available |
| **Server 5xx** | Yes, up to 2 retries | Exponential (1s, 2s) | Increments failure count | Yes — return stale cache if available | `ERROR` with status code and response excerpt |
| **Rate limit 429** | Yes, up to 3 retries | Respect `Retry-After` header; fallback to exponential (2s, 4s, 8s) | Does NOT increment failure count (per §Circuit Breaker) | Yes — return stale cache if available | `WARNING` with retry delay |
| **Network error** | Yes, up to 2 retries | Exponential (1s, 2s) with jitter | Increments failure count | Yes — return stale cache if available | `ERROR` with exception type |
| **Parse error** | No (deterministic failure) | N/A | Does NOT increment failure count | Per-fit: skip individual fit, continue others | `WARNING` with fit GUID and parse error detail |

**Retry budget:** A single `fit search` invocation has a maximum of **3 total retries** across all retriable errors for the metadata call and **1 retry per EFT fetch**. This bounds worst-case latency to approximately 10s for the metadata call and prevents a slow API from stalling the CLI.

### Error Propagation to Users

Errors are surfaced in the CLI output footer, below the fit results. Errors never block results from other sources — a Workbench failure still returns archetype and personal fit groups.

| Scenario | CLI Message |
|----------|-------------|
| API timeout / network error (with cache) | `⚠ Eve Workbench: showing cached results (API unreachable)` |
| API timeout / network error (no cache) | `⚠ Eve Workbench: unavailable (API unreachable)` |
| Rate limited (exhausted retries, with cache) | `⚠ Eve Workbench: showing cached results (rate limited)` |
| Rate limited (exhausted retries, no cache) | `⚠ Eve Workbench: unavailable (rate limited — try again later)` |
| Server error 5xx (with cache) | `⚠ Eve Workbench: showing cached results (API error)` |
| Server error 5xx (no cache) | `⚠ Eve Workbench: unavailable (API error)` |
| Circuit breaker open | `⚠ Eve Workbench: unavailable (temporarily disabled — too many failures)` |
| Authentication failure (401/403) | `⚠ Eve Workbench: authentication failed — check credentials or disable authentication` |
| All EFTs failed to parse | `⚠ Eve Workbench: 0 fits loaded (EFT parse errors — possible API format change)` |
| Some EFTs failed to parse | `ℹ Eve Workbench: {N} of {M} fits skipped (parse errors)` |
| Deleted fit during EFT fetch | *(silent — fit omitted from results, logged at INFO)* |

**Design principles:**
- **Source isolation:** Workbench errors never propagate to archetype or ESI sources. Each source group succeeds or fails independently.
- **Cache as safety net:** Stale cache is preferred over no results. Cache entries are served with the `⚠ showing cached results` indicator so users know data may be outdated.
- **No stack traces in CLI:** Technical details go to the log file. User-facing messages describe the impact, not the cause.
- **Actionable when possible:** Messages suggest a recovery action where one exists (e.g., "try again later", "check credentials").

---

## Logging Strategy

Structured logging for the fit sources subsystem follows ARIA's existing logging conventions with source-specific extensions.

### Log Levels

| Level | Usage | Examples |
|-------|-------|---------|
| `DEBUG` | API request/response details | `GET /latest/fits?typeId=626 → 200 (347ms)`, EFT fetch per fit GUID, cache key lookups |
| `INFO` | Cache hits/misses, normal operations | `Cache hit: eve_workbench/626.json (age: 4h12m)`, `Cache miss: eve_workbench/17726.json — fetching`, `Fit search completed: 3 sources, 24 candidates` |
| `WARNING` | Degraded sources, threshold anomalies | `Eve Workbench: serving stale cache (API returned 503)`, `quality_score out of range: clamped 1.3 → 1.0 for fit abc-123`, `Circuit breaker half-open: probing Eve Workbench` |
| `ERROR` | Unrecoverable failures | `Eve Workbench: circuit breaker OPEN after 5 consecutive failures`, `EFT parse failed for fit abc-123: unexpected module format`, `Cache write failed: permission denied on eve_workbench/626.json` |

### Structured Format

Log entries use JSON format for machine parseability. All fit source log entries include the `subsystem` field for filtering.

```json
{
  "timestamp": "2026-02-05T14:30:00.123Z",
  "level": "INFO",
  "subsystem": "fit_sources",
  "source": "eve_workbench",
  "action": "cache_miss",
  "type_id": 626,
  "hull": "Vexor",
  "message": "Cache miss — fetching from API",
  "duration_ms": null
}
```

```json
{
  "timestamp": "2026-02-05T14:30:00.470Z",
  "level": "DEBUG",
  "subsystem": "fit_sources",
  "source": "eve_workbench",
  "action": "api_request",
  "method": "GET",
  "endpoint": "/latest/fits",
  "params": {"typeId": 626},
  "status_code": 200,
  "duration_ms": 347,
  "message": "Metadata fetch complete"
}
```

### Sensitive Data Redaction

Tokens and credentials are **never** logged, even at `DEBUG` level.

| Data Type | Redaction Rule |
|-----------|---------------|
| API keys / tokens | Replace with `***REDACTED***` — applies to `Authorization` headers, query string tokens, and credential file contents |
| ESI OAuth tokens | Never included in log entries; ESI adapter strips before logging |
| Webhook URLs | Log domain only: `discord.com/api/webhooks/***` |
| Credential file paths | Log filename only, not full path: `eve_workbench.json` (not `userdata/credentials/eve_workbench.json`) |

### Log Rotation Policy

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Max file size | 10 MB | CLI sessions are short-lived; 10 MB covers weeks of usage |
| Max rotated files | 3 | Total cap: 40 MB (current + 3 rotated) |
| Rotation trigger | Size-based (not time-based) | CLI usage is bursty; time-based rotation wastes space on idle periods |
| Log location | `userdata/logs/fit_sources.log` | Follows existing ARIA log directory convention |
| Compression | gzip for rotated files | `.log.1.gz`, `.log.2.gz`, `.log.3.gz` |

---

## Selection Algorithm

### Input

```python
@dataclass
class FitSelectionRequest:
    hull: str  # Hull name or type_id
    activity: str | None  # e.g., "pve/missions/l3" (used by archetype source only in v1)
    pilot_skills: dict[int, int]  # skill_id -> level
    clone_status: Literal["alpha", "omega"]

    # Optional filters
    tank_preference: str | None  # "armor", "shield"
    tags: list[str] | None  # User-provided tags for Workbench filtering
```

**Clone status unknown:** If clone status cannot be determined (ESI unavailable), default to `"omega"`. This is fail-open: omega pilots get correct results; alpha pilots may see unflyable fits. Consistent with the conservative-correct principle — erring toward showing more fits rather than hiding flyable ones.

### Algorithm

```
FUNCTION select_fits(request):
    groups = []  # list of (source_name, SourceGroup), ordered by config list position

    # 1. Query all enabled sources (iterated in config order)
    FOR source IN enabled_sources:  # order from config
        IF NOT source.is_available():
            record_unavailable(source.name)
            CONTINUE

        candidates = source.query(request.hull, request.activity)

        # 2. Filter by flyability (all candidates must have EFT populated)
        FOR fit IN candidates:
            fit.can_fly = check_requirements(fit.eft, request.pilot_skills)
            IF request.clone_status == "alpha" AND fit.omega_required:
                fit.can_fly = False

        # 3. Apply optional filters
        IF request.tank_preference:
            candidates = [f for f in candidates if infer_tank(f.eft) == request.tank_preference]

        IF request.tags AND source.name == "eve_workbench":
            candidates = [f for f in candidates if matches_tags(f, request.tags)]

        # 4. Split into flyable / trainable
        flyable = [f for f in candidates if f.can_fly]
        trainable = [f for f in candidates if NOT f.can_fly]

        # 5. Sort within source by quality_score desc, source_id for determinism
        flyable.sort(key=lambda f: (-f.quality_score, f.source_id))
        trainable.sort(key=lambda f: (-f.quality_score, f.source_id))

        groups.append((source.name, SourceGroup(
            flyable=flyable[:10],
            trainable=trainable[:5]
        )))

    RETURN FitSearchResult(groups=groups, ...)
```

**Key differences from previous proposal:**
- No cross-source scoring or source bonuses
- No cross-source deduplication
- No on-demand EFT expansion loop
- Each source is queried independently and results stay grouped
- Within-source deduplication is handled internally by each source (trivial for archetypes/ESI)

### Non-Archetype Fit Processing

Non-archetype fits (ESI personal, Workbench) arrive as raw EFT strings and require processing before they can participate in selection. Each processing step is independent — failure in one does not cascade.

**EFT Parsing:**
Parse via `parse_eft()`. On `EFTParseError` or `TypeResolutionError` → log warning, skip individual fit, continue processing remaining fits. No cascading failures.

**Tank Inference:**
`classify_tank(parsed_fit)` runs on successful parse. On failure → `tank_type=None`. Fits with `tank_type=None` are excluded by `tank_preference` filter but included in unfiltered results.

**Skill Check:**
Requires successful `ParsedFit` (needs resolved type_ids). If EFT parsing failed → fit is excluded entirely (can't skill-check without type_ids). Successful parse → standard `check_requirements()` against pilot skills.

**Tag Matching:**
Local comparison per "Tag Matching Rules" section. Applied independently of parse/skill status. Missing tags field → treated as empty list (never matches tag filter).

---

## CLI Interface

### New Commands

```bash
# Search for fits across all sources (Phase A: archetype + ESI only)
uv run aria-esi fit search vexor

# Search with activity (passed to archetype source)
uv run aria-esi fit search vexor --activity pve/missions/l3

# Search specific source
uv run aria-esi fit search vexor --source archetype

# Search Workbench with tags (Phase C)
uv run aria-esi fit search vexor --source eve_workbench --tags pve,missions

# Standalone Workbench query (Phase B)
uv run aria-esi fit workbench-search vexor
uv run aria-esi fit workbench-search vexor --tags pve,ratting --limit 20

# Refresh Workbench cache (Phase B)
uv run aria-esi fit refresh-cache --hull vexor
uv run aria-esi fit refresh-cache --all-roster
```

### Output Format

```
Fit Search: Vexor / L3 Missions

  ARCHETYPES (curated)
  -------------------------------------------------------------------
  a1. L3 Missions - Armor T2              Tier: t2      [flyable]
      Tank: armor_active | DPS: 340 | EHP: 9,900

  a2. L3 Missions - Armor T2 Optimal      Tier: optimal [train 12d]
      Missing: Medium Drone Operation V

  a3. L3 Missions - Armor T1              Tier: t1      [flyable]
      Tank: armor_active | DPS: 220 | EHP: 7,200

  YOUR FITS (ESI personal)
  -------------------------------------------------------------------
  p1. My Vexor Fit                                      [flyable]

  COMMUNITY (Eve Workbench)                           [15 cached]
  -------------------------------------------------------------------
  w1. Vexor AFK Ratter             4.5/5 (127 votes)   [flyable]
      Tags: pve, ratting

  w2. Vexor Mission Runner         4.2/5 (85 votes)    [flyable]
      Tags: pve, missions

  w3. L3 Drone Vexor               3.8/5 (42 votes)    [train 3d]
      Missing: Gallente Cruiser IV

  -------------------------------------------------------------------
  ⚠ Eve Workbench: unavailable (API timeout)
```

**Source availability in output:**
- **Disabled sources:** Silently omitted (not shown in output at all)
- **Runtime failures:** Warning footer shown (API timeout, circuit breaker open, credentials missing)

**Per-group numbering.** Each group uses a source prefix (a=archetype, p=personal, w=workbench) to reinforce that groups are independent. No global numbering — that would imply cross-source ranking. Each group uses its own quality signal: tier for archetypes, rating/votes for Workbench, recency for personal.

---

## Risk Assessment

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Eve Workbench API changes/breaks | Medium | High | Response schema validation + contract tests |
| Rate limiting blocks queries | Medium | Medium | Cache warming, fixed top-N fetch budget |
| Low-quality fits in Workbench | High | Medium | Min votes threshold, Bayesian adjustment |
| EFT parse failures | Medium | Low | Log and skip, don't fail entire query |
| Authentication complexity | ~~Low~~ **CERTAIN** | ~~Medium~~ **TERMINAL** | ~~Start anonymous-only~~ **BLOCKED — Eve Workbench v2.0 requires developer registration + API key per user** |

**API stability:** Eve Workbench endpoints are under `/latest/` with no versioned paths. The client implements:
1. **Response schema validation:** Required fields/types checked per response. Validation failure logs warning, returns cached data, degrades gracefully.
2. **Contract tests:** Test suite against live API for schema drift detection. Weekly CI schedule.
3. **Adapter pattern:** Raw responses mapped to internal `WorkbenchFitMetadata`. Only adapter layer changes if API changes.
4. **Circuit breaker:** After N consecutive failures, degrade to archetype-only. No indefinite retry.

### Legal/Compliance Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| ToS prohibits caching | Low | High | Phase 0 gate G0-6 validates before commitment |
| ToS changes post-integration | Low | Medium | Annual review; degrade to archetype-only |
| Attribution requirements | Medium | Low | Implement attribution footer if required |

### Scope Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Scope creep into fit editing | Medium | High | Read-only in v1, explicit boundary |
| Feature parity expectations | Medium | Medium | Clear documentation of what's supported |
| Maintenance burden | Low | Medium | Cache-heavy, fixed API call budget |

---

## Architecture Review: Resolution Summary

All findings from the 2026-02-05 architecture review have been resolved. This section documents the decisions for traceability.

**⛔ UPDATE 2026-02-06:** Phase 0 validation **FAILED**. The Eve Workbench component of this proposal is **CANCELLED** due to v2.0 authentication requirements. Only Phase A (Archetype + ESI sources) remains viable. See "CRITICAL BLOCKER" section at top of document.

### Decision Tracker

| Finding | Decision | Status |
|---------|----------|--------|
| RF-1: Unvalidated API assumptions | Phase 0 go/no-go gates unchanged; must pass before Phase B | **FAILED** — Phase 0 revealed Eve Workbench v2.0 requires developer auth; effort stopped |
| RF-2: No FitSource abstraction | `FitSource` protocol adopted; `UnifiedFit` god object removed | **RESOLVED** — protocol is the architecture |
| RF-3: False precision from incomparable scores | Grouped-by-source output for v1; no cross-source ranking | **RESOLVED** — blended ranking deferred to Phase D |
| RF-4: Alpha cap data not in SDE | Descoped for v1; all non-archetype fits default `omega_required=True` | **RESOLVED** — conservative-correct |
| RF-5: EFT normalization chicken-and-egg | Cross-source dedup removed from v1 entirely | **RESOLVED** — no normalization needed |
| RF-6: Integration with existing select_fits() | Archetype source wraps existing logic as black box | **RESOLVED** — zero rewrite of existing code |
| RF-7: Skill-check scaling | Fixed top-N per source bounds candidate pool; profile during Phase B | **RESOLVED** — pool is bounded |

### Secondary Issues

| Issue | Phase | Resolution |
|-------|-------|------------|
| Cache coherence | ~~Phase B~~ | ~~Simplified: metadata + top-N EFT fetched together, no partial states~~ ⛔ **CANCELLED with Phase B** |
| Activity tag mapping | Phase D | Deferred; hull-only search for v1 |
| Cost estimation | Phase D | Deferred; compute only for user-selected fit |
| Circuit breaker | ~~Phase B~~ | ~~Degrade to archetype-only after N failures~~ ⛔ **CANCELLED with Phase B** |

---

## Implementation Phases

### Phase 0: API Validation (This Week)

**Goal:** Validate Eve Workbench API capabilities before committing to integration. **Produces a binding go/no-go decision with documented evidence.**

> **Phase A runs in parallel with Phase 0.** Phase A has no dependency on Phase 0 — it uses only internal sources. **Phase B and C are hard-blocked on Phase 0 GO decision — no code for Workbench client, cache, or adapter may be written until all gates are evaluated and evidence is recorded.**

#### Evidence Requirements

Phase 0 produces a single evidence document (`dev/evidence/phase0_workbench_validation.md`) containing:

| Section | Contents | Format |
|---------|----------|--------|
| Response schemas | Actual JSON from `/latest/fits` and `/latest/fits/:fitid` | Verbatim response excerpts |
| Authentication | Request/response for anonymous query | `curl` command + HTTP status + headers |
| Rate limits | Observed `X-RateLimit-*` headers or equivalent | Header captures from 20+ sequential requests + burst test (10 rapid requests) |
| EFT compatibility | Output of `parse_eft()` against 20-30 diverse fetched EFTs | Pass/fail per fit with error details, tag coverage stats |
| Pagination | Page structure for popular hull (100+ fits) | Two sequential page fetches with response excerpts |
| Tag behavior | Response with and without tag filter | Side-by-side response excerpts |
| ToS/usage policy | Relevant ToS sections on caching, redistribution, attribution | Quoted excerpts with source URLs |
| Score fields | Actual field names, types, and value ranges for rating/vote data | Annotated response JSON |

#### Deliverables

- [ ] Evidence document created at `dev/evidence/phase0_workbench_validation.md`
- [ ] Document actual API response schemas (verbatim JSON)
- [ ] Test anonymous vs authenticated access (HTTP status + headers captured)
- [ ] Identify rate limits (header captures from sequential requests + burst test)
- [ ] Verify EFT export format compatibility with `parse_eft()` (20-30 diverse fits tested)
- [ ] Test tag filtering behavior (with/without comparison)
- [ ] Document pagination behavior on popular hulls (Vexor, Drake)
- [ ] Investigate Eve Workbench Terms of Service and usage policy (caching rights, redistribution, attribution)
- [ ] Document actual score/rating field names, types, and value ranges
- [ ] **Test error response handling (5xx simulation, timeout behavior, deleted fit 404s)**
- [ ] **Generate quality distribution histogram for sample hulls**
- [ ] **Document Content-Type headers for all endpoints**
- [ ] **Test tag format variations (comma-separated, multiple params, case sensitivity)**
- [ ] **Verify GUID stability (daily check for 1 week)**
- [ ] Cross-reference evidence against provisional assumptions (C-1 through C-4 in §Caching Strategy)

#### Go/No-Go Gates

| Gate | Condition | Evidence Required | If NO-GO |
|------|-----------|-------------------|----------|
| G0-1: Anonymous access | Public fits queryable without API key | HTTP 200 on unauthenticated request | Evaluate API key process; if onerous, reconsider |
| G0-2: Inline metadata | `/latest/fits` returns rating, votes, tags per fit | Annotated response JSON showing fields | Redesign for per-fit detail calls; re-evaluate latency |
| G0-3: Rate limits viable | >=10 requests/minute sustained | Header captures from 20+ sequential requests | Reduce top-N to 5; evaluate authenticated limits |
| G0-4: EFT format compatible | `/latest/fits/:fitid/eft` parseable by `parse_eft()` | `parse_eft()` output for 20-30 diverse fits (varied hulls, modules, formats) | Implement EFT adapter; assess effort |
| G0-5: Sufficient volume | >=3 rated fits for common PvE hulls (Vexor, Drake, Dominix) | Response counts per hull | Insufficient value; defer or cancel |
| **G0-5b: Quality distribution** | **Fits span quality spectrum (not all 5-star or all 1-star)** | **Quality score histogram from sample of 50+ fits per hull** | **May indicate rating inflation or insufficient voting; adjust Bayesian prior** |
| G0-6: ToS compliance | Caching and redistribution permitted by ToS/usage policy | Quoted ToS excerpts with source URLs | Defer or cancel; evaluate terms restrictions |
| **G0-7: Error response handling** | **API returns consistent error codes (5xx, 4xx, timeouts) with parseable error bodies** | **Documented error responses: 5xx simulation, timeout test, 404/410 for deleted fits** | **Assess circuit breaker complexity; may require custom error taxonomy** |

**Exit criteria:** All gates evaluated with evidence recorded. GO requires G0-1 through G0-4, G0-6, and G0-7 passing. G0-5 failing downgrades scope; G0-5b failing triggers Bayesian prior adjustment. Evidence document must include cross-reference against provisional assumptions C-1 through C-4 (§Caching Strategy) and scoring assumptions (§Quality Score Derivation), confirming or invalidating each.

#### Phase 0 → Design Dependencies

If Phase 0 evidence contradicts any provisional assumption, the following sections **must be revised** before Phase B begins:

| Assumption Invalidated | Sections Requiring Revision |
|------------------------|----------------------------|
| No inline metadata (C-1 false) | §Caching Strategy (cache structure), §EFT Fetch Strategy (call budget), §Go/No-Go G0-2 |
| EFT is mutable (C-2 false) | §Cache Lifecycle (EFT reuse logic), §Cache Structure (add content hashing) |
| Pagination unreliable (C-3 false) | §EFT Fetch Strategy (top-N selection), §Result Set Limits, §Test Plan Phase B (top-N tests) |
| EFT not parseable (C-4 false) | §Non-Archetype Fit Processing, §Go/No-Go G0-4 |
| Rating is not 1–5 scale | §Quality Score Derivation (normalization formula), §Within-Source Ordering |
| No vote count field | §Quality Score Derivation (Bayesian adjustment), §Result Set Limits (min_votes threshold) |
| ToS prohibits caching | §Caching Strategy (entire section), §Cache Warming, §EFT Fetch Strategy |

### Phase A: FitSource Protocol + Registry + Archetype/ESI Adapters

**Goal:** Prove the extensibility architecture with only internal sources. No external API dependency.

**Prerequisites:** None (this is pure internal refactoring).

#### Protocol Stability Commitment

The `FitSource` protocol, `FitCandidate` dataclass, and `FitSearchResult` container defined in Phase A become the **stable interface** for Phase B/C. To minimize rework:

- The protocol and output model must be reviewed and approved before Phase A implementation begins
- Phase A PR must include a `PROTOCOL_FROZEN.md` marker documenting the locked interface
- Any post-Phase-A protocol change requires explicit justification and impact assessment against Phase B/C deliverables
- Additive changes (new optional fields on `FitCandidate`) are permitted; breaking changes (field removal, type changes, signature changes on `FitSource.query()`) require re-review

#### Deliverables

- [ ] `src/aria_esi/fit_sources/base.py` — `FitSource` protocol, `FitCandidate` dataclass, `FitSearchResult` container
- [ ] `src/aria_esi/fit_sources/registry.py` — Source registry with config-driven enablement
- [ ] `src/aria_esi/fit_sources/archetype_source.py` — Archetype adapter wrapping existing `select_fits()` as black box
- [ ] `src/aria_esi/fit_sources/esi_source.py` — ESI personal fittings adapter
- [ ] `src/aria_esi/fit_sources/selector.py` — Selection engine: query sources, filter by flyability, return grouped results
- [ ] CLI: `aria-esi fit search <hull> [--activity] [--source]`
- [ ] `tests/test_fit_source_protocol.py` — Protocol compliance tests for both adapters
- [ ] `tests/test_fit_selector.py` — Grouped selection, flyability filtering, tank preference filtering
- [ ] Migration acceptance test (see below)

#### Migration Acceptance Test

The refactored archetype source must produce **data-identical results** to the existing `archetype recommend` command. CLI formatting (headers, column widths, chrome) is explicitly out of scope — the new `fit search` command will have different output framing. The test asserts on structured data, not rendered text.

1. **Before Phase A begins:** Capture reference fixtures by running `archetype recommend` for every hull/activity combination that has archetypes. Extract and store the **structured data** (fit name, tier, sort position, flyability, missing skills) as `tests/fixtures/migration_snapshots/*.json`.
2. **Phase A test:** For each fixture, run the equivalent `fit search <hull> --activity <activity> --source archetype`, extract the archetype group's structured data, and assert equality against the fixture.
3. **Scope:** Fixtures cover the archetype source group only. ESI personal and Workbench groups are new output with no prior baseline.

**What is compared (must match):**
- Set of fits selected (by name/path)
- Sort order within the group
- Tier assignment per fit
- Flyability determination per fit (can_fly, missing_skills)

**What is not compared (may differ):**
- CLI column widths, headers, ANSI formatting
- Output framing (section titles, group labels)
- Fields that only exist in the new model (e.g., `source_id`, `quality_score`)

**Success criteria:** `fit search vexor --activity pve/missions/l3` returns grouped archetype + personal results. Archetype group matches pre-refactor `archetype recommend` data per migration fixtures.

### Phase B: Workbench Client + Cache + Standalone CLI

**⛔ STATUS: CANCELLED** — See "CRITICAL BLOCKER" section at top of document.

**Original Goal:** Build and validate the Workbench client independently. No integration into the selection engine yet.

**Original Prerequisites:** Phase 0 GO decision.

**Cancellation Reason:** Phase 0 failed — Eve Workbench v2.0 requires developer registration and API key authentication (not anonymous/OAuth). This creates unacceptable friction for ARIA users. See `dev/evidence/phase0_workbench_validation.md` for evidence.

~~Deliverables:~~
- [ ] ~~`src/aria_esi/fit_sources/eve_workbench_client.py` — API client with schema validation, circuit breaker, backoff~~
- [ ] ~~`userdata/cache/eve_workbench/` — Cache directory structure (keyed by type_id, unfiltered)~~
- [ ] ~~EFT fetch pipeline: metadata-first, top-N EFT fetch, cache alongside~~
- [ ] ~~CLI: `aria-esi fit workbench-search <hull> [--tags] [--limit]`~~
- [ ] ~~CLI: `aria-esi fit refresh-cache --hull <hull> | --all-roster`~~
- [ ] ~~`tests/test_workbench_client.py` — Unit tests with mocked HTTP (429, schema drift, timeout, circuit breaker)~~
- [ ] ~~Contract tests against live API (gated behind `--live-api` flag)~~
- [ ] ~~Performance profile: skill-check pipeline benchmarked with 50 fits~~

~~**Success criteria:** `fit workbench-search vexor` returns rated community fits with cached EFTs. Cache warms predictably within rate limits.~~

Deliverables:
- [ ] `src/aria_esi/fit_sources/eve_workbench_client.py` — API client with schema validation, circuit breaker, backoff
- [ ] `userdata/cache/eve_workbench/` — Cache directory structure (keyed by type_id, unfiltered)
- [ ] EFT fetch pipeline: metadata-first, top-N EFT fetch, cache alongside
- [ ] CLI: `aria-esi fit workbench-search <hull> [--tags] [--limit]`
- [ ] CLI: `aria-esi fit refresh-cache --hull <hull> | --all-roster`
- [ ] `tests/test_workbench_client.py` — Unit tests with mocked HTTP (429, schema drift, timeout, circuit breaker)
- [ ] Contract tests against live API (gated behind `--live-api` flag)
- [ ] Performance profile: skill-check pipeline benchmarked with 50 fits

**Success criteria:** `fit workbench-search vexor` returns rated community fits with cached EFTs. Cache warms predictably within rate limits.

### Phase C: Workbench as Optional Source (Grouped Results)

**⛔ STATUS: CANCELLED** — See "CRITICAL BLOCKER" section at top of document.

**Original Goal:** Add Workbench as a third source in the selection engine. No blended ranking, no cross-source dedup.

**Original Prerequisites:** Phase A and Phase B both complete.

**Cancellation Reason:** Phase B cancelled due to Eve Workbench v2.0 authentication requirements.

~~Deliverables:~~
- [ ] ~~`src/aria_esi/fit_sources/workbench_source.py` — Workbench `FitSource` adapter (wraps Phase B client)~~
- [ ] ~~Config: add `"eve_workbench"` to `enabled_sources` list~~
- [ ] ~~User-provided tag filtering via `--tags` flag~~
- [ ] ~~Quality thresholds applied by Workbench source (min_votes, max_candidates)~~
- [ ] ~~`tests/test_workbench_source.py` — Adapter tests, threshold tests~~
- [ ] ~~Integration test: `fit search vexor` returns all three source groups~~
- [ ] ~~User documentation for Workbench setup and configuration~~

~~**Success criteria:** `fit search vexor` shows archetype, personal, and community groups. Workbench results are cached, bounded, and degrade gracefully on API failure.~~

### Phase D: Future Enhancements (Backlog)

Items deferred from v1, to be prioritized based on real usage data:

| Enhancement | Trigger to Prioritize | Dependencies |
|-------------|----------------------|--------------|
| Blended ranking (`--blended` flag) | Users consistently pick community fits over archetypes | Usage telemetry, calibration data |
| Cross-source deduplication | Users complain about seeing same fit in multiple groups | Parse-first EFT normalization (RF-5 approach) |
| On-demand EFT expansion | Top-15 insufficient for common queries | Rate-limit budget analysis |
| Alpha/omega derivation for external fits | Alpha pilots are a significant user base | PyFA alpha cap table, refresh process |
| Cost estimation | Users want budget filtering | Market data integration |
| Activity tag mapping (automatic) | Users frequently search with activity context | Tag mapping YAML, maintenance process |
| MCP integration (`fitting(action="search_fits")`) | Data model stable, CLI well-tested | Stable FitCandidate schema |

---

## Open Questions

### Resolved

| Question | Resolution |
|----------|-----------|
| Priority when sources conflict? | Grouped output — no cross-source conflict |
| Grouped vs blended ranking? | Grouped for v1; blended behind flag in Phase D |
| Alpha/omega for external fits? | `omega_required=True` default for v1 |
| Cross-source dedup in v1? | No; within-source only |
| Activity tag mapping mandatory? | No; hull-only search, user-provided tags optional |

### Deferred to Phase 0

| Question | Investigation |
|----------|--------------|
| OQ-1: Does `/latest/fits` return inline metadata? | Test API, document response schema |
| OQ-3: Pagination behavior? | Test popular hull, document mechanism |
| Quality threshold for Workbench fits? | Evaluate after seeing real data distribution |
| Cache TTL tradeoffs? | 24h proposed; adjust based on API freshness |

---

## Test Plan

### Phase A Tests

#### FitSource Protocol Compliance

| Test | Assertions |
|------|------------|
| Archetype source returns FitCandidate list | Each candidate has eft, quality_score, source="archetype" |
| ESI source returns FitCandidate list | Each candidate has eft, quality_score=0.6, source="esi_personal" |
| Unavailable source returns empty | `is_available()` false -> `query()` not called |
| Unknown hull returns empty | No crash, empty candidate list |

#### Grouped Selection Engine

| Test | Setup | Assertions |
|------|-------|------------|
| Two sources, both available | Archetype + ESI with results | Result has both groups, sorted within each |
| Source unavailable | ESI credentials missing | ESI group absent, archetype group present |
| Flyability filtering | Mix of flyable/unflyable candidates | flyable and trainable split correctly per group |
| Tank preference | `tank_preference="armor"` | Only armor-tanked fits in results |
| Empty results | No archetypes, no personal fits | Empty groups, no crash |

#### Migration Preservation (Data-Level Equality)

| Test | Setup | Assertions |
|------|-------|------------|
| Fixture capture (pre-refactor) | Run `archetype recommend` for all hull/activity combos | Structured data saved to `tests/fixtures/migration_snapshots/*.json` (fit name, tier, sort position, flyability, missing skills) |
| Data comparison (post-refactor) | Run `fit search <hull> --activity <activity> --source archetype` | Archetype group data matches fixture: same fits, same order, same tiers, same flyability |
| CLI formatting excluded | N/A | Fixtures contain structured data only; column widths, headers, and ANSI formatting are not compared |

### Phase B Tests

#### Workbench Client

| Test | Setup | Assertions |
|------|-------|------------|
| Cold cache query | No cache, mock API response | N+1 API calls, cache file created |
| Warm cache query | Populated cache within TTL | 0 API calls, results from cache |
| Cache TTL expiry | Cache older than 24h | Re-fetches metadata, reuses cached EFTs |
| Rate limit (429) | Mock 429 response | Exponential backoff, returns cached data |
| Schema drift | Unexpected API response shape | Warning logged, graceful degradation |
| Circuit breaker | N consecutive failures | Source marked unavailable, no further calls |
| EFT parse failure | Malformed EFT from API | Logged and skipped, other fits unaffected |

#### Top-N EFT Fetch

| Test | Setup | Assertions |
|------|-------|------------|
| Fetch top 15 | 50 metadata results, no tags | 15 EFT fetches, 35 metadata-only in cache |
| All top-N flyable | 15 with EFT, all flyable | Returns all 15 |
| None flyable | 15 with EFT, none flyable | Returns empty (no expansion in v1) |
| Tag match outside overall top N | 50 fits; top 15 by rating have no matching tags; fits ranked 20-25 match tags | Tag-filtered top-N selects from matching subset; EFTs fetched for tag-matching fits, not overall top 15 |
| Tags narrow to fewer than N | 5 fits match tags out of 50 | Only 5 EFT fetches (not 15); all 5 returned |

### Phase C Tests

#### Workbench Source Adapter

| Test | Setup | Assertions |
|------|-------|------------|
| Quality thresholds | 100 candidates, min_votes=3 | Low-vote fits removed |
| User tag filtering | `--tags pve,missions` | Only matching fits returned |
| Max candidates cap | Popular hull, 200+ results | Capped to configured max |
| Grouped integration | All 3 sources enabled | 3 groups in output |

---

## What This Proposal Does NOT Cover

Explicitly out of scope:

| Topic | Reason |
|-------|--------|
| Fit editing/uploading to Eve Workbench | Write access adds complexity, start read-only |
| Personal fit syncing (ESI -> Workbench) | Privacy concerns, user workflow unknown |
| Fit comparison UI | Beyond CLI scope |
| Automatic fit generation | AI-generated fits need validation framework |
| PvP fit selection | Different criteria than PvE, separate proposal |
| Blended cross-source ranking | No empirical data to calibrate (Phase D) |
| Cross-source deduplication | Requires parse-first normalization (Phase D) |
| Alpha/omega derivation for external fits | No reliable data source (Phase D) |
| Cost estimation | Market lookups add latency (Phase D) |
| MCP integration | Data model must stabilize first (Phase D) |

---

## Success Criteria

### Phase 0 (API Validation)

- [ ] Eve Workbench API response schemas documented
- [ ] No blocking issues with anonymous access
- [ ] Rate limits are workable (>=10 requests/minute)

### Phase A (FitSource Architecture)

| Metric | Target |
|--------|--------|
| Existing behavior preserved | Archetype source returns data-identical results to `archetype recommend` (per migration fixtures) |
| Protocol compliance | Both adapters pass protocol tests |
| Search latency | <500ms for archetype + ESI (local data only) |

### Phase B (Workbench Client)

| Metric | Target |
|--------|--------|
| Cache hit latency | <500ms for cached hull |
| Cold cache latency | <5s for uncached hull (N+1 API calls) |
| API call budget | <=16 calls per uncached hull (1 metadata + 15 EFT) |
| Degradation | Graceful fallback on API failure |

### Phase C (Integration)

| Metric | Target |
|--------|--------|
| Grouped search latency | <2s for all sources (cached) |
| Fit eligibility accuracy | 100% match with EOS skill check |
| Source isolation | Workbench failure doesn't affect archetype/ESI |

---

## Appendix: Eve Workbench API Reference

> **⚠️ PROVISIONAL — DO NOT CODE AGAINST THIS SECTION**
>
> Everything below is based on documentation at https://devblog.eveworkbench.com/docs/api/available-endpoints/fit/ and has **not been validated against live API responses**. Field names, response shapes, pagination behavior, and authentication requirements are assumptions until Phase 0 produces observed schemas.
>
> **Phase 0 action:** Replace this entire appendix with observed schemas from `dev/evidence/phase0_workbench_validation.md` before Phase B begins. Any adapter code must be written against the observed schema, not this provisional reference.

### List Fits

```
GET /latest/fits
Query params:
  - typeId: int (EVE type ID for ship hull)
  - tags: string (comma or semicolon separated)

PROVISIONAL response shape (assumed, not observed):
  - Array of fit objects with: guid, name, rating (1-5?), votes (int?), tags (array?)
  - Pagination: unknown mechanism (offset? cursor? none?)
  - Inline metadata: assumed per G0-2, not confirmed
```

### Get Fit Details

```
GET /latest/fits/:fitid
Path params:
  - fitid: GUID format identifier (assumed — actual ID format unknown)

PROVISIONAL response shape (assumed, not observed):
  - Full fit metadata; field names and types unknown
```

### Export Fit as EFT

```
GET /latest/fits/:fitid/eft
Path params:
  - fitid: GUID format identifier
Returns: Plain text EFT format (assumed — format compatibility not confirmed per G0-4)
```

**Phase 0 must document:** Actual response JSON for all three endpoints, pagination headers/mechanism, rate-limit headers, authentication requirements, and any undocumented fields.

---

## Summary

| Aspect | Current | Proposed (v1) |
|--------|---------|---------------|
| Fit sources | Archetype + ESI | Archetype + ESI + Eve Workbench |
| Architecture | Monolithic selection | FitSource protocol + plugin registry |
| Curation burden | Manual for all fits | Curate core archetypes, query community for gaps |
| Discovery | Path-based lookup | Search across sources, grouped by source |
| Quality signal | Tier (implicit) | Within-source scoring (tier, votes, recency) |
| Pilot matching | Skill tier estimation | Exact skill check against all fits |
| Cross-source ranking | N/A | Deferred to Phase D (needs empirical data) |

This integration reduces the manual curation burden while preserving the quality of core archetypes. Eve Workbench provides breadth (many hulls, many fits), while archetypes provide depth (curated, faction-tunable, upgrade paths). The FitSource protocol ensures adding future sources (e.g., zKillboard fits, PyFA imports) requires only a new adapter with no changes to the selector.

The phased approach validates API capabilities before committing to integration, proves the architecture with internal sources first, and defers complexity that needs empirical data to justify.

---

## Appendix: Configuration Reference

Complete `fit_sources` configuration block for `userdata/config.json`. All fields shown with their defaults and documentation. Fields marked **(Phase X)** indicate when they become active.

```json
// userdata/config.json
{
  "fit_sources": {
    // --- Source Registry (Phase A) ---
    // Ordered list of enabled sources. Display order matches list order.
    // Valid values: "archetype", "esi_personal", "eve_workbench"
    "enabled_sources": ["archetype", "esi_personal"],

    // --- Eve Workbench Configuration (Phase B/C) ---
    "eve_workbench": {
      // Master toggle — must also appear in enabled_sources to be queried
      "enabled": false,

      // Authentication mode (Phase B)
      // false = anonymous access (public fits only)
      // true = use API key from userdata/credentials/eve_workbench.json
      "authenticated": false,

      // --- Quality Thresholds ---
      // Minimum community votes required for a fit to be considered.
      // Applied on hull-only queries; bypassed when user provides --tags.
      // Range: 0+ (integer). Set to 0 to disable.
      "min_votes": 3,

      // Maximum candidates retained per hull after quality filtering.
      // Applied at cache read time before returning to selection engine.
      // Range: 1-500 (integer).
      "max_candidates_per_hull": 50,

      // --- EFT Fetch Strategy ---
      // Number of top-rated fits to fetch full EFT for (per hull query).
      // Controls API call budget: total calls = 1 (metadata) + top_n_eft_fetch.
      // Range: 1-50 (integer). Higher values increase cold-cache latency.
      "top_n_eft_fetch": 15,

      // --- Caching ---
      // Cache time-to-live in hours. After expiry, metadata is re-fetched
      // from the API; cached EFTs for still-relevant fits are reused.
      // Range: 1-168 (integer, hours).
      "cache_ttl_hours": 24,

      // --- Circuit Breaker ---
      // Consecutive API failures before the circuit opens.
      // Range: 1-20 (integer).
      "circuit_breaker_threshold": 5,

      // Minutes the circuit stays open before a half-open probe.
      // Range: 1-60 (integer).
      "circuit_breaker_open_minutes": 5,

      // --- Retry Policy ---
      // Max retries for retriable errors (5xx, network) on the metadata call.
      // Range: 0-5 (integer). 0 disables retries.
      "metadata_max_retries": 2,

      // Max retries per individual EFT fetch call.
      // Range: 0-3 (integer).
      "eft_max_retries": 1
    }
  }
}
```

### Minimal Configuration Examples

**Phase A (internal sources only — default):**
```json
{
  "fit_sources": {
    "enabled_sources": ["archetype", "esi_personal"]
  }
}
```

**Phase C (all sources, anonymous Workbench):**
```json
{
  "fit_sources": {
    "enabled_sources": ["archetype", "esi_personal", "eve_workbench"],
    "eve_workbench": {
      "enabled": true
    }
  }
}
```

**Phase C (all sources, authenticated Workbench with relaxed thresholds):**
```json
{
  "fit_sources": {
    "enabled_sources": ["archetype", "esi_personal", "eve_workbench"],
    "eve_workbench": {
      "enabled": true,
      "authenticated": true,
      "min_votes": 1,
      "max_candidates_per_hull": 100,
      "top_n_eft_fetch": 25
    }
  }
}
```

### Configuration Validation

| Rule | Behavior on Violation |
|------|----------------------|
| `enabled_sources` contains unknown source name | `WARNING` logged, unknown source skipped |
| `eve_workbench` in `enabled_sources` but `eve_workbench.enabled` is `false` | Source skipped with `INFO` log |
| `min_votes` < 0 | Clamped to 0, `WARNING` logged |
| `top_n_eft_fetch` < 1 | Clamped to 1, `WARNING` logged |
| `top_n_eft_fetch` > 50 | Clamped to 50, `WARNING` logged |
| `cache_ttl_hours` < 1 | Clamped to 1, `WARNING` logged |
| `fit_sources` section missing entirely | Defaults applied: `enabled_sources: ["archetype"]`, Workbench disabled |
| `authenticated: true` but credentials file missing | Source marked unavailable with `ERROR`: `"credentials file not found"` |
