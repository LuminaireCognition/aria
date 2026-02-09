---
name: pilot
description: View pilot identity and configuration. Shows full data for authenticated pilot, public data for others.
model: haiku
category: identity
triggers:
  - "/pilot"
  - "/pilot me"
  - "/pilot [name]"
  - "who am I"
  - "my profile"
  - "show my profile"
  - "pilot identity"
  - "look up [name]"
  - "who is [name]"
requires_pilot: true
data_sources:
  - userdata/pilots/{active_pilot}/profile.md
esi_scopes:
  - esi-characters.read_corporation_roles.v1
  - esi-wallet.read_character_wallet.v1
  - esi-skills.read_skills.v1
---

# ARIA Pilot Identity Module

## Purpose
Provide a unified identity view combining local ARIA configuration with live ESI character data. This command answers "Who am I to ARIA?" for the authenticated pilot, or "Who is this pilot?" for public lookups.

## Command Syntax

```
/pilot           # Show authenticated pilot's full identity
/pilot me        # Same as above (explicit self-reference)
/pilot <name>    # Look up another pilot (public data only)
/pilot <id>      # Look up by character ID (public data only)
```

## Trigger Phrases

- `/pilot`
- "who am I" (when referring to ARIA identity, not location)
- "my profile" / "show my profile"
- "pilot identity"
- "check pilot <name>"
- "look up <name>"
- "who is <name>"

## Implementation

Run the `aria-esi pilot` wrapper command:

```bash
# Authenticated pilot (full data)
uv run aria-esi pilot

# Public lookup
uv run aria-esi pilot "Character Name"
uv run aria-esi pilot 2123984364
```

## ESI Availability Check (CRITICAL)

**BEFORE making any ESI queries**, check the session hook output for ESI status:

```json
"esi": {"status": "UNAVAILABLE"}
```

### If ESI is UNAVAILABLE:

1. **DO NOT** run `uv run aria-esi` commands - they will timeout
2. **USE** local profile data:
   - Read `userdata/pilots/{active_pilot}/profile.md`
   - Contains: character name, faction, RP level, module tier, goals, standings
3. **SHOW** "LOCAL PROFILE ONLY" format (documented in Error Handling section)
4. **SKIP** live data: wallet, skill points, current location
5. **NOTE** in response: "Showing local profile (ESI unavailable)"

### If ESI is AVAILABLE:

Proceed with full `uv run aria-esi pilot` query.

### Rationale

The local profile contains all ARIA configuration data. ESI only adds live snapshots (wallet, SP) which aren't critical for identity queries.

## Data Sources by Query Type

### Self Query (Authenticated)

| Data | Source | Access Level |
|------|--------|--------------|
| Character ID/Name | Credentials file | Authenticated |
| Corporation/Alliance | ESI public endpoint | Public |
| Security Status | ESI public endpoint | Public |
| Birthday | ESI public endpoint | Public |
| Faction Alignment | Local profile.md | Local config |
| EVE Experience | Local profile.md | Local config |
| RP Level | Local profile.md | Local config |
| Module Tier | Local profile.md | Local config |
| Operational Constraints | Local profile.md | Local config |
| Standings | ESI authenticated | Authenticated |
| ESI Scopes Available | Credentials file | Local config |
| Wallet Balance | ESI authenticated | Authenticated |
| Skill Points | ESI authenticated | Authenticated |

### Other Pilot Query (Public)

| Data | Source | Access Level |
|------|--------|--------------|
| Character ID/Name | ESI public search | Public |
| Corporation/Alliance | ESI public endpoint | Public |
| Security Status | ESI public endpoint | Public |
| Birthday | ESI public endpoint | Public |

## Response Format

### Self Query (Full Identity)

```
═══════════════════════════════════════════════════════════════════
PILOT IDENTITY
───────────────────────────────────────────────────────────────────
CHARACTER:     [Name]
CHARACTER ID:  [ID]
CORPORATION:   [Corp Name] [[Ticker]]
ALLIANCE:      [Alliance or "None"]
SECURITY:      [Status] ([Description])
CAPSULEER SINCE: [Date]

ARIA CONFIGURATION:
  EVE Experience:  [new/intermediate/veteran]
  RP Level:        [off/lite/moderate/full]
  Module Tier:     [T1/Meta or T2]
  Faction:         [Primary Faction]

CONSTRAINTS:
  Market Trading:  [enabled/disabled]
  Contracts:       [enabled/disabled]
  Fleet Required:  [yes/no]
  Security Pref:   [min security]

ESI STATUS: [Connected/Not Configured]
  Scopes: [X] personal, [Y] corporation
  Token Expires: [timestamp]

ACCOUNT SNAPSHOT: (as of [timestamp])
  Wallet:       [X,XXX,XXX ISK]
  Skill Points: [X,XXX,XXX SP]
───────────────────────────────────────────────────────────────────
Profile: [path to profile.md]
═══════════════════════════════════════════════════════════════════
```

### Other Pilot Query (Public Data)

```
═══════════════════════════════════════════════════════════════════
PILOT LOOKUP - PUBLIC DATA
───────────────────────────────────────────────────────────────────
CHARACTER:     [Name]
CHARACTER ID:  [ID]
CORPORATION:   [Corp Name] [[Ticker]]
ALLIANCE:      [Alliance or "None"]
SECURITY:      [Status] ([Description])
CAPSULEER SINCE: [Date]
───────────────────────────────────────────────────────────────────
⚠ Public data only. Private data requires authentication.
  Query timestamp: [timestamp]
═══════════════════════════════════════════════════════════════════
```

### Not Found Response

```
═══════════════════════════════════════════════════════════════════
PILOT LOOKUP - NOT FOUND
───────────────────────────────────────────────────────────────────
No pilot found matching: "[query]"

Suggestions:
• Check spelling of character name
• Try using character ID if known
• Names are case-sensitive for exact match
═══════════════════════════════════════════════════════════════════
```

## Security Status Descriptions

| Range | Description |
|-------|-------------|
| 5.0+ | Paragon |
| 2.0 to 4.99 | Upstanding |
| 0.0 to 1.99 | Neutral |
| -2.0 to -0.01 | Suspect |
| -5.0 to -2.01 | Criminal |
| Below -5.0 | Outlaw |

## Behavior Notes

1. **Default to Self**: `/pilot` with no arguments shows authenticated pilot
2. **Data Exposure**: Clearly distinguish between public and authenticated data
3. **ESI Optional**: If ESI not configured, still show local profile data with note
4. **Timestamp Volatile Data**: Wallet/SP are volatile - always show query timestamp
5. **Profile Path**: Include profile file path for easy editing

## Error Handling

### No ESI Credentials (Self Query)

```
═══════════════════════════════════════════════════════════════════
PILOT IDENTITY - LOCAL PROFILE ONLY
───────────────────────────────────────────────────────────────────
ARIA CONFIGURATION:
  Character Name:  [from profile]
  EVE Experience:  [level]
  RP Level:        [level]
  ...

ESI STATUS: Not Configured
  Live data (wallet, SP, location) unavailable.

  To enable: uv run python .claude/scripts/aria-oauth-setup.py
───────────────────────────────────────────────────────────────────
Profile: [path]
═══════════════════════════════════════════════════════════════════
```

### Character Not Found (Public Query)

Return "Not Found" response format with suggestions.

### ESI Error

```
═══════════════════════════════════════════════════════════════════
PILOT LOOKUP - ESI ERROR
───────────────────────────────────────────────────────────────────
Could not retrieve pilot data from GalNet.

Error: [error message]
Suggestion: [appropriate action]
═══════════════════════════════════════════════════════════════════
```

## Cross-References

| For This | Use Instead |
|----------|-------------|
| Current location | `/esi-query location` |
| Ship roster | `/aria-status` |
| Detailed standings | `/esi-query standings` |
| Skills list | `/esi-query skills` |
| Corporation details | `/corp` |

## Example Interactions

**User:** `/pilot`
**ARIA:** [Shows full identity card for authenticated pilot]

**User:** "who am I"
**ARIA:** [Shows full identity if context suggests ARIA identity, otherwise may clarify]

**User:** `/pilot Chribba`
**ARIA:** [Public lookup for the famous trader/miner]

**User:** "look up The Mittani"
**ARIA:** [Public lookup for specified pilot]
