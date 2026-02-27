---
name: sec-status
description: Security status tracking for Eve Online. Monitor sec status, calculate tag costs, and track empire access restrictions.
model: haiku
category: identity
triggers:
  - "/sec-status"
  - "sec status"
  - "security status"
  - "can I go to high-sec"
  - "empire access"
  - "how much to fix sec"
  - "tag costs"
requires_pilot: true
esi_scopes:
  - esi-characters.read_standings.v1
data_sources:
  - userdata/pilots/{active_pilot}/profile.md
  - reference/mechanics/security_status.json
---

# Security Status Module

## Command Syntax

```
/sec-status                     # Current status and implications
/sec-status --tags              # Tag costs to reach thresholds
/sec-status --target <value>    # Cost to reach specific status
```

## ESI Failure Handling

If ESI is unavailable or the `esi-characters.read_standings.v1` scope is missing, ask the pilot for their current security status and note "Based on self-reported value" in the response.

## Execution Flow

1. **Get current sec status** from ESI (or ask pilot if unavailable).
2. **Read `reference/mechanics/security_status.json`** for threshold data, faction police response times, clone soldier tag values, tag farming locations, and sec loss values.
3. **Present empire access** based on current status against thresholds from reference file.
4. **If `--tags` or `--target`:** Fetch tag prices via `market(action="prices", items=["Clone Soldier Trainer", "Clone Soldier Recruiter", "Clone Soldier Transporter", "Clone Soldier Negotiator"])`. Compute ISK-per-sec-point for each tag type. Recommend cheapest tags first.

## Response Format

```
SECURITY STATUS REPORT
───────────────────────────────────────────────────────────────────
CURRENT STATUS: [value]
───────────────────────────────────────────────────────────────────
EMPIRE ACCESS:

  [For each threshold from reference file, show access status]

  Station Docking: [restriction status]

FACTION POLICE:
  [Response behavior from reference file]

TAG RECOVERY OPTIONS:
  To [threshold]: [N] tags (~[computed] ISK)
  [Additional thresholds as relevant]

  Clone Soldier tags available at CONCORD stations
  or from clone soldier NPCs in low-sec belts.
───────────────────────────────────────────────────────────────────
```

## Behavior Notes

- Present status objectively - no judgment on playstyle
- Low sec status is an operating cost, not a moral failing
- Provide practical workarounds for restricted access

## DO NOT

- **DO NOT** lecture about getting sec status back
- **DO NOT** suggest the pilot should "go legit"
- **DO NOT** moralize about criminal gameplay
- **DO NOT** forget that low-sec/null are always accessible
