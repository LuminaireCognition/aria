# ESI Corporation API Capabilities Analysis

## Research Summary

**Date:** YC128.01.15
**Scope:** EVE Online ESI Corporation Endpoints
**Purpose:** Determine ARIA skill extensions for corporation management
**Context:** Horadric Acquisitions [AREAT] recently founded - CEO-level access available

---

## ESI Corporation API Overview

The ESI provides **44 corporation-related endpoints** requiring **21 unique OAuth scopes**. These fall into distinct functional categories with varying relevance to ARIA users.

---

## Endpoint Inventory by Category

### 1. Public Information (No Auth Required)

| Endpoint | Description | ARIA Value |
|----------|-------------|------------|
| `GET /corporations/{id}/` | Corp name, ticker, member count, CEO, tax rate | **HIGH** - Core identity info |
| `GET /corporations/{id}/icons/` | Corp logo URLs | Low - Cosmetic |
| `GET /corporations/{id}/alliancehistory/` | Alliance membership history | Low - Intel |
| `GET /corporations/npccorps/` | List all NPC corporations | Reference data |
| `GET /alliances/{id}/corporations/` | Corps in an alliance | Intel/Research |
| `GET /fw/leaderboards/corporations/` | FW corp rankings | Niche |

### 2. Member Management (CEO/Director Access)

**Scope Required:** `esi-corporations.read_corporation_membership.v1`, `esi-corporations.track_members.v1`, `esi-corporations.read_titles.v1`

| Endpoint | Description | ARIA Value |
|----------|-------------|------------|
| `GET /corporations/{id}/members/` | List all member character IDs | Medium - Solo irrelevant |
| `GET /corporations/{id}/members/limit/` | Max member capacity | Low |
| `GET /corporations/{id}/members/titles/` | Member title assignments | Low - Solo irrelevant |
| `GET /corporations/{id}/membertracking/` | Member login/location tracking | Low - Solo irrelevant |
| `GET /corporations/{id}/roles/` | Member role assignments | Low - Solo |
| `GET /corporations/{id}/roles/history/` | Role change audit log | Low - Solo |
| `GET /corporations/{id}/titles/` | Corp title definitions | Low - Solo |

**Assessment:** Member management endpoints are low priority for solo/small corps. May become relevant if recruiting.

### 3. Corporation Assets & Industry

**Scopes Required:** `esi-assets.read_corporation_assets.v1`, `esi-corporations.read_blueprints.v1`, `esi-industry.read_corporation_jobs.v1`

| Endpoint | Description | ARIA Value |
|----------|-------------|------------|
| `GET /corporations/{id}/assets/` | Full corp asset inventory | **HIGH** - Track corp hangars |
| `POST /corporations/{id}/assets/locations/` | Asset location coordinates | Medium - POS/structure positions |
| `POST /corporations/{id}/assets/names/` | Custom asset names | Medium - Ship names in corp hangar |
| `GET /corporations/{id}/blueprints/` | Corp BPO/BPC inventory | **HIGH** - Industry critical |
| `GET /corporations/{id}/industry/jobs/` | Manufacturing/research jobs | **HIGH** - Job tracking |

**Assessment:** Highly valuable for industry-focused operations. Direct parallel to character asset/blueprint tracking.

### 4. Corporation Finances

**Scopes Required:** `esi-wallet.read_corporation_wallets.v1`, `esi-corporations.read_divisions.v1`

| Endpoint | Description | ARIA Value |
|----------|-------------|------------|
| `GET /corporations/{id}/wallets/` | Balance for all 7 divisions | **HIGH** - Financial tracking |
| `GET /corporations/{id}/wallets/{div}/journal/` | Transaction history by division | **HIGH** - Income/expense tracking |
| `GET /corporations/{id}/wallets/{div}/transactions/` | Market transactions by division | Medium - Market restriction limits use |
| `GET /corporations/{id}/divisions/` | Division names (wallet & hangar) | Medium - Configuration info |
| `GET /corporations/{id}/shareholders/` | Corp share ownership | Low - Solo corp |

**Assessment:** Wallet and journal endpoints valuable for tracking mission income, bounties, and operational costs.

### 5. Structures & Infrastructure

**Scopes Required:** `esi-corporations.read_structures.v1`, `esi-corporations.read_starbases.v1`, `esi-corporations.read_facilities.v1`

| Endpoint | Description | ARIA Value |
|----------|-------------|------------|
| `GET /corporations/{id}/structures/` | Upwell structure list | Future - No structures yet |
| `GET /corporations/{id}/starbases/` | POS tower list | Future - No POSes |
| `GET /corporations/{id}/starbases/{id}/` | POS configuration | Future |
| `GET /corporations/{id}/facilities/` | Manufacturing/research facilities | Future - Outpost access |

**Assessment:** Future value when/if deploying structures. Not immediately relevant.

### 6. Mining Operations

**Scope Required:** `esi-industry.read_corporation_mining.v1`

| Endpoint | Description | ARIA Value |
|----------|-------------|------------|
| `GET /corporation/{id}/mining/observers/` | Mining ledger observers (structures) | Future - Requires Athanor/Tatara |
| `GET /corporation/{id}/mining/observers/{id}/` | Individual miner statistics | Future |
| `GET /corporation/{id}/mining/extractions/` | Moon extraction timers | Future - Requires refinery |

**Assessment:** Requires industrial structures. Not immediately relevant but valuable for future expansion.

### 7. Security & Diplomacy

**Scopes Required:** `esi-corporations.read_contacts.v1`, `esi-corporations.read_standings.v1`, `esi-corporations.read_medals.v1`

| Endpoint | Description | ARIA Value |
|----------|-------------|------------|
| `GET /corporations/{id}/contacts/` | Corp contact list | Medium - Diplomatic tracking |
| `GET /corporations/{id}/contacts/labels/` | Contact label definitions | Low |
| `GET /corporations/{id}/standings/` | Corp-level faction standings | **HIGH** - Mission standing tracking |
| `GET /corporations/{id}/medals/` | Medal definitions | Low - Solo |
| `GET /corporations/{id}/medals/issued/` | Issued medals | Low - Solo |

**Assessment:** Corp standings endpoint valuable for tracking standing progression at corp level.

### 8. Contracts & Markets

**Scopes Required:** `esi-contracts.read_corporation_contracts.v1`, `esi-markets.read_corporation_orders.v1`

| Endpoint | Description | ARIA Value |
|----------|-------------|------------|
| `GET /corporations/{id}/contracts/` | Corp contract list | Low - Market restriction |
| `GET /corporations/{id}/contracts/{id}/bids/` | Auction bids | Low |
| `GET /corporations/{id}/contracts/{id}/items/` | Contract contents | Low |
| `GET /corporations/{id}/orders/` | Active market orders | Low - Market restriction |
| `GET /corporations/{id}/orders/history/` | Historical orders | Low |

**Assessment:** Limited value given self-sufficiency playstyle restrictions.

### 9. Combat & Activity

**Scopes Required:** `esi-killmails.read_corporation_killmails.v1`, `esi-corporations.read_fw_stats.v1`

| Endpoint | Description | ARIA Value |
|----------|-------------|------------|
| `GET /corporations/{id}/killmails/recent/` | Recent kills/losses | Medium - Combat tracking |
| `GET /corporations/{id}/fw/stats/` | Faction warfare statistics | Niche - FW participation |

**Assessment:** Killmails could be useful for tracking mission/PvP performance.

### 10. Miscellaneous

**Scopes Required:** `esi-corporations.read_container_logs.v1`, `esi-planets.read_customs_offices.v1`

| Endpoint | Description | ARIA Value |
|----------|-------------|------------|
| `GET /corporations/{id}/containers/logs/` | Station container access logs | Low - Audit feature |
| `GET /corporations/{id}/customs_offices/` | POCO list | Future - PI infrastructure |

---

## All Required OAuth Scopes

```
esi-assets.read_corporation_assets.v1
esi-contracts.read_corporation_contracts.v1
esi-corporations.read_blueprints.v1
esi-corporations.read_contacts.v1
esi-corporations.read_container_logs.v1
esi-corporations.read_corporation_membership.v1
esi-corporations.read_divisions.v1
esi-corporations.read_facilities.v1
esi-corporations.read_fw_stats.v1
esi-corporations.read_medals.v1
esi-corporations.read_standings.v1
esi-corporations.read_starbases.v1
esi-corporations.read_structures.v1
esi-corporations.read_titles.v1
esi-corporations.track_members.v1
esi-industry.read_corporation_jobs.v1
esi-industry.read_corporation_mining.v1
esi-killmails.read_corporation_killmails.v1
esi-markets.read_corporation_orders.v1
esi-planets.read_customs_offices.v1
esi-wallet.read_corporation_wallets.v1
```

---

## Recommended ARIA Skill Extensions

### Priority 1: High Value - Immediate Implementation

| Skill | Endpoints Used | Value Proposition |
|-------|---------------|-------------------|
| `/corp-info` | Public corp info | Quick corp lookup (any corp) |
| `/corp-wallet` | Corp wallets + journal | Track ISK flow, mission income |
| `/corp-assets` | Corp assets + names | View corp hangar contents |
| `/corp-blueprints` | Corp blueprints | Industry planning with corp BPOs |
| `/corp-jobs` | Industry jobs | Track manufacturing/research |

### Priority 2: Medium Value - Phase 2

| Skill | Endpoints Used | Value Proposition |
|-------|---------------|-------------------|
| `/corp-standings` | Corp standings | Track corp-level standing gains |
| `/corp-killmails` | Recent killmails | Combat performance review |
| `/corp-status` | Combined status report | Unified corp dashboard |

### Priority 3: Future Value - When Needed

| Skill | Endpoints Used | Value Proposition |
|-------|---------------|-------------------|
| `/corp-structures` | Structures endpoint | When deploying Upwell structures |
| `/corp-mining` | Mining observers | When deploying refineries |
| `/corp-members` | Member tracking | If/when recruiting |

---

## Implementation Recommendations

### OAuth Scope Strategy

**Recommended Initial Scopes (CEO Authorization):**
```
esi-wallet.read_corporation_wallets.v1
esi-assets.read_corporation_assets.v1
esi-corporations.read_blueprints.v1
esi-industry.read_corporation_jobs.v1
esi-corporations.read_standings.v1
esi-corporations.read_divisions.v1
```

These cover the highest-value features while minimizing scope creep. Additional scopes can be added via re-authorization when needed.

### Data Architecture

**Pilot Directory Extension:**
```
pilots/{id}_{slug}/
  corporation/
    info.md           # Corp identity, CEO, tax rate
    wallet.md         # Division balances, recent journal
    assets.md         # Corp hangar inventory
    blueprints.md     # Corp BPO/BPC library
    jobs.md           # Active manufacturing/research
  ...existing files...
```

**ESI Sync Integration:**
- Add `--corp` flag to `aria-esi-sync.py`
- Sync corp data alongside character data
- Same volatility tier system applies

### Skill Design Patterns

**Follow existing `/esi-query` patterns:**
- Return JSON with `query_timestamp` and `volatility`
- Same wrapper script approach (`aria-esi corp-wallet`)
- Same error handling for missing scopes

**Example New Command: `corp-wallet`**
```
User: /corp-wallet

ARIA: [Queries corp wallet endpoints, returns formatted report]

═══════════════════════════════════════════════════════════════════
HORADRIC ACQUISITIONS [AREAT] - FINANCIAL STATUS
───────────────────────────────────────────────────────────────────
GalNet Sync: 2026-01-15 10:30 UTC

Division Balances:
  Master Wallet:     15,234,567.89 ISK
  [Other divisions as configured...]

Recent Activity (Master Wallet):
  + 1,250,000 ISK  Mission reward - Federation Navy
  +   125,000 ISK  Bounty prizes
  - 1,599,800 ISK  Corporation founding fee

───────────────────────────────────────────────────────────────────
Balance as of query time. Transactions since may not be reflected.
═══════════════════════════════════════════════════════════════════
```

---

## Context-Specific Notes

### Horadric Acquisitions [AREAT] Current State

- **Phase:** Initial Setup (Phase 3)
- **Members:** Solo (CEO only)
- **Infrastructure:** None yet (no office, no structures)
- **Market Restriction:** Self-sufficiency mode (no trading)

### Immediate Value Features

1. **Corp Wallet Tracking** - Monitor mission income flowing to corp
2. **Corp Blueprint Library** - Track BPOs/BPCs in corp hangar (when acquired)
3. **Corp Asset Management** - View items in corp hangar (when office rented)
4. **Industry Jobs** - Track corp-level manufacturing (when started)

### Deferred Features

- Member management (solo operation)
- Market orders/contracts (self-sufficiency restriction)
- Structures (no current infrastructure)
- Mining observers (no refinery)

---

## Security Considerations

### CEO-Only Scopes

Corporation ESI scopes require authorization from the **CEO character**. For Horadric Acquisitions, this is Federation Navy Suwayyah (the active pilot).

### Scope Separation

Consider separate ESI application registrations:
- **Personal scopes:** Current character-level scopes
- **Corporation scopes:** CEO-authorized corp data

This allows revoking corp access independently if needed.

### Data Sensitivity

Corporation financial data (wallet, assets) is sensitive:
- Don't expose in public channels
- Same credential security as character data
- Consider separate `credentials/corp_{corp_id}.json` file

---

## Summary Recommendation

### Phase 1 Implementation (Immediate)

1. **`/corp-info`** - Public corp lookup (no auth required)
2. **`/corp-wallet`** - Corp wallet balance and journal
3. **`/corp-assets`** - Corp hangar inventory
4. **`/corp-blueprints`** - Corp BPO/BPC library
5. **`/corp-jobs`** - Manufacturing/research job tracking
6. Update OAuth setup wizard with optional corp scopes

### Phase 2 Implementation (When Needed)

1. **`/corp-standings`** - Corp-level faction standings
2. **`/corp-killmails`** - Combat performance review
3. **`/corp-status`** - Unified dashboard combining wallet + assets + jobs

### Phase 3 Implementation (Future)

1. Structure management (when deployed)
2. Mining observer integration (when deployed)
3. Member management (if recruiting)

---

## Technical Implementation Notes

### Corporation ID Resolution

The character's corporation ID is available via:
- `GET /characters/{character_id}/` returns `corporation_id` (public, no auth)
- Can be cached as semi-stable data (changes only when joining/leaving corp)

This enables automatic corp ID resolution without requiring user input.

### Error Handling

Common corporation endpoint errors:
- **403 Forbidden:** Character lacks required role (CEO/Director)
- **404 Not Found:** Invalid corporation ID
- **520 Error:** ESI internal error (retry)

For role-restricted endpoints, clearly communicate when the active character lacks access.

### Volatility Classification

| Data Type | Volatility | Behavior |
|-----------|------------|----------|
| Corp info (name, ticker, CEO) | Stable | Cache indefinitely |
| Wallet balance | Semi-stable | Refresh on request |
| Wallet journal | Semi-stable | Append-only, refresh on request |
| Assets | Semi-stable | Refresh on request |
| Industry jobs | Semi-stable | Refresh on request |
| Structures | Semi-stable | Refresh on request |

---

*Research compiled from ESI Swagger specification at `esi.evetech.net`*
*All endpoints verified against official EVE Developers portal*
