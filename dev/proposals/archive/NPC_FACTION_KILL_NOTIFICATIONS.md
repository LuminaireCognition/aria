# NPC Faction Kill Notifications Proposal

**Status:** Approved
**Adopted Approach:** New `npc_faction_kill` trigger type

---

## Executive Summary

ARIA's notification system currently triggers on capsuleer activity: kills involving watched corporations/alliances, gatecamps, and high-value losses. For pilots with deep faction roleplay (e.g., PARIA-S Serpentis associates), there's an untapped notification category: **NPC faction kills**.

When Serpentis Corporation NPCs kill something, a PARIA-S user might want to know. These are "the Corporation's operations in progress"—kills where faction NPCs are the attackers, not the victims. This creates RP immersion by connecting the pilot to their faction's ongoing activities across the cluster.

**Adopted approach:** A new `npc_faction_kill` trigger type that:
- Accepts human-readable faction names (not IDs)
- Maps faction → NPC corporation IDs via static reference data
- Integrates with pattern detection and commentary generation
- Uses faction-appropriate framing ("SERPENTIS OPERATIONS" not "Watchlist activity")

---

## Problem Statement

### Current Capability

The notification system matches kills against watched entities (corporations and alliances). When a watched entity appears as victim OR attacker, the kill can trigger notifications.

```python
# entity_filter.py:177-181
for attacker in kill.attackers:
    if attacker.corporation_id in self._watched_corps:
        result.attacker_corp_matches.append(attacker.corporation_id)
```

**This already works for NPC corporations** if you add them to a watchlist. Serpentis Corporation (ID: 1000135) can be added like any other corporation.

### The Gap

While technically possible, the current approach has UX and semantic issues:

1. **Watchlist semantics:** Watchlists are designed for "entities I care about"—typically player groups, war targets, or intel subjects. NPC factions don't fit this mental model.

2. **Configuration burden:** Users must know NPC corporation IDs and manually add them. Serpentis has multiple NPC corps (Serpentis Corporation, Shadow Serpentis, Serpentis Drug Dealers, etc.).

3. **No faction grouping:** Adding one corp doesn't capture all faction activity. Serpentis kills from `Shadow Serpentis` won't match a watchlist containing only `Serpentis Corporation`.

4. **RP framing mismatch:** "Watchlist activity" trigger doesn't convey the right meaning for NPC faction kills. It's not "someone I'm watching"—it's "my faction's operations."

### RP Use Case: PARIA-S

A PARIA-S user (Serpentis associate persona) wants Discord notifications when:
- Serpentis NPCs kill a capsuleer anywhere (or in configured topology)
- Relevant faction activity occurs that reinforces the RP connection

The notification should feel like **corporate intelligence briefings**:

> **SERPENTIS OPERATIONS: Fountain**
> Retriever destroyed • Serpentis Corporation
> 12.4M ISK • 3 min ago
>
> ---
> *The Corporation's resource denial operations continue on schedule, Associate.*
> — PARIA-S

Not "watchlist activity" framing—faction operations framing.

---

## Design Decisions

The following decisions have been made for this implementation:

### Core Approach

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Implementation strategy | New `npc_faction_kill` trigger | Best UX, explicit intent, proper RP framing |
| ~~Watchlist extension~~ | Rejected | Wrong semantics, overloads existing concept |
| ~~faction_id filter~~ | Rejected | Overengineered, still wrong framing |

### Behavioral Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Topology filtering | Configurable, default cluster-wide | NPC ops are interesting everywhere; users can limit if noisy |
| NPC-as-victim (`as_victim`) | Include, default false | Enables anti-pirate RP; not primary use case |
| Persona coupling | Any persona works | ARIA narrates neutrally; faction personas get enhanced voice |
| NPC corp data source | Static JSON extracted from SDE | Simple, fast, manually updated when SDE changes |
| Initial faction scope | Pirate factions only | Most relevant for RP; empire navies added later |

### Volume Control Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Throttle handling | Use profile-level throttle (recommend 15+ min) | Consistent with existing system |
| Commentary cost control | Pattern-gated (2+ kills triggers commentary) | Avoids LLM calls on isolated NPC kills |
| Spam prevention | First kill notifies; pattern detection for subsequent | Balance between awareness and noise |

---

## Design

### 1. NPC Corporation Mapping

**Source:** EVE SDE provides `factionID` for NPC corporations.

**Reference table:** Create `reference/factions/npc_corporations.json`

```json
{
  "serpentis": {
    "faction_id": 500020,
    "name": "Serpentis",
    "corporations": [
      {"id": 1000135, "name": "Serpentis Corporation"},
      {"id": 1000157, "name": "Serpentis Inquest"}
    ]
  },
  "angel_cartel": {
    "faction_id": 500011,
    "name": "Angel Cartel",
    "corporations": [
      {"id": 1000124, "name": "Archangels"},
      {"id": 1000133, "name": "Salvation Angels"},
      {"id": 1000136, "name": "Guardian Angels"},
      {"id": 1000138, "name": "Dominations"},
      {"id": 1000436, "name": "Malakim Zealots"}
    ]
  },
  "guristas": {
    "faction_id": 500010,
    "name": "Guristas Pirates",
    "corporations": [
      {"id": 1000127, "name": "Guristas"},
      {"id": 1000141, "name": "Guristas Production"},
      {"id": 1000437, "name": "Commando Guri"}
    ]
  },
  "blood_raiders": {
    "faction_id": 500012,
    "name": "Blood Raider Covenant",
    "corporations": [
      {"id": 1000134, "name": "Blood Raiders"}
    ]
  },
  "sansha": {
    "faction_id": 500019,
    "name": "Sansha's Nation",
    "corporations": [
      {"id": 1000161, "name": "True Creations"},
      {"id": 1000162, "name": "True Power"}
    ]
  }
}
```

**Note:** Elite NPC variants (e.g., "Shadow Serpentis", "Dark Blood", "Dread Guristas") are not separate corporations in the SDE. They use the same corporation ID as their parent faction in killmails. Guardian Angels is part of the Angel Cartel faction (500011), not Serpentis, despite their lore partnership.

**Loader utility:**
```python
class NPCFactionMapper:
    """Maps NPC corporation IDs to faction names."""

    def __init__(self, reference_path: Path):
        self._corp_to_faction: dict[int, str] = {}
        self._faction_corps: dict[str, set[int]] = {}
        self._load_mapping(reference_path)

    def get_faction_for_corp(self, corp_id: int) -> str | None:
        """Get faction name for an NPC corporation ID."""
        return self._corp_to_faction.get(corp_id)

    def get_corps_for_faction(self, faction_name: str) -> set[int]:
        """Get all corporation IDs for a faction."""
        return self._faction_corps.get(faction_name.lower(), set())
```

### 2. Profile Schema Extension

**Add to `NotificationProfile`:**
```python
@dataclass
class NPCFactionKillConfig:
    """Configuration for NPC faction kill trigger."""
    enabled: bool = False
    factions: list[str] = field(default_factory=list)  # ["serpentis", "angel_cartel"]
    as_attacker: bool = True   # Notify when NPC kills someone
    as_victim: bool = False    # Notify when someone kills the NPC
    ignore_topology: bool = True  # Default: cluster-wide
```

**YAML:**
```yaml
triggers:
  npc_faction_kill:
    enabled: true
    factions:
      - serpentis
      - angel_cartel  # Includes Guardian Angels corp
    as_attacker: true
    as_victim: false
    ignore_topology: true  # Cluster-wide by default
```

### 3. Trigger Evaluation

**Extend `TriggerEvaluator`:**
```python
def _evaluate_npc_faction_kill(
    self,
    kill: ProcessedKill,
    config: NPCFactionKillConfig,
) -> NPCFactionTriggerResult | None:
    """Check if kill involves configured NPC factions."""

    if not config.enabled:
        return None

    watched_corps = set()
    for faction in config.factions:
        watched_corps.update(self._npc_mapper.get_corps_for_faction(faction))

    # Check attackers (NPC killed someone)
    if config.as_attacker:
        for attacker in kill.attackers:
            if attacker.corporation_id in watched_corps:
                faction = self._npc_mapper.get_faction_for_corp(attacker.corporation_id)
                return NPCFactionTriggerResult(
                    matched=True,
                    faction=faction,
                    corporation_id=attacker.corporation_id,
                    role="attacker",
                )

    # Check victim (someone killed the NPC)
    if config.as_victim:
        if kill.victim.corporation_id in watched_corps:
            faction = self._npc_mapper.get_faction_for_corp(kill.victim.corporation_id)
            return NPCFactionTriggerResult(
                matched=True,
                faction=faction,
                corporation_id=kill.victim.corporation_id,
                role="victim",
            )

    return None
```

**Result model:**
```python
@dataclass
class NPCFactionTriggerResult:
    matched: bool
    faction: str  # "serpentis", "guristas", etc.
    corporation_id: int
    role: str  # "attacker" or "victim"
```

**Data flow:**
```
Kill ingested
    ↓
Trigger evaluation
    ├─ watchlist_activity → check entity filter
    ├─ gatecamp_detected → check gatecamp patterns
    ├─ high_value → check ISK threshold
    ├─ war_activity → check war targets
    └─ npc_faction_kill → check NPC corporation → faction mapping
           ↓
    Faction matched → TriggerResult.npc_faction = "serpentis"
           ↓
    Commentary generator sees npc_faction context
           ↓
    Uses faction-appropriate voice ("The Corporation's operations...")
```

### 4. Pattern Detection Extension

**Add NPC faction pattern:**
```python
# In patterns.py
def _detect_npc_faction_activity(
    self,
    kill: ProcessedKill,
    npc_result: NPCFactionTriggerResult | None,
) -> DetectedPattern | None:
    """Detect sustained NPC faction activity."""

    if not npc_result:
        return None

    # Count recent kills by same faction
    recent_faction_kills = await self._count_faction_kills(
        faction=npc_result.faction,
        system_id=kill.solar_system_id,
        since_minutes=60,
    )

    if recent_faction_kills >= 2:
        return DetectedPattern(
            pattern_type="npc_faction_activity",
            description=f"{npc_result.faction.title()} operations active in system",
            weight=0.4,
            context={
                "faction": npc_result.faction,
                "kill_count": recent_faction_kills,
            },
        )

    return None
```

**Commentary warrant behavior:**
- First NPC kill in a system: Notification fires, but warrant score low → template only
- Second+ NPC kill (pattern detected): Warrant score increases → LLM commentary generated

This naturally throttles LLM costs while still notifying on all faction activity.

### 5. Commentary Integration

**Extend persona voice summary:**
```python
@dataclass
class PersonaVoiceSummary:
    # Existing fields...

    # New: Faction-specific language
    faction_ops_vocabulary: dict[str, dict[str, str]] = field(default_factory=dict)

# PARIA-S voice summary
PARIA_S_VOICE = PersonaVoiceSummary(
    name="PARIA-S",
    tone="Smooth, corporate, darkly luxurious...",
    address_form="Associate",
    faction_ops_vocabulary={
        "serpentis": {
            "operations": "Corporate operations",
            "kill_verb": "neutralized",
            "territory": "Corporate territory",
            "commentary_prefix": "The Corporation's",
        },
        "angel_cartel": {
            "operations": "Security operations",
            "kill_verb": "engaged",
            "territory": "Protected space",
            "commentary_prefix": "Guardian Angels",  # Lore: GA protects Serpentis
        },
    },
    # ...
)

# Default ARIA voice (neutral narration)
ARIA_VOICE = PersonaVoiceSummary(
    name="ARIA",
    tone="Professional tactical assistant...",
    address_form="Capsuleer",
    faction_ops_vocabulary={
        # Generic vocabulary for all factions
        "_default": {
            "operations": "NPC operations",
            "kill_verb": "destroyed",
            "territory": "faction space",
            "commentary_prefix": "Faction",
        },
    },
)
```

**Prompt enhancement:**
```python
# In commentary generation
if trigger_result.npc_faction:
    faction = trigger_result.npc_faction.faction
    vocab = persona_voice.faction_ops_vocabulary.get(
        faction,
        persona_voice.faction_ops_vocabulary.get("_default", {})
    )
    if vocab:
        user_prompt += f"\n\nFACTION CONTEXT: This is {vocab['operations']} by {faction.title()}. Use {vocab['commentary_prefix']} framing."
```

### 6. Message Formatting

**Faction-specific embed title:**
```python
def _get_embed_title(self, trigger_result: TriggerResult) -> str:
    if trigger_result.npc_faction:
        faction = trigger_result.npc_faction.faction.upper()
        return f"{faction} OPERATIONS"
    # Existing logic...
```

**Embed color by faction:**
```python
FACTION_COLORS = {
    "serpentis": 0x00FF00,       # Green (Serpentis brand)
    "angel_cartel": 0xFF6600,    # Orange (Angel Cartel / Guardian Angels)
    "guristas": 0x808080,         # Gray
    "blood_raiders": 0x8B0000,    # Dark red
    "sansha": 0x800080,           # Purple
}
```

---

## Implementation Plan

### Phase 1: NPC Faction Mapping (Foundation)

**Goal:** Create reference data for NPC corp → faction resolution.

**Deliverables:**
- [ ] `reference/factions/npc_corporations.json` with all pirate factions
- [ ] `NPCFactionMapper` utility class
- [ ] Unit tests for mapping
- [ ] CLI command: `uv run aria-esi sde export-npc-corps`

**Files:**
- `reference/factions/npc_corporations.json` (new)
- `src/aria_esi/services/redisq/notifications/npc_factions.py` (new)
- `tests/services/redisq/notifications/test_npc_factions.py` (new)

### Phase 2: Trigger Integration

**Goal:** Add `npc_faction_kill` trigger to profile evaluation.

**Deliverables:**
- [ ] `NPCFactionKillConfig` dataclass
- [ ] Profile schema update (YAML parsing)
- [ ] Trigger evaluation in `TriggerEvaluator`
- [ ] `ignore_topology` handling in profile evaluator
- [ ] Unit tests for trigger logic

**Files:**
- `src/aria_esi/services/redisq/notifications/profiles.py` (modify)
- `src/aria_esi/services/redisq/notifications/triggers.py` (modify)
- `tests/services/redisq/notifications/test_triggers.py` (extend)

### Phase 3: Pattern & Commentary

**Goal:** Enable faction-aware pattern detection and commentary.

**Deliverables:**
- [ ] `npc_faction_activity` pattern type
- [ ] Faction vocabulary in persona voice summaries (PARIA-S, ARIA default)
- [ ] Commentary prompt enhancement for faction context
- [ ] Unit tests

**Files:**
- `src/aria_esi/services/redisq/notifications/patterns.py` (modify)
- `src/aria_esi/services/redisq/notifications/persona.py` (modify)
- `src/aria_esi/services/redisq/notifications/prompts.py` (modify)

### Phase 4: Formatting & UX

**Goal:** Faction-appropriate notification appearance.

**Deliverables:**
- [ ] Faction-specific embed titles ("SERPENTIS OPERATIONS")
- [ ] Faction color coding
- [ ] Documentation update
- [ ] Example profile in `userdata/notifications/`

**Files:**
- `src/aria_esi/services/redisq/notifications/formatter.py` (modify)
- `docs/NOTIFICATION_PROFILES.md` (update)
- `userdata/notifications/serpentis-operations.yaml.example` (new)

---

## Configuration Example

### PARIA-S Serpentis Intel Profile

```yaml
# userdata/notifications/serpentis-operations.yaml
schema_version: 2
name: serpentis-operations
display_name: "Serpentis Corporate Intelligence"
enabled: true
webhook_url: ${DISCORD_WEBHOOK_SERPENTIS}

topology: {}  # Ignored when ignore_topology: true

triggers:
  watchlist_activity: false
  gatecamp_detected: false
  high_value_threshold: null
  war_activity: false

  npc_faction_kill:
    enabled: true
    factions:
      - serpentis
      - angel_cartel  # Includes Guardian Angels corp
    as_attacker: true
    as_victim: false
    ignore_topology: true  # Cluster-wide

throttle_minutes: 15  # Higher throttle for NPC activity volume

commentary:
  enabled: true
  persona: paria-s
  warrant_threshold: 0.3
  model: claude-3-haiku-20240307
  timeout_ms: 3000
  max_tokens: 100
```

### Example Notification Output

**First kill (template only):**
```
SERPENTIS OPERATIONS: Fountain

Retriever destroyed • Serpentis Corporation
12.4M ISK • 3 min ago
⚔️ 3 NPC attackers

https://zkillboard.com/kill/12345678/
```

**Subsequent kills (pattern detected, commentary generated):**
```
SERPENTIS OPERATIONS: Fountain

Covetor destroyed • Serpentis Corporation
18.2M ISK • 1 min ago
⚔️ 4 NPC attackers

---
Resource denial operations on schedule, Associate. Third mining vessel
this hour—the Corporation's presence discourages unsanctioned extraction.
                                                          — PARIA-S

https://zkillboard.com/kill/12345679/
```

---

## NPC Corporation Data

### Faction Coverage (SDE Verified)

| Faction Key | Faction ID | Corporations (with IDs) |
|-------------|------------|-------------------------|
| `serpentis` | 500020 | Serpentis Corporation (1000135), Serpentis Inquest (1000157) |
| `angel_cartel` | 500011 | Archangels (1000124), Salvation Angels (1000133), Guardian Angels (1000136), Dominations (1000138), Malakim Zealots (1000436) |
| `guristas` | 500010 | Guristas (1000127), Guristas Production (1000141), Commando Guri (1000437) |
| `blood_raiders` | 500012 | Blood Raiders (1000134) |
| `sansha` | 500019 | True Creations (1000161), True Power (1000162) |

**Data source:** EVE SDE via `sde(action="corporation_info")` — verified 2026-01-27

**Important notes:**
- Elite NPC variants ("Shadow Serpentis", "Dark Blood", "Dread Guristas") are **not separate corporations**. They share corporation IDs with their parent factions in killmails.
- Guardian Angels (corp 1000136) belongs to Angel Cartel faction (500011), not Serpentis (500020), despite their lore partnership protecting Serpentis assets.
- For PARIA-S users wanting both Serpentis and Guardian Angels notifications, configure both `serpentis` and `angel_cartel` factions.

### Future Extensions

| Faction Category | When to Add |
|------------------|-------------|
| Empire navies (Caldari Navy, etc.) | When empire-loyalist personas are implemented |
| EDENCOM / Triglavian | When invasion-era RP profiles are requested |
| Mordu's Legion | On request |

### Data Maintenance

The `reference/factions/npc_corporations.json` file is manually curated. Update process:

1. When SDE updates, run `uv run aria-esi sde export-npc-corps --diff`
2. Review changes (new corps, renamed corps)
3. Update reference file
4. Commit with SDE version in message

---

## Security Considerations

### Kill Data Trust

NPC corporation IDs in killmails come from ESI/zKillboard. The mapping is static (SDE data) and controlled. No injection risk from kill data affecting faction resolution.

### Commentary Context

NPC faction context passed to LLM is:
- Faction name (from static mapping)
- Kill count (numeric)
- Role (fixed enum: "attacker" or "victim")

No user-controlled strings injected into faction context.

---

## Success Criteria

| Metric | Target |
|--------|--------|
| NPC faction kills correctly identified | >99% |
| False positives (player corp matched as NPC) | 0% |
| Commentary uses faction-appropriate voice | >90% (manual review) |
| Notification latency impact | <50ms added |
| Configuration UX | Single YAML block, faction names (not IDs) |

---

## Alternatives Considered

### Option A: Add NPC Corps to Watchlist

Use existing watchlist system with NPC corporation IDs.

**Why rejected:**
- Wrong semantic framing ("watchlist" vs "faction operations")
- User must know NPC corp IDs (not discoverable)
- Incomplete faction coverage (easy to miss corps)
- Commentary system doesn't know it's faction activity

### Option B: Add `faction_id` Filter

Extend entity matching to resolve NPC corporation → faction at the filter level.

**Why rejected:**
- Schema migration required
- Overengineered for the use case
- Still uses "watchlist" framing
- Killmails may not include faction_id for all attackers

### Template-Only Commentary

Use fixed templates instead of LLM for NPC faction notifications.

**Why rejected as primary:** Repetitive, no contextual awareness

**Kept as fallback:** Template formatting used when LLM unavailable or warrant score too low.

---

## References

### Related Proposals
- `PERSONA_DRIVEN_DISCORD_NOTIFICATIONS.md` — Commentary system architecture
- `PARIA_S_SERPENTIS_PROPOSAL.md` — Serpentis persona design

### Code References
- `src/aria_esi/services/redisq/entity_filter.py` — Entity matching
- `src/aria_esi/services/redisq/notifications/profiles.py` — Profile schema
- `src/aria_esi/services/redisq/notifications/triggers.py` — Trigger evaluation
- `src/aria_esi/services/redisq/notifications/persona.py` — Persona voice loading

### EVE Data
- EVE SDE: `chrFactions`, `crpNPCCorporations` tables
- zKillboard API: Killmail attacker/victim corporation IDs

---

## Changelog

| Date | Change |
|------|--------|
| 2026-01-27 | Initial proposal |
| 2026-01-27 | Adopted Option C (new trigger type); resolved open questions |
| 2026-01-27 | Updated NPC corporation data with SDE-verified IDs; corrected faction IDs; removed non-existent corps (Shadow Serpentis, Dark Blood, Dread Guristas); renamed `guardian_angels` key to `angel_cartel` |
