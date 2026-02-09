# Political Entity Triggers Proposal

**Status:** Draft
**Owner:** ARIA Notifications

---

## Executive Summary

Add a per-profile trigger that matches **player corporations and alliances** by
attacker/victim involvement. This enables "political ties" channels that only
post when a kill involves a curated set of entities (e.g., Serpentis-aligned
player corps), without relying on the global watchlist.

This complements the existing `npc_faction_kill` trigger (NPC faction corps)
and allows Serpentis/Angel Cartel-aligned intelligence to include **player**
entities in the same channel.

---

## Problem Statement

Today, political filtering for player entities is only possible through the
global watchlist and the `watchlist_activity` trigger. That model has three
limitations:

1. **Global scope:** Watchlist matches apply to *all* profiles. You cannot have
   a Serpentis-only channel that watches a different set of entities from a
   trade-hub channel.
2. **No attacker/victim role control:** Watchlist triggers do not distinguish
   which side matters for political context (attacker vs. victim).
3. **Topology interaction is fixed:** Watchlist triggers always respect topology
   filters, but some political channels want global coverage or partial bypass.

We need a per-profile, role-aware trigger that matches **player corp/alliance**
IDs, analogous to `npc_faction_kill` for NPC factions.

---

## Goals

- Enable per-profile filtering for player corporations and alliances.
- Allow attacker/victim role configuration.
- Optional topology bypass (`ignore_topology`) like `npc_faction_kill`.
- Provide clear notification framing distinct from "watchlist activity."

## Non-Goals

- Replace the existing watchlist system.
- Auto-discover political ties or standings.
- Provide real-time name-to-ID resolution in config (initial version uses IDs).

---

## Proposed Solution

### 1) New Trigger: `political_entity_kill`

Add a new trigger type to notification profiles:

```yaml
triggers:
  political_entity_kill:
    enabled: true
    corporations: [98612345, 98456789]
    alliances: [99001234]
    as_attacker: true
    as_victim: true
    ignore_topology: false
    label: "SERPENTIS-ALIGNED"
```

**Field behavior:**
- `corporations`: player corp IDs to match (attacker or victim)
- `alliances`: player alliance IDs to match (attacker or victim)
- `as_attacker`: match when a listed entity is an attacker
- `as_victim`: match when a listed entity is a victim
- `ignore_topology`: if true, bypass topology filter for this trigger only
- `label`: optional label used in notification title (default: "POLITICAL")

### 2) Trigger Evaluation Logic

- Evaluate similarly to `npc_faction_kill`:
  - Build a set of watched corp/alliance IDs from config.
  - Match attacker/victim by role.
  - Return a `TriggerResult` with context (role, entity type, entity ID).

### 3) Topology Interaction

Use the same bypass pattern as `npc_faction_kill`:
- If topology fails and `ignore_topology` is true, allow this trigger only.
- If topology fails and no political match, filter the profile.

### 4) Formatter Framing

Add a distinct title prefix and color:
- Title prefix: `POLITICAL: ` or `SERPENTIS-ALIGNED: ` (if `label` set)
- Emoji: `⚖️` or `🜨` (final choice later)
- Include entity context in description:
  - `Attacker: <corp/alliance name>`
  - `Victim: <corp/alliance name>`

### 5) Optional: Unified Political Trigger (Stretch)

Allow `political_entity_kill` to also accept `npc_factions` to unify player
and NPC political ties under one trigger:

```yaml
political_entity_kill:
  npc_factions: [serpentis, angel_cartel]
  corporations: [98612345]
  alliances: [99001234]
```

This is optional and can be deferred if it increases complexity.

---

## Example: Serpentis Political Intel

```yaml
name: serpentis-intel
display_name: Serpentis Political Intel
enabled: true

topology:
  geographic:
    systems:
      - name: Serpentis Prime
        classification: home
      - name: Ignoitton
        classification: hunting

triggers:
  political_entity_kill:
    enabled: true
    corporations: [98612345]  # Example: Serpentis-aligned player corp
    alliances: [99001234]     # Example: allied bloc
    as_attacker: true
    as_victim: true
    ignore_topology: false
    label: "SERPENTIS-ALIGNED"

  npc_faction_kill:
    enabled: true
    factions: [serpentis, angel_cartel]
    as_attacker: true
    as_victim: true
    ignore_topology: false
```

This profile:
- Covers its defined topology.
- Posts only when **player political ties** or **NPC faction ties** are involved.
- Avoids unrelated gatecamp/watchlist noise.

---

## Implementation Details

### Schema / Config
- Add `PoliticalEntityKillConfig` to `src/aria_esi/services/redisq/notifications/config.py`
- Extend `TriggerConfig` with `political_entity_kill`
- Update validation to ensure at least one of:
  - `corporations`, `alliances` (and later `npc_factions`)
  - `as_attacker` or `as_victim` true

### Trigger Evaluation
- Add `TriggerType.POLITICAL_ENTITY_KILL`
- Implement evaluation in `notifications/triggers.py`
- Extend `TriggerResult` to carry matched entity context (type, id, role, label)

### Profile Evaluator
- Apply topology bypass if `political_entity_kill.ignore_topology` is true
- Ensure primary trigger ordering is deterministic

### Formatter
- Add color/emoji/prefix for political triggers
- Include entity context in description
- If name resolution is available, show resolved corp/alliance names

---

## Testing Plan

- Unit tests:
  - Matches for attacker/victim corp/alliance
  - `ignore_topology` bypass behavior
  - Validation errors when misconfigured
- Integration test:
  - A kill involving a listed corp triggers only the political profile
- Regression:
  - Existing `watchlist_activity` and `npc_faction_kill` behavior unchanged

---

## Backwards Compatibility

- No changes to existing profiles.
- New trigger is opt-in.
- Watchlist system remains global.

---

## Open Questions

1. Should config accept **names** as well as IDs (with ESI resolution)?
2. Should political triggers have **dedicated throttling** separate from profile?
3. Preferred title framing: `POLITICAL`, `AFFILIATION`, or custom label only?
4. Should `npc_faction_kill` be merged under a unified political trigger?

