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
argument-hint: "[pilot_name]"
injected_prerequisites:
  - .claude/skills/_shared/esi-error-handling.md
---

# ARIA Pilot Identity Module

## Command Syntax

```
/pilot           # Show authenticated pilot's full identity
/pilot me        # Same as above (explicit self-reference)
/pilot <name>    # Look up another pilot (public data only)
/pilot <id>      # Look up by character ID (public data only)
```

## Implementation

Run the `aria-esi pilot` wrapper command:

```bash
# Authenticated pilot (full data)
uv run aria-esi pilot

# Public lookup
uv run aria-esi pilot "Character Name"
uv run aria-esi pilot 2123984364
```

If ESI is unavailable, fall back to local profile data and note "Showing local profile (ESI unavailable)". Do not run CLI commands when ESI is unavailable.

## Data Sources by Query Type

| Data | Source | Self | Public |
|------|--------|------|--------|
| Character ID/Name | Credentials / ESI search | Yes | Yes |
| Corporation/Alliance | ESI public endpoint | Yes | Yes |
| Security Status | ESI public endpoint | Yes | Yes |
| Birthday | ESI public endpoint | Yes | Yes |
| Faction Alignment | Local profile.md | Yes | No |
| EVE Experience | Local profile.md | Yes | No |
| RP Level | Local profile.md | Yes | No |
| Module Tier | Local profile.md | Yes | No |
| Operational Constraints | Local profile.md | Yes | No |
| Standings | ESI authenticated | Yes | No |
| ESI Scopes Available | Credentials file | Yes | No |
| Wallet Balance | ESI authenticated | Yes | No |
| Skill Points | ESI authenticated | Yes | No |

## Hallucination Guard

Present only data returned by ESI or read from profile.md. If data is missing, state what is unavailable — do not estimate or fabricate values (especially wallet balance and skill points).

## Response Format

Use this template for self queries. For public queries, show only: name, corp, alliance, security, birthday.

```
═══════════════════════════════════════════════════════════════════
PILOT IDENTITY
───────────────────────────────────────────────────────────────────
CHARACTER:     [Name]
CHARACTER ID:  [ID]
CORPORATION:   [Corp Name] [[Ticker]]
ALLIANCE:      [Alliance or "None"]
SECURITY:      [Status]
CAPSULEER SINCE: [Date]

ARIA CONFIGURATION:
  EVE Experience:  [new/intermediate/veteran]
  RP Level:        [off/on/full]
  Module Tier:     [T1/Meta or T2]
  Faction:         [Primary Faction]

CONSTRAINTS:
  [Relevant constraints from profile]

ESI STATUS: [Connected/Not Configured]
  Scopes: [X] personal, [Y] corporation

ACCOUNT SNAPSHOT: (as of [timestamp])
  Wallet:       [X,XXX,XXX ISK]
  Skill Points: [X,XXX,XXX SP]
───────────────────────────────────────────────────────────────────
Profile: [path to profile.md]
═══════════════════════════════════════════════════════════════════
```

**For not found:** State the query and suggest checking spelling or using character ID.

**For no ESI credentials:** Show local profile data only with note that ESI setup enables live data (`uv run python .claude/scripts/aria-oauth-setup.py`).

**For ESI errors:** Show the error message and suggest retrying or checking ESI status.

## Behavior Notes

1. **Default to Self**: `/pilot` with no arguments shows authenticated pilot
2. **Data Exposure**: Clearly distinguish between public and authenticated data
3. **Timestamp Volatile Data**: Wallet/SP are volatile - always show query timestamp
4. **Profile Path**: Include profile file path for easy editing

## Cross-References

| For This | Use Instead |
|----------|-------------|
| Current location | `/esi-query location` |
| Ship roster | `/aria-status` |
| Detailed standings | `/esi-query standings` |
| Skills list | `/esi-query skills` |
| Corporation details | `/corp` |

## Reference: ESI Error Handling (injected)
<!-- prerequisite: .claude/skills/_shared/esi-error-handling.md -->
!`cat .claude/skills/_shared/esi-error-handling.md`
