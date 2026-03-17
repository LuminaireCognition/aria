---
name: skillqueue
description: Monitor EVE Online skill training queue and ETA. View current training progress and upcoming skills.
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
injected_prerequisites:
  - .claude/skills/_shared/esi-error-handling.md
---

# ARIA Skill Queue Monitor

When asked to modify the queue, explain ESI is read-only and provide in-game steps (Character Sheet: Alt+A → Skills → Add to queue).

Skill queue data is volatile — always display query timestamp and staleness warning.

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
  "skills": [...]
}
```

## Hallucination Guard

Present only data returned by the CLI. Do not estimate or fabricate training times, skill levels, or queue contents. If the CLI returns an error or partial data, state what is unavailable.

## Response Formats

### Standard Queue Display

```markdown
## Skill Queue Status
*Query: [timestamp]*

**Currently Training:**
[Skill] [Level] - [progress]% complete ([time] remaining)

**Queue:** ([N] skills, [total time] total)
| # | Skill | Level | ETA |
|---|-------|-------|-----|
| 1 | ... | ... | ... |

Queue completes: [date]

*Training progresses in real-time. Re-query for current status.*
```

### Compact Format

For quick checks or when brevity requested:

```
Skill Queue ([timestamp]): [Skill] [Level] - [progress]% ([time] left)
Next: [Skill] [Level], [Skill] [Level]
Queue total: [time] | Completes: [date]
⚠ Real-time data
```

### Empty Queue

Highlight as a warning — skill points are not accumulating:

```
⚠ SKILL QUEUE EMPTY (as of [timestamp])
No skills training. In-game: Alt+A → Skills → Right-click skill → Train
```

## Error Handling

| Error | Response |
|-------|----------|
| ESI unavailable | "Skill queue requires live ESI data. Check in-game: Alt+A → Skills tab." |
| Missing scope | "Skill queue scope not authorized. Run: `uv run python .claude/scripts/aria-oauth-setup.py`" |
| ESI error | Show error message, suggest retrying |

## Contextual Suggestions

After displaying skill queue, suggest ONE related action when relevant:

| Context | Suggest |
|---------|---------|
| Queue is empty | "Add skills to your queue to maximize SP generation" |
| Skill completing soon (<1h) | "Consider checking your queue - [skill] completes soon" |
| Training combat skills | "For fitting advice, try `/fitting`" |
| Training industry skills | "Check your blueprints with `/esi-query blueprints`" |

## Behavior Notes

- **Precision:** Show progress to one decimal place for currently training skill
- **Time Format:** Use "Xd Yh Zm" for durations, show dates for completion times
- **Empty Emphasis:** Empty queue is a significant state - highlight it as a warning

## Reference: ESI Error Handling (injected)
<!-- prerequisite: .claude/skills/_shared/esi-error-handling.md -->
!`cat .claude/skills/_shared/esi-error-handling.md`
