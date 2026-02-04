---
name: industry-jobs
description: Monitor personal manufacturing, research, copying, and invention jobs. View active jobs, completion times, and recent history.
model: haiku
category: industry
triggers:
  - "/industry-jobs"
  - "my industry jobs"
  - "manufacturing jobs"
  - "what's being built"
  - "check my jobs"
  - "industry status"
requires_pilot: true
esi_scopes:
  - esi-industry.read_character_jobs.v1
---

# ARIA Industry Jobs Monitor

## Purpose
Query the capsuleer's personal industry jobs to display active manufacturing runs, research in progress, copying jobs, and invention attempts. Essential for self-sufficient pilots who manufacture their own equipment.

## CRITICAL: Read-Only Limitation

**ESI industry endpoints are READ-ONLY.** ARIA can:
- View job status, progress, and completion times
- List active, completed, and historical jobs
- Show facility locations and costs

**ARIA CANNOT:**
- Deliver completed jobs
- Start new manufacturing/research jobs
- Cancel or modify existing jobs
- Interact with the EVE client in any way

**Always clarify this when showing job status.** If jobs are ready for delivery or user asks to start jobs, explicitly state this requires in-game action and provide the steps (Industry window, Alt+S, etc.).

## CRITICAL: Data Volatility

Industry job data is **semi-stable** - jobs progress on fixed timers:

1. **Display query timestamp** - jobs complete at specific times
2. **Jobs have fixed completion times** - unlike skills, progress is deterministic
3. **Can cache results** - job data doesn't change mid-run
4. **Check "ready for delivery"** - completed jobs need manual delivery

## Trigger Phrases

- `/industry-jobs`
- "my industry jobs"
- "manufacturing jobs"
- "what's being built"
- "check my jobs"
- "industry status"
- "research progress"
- "when will my job finish"
- "am I building anything"
- "manufacturing status"

## ESI Requirement

**Requires:** `esi-industry.read_character_jobs.v1` scope

This scope is included in ARIA's default scope set and should already be authorized.

If scope is not authorized:
```
Industry job access requires ESI authentication with industry jobs scope.

To enable: uv run python .claude/scripts/aria-oauth-setup.py
Select "esi-industry.read_character_jobs.v1" during scope selection.
```

## ESI Availability Check (CRITICAL)

**BEFORE making any ESI queries**, check the session hook output for ESI status:

```json
"esi": {"status": "UNAVAILABLE"}
```

### If ESI is UNAVAILABLE:

1. **DO NOT** run `uv run aria-esi` commands - they will timeout
2. **RESPOND IMMEDIATELY** with:
   ```
   Industry job monitoring requires live ESI data which is currently unavailable.

   Check this in-game:
   • Industry window (Alt+S) → Jobs tab
   • Shows active manufacturing, research, and invention jobs

   ESI usually recovers automatically.
   ```
3. **DO NOT** block waiting for ESI

### If ESI is AVAILABLE:

Proceed with normal industry job queries.

## Implementation

Run the ESI wrapper command:
```bash
uv run aria-esi industry-jobs [options]
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--active` | Show only active jobs | (default behavior) |
| `--completed` | Show only completed jobs awaiting delivery | - |
| `--history` | Include recently finished jobs (last 7 days) | - |
| `--all` | Show all jobs (active + completed + history) | - |

### JSON Response Structure

```json
{
  "query_timestamp": "2026-01-15T14:30:00Z",
  "volatility": "semi_stable",
  "character_id": 2119654321,
  "summary": {
    "active_jobs": 2,
    "completed_awaiting_delivery": 1,
    "manufacturing": 1,
    "research_me": 1,
    "research_te": 0,
    "copying": 1,
    "invention": 0
  },
  "jobs": [
    {
      "job_id": 123456789,
      "activity": "manufacturing",
      "activity_id": 1,
      "activity_display": "Manufacturing",
      "blueprint_name": "Hammerhead I Blueprint",
      "product_name": "Hammerhead I",
      "runs": 10,
      "status": "active",
      "installer_name": "Federation Navy Suwayyah",
      "facility_name": "Sortet V - X-Sense Chemical Refinery",
      "start_date": "2026-01-15T10:00:00Z",
      "end_date": "2026-01-15T18:30:00Z",
      "time_remaining": "4h 0m",
      "progress_percent": 52.5,
      "cost": 15000.00,
      "licensed_runs": null,
      "probability": null
    },
    {
      "job_id": 123456790,
      "activity": "research_me",
      "activity_id": 4,
      "activity_display": "ME Research",
      "blueprint_name": "Hobgoblin I Blueprint",
      "product_name": null,
      "runs": 1,
      "status": "ready",
      "installer_name": "Federation Navy Suwayyah",
      "facility_name": "Sortet V - X-Sense Chemical Refinery",
      "start_date": "2026-01-14T08:00:00Z",
      "end_date": "2026-01-15T12:00:00Z",
      "time_remaining": "0m",
      "progress_percent": 100.0,
      "cost": 5000.00,
      "licensed_runs": null,
      "probability": null
    }
  ]
}
```

### Empty Jobs Response

```json
{
  "query_timestamp": "2026-01-15T14:30:00Z",
  "volatility": "semi_stable",
  "character_id": 2119654321,
  "summary": {
    "active_jobs": 0,
    "completed_awaiting_delivery": 0
  },
  "jobs": [],
  "message": "No industry jobs found"
}
```

## Activity Types

| ID | Activity | Display | Description |
|----|----------|---------|-------------|
| 1 | manufacturing | Manufacturing | Producing items from blueprints |
| 3 | research_te | TE Research | Researching time efficiency |
| 4 | research_me | ME Research | Researching material efficiency |
| 5 | copying | Copying | Creating blueprint copies |
| 7 | reverse_engineering | Reverse Eng | T3 reverse engineering |
| 8 | invention | Invention | T2/T3 invention attempts |
| 9 | reactions | Reactions | Moon material reactions |

## Response Formats

### Standard Display (rp_level: off or lite)

```markdown
## Industry Jobs
*Query: 14:30 UTC*

### Active Jobs (2)
| Job | Blueprint | Runs | Completes | Progress |
|-----|-----------|------|-----------|----------|
| Manufacturing | Hammerhead I | 10 | 18:30 UTC | 52% |
| ME Research | Hobgoblin I BP | 1 | Complete | 100% |

### Ready for Delivery (1)
- **ME Research** - Hobgoblin I Blueprint (completed 12:00 UTC)

**In-Game Action Required:** Open Industry window (Alt+S) → Jobs tab → Deliver

*ARIA monitors job status but cannot interact with the EVE client.*
```

### Formatted Version (rp_level: moderate or full)

```
═══════════════════════════════════════════════════════════════════
ARIA INDUSTRY MONITOR
───────────────────────────────────────────────────────────────────
GalNet Sync: 14:30 UTC
───────────────────────────────────────────────────────────────────
ACTIVE JOBS: 2
───────────────────────────────────────────────────────────────────
  [Manufacturing] Hammerhead I x 10
  Location:   Sortet V - X-Sense Chemical Refinery
  Started:    10:00 UTC
  Completes:  18:30 UTC (4h 0m remaining)
  Progress:   52% [██████████░░░░░░░░░░]

  [ME Research] Hobgoblin I Blueprint (8% → 10%)
  Location:   Sortet V - X-Sense Chemical Refinery
  Status:     READY FOR DELIVERY
───────────────────────────────────────────────────────────────────
AWAITING DELIVERY: 1 job
───────────────────────────────────────────────────────────────────
  • Hobgoblin I Blueprint (ME Research) - completed 12:00 UTC
───────────────────────────────────────────────────────────────────
IN-GAME ACTION REQUIRED: Industry window (Alt+S) → Jobs → Deliver
ARIA monitors status only - cannot interact with EVE client.
═══════════════════════════════════════════════════════════════════
```

### No Jobs Display

```
═══════════════════════════════════════════════════════════════════
ARIA INDUSTRY MONITOR
───────────────────────────────────────────────────────────────────
GalNet Sync: 14:30 UTC
───────────────────────────────────────────────────────────────────
No industry jobs active.

Your manufacturing facilities are idle. Consider:
• Starting a manufacturing run with `/corp blueprints` to check available BPOs
• Researching a blueprint to improve ME/TE efficiency
═══════════════════════════════════════════════════════════════════
```

### Compact Format

For quick checks:
```
Industry (14:30 UTC): 2 active | 1 ready for delivery
  Manufacturing: Hammerhead I x10 (52%, 4h left)
  ME Research: Hobgoblin I BP (ready)
```

## Error Handling

### ESI Not Configured

```
═══════════════════════════════════════════════════════════════════
ARIA INDUSTRY MONITOR
───────────────────────────────────────────────────────────────────
Industry job monitoring requires ESI authentication.

ARIA works fully without ESI - you can track manufacturing
progress manually or tell me what you're building.

OPTIONAL: Enable live tracking (~5 min setup)
  → uv run python .claude/scripts/aria-oauth-setup.py
  → Select industry jobs scope during setup
═══════════════════════════════════════════════════════════════════
```

### Missing Scope

```
═══════════════════════════════════════════════════════════════════
ARIA INDUSTRY MONITOR - SCOPE NOT AUTHORIZED
───────────────────────────────────────────────────────────────────
ESI is configured but industry jobs scope is missing.

To enable industry monitoring:
  uv run python .claude/scripts/aria-oauth-setup.py

Select "esi-industry.read_character_jobs.v1" during scope selection.
═══════════════════════════════════════════════════════════════════
```

## Contextual Suggestions

After displaying industry jobs, suggest ONE related action when relevant:

| Context | Suggest |
|---------|---------|
| Jobs completed | "Deliver completed jobs in EVE to collect outputs" |
| Manufacturing in progress | "Check material prices with `/price <item>`" |
| No active jobs | "View available blueprints with `/esi-query blueprints`" |
| Research completing soon | "Consider queuing next research job" |

## Cross-References

| Related Command | Use Case |
|-----------------|----------|
| `/esi-query blueprints` | View owned blueprints with ME/TE levels |
| `/corp jobs` | Corporation industry jobs (if CEO/Director) |
| `/price` | Check market prices for outputs |
| `/wallet-journal` | Track industry costs and income |

## Self-Sufficiency Context

For pilots with `market_trading: false`:
- Emphasize manufacturing for personal use over profit margins
- Note which outputs are for self-use vs potential corp contributions
- Track material consumption for resource planning

## Behavior Notes

- **Brevity:** Default to compact table format unless RP mode requests formatted boxes
- **Precision:** Show progress to nearest percent for active jobs
- **Time Format:** Use "Xh Ym" for durations, full timestamps for completion
- **Ready Jobs:** Always highlight jobs awaiting delivery - pilot action needed
- **Sorting:** Active jobs first (by completion time), then ready-for-delivery
- **History:** Include completed jobs only when --history or --all flag used
