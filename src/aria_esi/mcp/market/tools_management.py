"""
MCP tools for managing watchlists and market scopes.

Provides CRUD operations for:
- Watchlists: Named item lists for scoped market fetching
- Market Scopes: Ad-hoc market scope definitions

These tools expose the Phase 1 database operations to users
via the MCP protocol.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from aria_esi.core.logging import get_logger
from aria_esi.mcp.market.database import get_market_database
from aria_esi.models.market import (
    ManagementError,
    MarketScopeInfo,
    ScopeCreateResult,
    ScopeDeleteResult,
    ScopeListResult,
    WatchlistAddItemResult,
    WatchlistCreateResult,
    WatchlistDeleteResult,
    WatchlistDetail,
    WatchlistInfo,
    WatchlistItemInfo,
    WatchlistListResult,
)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = get_logger("aria_market.tools_management")

# Valid ad-hoc scope types (hub_region is reserved for core hubs)
VALID_ADHOC_SCOPE_TYPES = {"region", "station", "system", "structure"}


# =============================================================================
# Implementation functions (called by both MCP tools and unified dispatcher)
# =============================================================================


async def _watchlist_create_impl(
    name: str,
    items: list[str] | None = None,
    owner_character_id: int | None = None,
) -> dict:
    """Create a new watchlist implementation."""
    db = get_market_database()

    # Create the watchlist
    try:
        watchlist = db.create_watchlist(name, owner_character_id)
    except sqlite3.IntegrityError:
        error = ManagementError(
            code="DUPLICATE_NAME",
            message=f"Watchlist '{name}' already exists for this owner",
            suggestions=[f"Use a different name or delete the existing '{name}' watchlist"],
        )
        return {"error": error.model_dump()}

    # Add items if provided
    items_added = 0
    unresolved: list[str] = []

    if items:
        for item_name in items:
            type_info = db.resolve_type_name(item_name)
            if type_info:
                try:
                    db.add_watchlist_item(watchlist.watchlist_id, type_info.type_id)
                    items_added += 1
                except sqlite3.IntegrityError:
                    # Duplicate item - skip silently
                    pass
            else:
                unresolved.append(item_name)
                suggestions = db.find_type_suggestions(item_name, limit=3)
                if suggestions:
                    logger.debug(
                        "Could not resolve '%s', suggestions: %s",
                        item_name,
                        suggestions,
                    )

    # Get item count for response
    item_count = len(db.get_watchlist_items(watchlist.watchlist_id))

    result = WatchlistCreateResult(
        watchlist=WatchlistInfo(
            watchlist_id=watchlist.watchlist_id,
            name=watchlist.name,
            owner_character_id=watchlist.owner_character_id,
            item_count=item_count,
            created_at=watchlist.created_at,
        ),
        items_added=items_added,
        unresolved_items=unresolved,
    )

    return result.model_dump()


async def _watchlist_add_item_impl(
    watchlist_name: str,
    item_name: str,
    owner_character_id: int | None = None,
) -> dict:
    """Add item to watchlist implementation."""
    db = get_market_database()

    # Get the watchlist
    watchlist = db.get_watchlist(watchlist_name, owner_character_id)
    if not watchlist:
        error = ManagementError(
            code="WATCHLIST_NOT_FOUND",
            message=f"Watchlist '{watchlist_name}' not found",
            suggestions=["Create the watchlist first with market_watchlist_create"],
        )
        return {"error": error.model_dump()}

    # Resolve the item name
    type_info = db.resolve_type_name(item_name)
    if not type_info:
        suggestions = db.find_type_suggestions(item_name, limit=5)
        error = ManagementError(
            code="TYPE_NOT_FOUND",
            message=f"Could not resolve item name '{item_name}'",
            suggestions=suggestions if suggestions else ["Check spelling or try a different name"],
        )
        return {"error": error.model_dump()}

    # Add the item
    try:
        item = db.add_watchlist_item(watchlist.watchlist_id, type_info.type_id)
    except sqlite3.IntegrityError:
        error = ManagementError(
            code="DUPLICATE_ITEM",
            message=f"Item '{type_info.type_name}' is already in watchlist '{watchlist_name}'",
            suggestions=[],
        )
        return {"error": error.model_dump()}

    result = WatchlistAddItemResult(
        item=WatchlistItemInfo(
            type_id=type_info.type_id,
            type_name=type_info.type_name,
            added_at=item.added_at,
        ),
        watchlist_name=watchlist_name,
    )

    return result.model_dump()


async def _watchlist_list_impl(
    owner_character_id: int | None = None,
    include_global: bool = True,
) -> dict:
    """List watchlists implementation."""
    db = get_market_database()

    watchlists: list[WatchlistInfo] = []

    if owner_character_id is None:
        # Global only
        db_watchlists = db.list_watchlists(owner_character_id=None)
    else:
        # Owner's watchlists
        db_watchlists = db.list_watchlists(owner_character_id=owner_character_id)

        # Optionally include global watchlists
        if include_global:
            global_watchlists = db.list_watchlists(owner_character_id=None)
            # Merge, avoiding duplicates by name (owner shadows global)
            owner_names = {w.name for w in db_watchlists}
            for gw in global_watchlists:
                if gw.name not in owner_names:
                    db_watchlists.append(gw)

    for w in db_watchlists:
        item_count = len(db.get_watchlist_items(w.watchlist_id))
        watchlists.append(
            WatchlistInfo(
                watchlist_id=w.watchlist_id,
                name=w.name,
                owner_character_id=w.owner_character_id,
                item_count=item_count,
                created_at=w.created_at,
            )
        )

    result = WatchlistListResult(
        watchlists=watchlists,
        total=len(watchlists),
    )

    return result.model_dump()


async def _watchlist_get_impl(
    name: str,
    owner_character_id: int | None = None,
) -> dict:
    """Get watchlist details implementation."""
    db = get_market_database()

    # Get the watchlist
    watchlist = db.get_watchlist(name, owner_character_id)
    if not watchlist:
        error = ManagementError(
            code="WATCHLIST_NOT_FOUND",
            message=f"Watchlist '{name}' not found",
            suggestions=["Use market_watchlist_list to see available watchlists"],
        )
        return {"error": error.model_dump()}

    # Get items with resolved names
    db_items = db.get_watchlist_items(watchlist.watchlist_id)
    items: list[WatchlistItemInfo] = []

    for item in db_items:
        type_info = db.resolve_type_id(item.type_id)
        type_name = type_info.type_name if type_info else f"Unknown ({item.type_id})"
        items.append(
            WatchlistItemInfo(
                type_id=item.type_id,
                type_name=type_name,
                added_at=item.added_at,
            )
        )

    result = WatchlistDetail(
        watchlist_id=watchlist.watchlist_id,
        name=watchlist.name,
        owner_character_id=watchlist.owner_character_id,
        items=items,
        created_at=watchlist.created_at,
    )

    return result.model_dump()


async def _watchlist_delete_impl(
    name: str,
    owner_character_id: int | None = None,
) -> dict:
    """Delete watchlist implementation."""
    db = get_market_database()

    # Get the watchlist first to check existence and get item count
    watchlist = db.get_watchlist(name, owner_character_id)
    if not watchlist:
        error = ManagementError(
            code="WATCHLIST_NOT_FOUND",
            message=f"Watchlist '{name}' not found",
            suggestions=["Use market_watchlist_list to see available watchlists"],
        )
        return {"error": error.model_dump()}

    # Get item count before deletion
    items_count = len(db.get_watchlist_items(watchlist.watchlist_id))

    # Delete (cascades to items)
    deleted = db.delete_watchlist(watchlist.watchlist_id)

    result = WatchlistDeleteResult(
        deleted=deleted,
        watchlist_name=name,
        items_deleted=items_count if deleted else 0,
    )

    return result.model_dump()


async def _scope_create_impl(
    name: str,
    scope_type: str,
    location_id: int,
    watchlist_name: str,
    owner_character_id: int | None = None,
    parent_region_id: int | None = None,
) -> dict:
    """Create ad-hoc market scope implementation."""
    db = get_market_database()

    # Validate scope_type
    if scope_type not in VALID_ADHOC_SCOPE_TYPES:
        error = ManagementError(
            code="INVALID_SCOPE_TYPE",
            message=f"Invalid scope_type '{scope_type}'",
            suggestions=[f"Use one of: {', '.join(sorted(VALID_ADHOC_SCOPE_TYPES))}"],
        )
        return {"error": error.model_dump()}

    # Get the watchlist
    watchlist = db.get_watchlist(watchlist_name, owner_character_id)
    if not watchlist:
        # Try global watchlist as fallback
        watchlist = db.get_watchlist(watchlist_name, owner_character_id=None)

    if not watchlist:
        error = ManagementError(
            code="WATCHLIST_NOT_FOUND",
            message=f"Watchlist '{watchlist_name}' not found",
            suggestions=["Create the watchlist first with market_watchlist_create"],
        )
        return {"error": error.model_dump()}

    # Map location_id to the correct column based on scope_type
    scope_kwargs = {
        "scope_name": name,
        "scope_type": scope_type,
        "watchlist_id": watchlist.watchlist_id,
        "owner_character_id": owner_character_id,
        "parent_region_id": parent_region_id,
        "is_core": False,
        "source": "esi",
    }

    if scope_type == "region":
        scope_kwargs["region_id"] = location_id
    elif scope_type == "station":
        scope_kwargs["station_id"] = location_id
    elif scope_type == "system":
        scope_kwargs["system_id"] = location_id
    elif scope_type == "structure":
        scope_kwargs["structure_id"] = location_id

    # Create the scope
    try:
        scope = db.create_scope(**scope_kwargs)  # type: ignore[arg-type]
    except sqlite3.IntegrityError as e:
        error_msg = str(e).lower()
        if "unique" in error_msg:
            error = ManagementError(
                code="DUPLICATE_NAME",
                message=f"Scope '{name}' already exists for this owner",
                suggestions=[f"Use a different name or delete the existing '{name}' scope"],
            )
        else:
            error = ManagementError(
                code="CONSTRAINT_VIOLATION",
                message=f"Failed to create scope: {e}",
                suggestions=["Check that all parameters are valid"],
            )
        return {"error": error.model_dump()}

    # Build response
    scope_info = MarketScopeInfo(
        scope_id=scope.scope_id,
        scope_name=scope.scope_name,
        scope_type=scope.scope_type,
        location_id=location_id,
        location_name=None,  # Would require ESI lookup - not implemented in Phase 2
        parent_region_id=scope.parent_region_id,
        watchlist_name=watchlist_name,
        is_core=scope.is_core,
        source=scope.source,
        owner_character_id=scope.owner_character_id,
        last_scan_status=scope.last_scan_status,
        last_scanned_at=scope.last_scanned_at,
    )

    result = ScopeCreateResult(scope=scope_info)
    return result.model_dump()


async def _scope_list_impl(
    owner_character_id: int | None = None,
    include_core: bool = True,
    include_global: bool = True,
) -> dict:
    """List market scopes implementation."""
    db = get_market_database()

    db_scopes = db.list_scopes(
        owner_character_id=owner_character_id,
        include_core=include_core,
        include_global=include_global,
    )

    scopes: list[MarketScopeInfo] = []
    core_count = 0
    adhoc_count = 0

    for s in db_scopes:
        # Determine location_id based on scope_type
        if s.region_id:
            location_id = s.region_id
        elif s.station_id:
            location_id = s.station_id
        elif s.system_id:
            location_id = s.system_id
        elif s.structure_id:
            location_id = s.structure_id
        else:
            location_id = 0  # Should not happen

        # Get watchlist name if applicable
        watchlist_name = None
        if s.watchlist_id:
            watchlist = db.get_watchlist_by_id(s.watchlist_id)
            if watchlist:
                watchlist_name = watchlist.name

        scopes.append(
            MarketScopeInfo(
                scope_id=s.scope_id,
                scope_name=s.scope_name,
                scope_type=s.scope_type,
                location_id=location_id,
                location_name=None,  # Would require ESI lookup
                parent_region_id=s.parent_region_id,
                watchlist_name=watchlist_name,
                is_core=s.is_core,
                source=s.source,
                owner_character_id=s.owner_character_id,
                last_scan_status=s.last_scan_status,
                last_scanned_at=s.last_scanned_at,
            )
        )

        if s.is_core:
            core_count += 1
        else:
            adhoc_count += 1

    result = ScopeListResult(
        scopes=scopes,
        core_count=core_count,
        adhoc_count=adhoc_count,
    )

    return result.model_dump()


async def _scope_delete_impl(
    name: str,
    owner_character_id: int | None = None,
) -> dict:
    """Delete ad-hoc market scope implementation."""
    db = get_market_database()

    # Get the scope
    scope = db.get_scope(name, owner_character_id)
    if not scope:
        error = ManagementError(
            code="SCOPE_NOT_FOUND",
            message=f"Scope '{name}' not found",
            suggestions=["Use market_scope_list to see available scopes"],
        )
        return {"error": error.model_dump()}

    # Try to delete (will raise ValueError for core scopes)
    try:
        deleted = db.delete_scope(scope.scope_id)
    except ValueError as e:
        error = ManagementError(
            code="CORE_SCOPE_PROTECTED",
            message=str(e),
            suggestions=["Core trade hub scopes cannot be deleted"],
        )
        return {"error": error.model_dump()}

    result = ScopeDeleteResult(
        deleted=deleted,
        scope_name=name,
    )

    return result.model_dump()


def register_management_tools(server: FastMCP) -> None:
    """Register watchlist and scope management tools with MCP server."""

    # =========================================================================
    # Watchlist Tools
    # =========================================================================

    @server.tool()
    async def market_watchlist_create(
        name: str,
        items: list[str] | None = None,
        owner_character_id: int | None = None,
    ) -> dict:
        """
        Create a new watchlist for scoped market fetching.

        Watchlists define which items to track in ad-hoc market scopes.
        They enable bounded ESI queries for arbitrary regions, stations,
        systems, or structures.

        Args:
            name: Watchlist name (must be unique per owner)
            items: Optional list of item names to add initially
            owner_character_id: Character ID for ownership (None = global)

        Returns:
            WatchlistCreateResult with watchlist info and item resolution status

        Examples:
            market_watchlist_create("mining_ores", items=["Veldspar", "Scordite"])
            market_watchlist_create("personal_list", owner_character_id=12345)
        """
        db = get_market_database()

        # Create the watchlist
        try:
            watchlist = db.create_watchlist(name, owner_character_id)
        except sqlite3.IntegrityError:
            error = ManagementError(
                code="DUPLICATE_NAME",
                message=f"Watchlist '{name}' already exists for this owner",
                suggestions=[f"Use a different name or delete the existing '{name}' watchlist"],
            )
            return {"error": error.model_dump()}

        # Add items if provided
        items_added = 0
        unresolved: list[str] = []

        if items:
            for item_name in items:
                type_info = db.resolve_type_name(item_name)
                if type_info:
                    try:
                        db.add_watchlist_item(watchlist.watchlist_id, type_info.type_id)
                        items_added += 1
                    except sqlite3.IntegrityError:
                        # Duplicate item - skip silently
                        pass
                else:
                    unresolved.append(item_name)
                    suggestions = db.find_type_suggestions(item_name, limit=3)
                    if suggestions:
                        logger.debug(
                            "Could not resolve '%s', suggestions: %s",
                            item_name,
                            suggestions,
                        )

        # Get item count for response
        item_count = len(db.get_watchlist_items(watchlist.watchlist_id))

        result = WatchlistCreateResult(
            watchlist=WatchlistInfo(
                watchlist_id=watchlist.watchlist_id,
                name=watchlist.name,
                owner_character_id=watchlist.owner_character_id,
                item_count=item_count,
                created_at=watchlist.created_at,
            ),
            items_added=items_added,
            unresolved_items=unresolved,
        )

        return result.model_dump()

    @server.tool()
    async def market_watchlist_add_item(
        watchlist_name: str,
        item_name: str,
        owner_character_id: int | None = None,
    ) -> dict:
        """
        Add an item to a watchlist by name.

        Items are resolved via the SDE (Static Data Export) using
        case-insensitive fuzzy matching.

        Args:
            watchlist_name: Name of the watchlist
            item_name: Item name to add (resolved via SDE)
            owner_character_id: Watchlist owner (None = global)

        Returns:
            WatchlistAddItemResult with added item info, or error with suggestions

        Examples:
            market_watchlist_add_item("mining_ores", "Pyroxeres")
            market_watchlist_add_item("my_list", "Tritanium", owner_character_id=12345)
        """
        db = get_market_database()

        # Get the watchlist
        watchlist = db.get_watchlist(watchlist_name, owner_character_id)
        if not watchlist:
            error = ManagementError(
                code="WATCHLIST_NOT_FOUND",
                message=f"Watchlist '{watchlist_name}' not found",
                suggestions=["Create the watchlist first with market_watchlist_create"],
            )
            return {"error": error.model_dump()}

        # Resolve the item name
        type_info = db.resolve_type_name(item_name)
        if not type_info:
            suggestions = db.find_type_suggestions(item_name, limit=5)
            error = ManagementError(
                code="TYPE_NOT_FOUND",
                message=f"Could not resolve item name '{item_name}'",
                suggestions=suggestions
                if suggestions
                else ["Check spelling or try a different name"],
            )
            return {"error": error.model_dump()}

        # Add the item
        try:
            item = db.add_watchlist_item(watchlist.watchlist_id, type_info.type_id)
        except sqlite3.IntegrityError:
            error = ManagementError(
                code="DUPLICATE_ITEM",
                message=f"Item '{type_info.type_name}' is already in watchlist '{watchlist_name}'",
                suggestions=[],
            )
            return {"error": error.model_dump()}

        result = WatchlistAddItemResult(
            item=WatchlistItemInfo(
                type_id=type_info.type_id,
                type_name=type_info.type_name,
                added_at=item.added_at,
            ),
            watchlist_name=watchlist_name,
        )

        return result.model_dump()

    @server.tool()
    async def market_watchlist_list(
        owner_character_id: int | None = None,
        include_global: bool = True,
    ) -> dict:
        """
        List available watchlists.

        Args:
            owner_character_id: Filter to specific owner (None = global only)
            include_global: Include global watchlists when owner specified

        Returns:
            WatchlistListResult with watchlist summaries

        Examples:
            market_watchlist_list()  # List global watchlists
            market_watchlist_list(owner_character_id=12345)  # List owner's + global
            market_watchlist_list(owner_character_id=12345, include_global=False)  # Owner only
        """
        db = get_market_database()

        watchlists: list[WatchlistInfo] = []

        if owner_character_id is None:
            # Global only
            db_watchlists = db.list_watchlists(owner_character_id=None)
        else:
            # Owner's watchlists
            db_watchlists = db.list_watchlists(owner_character_id=owner_character_id)

            # Optionally include global watchlists
            if include_global:
                global_watchlists = db.list_watchlists(owner_character_id=None)
                # Merge, avoiding duplicates by name (owner shadows global)
                owner_names = {w.name for w in db_watchlists}
                for gw in global_watchlists:
                    if gw.name not in owner_names:
                        db_watchlists.append(gw)

        for w in db_watchlists:
            item_count = len(db.get_watchlist_items(w.watchlist_id))
            watchlists.append(
                WatchlistInfo(
                    watchlist_id=w.watchlist_id,
                    name=w.name,
                    owner_character_id=w.owner_character_id,
                    item_count=item_count,
                    created_at=w.created_at,
                )
            )

        result = WatchlistListResult(
            watchlists=watchlists,
            total=len(watchlists),
        )

        return result.model_dump()

    @server.tool()
    async def market_watchlist_get(
        name: str,
        owner_character_id: int | None = None,
    ) -> dict:
        """
        Get watchlist details including all items.

        Args:
            name: Watchlist name
            owner_character_id: Watchlist owner (None = global)

        Returns:
            WatchlistDetail with items and resolved type names

        Examples:
            market_watchlist_get("mining_ores")
            market_watchlist_get("my_list", owner_character_id=12345)
        """
        db = get_market_database()

        # Get the watchlist
        watchlist = db.get_watchlist(name, owner_character_id)
        if not watchlist:
            error = ManagementError(
                code="WATCHLIST_NOT_FOUND",
                message=f"Watchlist '{name}' not found",
                suggestions=["Use market_watchlist_list to see available watchlists"],
            )
            return {"error": error.model_dump()}

        # Get items with resolved names
        db_items = db.get_watchlist_items(watchlist.watchlist_id)
        items: list[WatchlistItemInfo] = []

        for item in db_items:
            type_info = db.resolve_type_id(item.type_id)
            type_name = type_info.type_name if type_info else f"Unknown ({item.type_id})"
            items.append(
                WatchlistItemInfo(
                    type_id=item.type_id,
                    type_name=type_name,
                    added_at=item.added_at,
                )
            )

        result = WatchlistDetail(
            watchlist_id=watchlist.watchlist_id,
            name=watchlist.name,
            owner_character_id=watchlist.owner_character_id,
            items=items,
            created_at=watchlist.created_at,
        )

        return result.model_dump()

    @server.tool()
    async def market_watchlist_delete(
        name: str,
        owner_character_id: int | None = None,
    ) -> dict:
        """
        Delete a watchlist and all its items.

        This also invalidates any market scopes that reference this watchlist,
        as they require a valid watchlist for fetching.

        Args:
            name: Watchlist name
            owner_character_id: Watchlist owner (None = global)

        Returns:
            WatchlistDeleteResult with success status and deleted item count

        Examples:
            market_watchlist_delete("old_list")
            market_watchlist_delete("my_list", owner_character_id=12345)
        """
        db = get_market_database()

        # Get the watchlist first to check existence and get item count
        watchlist = db.get_watchlist(name, owner_character_id)
        if not watchlist:
            error = ManagementError(
                code="WATCHLIST_NOT_FOUND",
                message=f"Watchlist '{name}' not found",
                suggestions=["Use market_watchlist_list to see available watchlists"],
            )
            return {"error": error.model_dump()}

        # Get item count before deletion
        items_count = len(db.get_watchlist_items(watchlist.watchlist_id))

        # Delete (cascades to items)
        deleted = db.delete_watchlist(watchlist.watchlist_id)

        result = WatchlistDeleteResult(
            deleted=deleted,
            watchlist_name=name,
            items_deleted=items_count if deleted else 0,
        )

        return result.model_dump()

    # =========================================================================
    # Scope Tools
    # =========================================================================

    @server.tool()
    async def market_scope_create(
        name: str,
        scope_type: str,
        location_id: int,
        watchlist_name: str,
        owner_character_id: int | None = None,
        parent_region_id: int | None = None,
    ) -> dict:
        """
        Create an ad-hoc market scope.

        Ad-hoc scopes enable market fetching from arbitrary EVE locations
        beyond the 5 core trade hubs. They require a watchlist to bound
        which items are fetched.

        Args:
            name: Scope name (must be unique per owner)
            scope_type: One of: region, station, system, structure
            location_id: The location ID matching scope_type:
                - region: Region ID (e.g., 10000037 for Everyshore)
                - station: Station ID
                - system: Solar system ID
                - structure: Structure ID
            watchlist_name: Name of watchlist to use for fetching
            owner_character_id: Scope owner (None = global)
            parent_region_id: Parent region for station/system scopes (optimization)

        Returns:
            ScopeCreateResult with scope info

        Examples:
            # Create a region scope
            market_scope_create("Everyshore", "region", 10000037, "mining_ores")

            # Create a station scope
            market_scope_create(
                "Oursulaert Station",
                "station",
                60011866,
                "my_items",
                parent_region_id=10000032
            )
        """
        db = get_market_database()

        # Validate scope_type
        if scope_type not in VALID_ADHOC_SCOPE_TYPES:
            error = ManagementError(
                code="INVALID_SCOPE_TYPE",
                message=f"Invalid scope_type '{scope_type}'",
                suggestions=[f"Use one of: {', '.join(sorted(VALID_ADHOC_SCOPE_TYPES))}"],
            )
            return {"error": error.model_dump()}

        # Get the watchlist
        watchlist = db.get_watchlist(watchlist_name, owner_character_id)
        if not watchlist:
            # Try global watchlist as fallback
            watchlist = db.get_watchlist(watchlist_name, owner_character_id=None)

        if not watchlist:
            error = ManagementError(
                code="WATCHLIST_NOT_FOUND",
                message=f"Watchlist '{watchlist_name}' not found",
                suggestions=["Create the watchlist first with market_watchlist_create"],
            )
            return {"error": error.model_dump()}

        # Map location_id to the correct column based on scope_type
        scope_kwargs = {
            "scope_name": name,
            "scope_type": scope_type,
            "watchlist_id": watchlist.watchlist_id,
            "owner_character_id": owner_character_id,
            "parent_region_id": parent_region_id,
            "is_core": False,
            "source": "esi",
        }

        if scope_type == "region":
            scope_kwargs["region_id"] = location_id
        elif scope_type == "station":
            scope_kwargs["station_id"] = location_id
        elif scope_type == "system":
            scope_kwargs["system_id"] = location_id
        elif scope_type == "structure":
            scope_kwargs["structure_id"] = location_id

        # Create the scope
        try:
            scope = db.create_scope(**scope_kwargs)  # type: ignore[arg-type]
        except sqlite3.IntegrityError as e:
            error_msg = str(e).lower()
            if "unique" in error_msg:
                error = ManagementError(
                    code="DUPLICATE_NAME",
                    message=f"Scope '{name}' already exists for this owner",
                    suggestions=[f"Use a different name or delete the existing '{name}' scope"],
                )
            else:
                error = ManagementError(
                    code="CONSTRAINT_VIOLATION",
                    message=f"Failed to create scope: {e}",
                    suggestions=["Check that all parameters are valid"],
                )
            return {"error": error.model_dump()}

        # Build response
        scope_info = MarketScopeInfo(
            scope_id=scope.scope_id,
            scope_name=scope.scope_name,
            scope_type=scope.scope_type,
            location_id=location_id,
            location_name=None,  # Would require ESI lookup - not implemented in Phase 2
            parent_region_id=scope.parent_region_id,
            watchlist_name=watchlist_name,
            is_core=scope.is_core,
            source=scope.source,
            owner_character_id=scope.owner_character_id,
            last_scan_status=scope.last_scan_status,
            last_scanned_at=scope.last_scanned_at,
        )

        result = ScopeCreateResult(scope=scope_info)
        return result.model_dump()

    @server.tool()
    async def market_scope_list(
        owner_character_id: int | None = None,
        include_core: bool = True,
        include_global: bool = True,
    ) -> dict:
        """
        List available market scopes.

        Args:
            owner_character_id: Filter to specific owner
            include_core: Include core hub scopes (Jita, Amarr, etc.)
            include_global: Include global scopes when owner specified

        Returns:
            ScopeListResult with scope summaries

        Examples:
            market_scope_list()  # List all global scopes including core hubs
            market_scope_list(include_core=False)  # Ad-hoc scopes only
            market_scope_list(owner_character_id=12345)  # Owner's + global scopes
        """
        db = get_market_database()

        db_scopes = db.list_scopes(
            owner_character_id=owner_character_id,
            include_core=include_core,
            include_global=include_global,
        )

        scopes: list[MarketScopeInfo] = []
        core_count = 0
        adhoc_count = 0

        for s in db_scopes:
            # Determine location_id based on scope_type
            if s.region_id:
                location_id = s.region_id
            elif s.station_id:
                location_id = s.station_id
            elif s.system_id:
                location_id = s.system_id
            elif s.structure_id:
                location_id = s.structure_id
            else:
                location_id = 0  # Should not happen

            # Get watchlist name if applicable
            watchlist_name = None
            if s.watchlist_id:
                watchlist = db.get_watchlist_by_id(s.watchlist_id)
                if watchlist:
                    watchlist_name = watchlist.name

            scopes.append(
                MarketScopeInfo(
                    scope_id=s.scope_id,
                    scope_name=s.scope_name,
                    scope_type=s.scope_type,
                    location_id=location_id,
                    location_name=None,  # Would require ESI lookup
                    parent_region_id=s.parent_region_id,
                    watchlist_name=watchlist_name,
                    is_core=s.is_core,
                    source=s.source,
                    owner_character_id=s.owner_character_id,
                    last_scan_status=s.last_scan_status,
                    last_scanned_at=s.last_scanned_at,
                )
            )

            if s.is_core:
                core_count += 1
            else:
                adhoc_count += 1

        result = ScopeListResult(
            scopes=scopes,
            core_count=core_count,
            adhoc_count=adhoc_count,
        )

        return result.model_dump()

    @server.tool()
    async def market_scope_delete(
        name: str,
        owner_character_id: int | None = None,
    ) -> dict:
        """
        Delete an ad-hoc market scope.

        Core hub scopes (Jita, Amarr, Dodixie, Rens, Hek) cannot be deleted
        as they are required for the hub-centric market engine.

        Args:
            name: Scope name
            owner_character_id: Scope owner (None = global)

        Returns:
            ScopeDeleteResult with success status

        Examples:
            market_scope_delete("Everyshore")
            market_scope_delete("my_scope", owner_character_id=12345)
        """
        db = get_market_database()

        # Get the scope
        scope = db.get_scope(name, owner_character_id)
        if not scope:
            error = ManagementError(
                code="SCOPE_NOT_FOUND",
                message=f"Scope '{name}' not found",
                suggestions=["Use market_scope_list to see available scopes"],
            )
            return {"error": error.model_dump()}

        # Try to delete (will raise ValueError for core scopes)
        try:
            deleted = db.delete_scope(scope.scope_id)
        except ValueError as e:
            error = ManagementError(
                code="CORE_SCOPE_PROTECTED",
                message=str(e),
                suggestions=["Core trade hub scopes cannot be deleted"],
            )
            return {"error": error.model_dump()}

        result = ScopeDeleteResult(
            deleted=deleted,
            scope_name=name,
        )

        return result.model_dump()
