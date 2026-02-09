# ADR-002: Skill Metadata Schema

**Status:** Accepted
**Date:** 2026-01

## Context

ARIA uses Claude Code skills for specialized functionality (missions, fitting, exploration, etc.). Initially, skills had no standardized metadata, making it difficult to:

- Choose appropriate models (haiku vs sonnet)
- Auto-generate help documentation
- Match natural language triggers
- Validate skill configurations

## Decision

Define a YAML frontmatter schema for all SKILL.md files:

```yaml
---
name: skill-name
description: One-line description for help text
model: haiku  # or sonnet for complex tasks
category: tactical|operations|financial|identity|system
triggers:
  - "/skill-name"
  - "natural language phrase"
requires_pilot: true|false
data_sources:
  - userdata/pilots/{active_pilot}/profile.md
  - reference/mechanics/file.md
external_sources:
  - wiki.eveuniversity.org
esi_scopes:
  - esi-wallet.read_character_wallet.v1
---
```

### Auto-Generated Index

`aria-skill-index.py` parses all SKILL.md files and generates `_index.json` with:
- Consolidated skill metadata
- Trigger-to-skill mapping
- Category groupings

## Consequences

### Positive

- Consistent skill structure across all 26 skills
- Automatic model selection (haiku for simple, sonnet for complex)
- Self-documenting via description field
- Trigger phrases enable natural language activation
- Data source documentation aids context loading
- ESI scope tracking for permission checks

### Negative

- Frontmatter must be kept in sync with implementation
- Index regeneration needed after changes (automated in boot)
- YAML parsing adds complexity to skill discovery

## Alternatives Considered

### JSON Schema Files
Rejected: Separates metadata from skill content, harder to maintain.

### Directory Convention
Rejected: Limited expressiveness, can't capture triggers.

### Claude Code Native Discovery
Not available: Claude Code doesn't provide skill metadata introspection.
