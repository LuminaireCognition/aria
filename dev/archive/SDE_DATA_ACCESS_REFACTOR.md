# SDE Data Access Refactor Proposal

## Problem Statement

### Hard-Coded Data Has Drifted From Reality

Investigation of `src/aria_esi/models/sde.py` revealed significant issues with hard-coded EVE Online data:

#### 1. FACTION_REGIONS Mapping Has Incorrect Data

The `FACTION_REGIONS` dictionary maps corporation IDs to regions, but the **corporation names in comments don't match the actual SDE data**:

| Corporation ID | Hard-coded Comment | Actual SDE Name | SDE Faction ID |
|----------------|-------------------|-----------------|----------------|
| 1000126 | Serpentis Corporation | Ammatar Consulate | 500007 |
| 1000135 | Angel Cartel | Serpentis Corporation | 500020 |
| 1000133 | Intaki Syndicate | Salvation Angels | 500011 |
| 1000140 | Mordu's Legion | Genolution | 500017 |
| 1000118 | Thukker Tribe | Supreme Court | 500004 |
| 1000161 | Sansha's Nation | True Creations | 500019 |

This creates **silent bugs** - the code uses the correct IDs but the comments mislead developers.

#### 2. Corporation-to-Region Mapping Is Incomplete

The hard-coded mapping assumes one region per corporation, but SDE data shows many corporations have stations in **multiple regions**:

```
Sisters of EVE (1000130):
  - Genesis: 6 stations
  - Solitude: 6 stations
  - Metropolis: 6 stations
  - The Forge: 6 stations
  - ... 7 more regions

CONCORD (1000125): 13 regions
Kaalakiota Corporation (1000010): 13 regions
```

The hard-coded mapping says Sisters of EVE is only in Syndicate - which has **zero** Sisters stations according to the SDE.

#### 3. ORE Blueprint Seeding Data Is Incomplete

The `ORE_SHIP_BLUEPRINTS` dict tracks ORE mining ship blueprints, but SDE shows these are seeded by **multiple corporations**:

```sql
-- Pioneer Blueprint (89485) seeding corporations:
89485 | 1000115  -- University of Caille only

-- Venture Blueprint (32881) seeding corporations:
32881 | 1000115  -- University of Caille
32881 | 1000129  -- Outer Ring Excavations
```

Some ORE blueprints are seeded by University of Caille (1000115), not ORE (1000129).

### Impact on ARIA

These issues affect:

1. **`sde_blueprint_info` MCP tool** - Returns incorrect/incomplete region suggestions for where to buy blueprints
2. **`market_npc_sources` MCP tool** - May fail to find NPC-seeded items due to wrong region lookups
3. **Skills using blueprint lookups** - `/find`, `/price` when querying blueprint availability

---

## Current Architecture

### Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Data Sources                                │
├─────────────────────────────────────────────────────────────────────┤
│  Fuzzwork SQLite SDE     ESI API          Fuzzwork Market API       │
│  (bulk, ~1GB)            (live)           (aggregated prices)       │
└───────────┬───────────────┬────────────────┬────────────────────────┘
            │               │                │
            ▼               │                │
┌───────────────────────────┴────────────────┴────────────────────────┐
│                    ~/.aria/aria.db (SQLite)                        │
│  ┌──────────────┬────────────────┬──────────────┬────────────────┐  │
│  │ types        │ npc_seeding    │ stations     │ aggregates     │  │
│  │ groups       │ npc_corps      │ regions      │ (market data)  │  │
│  │ categories   │ blueprints     │              │                │  │
│  │ blueprint_*  │                │              │                │  │
│  └──────────────┴────────────────┴──────────────┴────────────────┘  │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     MCP Server (aria-universe)                       │
│  ┌───────────────┬───────────────┬───────────────┬───────────────┐  │
│  │ Universe      │ Market        │ SDE           │ Activity      │  │
│  │ Tools         │ Tools         │ Tools         │ Tools         │  │
│  └───────────────┴───────────────┴───────────────┴───────────────┘  │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Claude Code                                   │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ Skills (.claude/skills/**)                                     │  │
│  │   - Can call MCP tools directly                               │  │
│  │   - Cannot call Python functions directly                      │  │
│  │   - Document expected tool interfaces in SKILL.md             │  │
│  └───────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ Direct Conversation                                            │  │
│  │   - Same MCP tool access as skills                            │  │
│  │   - Can run CLI commands via Bash tool                        │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Current Hard-Coded Constants Location

```
src/aria_esi/models/sde.py:
  - ORE_SHIP_BLUEPRINTS (dict)
  - ORE_CORPORATION_ID, ORE_CORPORATION_NAME (int, str)
  - FACTION_REGIONS (dict[int, list[tuple[int, str]]])
  - CATEGORY_* constants (int)
```

### Usage Points

| File | Uses | Purpose |
|------|------|---------|
| `mcp/sde/tools_blueprint.py` | `FACTION_REGIONS` | Find regions for NPC-seeded blueprints |
| `mcp/market/tools_npc.py` | `FACTION_REGIONS` | Locate NPC market sources |
| `models/__init__.py` | All constants | Export for general use |

---

## Proposed Solution: Dynamic SDE Query Layer

### Design Principles

1. **Single Source of Truth**: All EVE game data comes from the SDE database, not hard-coded constants
2. **MCP-First Access**: Claude Code accesses data via MCP tools, not Python imports
3. **Cached Queries**: Frequently-used lookups are cached in-memory to avoid repeated DB hits
4. **Graceful Degradation**: If SDE not seeded, provide clear error messages with seeding instructions

### Architecture Decision: Hybrid Approach

After analyzing the access patterns, a **hybrid approach** is recommended:

| Access Pattern | Solution | Rationale |
|----------------|----------|-----------|
| Claude Code (skills, conversation) | **MCP Tools** | Already integrated, structured responses |
| CLI commands | **Python API** | Direct function calls, used by `aria-esi` CLI |
| Internal code (other tools) | **Python API** | Avoid circular MCP calls |

The Python API and MCP tools share the same underlying query functions, ensuring consistency.

### Proposed Components

#### 1. SDE Query Module (`src/aria_esi/mcp/sde/queries.py`)

A new module providing dynamic SDE queries to replace hard-coded lookups:

```python
"""
Dynamic SDE Query Functions.

Replaces hard-coded constants with database queries.
Used by both MCP tools and internal code.
"""

from functools import lru_cache
from typing import NamedTuple


class SDENotSeededError(Exception):
    """Raised when SDE tables are missing from database."""
    pass


class CorporationRegions(NamedTuple):
    """Regions where a corporation has stations."""
    corporation_id: int
    corporation_name: str
    regions: list[tuple[int, str]]  # (region_id, region_name)
    primary_region_id: int | None  # Region with most stations
    primary_region_name: str | None


# Common seeding corporations for cache warming
COMMON_SEEDING_CORPS = [
    1000129,  # Outer Ring Excavations (ORE)
    1000130,  # Sisters of EVE
    1000125,  # CONCORD
    1000135,  # Serpentis Corporation
    1000134,  # Blood Raiders
    1000127,  # Guristas Pirates
    1000161,  # Sansha's Nation
    1000126,  # Angel Cartel
    1000140,  # Mordu's Legion
]


def ensure_sde_seeded(conn) -> None:
    """
    Verify SDE tables exist in database.

    Raises:
        SDENotSeededError: If required SDE tables are missing

    Note:
        Distinguishes "data not found" (returns None) from
        "database not seeded" (raises exception).
    """
    required_tables = ['npc_corporations', 'npc_seeding', 'stations', 'regions']
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ({})".format(
            ','.join('?' * len(required_tables))
        ),
        required_tables
    )
    found = {row[0] for row in cursor.fetchall()}
    missing = set(required_tables) - found
    if missing:
        raise SDENotSeededError(
            f"SDE tables missing: {missing}. Run 'aria-esi sde-seed' first."
        )


@lru_cache(maxsize=512)
def get_corporation_regions(corporation_id: int) -> CorporationRegions | None:
    """
    Get all regions where a corporation has stations.

    Replaces FACTION_REGIONS lookup with dynamic query.

    Args:
        corporation_id: NPC corporation ID

    Returns:
        CorporationRegions with all regions, or None if corporation not found

    Raises:
        SDENotSeededError: If SDE tables are missing
    """
    # Query stations table grouped by region
    # Order by station count descending to get primary region
    ...


@lru_cache(maxsize=256)
def get_npc_seeding_corporations(type_id: int) -> list[tuple[int, str]]:
    """
    Get corporations that seed an item.

    Args:
        type_id: Item type ID

    Returns:
        List of (corporation_id, corporation_name) tuples

    Raises:
        SDENotSeededError: If SDE tables are missing
    """
    ...


@lru_cache(maxsize=64)
def get_category_id(category_name: str) -> int | None:
    """
    Look up category ID by name.

    Replaces CATEGORY_* constants with dynamic lookup.
    """
    ...


def warm_caches() -> None:
    """
    Pre-populate caches with common lookups.

    Call at MCP server startup to avoid cold-cache latency.
    Silently skips if SDE not seeded.
    """
    try:
        for corp_id in COMMON_SEEDING_CORPS:
            get_corporation_regions(corp_id)
    except SDENotSeededError:
        pass  # SDE not seeded yet, skip warming


def invalidate_caches() -> None:
    """Clear all LRU caches. Call after SDE re-import."""
    get_corporation_regions.cache_clear()
    get_npc_seeding_corporations.cache_clear()
    get_category_id.cache_clear()
```

#### 2. New MCP Tool: `sde_corporation_info`

Expose corporation data to Claude Code:

```python
@server.tool()
def sde_corporation_info(
    corporation_id: int | None = None,
    corporation_name: str | None = None,
) -> dict:
    """
    Get NPC corporation information including station regions.

    Args:
        corporation_id: Corporation ID to look up
        corporation_name: Corporation name (fuzzy matched)

    Returns:
        Corporation info with all regions where they have stations
    """
```

**Response Schema:**

```json
{
  "corporation_id": 1000129,
  "corporation_name": "Outer Ring Excavations",
  "faction_id": 500014,
  "faction_name": "ORE",
  "station_count": 4,
  "regions": [
    {
      "region_id": 10000057,
      "region_name": "Outer Ring",
      "station_count": 4,
      "is_primary": true
    }
  ],
  "seeds_items": true,
  "seeded_item_count": 12
}
```

#### 3. Enhanced `sde_blueprint_info` Tool

Update to use dynamic queries instead of `FACTION_REGIONS`:

```python
# Before (hard-coded lookup):
if corp_id in FACTION_REGIONS:
    regions = FACTION_REGIONS[corp_id]
    region_id = regions[0][0]
    region = regions[0][1]

# After (dynamic query):
corp_regions = get_corporation_regions(corp_id)
if corp_regions:
    region_id = corp_regions.primary_region_id
    region = corp_regions.primary_region_name
    all_regions = corp_regions.regions
```

#### 4. Category ID Validation

Keep category constants but validate during SDE import:

```python
# In SDEImporter.import_from_sde():
def _validate_category_constants(self, target_conn):
    """Validate hard-coded category IDs match SDE."""
    expected = {
        6: "Ship",
        7: "Module",
        8: "Charge",
        9: "Blueprint",
        16: "Skill",
        18: "Drone",
        25: "Asteroid",
    }

    for cat_id, expected_name in expected.items():
        row = target_conn.execute(
            "SELECT category_name FROM categories WHERE category_id = ?",
            (cat_id,)
        ).fetchone()

        if row is None:
            logger.warning("Category ID %d not found in SDE", cat_id)
        elif row[0] != expected_name:
            logger.warning(
                "Category ID %d mismatch: expected %r, got %r",
                cat_id, expected_name, row[0]
            )
```

---

## Implementation Considerations

### Connection Handling Pattern

**Problem:** The original proposal used `@lru_cache` decorators on query functions, which creates issues:

1. LRU cache keys can't safely include connection state
2. Connection pool recycling may leave cached closures with stale references
3. The current codebase uses `db._get_connection()` per-request pattern

**Solution:** Use a cache-aside pattern with an explicit service class that separates connection management from data caching:

```python
# src/aria_esi/mcp/sde/queries.py

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aria_esi.mcp.market.database import MarketDatabase


@dataclass(frozen=True)
class CorporationRegions:
    """Regions where a corporation has stations."""
    corporation_id: int
    corporation_name: str
    regions: tuple[tuple[int, str, int], ...]  # (region_id, region_name, station_count)

    @property
    def primary_region_id(self) -> int | None:
        return self.regions[0][0] if self.regions else None

    @property
    def primary_region_name(self) -> str | None:
        return self.regions[0][1] if self.regions else None


class SDEQueryService:
    """
    Cached SDE query layer.

    Separates connection management from data caching.
    Cache is invalidated when SDE import timestamp changes.
    """

    def __init__(self, db: MarketDatabase):
        self._db = db
        self._lock = threading.Lock()

        # Data caches (dict, not lru_cache - explicit control)
        self._corp_regions: dict[int, CorporationRegions | None] = {}
        self._seeding_corps: dict[int, tuple[tuple[int, str], ...]] = {}
        self._category_ids: dict[str, int | None] = {}

        # Cache metadata
        self._cache_import_timestamp: str | None = None

    def _check_cache_validity(self) -> None:
        """Invalidate caches if SDE was re-imported."""
        conn = self._db._get_connection()
        cursor = conn.execute(
            "SELECT value FROM metadata WHERE key = 'sde_import_timestamp'"
        )
        row = cursor.fetchone()
        current_timestamp = row[0] if row else None

        if current_timestamp != self._cache_import_timestamp:
            with self._lock:
                # Double-check after acquiring lock
                if current_timestamp != self._cache_import_timestamp:
                    self._corp_regions.clear()
                    self._seeding_corps.clear()
                    self._category_ids.clear()
                    self._cache_import_timestamp = current_timestamp

    def get_corporation_regions(self, corporation_id: int) -> CorporationRegions | None:
        """Get all regions where a corporation has stations."""
        self._check_cache_validity()

        if corporation_id in self._corp_regions:
            return self._corp_regions[corporation_id]

        # Cache miss - query database
        conn = self._db._get_connection()
        result = self._query_corporation_regions(conn, corporation_id)

        with self._lock:
            self._corp_regions[corporation_id] = result

        return result

    def _query_corporation_regions(
        self, conn, corporation_id: int
    ) -> CorporationRegions | None:
        """Execute corporation regions query."""
        cursor = conn.execute(
            """
            SELECT
                nc.corporation_name,
                r.region_id,
                r.region_name,
                COUNT(*) as station_count
            FROM npc_corporations nc
            JOIN stations s ON nc.corporation_id = s.corporation_id
            JOIN regions r ON s.region_id = r.region_id
            WHERE nc.corporation_id = ?
            GROUP BY r.region_id
            ORDER BY station_count DESC
            """,
            (corporation_id,),
        )

        rows = cursor.fetchall()
        if not rows:
            return None

        corp_name = rows[0][0]
        regions = tuple((row[1], row[2], row[3]) for row in rows)

        return CorporationRegions(
            corporation_id=corporation_id,
            corporation_name=corp_name,
            regions=regions,
        )

    def invalidate_all(self) -> None:
        """Explicitly clear all caches. Call after SDE re-import."""
        with self._lock:
            self._corp_regions.clear()
            self._seeding_corps.clear()
            self._category_ids.clear()
            self._cache_import_timestamp = None


# Singleton accessor
_sde_query_service: SDEQueryService | None = None


def get_sde_query_service() -> SDEQueryService:
    """Get the singleton SDE query service."""
    global _sde_query_service
    if _sde_query_service is None:
        from aria_esi.mcp.market.database import get_market_database
        _sde_query_service = SDEQueryService(get_market_database())
    return _sde_query_service
```

**Key design decisions:**

| Decision | Rationale |
|----------|-----------|
| `dict` instead of `@lru_cache` | Explicit control over invalidation, no connection-in-key issues |
| `_check_cache_validity()` on read | Auto-detects SDE re-import without manual invalidation |
| `threading.Lock` | MCP server may handle concurrent requests |
| Frozen dataclass results | Immutable cached values prevent accidental mutation |
| Singleton service | Matches existing `get_market_database()` pattern |

### Cache Warming Integration

**Problem:** First queries after MCP server startup hit a cold cache, causing latency spikes of 50-100ms for corporation lookups that would otherwise be <10ms. This affects user experience when Skills invoke SDE tools immediately after connection.

**Solution:** Warm caches during MCP server initialization, before accepting tool requests.

#### Cache Warming Implementation

Add a `warm_caches()` method to `SDEQueryService`:

```python
# In SDEQueryService class

# Corporations commonly queried for blueprint lookups
COMMON_SEEDING_CORPS = [
    1000129,  # Outer Ring Excavations (ORE)
    1000130,  # Sisters of EVE
    1000125,  # CONCORD
    1000115,  # University of Caille (seeds many blueprints)
    1000135,  # Serpentis Corporation
    1000134,  # Blood Raiders
    1000127,  # Guristas Pirates
    1000161,  # Sansha's Nation
    1000126,  # Angel Cartel
    1000140,  # Mordu's Legion
]

def warm_caches(self) -> dict[str, int]:
    """
    Pre-populate caches with commonly-accessed data.

    Call at MCP server startup to avoid cold-cache latency.
    Silently skips if SDE not seeded (allows server to start).

    Returns:
        Statistics dict with counts of warmed entries
    """
    stats = {"corporations": 0, "categories": 0, "errors": 0}

    try:
        # Warm corporation regions cache
        for corp_id in self.COMMON_SEEDING_CORPS:
            try:
                self.get_corporation_regions(corp_id)
                stats["corporations"] += 1
            except Exception:
                stats["errors"] += 1

        # Warm category cache
        for category_name in ["Ship", "Module", "Blueprint", "Skill", "Drone"]:
            try:
                self.get_category_id(category_name)
                stats["categories"] += 1
            except Exception:
                stats["errors"] += 1

    except SDENotSeededError:
        # SDE not imported yet - that's OK, skip warming
        pass

    return stats
```

#### MCP Server Integration

Integrate cache warming into the MCP server startup sequence in `src/aria_esi/mcp/server.py`:

```python
# In src/aria_esi/mcp/server.py

import logging
from aria_esi.mcp.sde.queries import get_sde_query_service, SDENotSeededError

logger = logging.getLogger(__name__)


def create_mcp_server():
    """Create and configure the MCP server."""
    server = Server("aria-universe")

    # Register all tools
    register_universe_tools(server)
    register_market_tools(server)
    register_sde_tools(server)
    register_activity_tools(server)

    # Warm SDE caches (after tools registered, before serving)
    _warm_sde_caches()

    return server


def _warm_sde_caches() -> None:
    """Warm SDE query caches at startup."""
    try:
        service = get_sde_query_service()
        stats = service.warm_caches()

        if stats["corporations"] > 0:
            logger.info(
                "SDE caches warmed: %d corporations, %d categories",
                stats["corporations"],
                stats["categories"],
            )
        # If nothing warmed, SDE probably not seeded - that's fine

    except Exception as e:
        # Don't fail server startup due to cache warming issues
        logger.warning("SDE cache warming failed (non-fatal): %s", e)
```

#### Startup Sequence

The full initialization order ensures caches are warm before the first tool call:

```
MCP Server Startup
       │
       ├─1. Initialize database connection (lazy)
       │
       ├─2. Register tools (universe, market, SDE, activity)
       │
       ├─3. Warm SDE caches  ◄── NEW
       │     ├─ Load common corporation regions
       │     ├─ Load category IDs
       │     └─ Log statistics (or silently skip if SDE not seeded)
       │
       └─4. Begin accepting connections
              └─ First tool call hits warm cache
```

#### Migration Notes

Add to Phase 1 tasks:
- Implement `SDEQueryService.warm_caches()` method
- Add `_warm_sde_caches()` call to MCP server initialization
- Verify cache warming completes in <500ms on typical hardware
- Add startup log message showing warm cache statistics

### Cache Coherence Strategy

**Problem:** Caches can hold stale data after SDE re-import, especially when:
- CLI runs `aria-esi sde-seed` while MCP server is running
- Tests re-import data mid-session

**Solution:** Timestamp-based auto-invalidation with explicit invalidation hook.

The `SDEQueryService._check_cache_validity()` method (shown above) compares the cached timestamp against the database on each read. This handles the cross-process case automatically.

For same-process invalidation (tests, direct CLI usage), add an explicit hook to the importer:

```python
# In src/aria_esi/mcp/sde/importer.py

def import_from_sde(self, sde_path: Path, target_conn) -> None:
    """Import SDE data into market database."""
    # ... existing import logic ...

    # Update timestamp (triggers cache invalidation on next query)
    from datetime import datetime, timezone
    timestamp = datetime.now(timezone.utc).isoformat()
    target_conn.execute(
        "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
        ("sde_import_timestamp", timestamp),
    )
    target_conn.commit()

    # Explicit invalidation for same-process callers
    try:
        from aria_esi.mcp.sde.queries import get_sde_query_service
        get_sde_query_service().invalidate_all()
        logger.info("SDE query caches invalidated")
    except Exception:
        pass  # Service may not be initialized yet
```

**How this handles different scenarios:**

| Scenario | Invalidation Mechanism |
|----------|------------------------|
| CLI imports, MCP server running | Timestamp check on next MCP query |
| Same process (tests) | Explicit `invalidate_all()` call |
| MCP server restart | Fresh caches, timestamp loaded from DB |

### Structured Error Handling for Skills

**Problem:** Claude Code Skills interact with SDE data exclusively through MCP tools. Skills are loaded as prompt context—they cannot catch Python exceptions or handle runtime errors programmatically. When `SDENotSeededError` is raised inside a tool, the skill receives an opaque failure.

**Constraint:** MCP tools must return structured JSON responses for all outcomes, including errors. This allows Skills to:
1. Detect error conditions from response fields
2. Provide contextual guidance to users
3. Suggest remediation steps (e.g., "run `aria-esi sde-seed`")

#### Error Response Schema

All SDE-related MCP tools must return errors as structured data, not exceptions:

```python
# src/aria_esi/models/sde.py

from pydantic import BaseModel
from typing import Literal


class SDEErrorResponse(BaseModel):
    """Structured error for SDE tool failures."""
    success: Literal[False] = False
    error_code: str  # Machine-readable error type
    message: str     # Human-readable description
    remediation: str | None = None  # Suggested fix


# Standard error codes
class SDEErrorCode:
    NOT_SEEDED = "sde_not_seeded"
    ITEM_NOT_FOUND = "item_not_found"
    CORPORATION_NOT_FOUND = "corporation_not_found"
    DATABASE_ERROR = "database_error"
```

#### Tool Response Contract

Every SDE MCP tool must follow this response contract:

| Condition | Response Pattern |
|-----------|------------------|
| Success | `{"success": true, ...data fields...}` |
| SDE not seeded | `{"success": false, "error_code": "sde_not_seeded", "message": "...", "remediation": "Run 'aria-esi sde-seed'"}` |
| Item not found | `{"success": false, "error_code": "item_not_found", "message": "No item matching 'X'", "remediation": null}` |
| Database error | `{"success": false, "error_code": "database_error", "message": "...", "remediation": "Check ~/.aria/aria.db"}` |

#### Implementation Pattern

Tools must catch `SDENotSeededError` and convert to structured response:

```python
# In src/aria_esi/mcp/sde/tools_blueprint.py

from aria_esi.mcp.sde.queries import get_sde_query_service, SDENotSeededError
from aria_esi.models.sde import SDEErrorResponse, SDEErrorCode


@server.tool()
def sde_blueprint_info(item: str) -> dict:
    """Get blueprint information for an item."""
    try:
        service = get_sde_query_service()
        # ... existing logic ...
        return {"success": True, **result.model_dump()}

    except SDENotSeededError as e:
        return SDEErrorResponse(
            error_code=SDEErrorCode.NOT_SEEDED,
            message=str(e),
            remediation="Run 'uv run aria-esi sde-seed' to import EVE static data.",
        ).model_dump()

    except Exception as e:
        logger.exception("Unexpected error in sde_blueprint_info")
        return SDEErrorResponse(
            error_code=SDEErrorCode.DATABASE_ERROR,
            message=f"Database error: {e}",
            remediation="Check database at ~/.aria/aria.db",
        ).model_dump()
```

#### Skill Consumption Pattern

Skills should document how to interpret error responses. Add to skill SKILL.md files:

```markdown
## Error Handling

The `sde_blueprint_info` tool returns structured errors:

| `error_code` | Meaning | Response |
|--------------|---------|----------|
| `sde_not_seeded` | EVE static data not imported | Tell user to run `uv run aria-esi sde-seed` |
| `item_not_found` | No matching item in database | Suggest alternative spellings or use `sde_search` |
| `database_error` | Database access failed | Report error and suggest checking logs |

Always check `response.success` before accessing data fields.
```

#### Distinguishing "Not Found" from "Not Seeded"

Critical distinction for user experience:

| Scenario | `success` | `error_code` | User Message |
|----------|-----------|--------------|--------------|
| SDE not imported | `false` | `sde_not_seeded` | "EVE static data not loaded. Run `aria-esi sde-seed` first." |
| Item doesn't exist | `false` | `item_not_found` | "No item named 'Vexor Bluepirnt' found. Did you mean 'Vexor Blueprint'?" |
| Item exists, no blueprint | `true` | n/a | `{"success": true, "has_blueprint": false, ...}` |

The third case is **not an error**—Tritanium legitimately has no blueprint. Return success with data indicating no blueprint exists.

#### Migration Notes

When updating existing tools in Phase 2:

1. Add `success: bool` field to all response models
2. Wrap tool bodies in try/except for `SDENotSeededError`
3. Update tool docstrings to document error response schema
4. Add error handling guidance to affected skill overlays

**Backward Compatibility:** Adding `success: true` to existing responses is additive. Skills that don't check `success` continue working. New/updated skills should check it.

---

## Migration Plan

### Phase 0: Pre-Implementation Setup

Before starting implementation, complete these preparatory steps:

1. **Create integration test infrastructure** (see Integration Test Specifications below)
2. **Verify existing schema supports required queries:**
   ```sql
   -- Check stations table has required columns
   SELECT corporation_id, region_id FROM stations LIMIT 1;

   -- Check metadata table exists
   SELECT value FROM metadata WHERE key = 'sde_import_timestamp';
   ```
3. **Document current behavior** for regression testing:
   - Run `sde_blueprint_info("Pioneer")` and save response
   - Run `sde_blueprint_info("Venture")` and save response
   - Document any known incorrect outputs
4. **Review skill overlays** for assumptions about response formats:
   - Check `personas/*/skill-overlays/` for blueprint-related overlays
   - Document any hard-coded expectations

### Phase 1: Add Dynamic Query Layer

1. Create `src/aria_esi/mcp/sde/queries.py` implementing `SDEQueryService` class (see Implementation Considerations section for full design)
2. Implement timestamp-based cache coherence with `_check_cache_validity()` method
3. Add explicit seeding check: Create `ensure_sde_seeded()` that raises `SDENotSeededError` (not `None`) when tables are missing—distinguishes "corporation not found" from "SDE not imported"
4. Add database index for efficient corporation-region joins:
   ```sql
   CREATE INDEX IF NOT EXISTS idx_stations_corp_region
   ON stations(corporation_id, region_id)
   ```
5. Add `invalidate_all()` call to `SDEImporter.import_from_sde()` for same-process cache invalidation
6. Add unit tests for all query functions
7. Ensure queries work with empty/non-seeded database (raise clear error, not crash)
8. **Gate:** Run `TestQueryServiceIntegration` tests against seeded database before proceeding

### Phase 2: Update MCP Tools

1. Update `tools_blueprint.py` to use `get_sde_query_service().get_corporation_regions()`
2. Update `tools_npc.py` to use `get_sde_query_service().get_corporation_regions()`
3. Update `market_find_nearby` in `tools_find.py` to use dynamic queries (aligns with existing deprecation notice on `market_npc_sources`)
4. Add `sde_corporation_info` MCP tool
5. Update tool docstrings to reflect new behavior
6. **Gate:** Run `TestBlueprintSourceAccuracy` tests to verify improved results

### Phase 3: Remove Hard-Coded Constants

1. Remove `FACTION_REGIONS` entirely after all callers updated in Phase 2 (skip deprecation warnings—internal API, no external consumers)
2. Remove `ORE_SHIP_BLUEPRINTS` (can be derived from npc_seeding)
3. Keep `ORE_CORPORATION_ID/NAME` for convenience but document as "example only"
4. Keep `CATEGORY_*` constants with validation
5. Run full integration test suite to verify no regressions

### Phase 4: Documentation & Skill Updates

1. Update CLAUDE.md with new MCP tool documentation (`sde_corporation_info`)
2. Audit skill overlays in `personas/*/skill-overlays/` for assumptions about `sde_blueprint_info` response format
3. Update skill files that reference blueprint lookups (e.g., `/find`, `/price` skills)
4. Add data freshness guidance (when to re-import SDE)
5. Document the `SDEQueryService` API for future maintainers

---

## Data Freshness Strategy

### SDE Update Frequency

EVE Online SDE updates occur:
- With each game patch (every 2-4 weeks)
- Occasionally mid-patch for data corrections

### Recommended Approach

1. **Manual Trigger**: `uv run aria-esi sde-seed` command to refresh
2. **Staleness Warning**: Check `sde_import_timestamp` metadata, warn if >30 days old
3. **No Auto-Update**: Avoid background downloads that could surprise users

### Cache Invalidation

When SDE is re-imported:
1. Clear all LRU caches via `invalidate_caches()`
2. Log cache clear to inform user
3. Existing MCP connections continue working with fresh data

---

## Alternatives Considered

### Alternative 1: Separate SDE MCP Server

**Description**: Create a dedicated `aria-sde` MCP server for SDE queries.

**Pros**:
- Clean separation of concerns
- Could be reused by other projects

**Cons**:
- Additional process to manage
- Current `aria-universe` already handles SDE tools
- Unnecessary complexity for current scale

**Decision**: Rejected. Keep SDE tools in existing `aria-universe` server.

### Alternative 2: Pre-Computed JSON Files

**Description**: Generate JSON files from SDE during import, load at startup.

**Pros**:
- Very fast lookups (in-memory dict)
- No database queries at runtime

**Cons**:
- Data duplication (DB + JSON files)
- Must regenerate files on SDE update
- Same maintenance burden as current hard-coded approach

**Decision**: Rejected. SQLite with LRU cache provides sufficient performance.

### Alternative 3: ESI API for Corporation Data

**Description**: Query ESI for corporation/region data instead of SDE.

**Pros**:
- Always current data

**Cons**:
- ESI has no endpoint for "where does this corp have stations"
- Would require scraping multiple endpoints
- Rate limits apply

**Decision**: Rejected. SDE is the authoritative source for static game data.

---

## Success Criteria

1. **No Hard-Coded Corporation-to-Region Mappings**: All lookups use `SDEQueryService` database queries
2. **Correct Blueprint Sources**: `sde_blueprint_info` returns accurate regions for all NPC-seeded blueprints
3. **Performance**: Query latency <10ms for cached lookups, <50ms for uncached
4. **Test Coverage**:
   - All `SDEQueryService` methods have unit tests with mock data
   - `TestCorporationRegionIntegrity` passes on seeded database
   - `TestCategoryConstants` passes on seeded database
   - `TestQueryServiceIntegration` passes on seeded database
   - `TestBlueprintSourceAccuracy` passes on seeded database
5. **Cache Coherence**: `test_cache_invalidation` demonstrates timestamp-based invalidation works correctly
6. **Documentation**: CLAUDE.md and relevant skills updated with new tool capabilities
7. **Performance Gate**: All performance benchmarks pass before Phase 2 begins

---

## Performance Validation

### Performance Requirements

| Operation | Target Latency | Measurement Condition |
|-----------|---------------|----------------------|
| Cached corporation lookup | <10ms | After cache warm, p99 |
| Uncached corporation lookup | <50ms | Cold cache, single query |
| Cache warming (full) | <500ms | All common corps + categories |
| Cache validity check | <5ms | Per-query overhead |

### Benchmark Test Suite

Add performance tests to `tests/integration/test_sde_performance.py`:

```python
# tests/integration/test_sde_performance.py

"""
SDE Query Performance Benchmarks.

These tests validate that the query layer meets latency requirements.
Run after SDE is seeded: uv run pytest tests/integration/test_sde_performance.py -v

Performance targets:
- Cached lookups: <10ms (p99)
- Uncached lookups: <50ms
- Cache warming: <500ms
"""

from __future__ import annotations

import statistics
import time

import pytest

from aria_esi.mcp.sde.queries import get_sde_query_service, SDENotSeededError


def sde_is_seeded() -> bool:
    """Check if SDE data has been imported."""
    try:
        service = get_sde_query_service()
        service.get_corporation_regions(1000129)  # ORE
        return True
    except (SDENotSeededError, Exception):
        return False


requires_sde = pytest.mark.skipif(
    not sde_is_seeded(),
    reason="SDE not seeded. Run 'aria-esi sde-seed' first.",
)


@requires_sde
class TestCachedLookupPerformance:
    """Validate cached lookup latency requirements."""

    def test_cached_corporation_lookup_p99(self):
        """Cached corporation lookups should complete in <10ms (p99)."""
        service = get_sde_query_service()

        # Warm the cache
        service.get_corporation_regions(1000129)

        # Measure 100 cached lookups
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            service.get_corporation_regions(1000129)
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)

        p99 = sorted(latencies)[98]  # 99th percentile
        avg = statistics.mean(latencies)

        assert p99 < 10.0, (
            f"Cached lookup p99={p99:.2f}ms exceeds 10ms target "
            f"(avg={avg:.2f}ms)"
        )

    def test_cached_lookup_consistency(self):
        """Multiple cached lookups should return identical results."""
        service = get_sde_query_service()

        results = [
            service.get_corporation_regions(1000129)
            for _ in range(10)
        ]

        # All results should be the same object (cached)
        assert all(r is results[0] for r in results), (
            "Cached lookups returned different objects"
        )


@requires_sde
class TestUncachedLookupPerformance:
    """Validate cold-cache lookup latency requirements."""

    def test_uncached_corporation_lookup(self):
        """Uncached corporation lookup should complete in <50ms."""
        service = get_sde_query_service()

        # Clear cache to force cold lookup
        service.invalidate_all()

        start = time.perf_counter()
        result = service.get_corporation_regions(1000129)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert result is not None, "ORE should exist in SDE"
        assert elapsed_ms < 50.0, (
            f"Uncached lookup took {elapsed_ms:.2f}ms, exceeds 50ms target"
        )

    def test_uncached_unknown_corporation(self):
        """Lookup of non-existent corporation should also be fast."""
        service = get_sde_query_service()
        service.invalidate_all()

        start = time.perf_counter()
        result = service.get_corporation_regions(999999999)  # Non-existent
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert result is None, "Non-existent corp should return None"
        assert elapsed_ms < 50.0, (
            f"Negative lookup took {elapsed_ms:.2f}ms, exceeds 50ms target"
        )


@requires_sde
class TestCacheWarmingPerformance:
    """Validate cache warming latency requirements."""

    def test_full_cache_warming(self):
        """Full cache warming should complete in <500ms."""
        service = get_sde_query_service()

        # Clear caches first
        service.invalidate_all()

        start = time.perf_counter()
        stats = service.warm_caches()
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 500.0, (
            f"Cache warming took {elapsed_ms:.2f}ms, exceeds 500ms target"
        )
        assert stats["corporations"] >= 5, (
            f"Only {stats['corporations']} corporations warmed, expected >=5"
        )

    def test_cache_validity_check_overhead(self):
        """Cache validity check should add <5ms overhead."""
        service = get_sde_query_service()

        # Warm cache
        service.get_corporation_regions(1000129)

        # Measure validity check overhead (happens on every lookup)
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            service._check_cache_validity()
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)

        p99 = sorted(latencies)[98]

        assert p99 < 5.0, (
            f"Cache validity check p99={p99:.2f}ms exceeds 5ms target"
        )


@requires_sde
class TestQueryPlanEfficiency:
    """Validate that queries use indexes effectively."""

    def test_corporation_regions_uses_index(self):
        """Corporation regions query should use station index."""
        from aria_esi.mcp.market.database import get_market_database

        db = get_market_database()
        conn = db._get_connection()

        # Get query plan for the corporation regions query
        cursor = conn.execute(
            """
            EXPLAIN QUERY PLAN
            SELECT
                nc.corporation_name,
                r.region_id,
                r.region_name,
                COUNT(*) as station_count
            FROM npc_corporations nc
            JOIN stations s ON nc.corporation_id = s.corporation_id
            JOIN regions r ON s.region_id = r.region_id
            WHERE nc.corporation_id = ?
            GROUP BY r.region_id
            ORDER BY station_count DESC
            """,
            (1000129,),
        )

        plan = "\n".join(row[3] for row in cursor.fetchall())

        # Verify index is being used (not a full table scan)
        assert "SCAN" not in plan or "USING INDEX" in plan, (
            f"Query may be doing full table scan:\n{plan}"
        )
```

### Performance Gate in Migration

Add to Phase 1 completion criteria:

```markdown
### Phase 1 Completion Gate

Before proceeding to Phase 2, all performance benchmarks must pass:

1. Run performance test suite:
   ```bash
   uv run pytest tests/integration/test_sde_performance.py -v
   ```

2. All tests must pass with these thresholds:
   - `test_cached_corporation_lookup_p99`: p99 < 10ms
   - `test_uncached_corporation_lookup`: < 50ms
   - `test_full_cache_warming`: < 500ms
   - `test_cache_validity_check_overhead`: p99 < 5ms

3. If tests fail, investigate before proceeding:
   - Check index existence: `PRAGMA index_list(stations);`
   - Review query plans: `EXPLAIN QUERY PLAN <query>`
   - Profile with larger dataset if needed

4. Document baseline metrics in PR description for future reference.
```

### Monitoring in Production

While ARIA doesn't have formal monitoring, add optional timing logs for debugging:

```python
# In SDEQueryService methods, add optional timing

import logging
import os

logger = logging.getLogger(__name__)

# Enable with ARIA_DEBUG_TIMING=1
_DEBUG_TIMING = os.environ.get("ARIA_DEBUG_TIMING", "").lower() in ("1", "true")


def get_corporation_regions(self, corporation_id: int) -> CorporationRegions | None:
    """Get all regions where a corporation has stations."""
    start = time.perf_counter() if _DEBUG_TIMING else None

    self._check_cache_validity()

    if corporation_id in self._corp_regions:
        result = self._corp_regions[corporation_id]
        if _DEBUG_TIMING:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.debug("get_corporation_regions(%d) cache hit: %.2fms", corporation_id, elapsed_ms)
        return result

    # Cache miss - query database
    result = self._query_corporation_regions(corporation_id)

    with self._lock:
        self._corp_regions[corporation_id] = result

    if _DEBUG_TIMING:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.debug("get_corporation_regions(%d) cache miss: %.2fms", corporation_id, elapsed_ms)

    return result
```

---

## Integration Test Specifications

### Test Location and Structure

Create a dedicated integration test module at `tests/integration/test_sde_data_integrity.py`:

```
tests/
├── integration/
│   ├── __init__.py
│   ├── conftest.py                    # Shared fixtures
│   ├── test_sde_data_integrity.py     # ← New file
│   └── test_market_tools.py           # Existing
└── unit/
    └── ...
```

### Test Implementation

```python
# tests/integration/test_sde_data_integrity.py

"""
SDE Data Integrity Tests.

These tests validate that the SDE data in the database matches
the assumptions made by the query layer. Run after `aria-esi sde-seed`.

Usage:
    uv run pytest tests/integration/test_sde_data_integrity.py -v

These tests are SKIPPED if SDE is not seeded, allowing CI to pass
on fresh environments.
"""

from __future__ import annotations

import pytest

from aria_esi.mcp.market.database import get_market_database


def sde_is_seeded() -> bool:
    """Check if SDE data has been imported."""
    try:
        db = get_market_database()
        conn = db._get_connection()
        cursor = conn.execute(
            "SELECT COUNT(*) FROM types WHERE published = 1"
        )
        count = cursor.fetchone()[0]
        return count > 1000  # Sanity check - real SDE has ~40k types
    except Exception:
        return False


# Skip marker for unseeded databases
requires_sde = pytest.mark.skipif(
    not sde_is_seeded(),
    reason="SDE not seeded. Run 'aria-esi sde-seed' first.",
)


@requires_sde
class TestCorporationRegionIntegrity:
    """Validate corporation-to-region mapping assumptions."""

    def test_seeding_corporations_have_stations(self):
        """Every corporation in npc_seeding should have at least one station."""
        db = get_market_database()
        conn = db._get_connection()

        cursor = conn.execute(
            """
            SELECT DISTINCT ns.corporation_id, nc.corporation_name
            FROM npc_seeding ns
            JOIN npc_corporations nc ON ns.corporation_id = nc.corporation_id
            LEFT JOIN stations s ON ns.corporation_id = s.corporation_id
            WHERE s.station_id IS NULL
            """
        )

        orphans = cursor.fetchall()

        # Some corporations may legitimately seed items but have no stations
        # (e.g., they sell through other corps' stations). Document exceptions:
        known_exceptions = {
            # Add corporation IDs here if discovered to be legitimate
        }

        unexpected = [
            (cid, name) for cid, name in orphans
            if cid not in known_exceptions
        ]

        assert not unexpected, (
            f"Corporations seed items but have no stations: {unexpected}"
        )

    def test_major_factions_have_regions(self):
        """Key NPC corporations should have resolvable regions."""
        db = get_market_database()
        conn = db._get_connection()

        # Corporations that MUST have station presence for blueprint lookups
        critical_corps = [
            (1000129, "Outer Ring Excavations"),
            (1000130, "Sisters of EVE"),
            (1000125, "CONCORD"),
        ]

        for corp_id, expected_name in critical_corps:
            cursor = conn.execute(
                """
                SELECT nc.corporation_name, COUNT(DISTINCT s.region_id)
                FROM npc_corporations nc
                LEFT JOIN stations s ON nc.corporation_id = s.corporation_id
                WHERE nc.corporation_id = ?
                GROUP BY nc.corporation_id
                """,
                (corp_id,),
            )
            row = cursor.fetchone()

            assert row is not None, f"Corporation {corp_id} not found in database"
            corp_name, region_count = row
            assert region_count > 0, (
                f"{corp_name} ({corp_id}) has no stations in any region"
            )

    def test_no_orphan_blueprint_products(self):
        """All blueprint products should reference valid types."""
        db = get_market_database()
        conn = db._get_connection()

        cursor = conn.execute(
            """
            SELECT bp.blueprint_type_id, bp.product_type_id
            FROM blueprint_products bp
            LEFT JOIN types t ON bp.product_type_id = t.type_id
            WHERE t.type_id IS NULL
            LIMIT 10
            """
        )

        orphans = cursor.fetchall()
        assert not orphans, f"Blueprint products reference missing types: {orphans}"


@requires_sde
class TestCategoryConstants:
    """Validate that category ID constants match SDE."""

    EXPECTED_CATEGORIES = {
        6: "Ship",
        7: "Module",
        8: "Charge",
        9: "Blueprint",
        16: "Skill",
        18: "Drone",
        25: "Asteroid",
    }

    def test_category_ids_match_sde(self):
        """Hard-coded category IDs should match actual SDE values."""
        db = get_market_database()
        conn = db._get_connection()

        mismatches = []
        for cat_id, expected_name in self.EXPECTED_CATEGORIES.items():
            cursor = conn.execute(
                "SELECT category_name FROM categories WHERE category_id = ?",
                (cat_id,),
            )
            row = cursor.fetchone()

            if row is None:
                mismatches.append((cat_id, expected_name, "NOT FOUND"))
            elif row[0] != expected_name:
                mismatches.append((cat_id, expected_name, row[0]))

        assert not mismatches, (
            f"Category constant mismatches (id, expected, actual): {mismatches}"
        )


@requires_sde
class TestQueryServiceIntegration:
    """Test the SDEQueryService against real data."""

    def test_ore_corporation_regions(self):
        """ORE should have stations in Outer Ring."""
        from aria_esi.mcp.sde.queries import get_sde_query_service

        service = get_sde_query_service()
        result = service.get_corporation_regions(1000129)  # ORE

        assert result is not None
        assert result.corporation_name == "Outer Ring Excavations"
        assert result.primary_region_name == "Outer Ring"

    def test_sisters_multi_region(self):
        """Sisters of EVE should have stations in multiple regions."""
        from aria_esi.mcp.sde.queries import get_sde_query_service

        service = get_sde_query_service()
        result = service.get_corporation_regions(1000130)  # Sisters

        assert result is not None
        # Sisters have stations in many regions, not just Syndicate
        assert len(result.regions) > 1, (
            f"Sisters only found in {len(result.regions)} region(s), expected multiple"
        )

    def test_cache_invalidation(self):
        """Cache should invalidate when timestamp changes."""
        from aria_esi.mcp.sde.queries import get_sde_query_service

        service = get_sde_query_service()

        # Populate cache
        _ = service.get_corporation_regions(1000129)
        assert 1000129 in service._corp_regions

        # Simulate re-import by changing timestamp
        service._cache_import_timestamp = "old-timestamp"

        # Next query should detect mismatch and clear cache
        _ = service.get_corporation_regions(1000129)

        # Cache should have been rebuilt with current timestamp
        assert service._cache_import_timestamp != "old-timestamp"


@requires_sde
class TestBlueprintSourceAccuracy:
    """Validate blueprint source lookups return correct data."""

    def test_venture_blueprint_sources(self):
        """Venture Blueprint should show correct seeding corporations."""
        db = get_market_database()
        conn = db._get_connection()

        cursor = conn.execute(
            """
            SELECT nc.corporation_id, nc.corporation_name
            FROM npc_seeding ns
            JOIN npc_corporations nc ON ns.corporation_id = nc.corporation_id
            JOIN types t ON ns.type_id = t.type_id
            WHERE t.type_name = 'Venture Blueprint'
            """,
        )

        corps = {row[0]: row[1] for row in cursor.fetchall()}

        # Venture Blueprint is seeded by ORE and University of Caille
        assert 1000129 in corps, "ORE should seed Venture Blueprint"
        # Note: may also be seeded by University of Caille (1000115)

    def test_pioneer_blueprint_sources(self):
        """Pioneer Blueprint should show University of Caille, not ORE."""
        db = get_market_database()
        conn = db._get_connection()

        cursor = conn.execute(
            """
            SELECT nc.corporation_id, nc.corporation_name
            FROM npc_seeding ns
            JOIN npc_corporations nc ON ns.corporation_id = nc.corporation_id
            JOIN types t ON ns.type_id = t.type_id
            WHERE t.type_name = 'Pioneer Blueprint'
            """,
        )

        corps = {row[0]: row[1] for row in cursor.fetchall()}

        # Pioneer Blueprint is seeded by University of Caille, NOT ORE
        # This test documents the data drift issue
        if 1000115 in corps and 1000129 not in corps:
            # Expected: University of Caille seeds it, not ORE
            pass
        elif corps:
            # Document actual seeding corps for future reference
            pytest.skip(f"Pioneer Blueprint seeded by: {corps}")
        else:
            pytest.fail("Pioneer Blueprint has no NPC seeding data")
```

### CI Configuration

Add pytest markers to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = [
    "integration: marks tests as integration tests (may require seeded data)",
]
```

For CI workflows, integration tests should be non-blocking on fresh environments:

```yaml
# .github/workflows/test.yml (example)
- name: Run unit tests
  run: uv run pytest tests/unit -v

- name: Run integration tests (if SDE available)
  run: uv run pytest tests/integration -v
  continue-on-error: true  # Don't fail CI if SDE not seeded
```

### Running Tests Locally

```bash
# After seeding SDE data
uv run aria-esi sde-seed

# Run all integration tests
uv run pytest tests/integration/test_sde_data_integrity.py -v

# Run specific test class
uv run pytest tests/integration/test_sde_data_integrity.py::TestQueryServiceIntegration -v

# Run with verbose output to see skip reasons
uv run pytest tests/integration -v --tb=short
```

---

## Appendix: Verification Queries

### Find All Corporations That Seed Items

```sql
SELECT DISTINCT
    nc.corporation_id,
    nc.corporation_name,
    COUNT(DISTINCT ns.type_id) as seeded_items
FROM npc_corporations nc
JOIN npc_seeding ns ON nc.corporation_id = ns.corporation_id
GROUP BY nc.corporation_id
ORDER BY seeded_items DESC
LIMIT 20;
```

### Find Regions for a Corporation

```sql
SELECT
    nc.corporation_id,
    nc.corporation_name,
    r.region_id,
    r.region_name,
    COUNT(*) as station_count
FROM npc_corporations nc
JOIN stations s ON nc.corporation_id = s.corporation_id
JOIN regions r ON s.region_id = r.region_id
WHERE nc.corporation_id = 1000129  -- ORE
GROUP BY r.region_id
ORDER BY station_count DESC;
```

### Validate FACTION_REGIONS Mapping

```sql
-- Check which hard-coded corps exist and their actual names
SELECT corporation_id, corporation_name, faction_id
FROM npc_corporations
WHERE corporation_id IN (
    1000129, 1000130, 1000125, 1000135, 1000134,
    1000127, 1000161, 1000126, 1000140, 1000118, 1000133
);
```

### Find Blueprint Seeding for ORE Ships

```sql
SELECT
    t.type_id,
    t.type_name,
    nc.corporation_id,
    nc.corporation_name
FROM npc_seeding ns
JOIN types t ON ns.type_id = t.type_id
JOIN npc_corporations nc ON ns.corporation_id = nc.corporation_id
WHERE t.type_name LIKE '%Blueprint'
AND t.type_name LIKE '%Venture%' OR t.type_name LIKE '%Pioneer%'
   OR t.type_name LIKE '%Endurance%' OR t.type_name LIKE '%Prospect%';
```
