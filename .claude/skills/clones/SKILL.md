---
name: clones
description: Clone and implant status tracking. Safety-critical for knowing your medical clone location and active implants before risky operations.
model: haiku
category: tactical
triggers:
  - "/clones"
  - "clone status"
  - "where's my clone"
  - "check my implants"
  - "jump clone status"
  - "can I jump clone"
  - "medical clone location"
requires_pilot: true
esi_scopes:
  - esi-clones.read_clones.v1
  - esi-clones.read_implants.v1
allowed-tools: [Read, Grep, Glob, "mcp__aria-universe__pilot"]
injected_prerequisites:
  - .claude/skills/_shared/esi-error-handling.md
---

# ARIA Clone Status Module

> **HALLUCINATION GUARD:** All clone locations, implant names, jump clone data, and cooldown timers MUST come from ESI CLI responses. Do NOT supplement with training data knowledge.

## Commands

### Full Clone Status

```bash
PYTHONPATH=.claude/scripts uv run python -m aria_esi clones
```

Shows medical clone location, all jump clones and their locations, implants in each clone, and jump clone cooldown status.

### Active Implants Only

```bash
PYTHONPATH=.claude/scripts uv run python -m aria_esi implants
```

Shows implants in your current active clone, organized by slot (Attribute Enhancers slots 1-5, Hardwirings slots 6-10).

### Jump Clone Status

```bash
PYTHONPATH=.claude/scripts uv run python -m aria_esi jump-clones
```

Shows jump clone locations and whether you can currently jump (24h cooldown).

## Response Format

Present clone data in a structured display including:
- **Medical clone:** Location and system security
- **Jump clones:** Numbered list with location, implant count, and optional name
- **Jump status:** Available or cooldown remaining with availability time
- **Active implants:** Listed by slot number with full implant name
- **Safety warning:** Note that implants are lost on pod destruction when applicable

Adapt format to RP level: markdown table for `off`, box-drawing for `on`/`full`.

## Safety Protocols

Warn about implant risk when pilot discusses low-sec, null-sec, PvP, or L4+ missions. Suggest checking `/clones` before risky operations. When `/threat-assessment` indicates HIGH or CRITICAL risk, remind pilot about clone status.

## Contextual Suggestions

Suggest one related command when contextually relevant (e.g., `/threat-assessment` before risky missions, jump clone skill info when no jump clones found).

## Error Handling

### Missing Scope

```
Clone data requires ESI authorization.

To enable clone tracking:
  uv run python .claude/scripts/aria-oauth-setup.py

This will authorize:
  - esi-clones.read_clones.v1 (clone locations)
  - esi-clones.read_implants.v1 (active implants)
```

### No Jump Clones

```
No jump clones found.

Jump clones require the Infomorph Psychology skill:
  Level 1: 1 jump clone
  Level 2: 2 jump clones
  ...up to 5 at Level 5

Additional clones available via:
  - Advanced Infomorph Psychology skill (+1 per level)
  - Clone Soldier Tags (from pirate NPCs)
```

## Reference: ESI Error Handling (injected)
<!-- prerequisite: .claude/skills/_shared/esi-error-handling.md -->
!`cat .claude/skills/_shared/esi-error-handling.md`
