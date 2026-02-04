---
name: skillqueue
description: Monitor EVE Online skill training queue and ETA. View current training progress and upcoming skills.
model: haiku
category: tactical
triggers:
  - "/skillqueue"
  - "skill queue"
  - "what am I training"
  - "training status"
  - "skill ETA"
  - "when will skills finish"
requires_pilot: true
esi_scopes:
  - esi-skills.read_skillqueue.v1
---

# ARIA Skill Queue Monitor

## Purpose
Query the capsuleer's skill training queue to display current training progress, upcoming skills, and queue completion estimates. This is **volatile data** - training progresses continuously.

## CRITICAL: Read-Only Limitation

**ESI skill endpoints are READ-ONLY.** ARIA can:
- View current training skill and progress
- List queued skills with completion times
- Show total SP and trained skill levels

**ARIA CANNOT:**
- Add or remove skills from the queue
- Pause or restart training
- Inject skill points or extractors
- Interact with the EVE client

**When queue is empty or training completes**, provide in-game steps: Character Sheet (Alt+A) → Skills → Add to queue.

## CRITICAL: Data Volatility

Skill queue data is **VOLATILE** - it changes continuously as skills train:

1. **Always display the query timestamp** prominently
2. **Include staleness warning** - skills train in real-time
3. **Never cache results** to files
4. **Never reference results in future turns** without re-querying

Skills can complete mid-conversation. Always re-query for current status.

## Trigger Phrases

- `/skillqueue`
- "what am I training"
- "skill queue"
- "training queue"
- "skill eta"
- "when will [skill] finish"
- "training status"
- "check my skills" (when context suggests queue, not list)
- "how long until skills done"

## ESI Requirement

**Requires:** `esi-skills.read_skillqueue.v1` scope

If scope is not authorized:
```
Skill queue access requires ESI authentication with skill queue scope.

To enable: uv run python .claude/scripts/aria-oauth-setup.py
Select "esi-skills.read_skillqueue.v1" during scope selection.
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
   Skill queue monitoring requires live ESI data which is currently unavailable.

   Check this in-game: Alt+A (Character Sheet) → Skills tab → Training Queue

   ESI usually recovers automatically.
   ```
3. **DO NOT** block waiting for ESI

### If ESI is AVAILABLE:

Proceed with normal skill queue queries.

## Implementation

Run the ESI wrapper command:
```bash
uv run aria-esi skillqueue
```

### JSON Response Structure

```json
{
  "query_timestamp": "2026-01-15T14:30:00Z",
  "volatility": "volatile",
  "queue_status": "active",
  "queue_length": 5,
  "total_queue_time": "4d 12h 30m",
  "queue_completion": "2026-01-20T03:00:00Z",
  "currently_training": {
    "name": "Drones",
    "level": 5,
    "level_display": "V",
    "progress": 42.5,
    "time_remaining": "1d 6h 15m",
    "finish_date": "2026-01-16T20:45:00Z"
  },
  "skills": [
    {
      "queue_position": 0,
      "skill_id": 3436,
      "name": "Drones",
      "target_level": 5,
      "level_display": "V",
      "status": "training",
      "progress_percent": 42.5,
      "time_remaining": "1d 6h 15m",
      "finish_date": "2026-01-16T20:45:00Z"
    },
    {
      "queue_position": 1,
      "skill_id": 23618,
      "name": "Gallente Drone Specialization",
      "target_level": 3,
      "level_display": "III",
      "status": "queued",
      "time_remaining": "2d 4h 30m",
      "finish_date": "2026-01-18T01:15:00Z"
    }
  ]
}
```

### Empty Queue Response

```json
{
  "query_timestamp": "2026-01-15T14:30:00Z",
  "volatility": "volatile",
  "queue_status": "empty",
  "message": "Skill queue is empty - no skills training!",
  "queue_length": 0,
  "skills": []
}
```

## Response Formats

### Standard Queue Display

**Plain version (rp_level: off or lite):**

```markdown
## Skill Queue Status
*Query: 14:30 UTC*

**Currently Training:**
Drones V - 42.5% complete (1d 6h 15m remaining)

**Queue:** (5 skills, 4d 12h total)
| # | Skill | Level | ETA |
|---|-------|-------|-----|
| 1 | Drones | V | 1d 6h 15m |
| 2 | Gallente Drone Spec | III | 2d 4h 30m |
| 3 | Heavy Drone Operation | IV | 3d 1h 45m |
| 4 | Drone Durability | III | 3d 18h 20m |
| 5 | Drone Navigation | IV | 4d 12h 30m |

Queue completes: Jan 20, 03:00 UTC

*Training progresses in real-time. Re-query for current status.*
```

**Formatted version (rp_level: moderate or full):**

```
═══════════════════════════════════════════════════════════════════
ARIA SKILL TRAINING MONITOR
───────────────────────────────────────────────────────────────────
GalNet Sync: 14:30 UTC
───────────────────────────────────────────────────────────────────
CURRENTLY TRAINING:
  Drones V .......................... 42.5% [████████░░░░░░░░░░░░]
  Time Remaining: 1d 6h 15m
  Completion: Jan 16, 20:45 UTC

QUEUE STATUS: 5 skills | 4d 12h total
───────────────────────────────────────────────────────────────────
  #1  Drones V ..................... 1d 6h 15m   [TRAINING]
  #2  Gallente Drone Spec III ...... 2d 4h 30m
  #3  Heavy Drone Operation IV ..... 3d 1h 45m
  #4  Drone Durability III ......... 3d 18h 20m
  #5  Drone Navigation IV .......... 4d 12h 30m
───────────────────────────────────────────────────────────────────
Queue Completion: 2026-01-20 03:00 UTC
───────────────────────────────────────────────────────────────────
⚠ Training data reflects query time. Skills train in real-time.
═══════════════════════════════════════════════════════════════════
```

### Empty Queue Warning

```
═══════════════════════════════════════════════════════════════════
ARIA SKILL TRAINING MONITOR
───────────────────────────────────────────────────────────────────
GalNet Sync: 14:30 UTC
───────────────────────────────────────────────────────────────────
⚠ SKILL QUEUE EMPTY

No skills are currently training. Skill points are not accumulating.

IN-GAME ACTION REQUIRED:
  Character Sheet (Alt+A) → Skills tab → Right-click skill → Train

ARIA monitors training status but cannot modify the queue.
═══════════════════════════════════════════════════════════════════
```

### Compact Format

For quick checks or when brevity requested:

```
Skill Queue (14:30 UTC): Drones V - 42.5% (1d 6h left)
Next: Gallente Drone Spec III, Heavy Drone Op IV
Queue total: 4d 12h | Completes: Jan 20
⚠ Real-time data
```

## Error Handling

### ESI Not Configured

```
═══════════════════════════════════════════════════════════════════
ARIA SKILL QUEUE
───────────────────────────────────────────────────────────────────
Skill queue monitoring requires ESI authentication.

ARIA works fully without ESI - you can tell me what you're training
and I can help plan skill paths.

OPTIONAL: Enable live tracking (~5 min setup)
  → uv run python .claude/scripts/aria-oauth-setup.py
  → Select skill queue scope during setup
═══════════════════════════════════════════════════════════════════
```

### Missing Scope

```
═══════════════════════════════════════════════════════════════════
ARIA SKILL QUEUE - SCOPE NOT AUTHORIZED
───────────────────────────────────────────────────────────────────
ESI is configured but skill queue scope is missing.

To enable skill queue monitoring:
  uv run python .claude/scripts/aria-oauth-setup.py

Select "esi-skills.read_skillqueue.v1" during scope selection.
═══════════════════════════════════════════════════════════════════
```

## Contextual Suggestions

After displaying skill queue, suggest ONE related action when relevant:

| Context | Suggest |
|---------|---------|
| Queue is empty | "Add skills to your queue to maximize SP generation" |
| Skill completing soon (<1h) | "Consider checking your queue - [skill] completes soon" |
| Training combat skills | "For fitting advice, try `/fitting`" |
| Training industry skills | "Check your blueprints with `/esi-query blueprints`" |

## Cross-References

| Related Command | Use Case |
|-----------------|----------|
| `/esi-query skills` | List all trained skill levels (not queue) |
| `/pilot` | Full identity including total skill points |
| `/aria-status` | Overall operational status |

## Progress Bar Generation

For `rp_level: moderate` or `full`, render a visual progress bar:

```python
def progress_bar(percent, width=20):
    filled = int(percent / 100 * width)
    empty = width - filled
    return f"[{'█' * filled}{'░' * empty}]"

# Example: 42.5% -> [████████░░░░░░░░░░░░]
```

## Behavior Notes

- **Brevity:** Default to compact table format unless RP mode requests formatted boxes
- **Precision:** Show progress to one decimal place for currently training skill
- **Time Format:** Use "Xd Yh Zm" for durations, show dates for completion times
- **Empty Emphasis:** Empty queue is a significant state - highlight it as a warning
- **Staleness Warning:** Always include warning that data is real-time
