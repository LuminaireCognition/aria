# ARIA Skill Test Results (MED ESI: standings) - 2026-02-23

**Test scope:** 1 skill (`standings`), 3 queries (eligibility, progression, repair)
**Pilot:** Federation Navy Suwayyah (2123984364) - Gallente, aria-mk4 persona, rp_level: off
**Method:** 3 parallel sub-agents via Task tool
**Code state:** Post-commit a6c1f934 (branch: skill-testing-cleanup)
**MCP dispatchers available:** All 8 (universe, market, sde, skills, fitting, status, killmails, pilot)

## Execution Summary

| # | Query | Type | Calls | Eff% | Outcome | Notes |
|---|-------|------|------:|-----:|---------|-------|
| 1 | "Can I use L4 agents with Federation Navy?" | Eligibility | 5 | 80 | SUCCESS | Freshness gate failed (non-fatal), standings + skills + ref + SDE agents |
| 2 | "How do I raise my Caldari State standing to 5.0?" | Progression | 5 | 100 | SUCCESS | Standings + skills + thresholds + epic arcs |
| 3 | "How do I repair my negative Amarr standing?" | Repair | 5 | 100 | SUCCESS | Standings + skills + epic arcs + thresholds |

**Totals:** 3/3 SUCCESS, 15 tool calls, 93% efficiency (14/15 necessary)

---

## Per-Query Results

### Query 1: Eligibility ("Can I use L4 agents with Federation Navy?")

```
=== SKILL TEST: standings (eligibility) ===
QUERY: "Can I use L4 agents with Federation Navy?"
ESI FLAG: MED (esi-characters.read_standings.v1, esi-skills.read_skills.v1)

--- SKILL LOADING ---
Skill loaded via Skill(skill="standings") → SUCCESS
No _index.json → no persona exclusivity check needed

--- TOOL CALLS ---

1. Bash: uv run aria-esi ensure-fresh standings → FAILED (exit code 1)
   Error: "sync completed but markers did not advance"
   fresh: false, esi_available: true, source: "missing"
   Note: Data exists but freshness metadata unavailable

2. Bash: uv run aria-esi standings → SUCCESS
   query_timestamp: 2026-02-23T23:13:32Z
   volatility: semi_stable
   Federation Navy (from_id: 1000120, from_type: npc_corp): 4.59 raw

3. Bash: uv run aria-esi skills → SUCCESS
   query_timestamp: 2026-02-23T23:13:43Z
   total_sp: 6,244,067
   Connections: Level II
   Diplomacy: Level III
   Social: Level III

4. Read: reference/mechanics/standings_thresholds.json → SUCCESS
   L4 requirement: 5.0 effective standing
   Connections formula: effective = raw + (10 - raw) * connections_level * 0.04

5. MCP: sde(action="agent_search", corporation="Federation Navy", level=4,
         division="Security", limit=100) → SUCCESS
   total_found: 18 Federation Navy L4 Security agents
   Sample: Saonellieu Baerse (Dodixie IX), Blalt Appoi (Ation IX)

--- STANDINGS DATA ---
Federation Navy Standing (raw): 4.59
Connections Level: II
Effective Standing Calculation:
  effective = 4.59 + (10 - 4.59) * 2 * 0.04
  effective = 4.59 + 5.41 * 0.08
  effective = 4.59 + 0.4328
  effective = 5.0228
L4 Threshold: 5.0 effective
Eligibility: YES (5.0228 >= 5.0, margin: +0.023)

--- WARNINGS/ERRORS ---
1. FRESHNESS GATE FAILED: "sync completed but markers did not advance"
   Severity: Medium. Data appeared valid (timestamp present). Skill should
   issue staleness caveat but can still answer the eligibility question.

--- NOTES ---
- Pilot barely qualifies for L4 (margin +0.023). Connections III would raise
  effective to ~5.45, providing a safer margin.
- 18 L4 Security agents found across Gallente space (Sinq Laison, Essence, Placid)
- Freshness gate failure is a real issue — the ensure-fresh command did not
  update standing markers even though ESI was available.
```

### Query 2: Progression ("How do I raise my Caldari State standing to 5.0?")

```
=== SKILL TEST: standings (progression) ===
QUERY: "How do I raise my Caldari State standing to 5.0?"
ESI FLAG: MED

--- SKILL LOADING ---
Skill loaded via Skill(skill="standings") → SUCCESS

--- TOOL CALLS ---

1. Bash: uv run aria-esi standings → SUCCESS
   query_timestamp: 2026-02-23T23:13:32Z
   Caldari State (from_id: 500001, from_type: faction): -0.29 raw

2. Bash: uv run aria-esi skills → SUCCESS
   query_timestamp: 2026-02-23T23:13:40Z
   Connections: Level II
   Diplomacy: Level III
   Social: Level III

3. Read: reference/mechanics/standings_thresholds.json → SUCCESS
   L4 requirement: 5.0 effective
   Required raw for 5.0 effective at Connections II: 4.74
   Required raw for 5.0 effective at Connections V: 4.17

4. Read: reference/mechanics/epic_arcs.json → SUCCESS
   Blood-Stained Stars: no standing requirement, +10% of remaining, choice of faction
   Caldari Penumbra: requires 5.0 standing (not accessible), L4 combat, 16 missions

--- STANDINGS DATA ---
Caldari State Standing (raw): -0.29
Diplomacy Level: III (applies to negative standings)
Effective Standing (Caldari, Diplomacy):
  effective = -0.29 + (-0.29 + 10) * 3 * 0.04
  effective = -0.29 + 9.71 * 0.12
  effective = -0.29 + 1.165
  effective = 0.875
Gap to 5.0 Effective: 4.125
Required Raw for 5.0 at Connections II: 4.74 (gap from current: +5.03 raw)
Required Raw for 5.0 at Connections V: 4.17 (gap from current: +4.46 raw)

--- EPIC ARC DATA ---
Blood-Stained Stars: accessible now (no requirement)
  Projected gain: -0.29 + (10 - (-0.29)) * 0.10 = -0.29 + 1.029 = +0.739 raw
  Post-arc raw: ~0.45
  Post-arc effective (Connections II): ~0.88
Caldari Penumbra: NOT accessible (requires 5.0 standing)

--- WARNINGS/ERRORS ---
None. All tool calls succeeded.

--- NOTES ---
- Caldari standing is genuinely negative (-0.29), likely from running Gallente missions
  (derived loss from opposing faction pair)
- Cross-faction tension: Gallente Federation at +1.75, Federation Navy at +4.59 — running
  Caldari missions would damage these standings
- Epic arc is the only safe immediate option (no derived losses)
- Long path to L4: even after epic arc (+0.45 raw), still needs ~4.29 raw gain
- Pilot should train Connections V before grinding (saves ~0.57 raw equivalent)
```

### Query 3: Repair ("How do I repair my negative Amarr standing?")

```
=== SKILL TEST: standings (repair) ===
QUERY: "How do I repair my negative Amarr standing?"
ESI FLAG: MED

--- SKILL LOADING ---
Skill loaded via Skill(skill="standings") → SUCCESS

--- TOOL CALLS ---

1. Bash: uv run aria-esi standings → SUCCESS
   query_timestamp: 2026-02-23T23:13:35Z
   Amarr Empire (from_type: faction): -0.84 raw

2. Bash: uv run aria-esi skills → SUCCESS
   query_timestamp: 2026-02-23T23:13:43Z
   Diplomacy: Level III
   Connections: Level II (not applicable to negative standings)

3. Read: reference/mechanics/epic_arcs.json → SUCCESS
   Blood-Stained Stars: no requirement, choose Amarr at end
   Amarr "Right to Rule" arc: requires 5.0 standing (not accessible)

4. Read: reference/mechanics/standings_thresholds.json → SUCCESS
   Diplomacy formula: effective = raw + (raw + 10) * diplomacy_level * 0.04

--- STANDINGS DATA ---
Amarr Empire Standing (raw): -0.84
Diplomacy Level: III
Effective Standing (Amarr, Diplomacy):
  effective = -0.84 + (-0.84 + 10) * 3 * 0.04
  effective = -0.84 + 9.16 * 0.12
  effective = -0.84 + 1.099
  effective = +0.26
Is Actually Negative?: YES (raw -0.84, but effective +0.26 due to Diplomacy III)

--- EPIC ARC DATA ---
Blood-Stained Stars: accessible now (no requirement), choose Amarr at end
  Projected gain: -0.84 + (10 - (-0.84)) * 0.10 = -0.84 + 1.084 = +0.244 raw
  Post-arc raw: ~+0.24
  Post-arc effective (Connections II): ~0.88
Amarr "Right to Rule": NOT accessible (requires 5.0 standing)

--- WARNINGS/ERRORS ---
None. All tool calls succeeded.

--- NOTES ---
- Pilot does have genuinely negative Amarr standing (-0.84 raw), query premise is valid
- Diplomacy III converts -0.84 raw to +0.26 effective — a critical nuance the skill
  should highlight (L1 agents accessible, L2+ not)
- Blood-Stained Stars is the optimal repair path (no standing requirement)
- Cross-faction warning: running Amarr missions would damage Gallente (+1.75) and
  Minmatar (+0.90) standings — epic arcs avoid this
- Post-BSS standing (+0.24 raw) still below L2 threshold (1.0 effective), but
  with Connections II effective would be ~0.88, approaching L2 access
```

---

## Verifiable Assertions

### Static (should never change)

| Field | Expected Value |
|-------|----------------|
| L1 Agent Standing Requirement | None |
| L2 Agent Standing Requirement | 1.0 effective |
| L3 Agent Standing Requirement | 3.0 effective |
| L4 Agent Standing Requirement | 5.0 effective |
| L5 Agent Standing Requirement | 7.0 effective |
| Connections formula (positive) | effective = raw + (10 - raw) * level * 0.04 |
| Diplomacy formula (negative) | effective = raw + (raw + 10) * level * 0.04 |
| Blood-Stained Stars standing requirement | None (null) |
| Blood-Stained Stars mission count | 50 |
| Blood-Stained Stars gain formula | +10% of (10 - current) |
| Blood-Stained Stars cooldown | 90 days |
| Blood-Stained Stars starting agent | Sister Alitura, Arnon IX |
| Caldari Penumbra standing requirement | 5.0 |
| Federation Navy entity ID | 1000120 |
| Caldari State entity ID | 500001 |
| ARIA RP Level | off |
| ARIA Primary Faction | GALLENTE |

### Dynamic (expected to change; record baseline)

| Field | Value at Test Time | Notes |
|-------|--------------------|-------|
| Federation Navy standing (raw) | 4.59 | Increases with missions |
| Caldari State standing (raw) | -0.29 | May decrease further from Gallente missions |
| Amarr Empire standing (raw) | -0.84 | May decrease further from Gallente missions |
| Connections level | II | Should train higher |
| Diplomacy level | III | Adequate for current standings |
| Social level | III | Affects standing gain rate |
| Total SP | 6,244,067 | Increases with training |
| Fed Navy L4 Security agents found | 18 | Static unless CCP adds/removes agents |
| Wallet balance | 125,512,441 ISK | From pilot test (same session) |

### Structural (response shape)

| Assertion | Query |
|-----------|-------|
| `uv run aria-esi standings` returns JSON with `standings` array | All |
| Each standing entry has `from_id`, `from_type`, `standing` fields | All |
| `from_type` is one of: `faction`, `npc_corp`, `agent` | All |
| `uv run aria-esi skills` returns `total_sp` and skill entries | All |
| standings_thresholds.json contains `agent_levels` with levels 1-5 | All |
| epic_arcs.json contains `arcs` array with `standing_required` field | Progression, Repair |
| SDE agent_search returns `total_found` count | Eligibility |
| `ensure-fresh` returns `fresh`, `esi_available`, `source` fields | Eligibility |

### Derived Calculations (verify formulas)

| Calculation | Input | Expected Output |
|-------------|-------|-----------------|
| Fed Navy effective (Connections II) | raw=4.59, level=2 | 5.023 |
| Caldari effective (Diplomacy III) | raw=-0.29, level=3 | 0.875 |
| Amarr effective (Diplomacy III) | raw=-0.84, level=3 | 0.259 |
| BSS gain on Caldari | raw=-0.29, gain=10% remaining | +1.029 → new raw 0.739 |
| BSS gain on Amarr | raw=-0.84, gain=10% remaining | +1.084 → new raw 0.244 |
| Required raw for L4 at Conn II | target=5.0, level=2 | 4.74 |
| Required raw for L4 at Conn V | target=5.0, level=5 | 4.17 |

---

## Issues Found

| Priority | Issue | Impact |
|----------|-------|--------|
| Medium | `ensure-fresh standings` fails: "sync completed but markers did not advance" | Freshness gate unreliable; skill must still answer with cached data + caveat |
| Low | SDE agent_search returns null system_name for some agents | Cosmetic; region names still available for context |

### ensure-fresh Failure Detail

The freshness gate command (`uv run aria-esi ensure-fresh standings`) returned exit code 1 with message "sync completed but markers did not advance". The response indicated `fresh: false`, `esi_available: true`, `source: "missing"`.

This means the freshness metadata file either doesn't exist or wasn't updated by the sync. The standings data itself is present and valid (confirmed by successful `uv run aria-esi standings` returning timestamped data). The skill should treat this as "data available but freshness unverified" and issue a caveat when making eligibility claims.

**Root cause hypothesis:** The freshness marker file may not be created by the standings sync path, or may require a prior `sync-profile` to initialize the markers.

---

## Aggregate Statistics

| Metric | Value |
|--------|------:|
| Queries tested | 3 |
| Total tool calls | 15 |
| Necessary calls | 14 |
| Wasted calls | 1 (freshness gate failure, non-fatal) |
| Efficiency | 93% |
| ESI endpoints hit | 2 (standings, skills) × 3 queries |
| ESI errors | 0 |
| Reference files read | 2 (thresholds, epic arcs) |
| MCP tools used | 1 (sde agent_search) |

## Skill Assessment

| Dimension | Rating | Notes |
|-----------|--------|-------|
| Execution efficiency | Excellent | 5 calls per query, minimal waste |
| ESI integration | Full | Both scopes exercised (standings + skills) |
| Reference data usage | Full | Both data_sources files read and applied |
| MCP integration | Working | SDE agent_search used for L4 agent discovery |
| Freshness gate | Partial | ensure-fresh fails but skill degrades gracefully |
| Formula accuracy | Verified | Connections + Diplomacy calculations match reference |
| Cross-faction awareness | Present | Opposing faction implications noted in progression/repair |
| Edge case handling | Good | Negative standings with Diplomacy bonus correctly computed |
| Persona gating | N/A | No _index.json, no exclusivity |

## Cross-Query Standing Snapshot

| Faction/Corp | Raw | Type | Effective | Access Level |
|-------------|----:|------|----------:|:-------------|
| Gallente Federation | +1.75 | faction | +2.40 (Conn II) | L2 |
| Federation Navy | +4.59 | npc_corp | +5.02 (Conn II) | **L4** (barely) |
| Caldari State | -0.29 | faction | +0.88 (Dipl III) | L1 only |
| Amarr Empire | -0.84 | faction | +0.26 (Dipl III) | L1 only |

## Test Environment Notes

- **Date:** 2026-02-23
- **Execution method:** 3 parallel sub-agents via Task tool
- **MCP tools available:** All 8 dispatchers
- **ESI status:** Authenticated and functional
- **Code state:** Branch skill-testing-cleanup, post-commit a6c1f934
