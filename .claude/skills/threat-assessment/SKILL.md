---
name: threat-assessment
description: ARIA security and threat analysis for Eve Online. Use for system safety evaluation, activity risk assessment, or travel route analysis.
model: haiku
category: tactical
triggers:
  - "/threat-assessment"
  - "threat assessment"
  - "is [system] safe"
  - "security analysis"
  - "can I go to [location]"
  - "what are the risks of [activity]"
requires_pilot: true
data_sources:
  - userdata/pilots/{active_pilot}/profile.md
---

# ARIA Threat Assessment Module

## Purpose
Provide security analysis for systems, activities, and travel routes with emphasis on capsuleer safety.

## Trigger Phrases
- "threat assessment"
- "is [system] safe"
- "security analysis"
- "can I go to [location]"
- "what are the risks of [activity]"

## Default Behavior

When no system is specified, queries default to the pilot's current region:
1. ESI location if available (requires `esi-location.read_location.v1` scope)
2. Profile home region as fallback (from `operations.md`)

## Live Activity Intel

**CRITICAL:** For specific system assessments, ARIA should query live activity data to enhance threat analysis.

### Data Sources (Fallback Chain)

Activity data can be obtained from multiple sources. Use in order of preference:

#### 1. MCP Tools (preferred if available)

If the `aria-universe` MCP server is connected, use the `universe` dispatcher:

```
universe(action="activity", systems=["Simela"], include_realtime=True)
```

**Response includes:** system name, security status, ship/pod/NPC kills, jumps, activity level.

**Advantages:** Sub-millisecond response, security status included, batch queries supported.

#### 2. CLI Commands (fallback)

If MCP tools are not available, use the `aria-esi` CLI:

```bash
uv run aria-esi activity <system>
```

#### 3. How to Check MCP Availability

If `universe` appears in your available tools, MCP is connected. Otherwise, fall back to CLI.

### Activity Data Fields

All sources return:
- **Ship kills** - Player ship losses in last hour
- **Pod kills** - Capsule losses in last hour
- **NPC kills** - NPC ship destructions (indicates ratting/missions)
- **Jumps** - Total ship traffic through system
- **Security** - System security status (MCP/CLI include this)

### Interpreting Activity Data

| PvP Kills (last hour) | Traffic | Interpretation |
|----------------------|---------|----------------|
| 0 | <50 | Quiet system - minimal activity |
| 0 | 50-200 | Low traffic, safe passage likely |
| 0 | 200+ | High traffic but no PvP - trade route |
| 1-5 | Any | Some PvP activity - stay alert |
| 5-20 | Any | Active PvP - gate camps possible |
| 20+ | Any | **Active combat zone** - avoid or prepare |
| 50+ | Any | **Major engagement** - fleet fight in progress |

### Enhanced Response Format

When live activity data is available, include it in the assessment:

```
═══════════════════════════════════════════
ARIA THREAT ASSESSMENT
───────────────────────────────────────────
SUBJECT: Tama (0.3)
THREAT LEVEL: HIGH
───────────────────────────────────────────
LIVE INTEL (last hour):
  Ship kills: 47
  Pod kills: 12
  Jumps: 892

ASSESSMENT: Active PvP zone - gate camps likely
───────────────────────────────────────────
ANALYSIS:
• Low-sec system - no CONCORD protection
• Elevated PvP activity indicates active hunters
• High traffic suggests bottleneck system
...
═══════════════════════════════════════════
```

### Response Format with Real-Time Data

When the RedisQ poller is active and `include_realtime=True` returns real-time data, enhance the response with gatecamp alerts and recent kill information.

**Gatecamp Alert Block (when `realtime.gatecamp` is present):**

```
⚠️ ACTIVE GATECAMP DETECTED (HIGH confidence)
  5 kills in 10 minutes
  Attackers: CODE. (Tornado, Thrasher)
───────────────────────────────────────────
```

**Real-Time Intel Section:**

```
REAL-TIME INTEL (10 min / 1 hour):
  Ship kills:  3 / 47
  Pod kills:   2 / 12

RECENT KILLS:
  2 min ago  Procurer    (CODE.)
  5 min ago  Retriever   (CODE.)
  8 min ago  Capsule     (CODE.)
```

**Response with Real-Time Data:**

```
═══════════════════════════════════════════
ARIA THREAT ASSESSMENT
───────────────────────────────────────────
SUBJECT: Niarja (0.5)
THREAT LEVEL: CRITICAL
───────────────────────────────────────────
⚠️ ACTIVE GATECAMP DETECTED (HIGH confidence)
  5 kills in 10 minutes
  Attackers: CODE. (Tornado, Thrasher)
───────────────────────────────────────────
REAL-TIME INTEL (10 min / 1 hour):
  Ship kills:  5 / 47
  Pod kills:   3 / 12
  Jumps: 890

RECENT KILLS:
  2 min ago  Procurer    (CODE.)
  5 min ago  Retriever   (CODE.)
  8 min ago  Capsule     (CODE.)
───────────────────────────────────────────
ANALYSIS:
• Active gatecamp with alpha-strike gankers
• High traffic indicates chokepoint system
• CODE. operating with Tornado fleet
...
═══════════════════════════════════════════
```

**Degraded Mode (when `realtime_healthy: false`):**

When the RedisQ poller is not running or data is stale, the system falls back to hourly ESI data silently. If `realtime_healthy` is explicitly false in the response, add a note:

```
Note: Real-time intel unavailable. Data shows hourly aggregates only.
```

### Watched Entity Activity Integration

When entity watchlists are configured (via `/watchlist`), threat assessments should include activity involving watched entities. Query watched entity kills using:

```bash
uv run aria-esi redisq-watched --minutes 60
```

**Watched Entity Activity Block (when matches found):**

```
WATCHED ENTITY ACTIVITY (last hour):
  3 kills involving watched entities
  - CODE. (attacker) - 2 kills in Uedama
  - Enemy Alliance (victim) - 1 kill in Tama
```

**Response with Watched Entity Data:**

```
═══════════════════════════════════════════
ARIA THREAT ASSESSMENT
───────────────────────────────────────────
SUBJECT: Uedama (0.5)
THREAT LEVEL: HIGH
───────────────────────────────────────────
⚠️ WATCHED ENTITY ACTIVITY DETECTED
  CODE. active in system (2 kills as attacker)
───────────────────────────────────────────
REAL-TIME INTEL (10 min / 1 hour):
  Ship kills:  5 / 47
  Pod kills:   3 / 12
  Jumps: 890

RECENT KILLS:
  2 min ago  Procurer    (CODE.) ⚠️ WATCHLIST
  5 min ago  Retriever   (CODE.) ⚠️ WATCHLIST
  8 min ago  Capsule     (CODE.)
───────────────────────────────────────────
ANALYSIS:
• Watched entity CODE. is actively hunting
• Consider avoiding or using scout
...
═══════════════════════════════════════════
```

**When to Show Watched Entity Data:**

1. Always check for watched entity activity when assessing specific systems
2. Flag kills where watched entities appear as attacker OR victim
3. Highlight the warning prominently if watched entities are active in the target system

### When to Query Activity Data

1. **System-specific assessments** - Always query when evaluating a specific system
2. **Route planning** - Query key waypoint systems (low-sec entries, choke points)
3. **On request** - When capsuleer asks "is X safe right now"

### Activity Data Limitations

- **Hourly baseline** - ESI data represents the last hour only
- **Volatile** - Conditions can change rapidly; include timestamp
- **Real-time when available** - With RedisQ poller active, 10-minute kill data and gatecamp detection are available
- **Graceful degradation** - If real-time unavailable, falls back to hourly data silently

## Response Format

```
═══════════════════════════════════════════
ARIA THREAT ASSESSMENT
───────────────────────────────────────────
SUBJECT: [System/Activity/Route]
THREAT LEVEL: [MINIMAL/ELEVATED/HIGH/CRITICAL]
───────────────────────────────────────────
ANALYSIS:
[Detailed breakdown of risks]

RISK FACTORS:
• [Specific threats]

MITIGATION RECOMMENDATIONS:
• [Actionable safety measures]

ADVISORY:
[Final recommendation]
═══════════════════════════════════════════
```

## Security Status Reference

| Sec Status | CONCORD Response | PvP Risk | Notes |
|------------|------------------|----------|-------|
| 1.0 | Instant | Minimal | Gate guns, CONCORD |
| 0.9-0.8 | Fast | Low | Some belt rats |
| 0.7-0.6 | Moderate | Low | More hostiles |
| 0.5 | Slower | Moderate | Suicide ganking viable |
| 0.4-0.1 | None | HIGH | Low-sec, gate guns only |
| 0.0 | None | CRITICAL | Null-sec, no protection |
| Negative | None | CRITICAL | Wormhole space |

## Sovereignty-Aware Threat Assessment (Null-Sec)

When assessing null-sec systems (security <= 0.0), include sovereignty data for enhanced context.

### Data Authority

Sovereignty data follows the authority hierarchy defined in `docs/DATA_AUTHORITY.md`:

| Data Type | Source | Authority |
|-----------|--------|-----------|
| Alliance ID/Name | ESI `/sovereignty/map/` | Authoritative |
| Coalition membership | `coalitions.yaml` | Community (validated against ESI) |

**Note:** Coalition characteristics (response times, fleet compositions) are community knowledge based on historical patterns. These may change as player organizations evolve.

### Getting Sovereignty Data

```
universe(action="systems", systems=["1DQ1-A"])
```

The response includes a `sovereignty` field for null-sec systems:
```json
{
  "sovereignty": {
    "alliance_id": 1354830081,
    "alliance_name": "[GSF] Goonswarm Federation",
    "coalition_id": "imperium",
    "coalition_name": "The Imperium"
  }
}
```

### Sovereignty Threat Factors

| Factor | Threat Implication |
|--------|-------------------|
| Major Coalition (Imperium, PanFam, FIRE) | Standing fleets, rapid intel response, organized defense |
| Mid-tier Alliance | Moderate response capability, check activity data |
| Small Alliance / Renter Space | Softer targets, less organized defense |
| NPC Null-sec | No player sovereignty, NPC pirates present |
| Unclaimed Space | Contested, potentially active combat zone |

### Coalition Response Characteristics

| Coalition | Typical Response |
|-----------|------------------|
| Imperium | Standing fleets, organized caps, rapid comms |
| PanFam | Blops/caps, coordinated response, intel channels |
| FIRE | Regional defense, varied response times |

### Sovereignty Block Format

Include in threat assessment when in null-sec:

```
───────────────────────────────────────────
SOVEREIGNTY: [GSF] Goonswarm Federation
  Coalition: The Imperium
  Response Risk: HIGH - organized standing fleets
───────────────────────────────────────────
```

### Activity Defense Multiplier (ADM) Context

High NPC kills and ship jumps in a system suggest:
- Active ratting/mining operations
- Higher ADM (harder to entosis)
- Likely inhabitants who will respond to threats

## Threat Level Definitions

**MINIMAL:** Standard high-sec operations, normal NPC threats only
**ELEVATED:** Low-sec adjacent, 0.5 systems, or valuable cargo
**HIGH:** Low-sec operations, known hostile activity, PvP likely
**CRITICAL:** Null-sec, wormholes, or confirmed hostile presence

## Common Threats for Self-Sufficient Pilots

### Mining (Venture)
- Belt rats (NPCs) - manageable
- Suicide gankers in 0.5 - use +2 warp strength
- Ninja looters - annoying but harmless

### Mission Running
- Mission pocket hazards - triggers, EWAR
- Failed missions - standing loss
- Storyline mission difficulty spikes

### Exploration
- Hostile site variants (Ghost/Sleeper)
- Wormhole connections - check before entering
- Competition for sites - scan quickly

## Safety Protocols for Venture Operations
1. Fit for align speed and warp stability
2. Monitor D-Scan every 5-10 seconds in <0.8
3. Never AFK mine below 0.9
4. Bookmark safe spots in regular systems
5. Update clone before risky operations

## Behavior
- Always err on the side of caution
- Express genuine concern for capsuleer safety (in character)
- Provide specific, actionable recommendations
- Remind about clone status for high-risk activities
- The capsuleer's life is more valuable than any cargo
- **Intelligence Framing:** Follow the Intelligence Sourcing Protocol in CLAUDE.md - present threat data as live security feeds from faction-appropriate agencies (RSS, FIO, etc.) and CONCORD/DED, never as archival records.
- **Brevity:** Threat level + key risks + top mitigation. Expand on request.

## Experience-Based Adaptation

Check the active pilot's profile for **EVE Experience** level and adapt explanations.

**Pilot Resolution:** Read `userdata/config.json` for `active_pilot` ID, then `userdata/pilots/_registry.json` to get the `directory` field. Single-pilot shortcut: if config missing, use the sole pilot from registry.

**Profile Location:** `userdata/pilots/{active_pilot}/profile.md` (where `{active_pilot}` is the resolved directory)

### Security Status Explanation

**new:**
```
SECURITY: 0.5 (Borderline Dangerous)
This is the lowest "high-security" rating. CONCORD police still respond
to attacks, but slowly - giving pirates 15-20 seconds to destroy you
before help arrives. "Suicide ganking" (where attackers accept ship loss
to kill you) becomes profitable here. Recommendation: Use a tankier ship
or route through 0.6+ systems.
```

**intermediate:**
```
SECURITY: 0.5 | CONCORD Response: Delayed (~15s)
Suicide ganking viable. Stay aligned while stationary. Consider
anti-gank fit if carrying valuable cargo.
```

**veteran:**
```
SECURITY: 0.5 | CONCORD 15s | gank threshold
```

### Risk Factor Explanation

**new:**
- Explain what each risk means and how to counter it
- Define terms like "EWAR", "neut pressure", "tackle"
- Suggest specific modules to fit for defense

**veteran:**
- List risks tersely: "neuts, damps, webs"
- Assume player knows countermeasures

## Contextual Suggestions

After providing threat assessment, suggest ONE related command when contextually relevant:

| Context | Suggest |
|---------|---------|
| Assessment for mission area | "Run `/mission-brief` for enemy intel" |
| Capsuleer planning to mine | "My `/mining-advisory` can help with belt selection" |
| Capsuleer needs survival fit | "Try `/fitting` for a tank-focused build" |
| Assessment involves exploration | "Use `/exploration` when you find sites" |

Don't add suggestions to every assessment - only when clearly helpful.

---

## Persona Adaptation

This skill supports persona-specific overlays. When active persona has an overlay file, load additional context from:

```
personas/{active_persona}/skill-overlays/threat-assessment.md
```

If no overlay exists, use the default (empire) framing above.
