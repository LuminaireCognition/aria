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
argument-hint: "[--active|--history]"
allowed-tools: [Read, Grep, Glob, Bash, "mcp__aria-universe__pilot"]
injected_prerequisites:
  - .claude/skills/_shared/esi-error-handling.md
---

# ARIA Industry Jobs Monitor

If the user asks to deliver jobs or start new jobs, remind them that job delivery requires in-game action (Industry window, Alt+S).

> **HALLUCINATION GUARD:** All job data (blueprints, runs, progress, facilities) MUST come from CLI output. Do NOT supplement with training data knowledge.

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

### Key Response Fields

The CLI returns JSON with these key fields per job:
- `activity_display` — Manufacturing, ME Research, TE Research, Copying, Invention, Reactions
- `blueprint_name`, `product_name` — what is being built/researched
- `runs` — number of runs
- `status` — `active` or `ready` (ready = awaiting delivery)
- `time_remaining`, `progress_percent` — completion tracking
- `facility_name` — where the job is running
- `cost` — installation cost

Summary block includes `active_jobs`, `completed_awaiting_delivery`, counts by activity type.

Empty response returns `"jobs": []` with a message.

## Response Format

Present industry jobs in a markdown table with query timestamp:

```markdown
## Industry Jobs
*Query: {timestamp}*

### Active Jobs ({count})
| Job | Blueprint | Runs | Completes | Progress |
|-----|-----------|------|-----------|----------|
| {activity} | {blueprint} | {runs} | {end_time} | {percent}% |

### Ready for Delivery ({count})
- **{activity}** - {blueprint} (completed {end_time})

**In-Game Action Required:** Open Industry window (Alt+S) → Jobs tab → Deliver

*ARIA monitors job status but cannot interact with the EVE client.*
```

If no jobs: state that no industry jobs are active and suggest checking available blueprints.

If ESI is not configured or scope is missing: state the limitation and provide the setup command (`uv run python .claude/scripts/aria-oauth-setup.py`).

## Contextual Suggestions

After displaying industry jobs, suggest ONE related action when relevant:

| Context | Suggest |
|---------|---------|
| Jobs completed | "Deliver completed jobs in EVE to collect outputs" |
| Manufacturing in progress | "Check material prices with `/price <item>`" |
| No active jobs | "View available blueprints with `/esi-query blueprints`" |
| Research completing soon | "Consider queuing next research job" |

## Behavior Notes

- **Precision:** Show progress to nearest percent for active jobs
- **Time Format:** Use "Xh Ym" for durations, full timestamps for completion
- **Ready Jobs:** Always highlight jobs awaiting delivery - pilot action needed
- **Sorting:** Active jobs first (by completion time), then ready-for-delivery
- **History:** Include completed jobs only when --history or --all flag used

## Reference: ESI Error Handling (injected)
<!-- prerequisite: .claude/skills/_shared/esi-error-handling.md -->
!`cat .claude/skills/_shared/esi-error-handling.md`
