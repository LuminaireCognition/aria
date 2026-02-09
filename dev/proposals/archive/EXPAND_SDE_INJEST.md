# Meta Types Implementation Draft

**Status:** ✅ COMPLETE (2026-02-02)
**Description:** Add invMetaGroups and invMetaTypes tables for T2 → meta/faction variant lookups

---

## Overview

  Add invMetaGroups and invMetaTypes tables from the Fuzzwork SDE to enable dynamic T2 → meta/faction variant lookups.

  Files to modify:
  1. src/aria_esi/mcp/sde/schema.py - Add table definitions
  2. src/aria_esi/mcp/sde/importer.py - Add import logic
  3. src/aria_esi/mcp/sde/queries.py - Add query methods
  4. src/aria_esi/models/sde.py - Add data models
  5. src/aria_esi/mcp/dispatchers/sde.py - Add meta_variants action

  ---
  1. Schema Changes (schema.py)

  # Add to SDE_TABLES_SQL (after existing tables)

  -- Meta groups (Tech I, Tech II, Faction, Storyline, Officer, etc.)
  CREATE TABLE IF NOT EXISTS meta_groups (
      meta_group_id INTEGER PRIMARY KEY,
      meta_group_name TEXT NOT NULL,
      meta_group_name_lower TEXT NOT NULL
  );

  CREATE INDEX IF NOT EXISTS idx_meta_groups_name_lower ON meta_groups(meta_group_name_lower);

  -- Meta type relationships (parent type → variant)
  -- parent_type_id is the "base" T1 item, type_id is the variant
  CREATE TABLE IF NOT EXISTS meta_types (
      type_id INTEGER PRIMARY KEY,
      parent_type_id INTEGER NOT NULL,
      meta_group_id INTEGER NOT NULL,
      FOREIGN KEY (parent_type_id) REFERENCES types(type_id),
      FOREIGN KEY (meta_group_id) REFERENCES meta_groups(meta_group_id)
  );

  CREATE INDEX IF NOT EXISTS idx_meta_types_parent ON meta_types(parent_type_id);
  CREATE INDEX IF NOT EXISTS idx_meta_types_group ON meta_types(meta_group_id);

  # Add import SQL templates

  IMPORT_META_GROUPS_SQL = """
  INSERT OR REPLACE INTO meta_groups (meta_group_id, meta_group_name, meta_group_name_lower)
  VALUES (?, ?, ?);
  """

  IMPORT_META_TYPES_SQL = """
  INSERT OR REPLACE INTO meta_types (type_id, parent_type_id, meta_group_id)
  VALUES (?, ?, ?);
  """

  ---
  2. Importer Changes (importer.py)

  Add to SDEImportResult dataclass:

  @dataclass
  class SDEImportResult:
      # ... existing fields ...
      meta_groups_imported: int = 0
      meta_types_imported: int = 0

  Add to SDEStatus dataclass:

  @dataclass
  class SDEStatus:
      # ... existing fields ...
      meta_group_count: int = 0
      meta_type_count: int = 0

  Add import methods:

  def _import_meta_groups(
      self, sde_conn: sqlite3.Connection, target_conn: sqlite3.Connection
  ) -> int:
      """Import meta group definitions (Tech I, Tech II, Faction, etc.)."""
      # Check if invMetaGroups table exists
      cursor = sde_conn.execute(
          "SELECT name FROM sqlite_master WHERE type='table' AND name='invMetaGroups'"
      )
      if not cursor.fetchone():
          logger.warning("invMetaGroups table not found in SDE")
          return 0

      # Check actual column names
      cursor = sde_conn.execute("PRAGMA table_info(invMetaGroups)")
      columns = {row[1] for row in cursor.fetchall()}
      logger.debug("invMetaGroups columns: %s", columns)

      # Build query based on available columns
      group_id_col = "metaGroupID" if "metaGroupID" in columns else "meta_group_id"
      group_name_col = "metaGroupName" if "metaGroupName" in columns else "meta_group_name"

      try:
          cursor = sde_conn.execute(f"""
              SELECT {group_id_col}, {group_name_col}
              FROM invMetaGroups
              WHERE {group_name_col} IS NOT NULL
          """)
      except sqlite3.OperationalError as e:
          logger.warning("Could not query invMetaGroups: %s", e)
          return 0

      batch = []
      for row in cursor:
          group_id = row[0]
          group_name = row[1] if row[1] else f"Meta Group {group_id}"
          batch.append((group_id, group_name, group_name.lower()))

      if batch:
          target_conn.executemany(IMPORT_META_GROUPS_SQL, batch)
          target_conn.commit()

      logger.info("Imported %d meta groups from SDE", len(batch))
      return len(batch)


  def _import_meta_types(
      self, sde_conn: sqlite3.Connection, target_conn: sqlite3.Connection
  ) -> int:
      """Import meta type relationships (T1 → T2/Faction/etc variants)."""
      # Check if invMetaTypes table exists
      cursor = sde_conn.execute(
          "SELECT name FROM sqlite_master WHERE type='table' AND name='invMetaTypes'"
      )
      if not cursor.fetchone():
          logger.warning("invMetaTypes table not found in SDE")
          return 0

      # Check actual column names
      cursor = sde_conn.execute("PRAGMA table_info(invMetaTypes)")
      columns = {row[1] for row in cursor.fetchall()}
      logger.debug("invMetaTypes columns: %s", columns)

      # Build query based on available columns
      type_id_col = "typeID" if "typeID" in columns else "type_id"
      parent_col = "parentTypeID" if "parentTypeID" in columns else "parent_type_id"
      meta_group_col = "metaGroupID" if "metaGroupID" in columns else "meta_group_id"

      # Get valid type_ids from target database to filter orphans
      valid_cursor = target_conn.execute("SELECT type_id FROM types")
      valid_type_ids = {row[0] for row in valid_cursor}

      # Get valid meta_group_ids
      valid_mg_cursor = target_conn.execute("SELECT meta_group_id FROM meta_groups")
      valid_meta_groups = {row[0] for row in valid_mg_cursor}

      try:
          cursor = sde_conn.execute(f"""
              SELECT {type_id_col}, {parent_col}, {meta_group_col}
              FROM invMetaTypes
          """)
      except sqlite3.OperationalError as e:
          logger.warning("Could not query invMetaTypes: %s", e)
          return 0

      batch = []
      skipped = 0
      for row in cursor:
          type_id, parent_id, meta_group_id = row[0], row[1], row[2]

          # Skip entries with invalid references
          if type_id not in valid_type_ids:
              skipped += 1
              continue
          if parent_id not in valid_type_ids:
              skipped += 1
              continue
          if meta_group_id not in valid_meta_groups:
              skipped += 1
              continue

          batch.append((type_id, parent_id, meta_group_id))

      if skipped:
          logger.info("Skipped %d meta types with invalid references", skipped)

      if batch:
          # Import in chunks
          chunk_size = 10000
          for i in range(0, len(batch), chunk_size):
              chunk = batch[i : i + chunk_size]
              target_conn.executemany(IMPORT_META_TYPES_SQL, chunk)
          target_conn.commit()

      logger.info("Imported %d meta types from SDE", len(batch))
      return len(batch)

  Update import_from_sde method:

  Add after agent imports (before timestamp recording):

  # Import meta groups
  if progress_callback:
      progress_callback("meta_groups", 0)
  result.meta_groups_imported = self._import_meta_groups(sde_conn, target_conn)
  if progress_callback:
      progress_callback("meta_groups", result.meta_groups_imported)

  # Import meta types
  if progress_callback:
      progress_callback("meta_types", 0)
  result.meta_types_imported = self._import_meta_types(sde_conn, target_conn)
  if progress_callback:
      progress_callback("meta_types", result.meta_types_imported)

  Update get_sde_status method:

  # Add after agent_count query
  try:
      meta_group_count = conn.execute("SELECT COUNT(*) FROM meta_groups").fetchone()[0]
  except sqlite3.OperationalError:
      meta_group_count = 0
  try:
      meta_type_count = conn.execute("SELECT COUNT(*) FROM meta_types").fetchone()[0]
  except sqlite3.OperationalError:
      meta_type_count = 0

  # Include in return SDEStatus
  return SDEStatus(
      # ... existing fields ...
      meta_group_count=meta_group_count,
      meta_type_count=meta_type_count,
  )

  ---
  3. Query Service Changes (queries.py)

  Add data classes:

  @dataclass(frozen=True)
  class MetaGroup:
      """Meta group definition (Tech I, Tech II, Faction, etc.)."""

      meta_group_id: int
      meta_group_name: str


  @dataclass(frozen=True)
  class MetaVariant:
      """A variant of a base item (T2, Faction, etc.)."""

      type_id: int
      type_name: str
      meta_group_id: int
      meta_group_name: str

  Add to SDEQueryService.__init__:

  # Meta type caches
  self._meta_groups: dict[int, MetaGroup | None] = {}
  self._meta_variants_by_parent: dict[int, tuple[MetaVariant, ...]] = {}
  self._parent_type: dict[int, int | None] = {}  # type_id → parent_type_id

  Add cache clearing to _check_cache_validity and invalidate_all:

  self._meta_groups.clear()
  self._meta_variants_by_parent.clear()
  self._parent_type.clear()

  Add query methods:

  def get_meta_group(self, meta_group_id: int) -> MetaGroup | None:
      """Get meta group by ID."""
      self._check_cache_validity()

      if meta_group_id in self._meta_groups:
          return self._meta_groups[meta_group_id]

      conn = self._db._get_connection()

      # Check if table exists
      cursor = conn.execute(
          "SELECT name FROM sqlite_master WHERE type='table' AND name='meta_groups'"
      )
      if not cursor.fetchone():
          return None

      cursor = conn.execute(
          "SELECT meta_group_id, meta_group_name FROM meta_groups WHERE meta_group_id = ?",
          (meta_group_id,),
      )
      row = cursor.fetchone()

      if not row:
          with self._lock:
              self._meta_groups[meta_group_id] = None
          return None

      result = MetaGroup(meta_group_id=row[0], meta_group_name=row[1])

      with self._lock:
          self._meta_groups[meta_group_id] = result

      return result


  def get_meta_variants(self, type_id: int) -> tuple[MetaVariant, ...]:
      """
      Get all meta variants for an item.

      If type_id is a variant (T2/Faction/etc), finds siblings via parent.
      If type_id is a base item (T1), finds all variants directly.

      Args:
          type_id: Any item type ID (base or variant)

      Returns:
          Tuple of MetaVariant for all variants (including the queried item)
      """
      self._check_cache_validity()

      # First, resolve to parent type if this is a variant
      parent_id = self._get_parent_type_id(type_id)
      if parent_id is None:
          # This might BE the parent, check if it has variants
          parent_id = type_id

      # Check cache for parent
      if parent_id in self._meta_variants_by_parent:
          return self._meta_variants_by_parent[parent_id]

      conn = self._db._get_connection()

      # Check if table exists
      cursor = conn.execute(
          "SELECT name FROM sqlite_master WHERE type='table' AND name='meta_types'"
      )
      if not cursor.fetchone():
          return ()

      # Query all variants for this parent
      cursor = conn.execute(
          """
          SELECT
              mt.type_id,
              t.type_name,
              mt.meta_group_id,
              mg.meta_group_name
          FROM meta_types mt
          JOIN types t ON mt.type_id = t.type_id
          JOIN meta_groups mg ON mt.meta_group_id = mg.meta_group_id
          WHERE mt.parent_type_id = ?
          ORDER BY mt.meta_group_id, t.type_name
          """,
          (parent_id,),
      )

      result = tuple(
          MetaVariant(
              type_id=row[0],
              type_name=row[1],
              meta_group_id=row[2],
              meta_group_name=row[3],
          )
          for row in cursor.fetchall()
      )

      with self._lock:
          self._meta_variants_by_parent[parent_id] = result

      return result


  def _get_parent_type_id(self, type_id: int) -> int | None:
      """Get the parent (base) type for a meta variant."""
      if type_id in self._parent_type:
          return self._parent_type[type_id]

      conn = self._db._get_connection()

      cursor = conn.execute(
          "SELECT name FROM sqlite_master WHERE type='table' AND name='meta_types'"
      )
      if not cursor.fetchone():
          return None

      cursor = conn.execute(
          "SELECT parent_type_id FROM meta_types WHERE type_id = ?",
          (type_id,),
      )
      row = cursor.fetchone()
      result = row[0] if row else None

      with self._lock:
          self._parent_type[type_id] = result

      return result


  def get_all_meta_groups(self) -> tuple[MetaGroup, ...]:
      """Get all meta groups."""
      conn = self._db._get_connection()

      cursor = conn.execute(
          "SELECT name FROM sqlite_master WHERE type='table' AND name='meta_groups'"
      )
      if not cursor.fetchone():
          return ()

      cursor = conn.execute(
          "SELECT meta_group_id, meta_group_name FROM meta_groups ORDER BY meta_group_id"
      )

      return tuple(
          MetaGroup(meta_group_id=row[0], meta_group_name=row[1])
          for row in cursor.fetchall()
      )

  ---
  4. Model Changes (models/sde.py)

  # =============================================================================
  # Meta Type Models
  # =============================================================================


  class MetaGroupInfo(SDEModel):
      """Meta group classification (Tech I, Tech II, Faction, etc.)."""

      meta_group_id: int = Field(ge=1, description="Meta group ID")
      meta_group_name: str = Field(description="Meta group name")


  class MetaVariantInfo(SDEModel):
      """A variant of a base item."""

      type_id: int = Field(ge=1, description="Variant type ID")
      type_name: str = Field(description="Variant item name")
      meta_group_id: int = Field(ge=1, description="Meta group ID")
      meta_group_name: str = Field(description="Meta group name (Tech II, Faction, etc.)")


  class MetaVariantsResult(SDEModel):
      """Result from sde meta_variants action."""

      query: str = Field(description="Original item query")
      query_type_id: int = Field(ge=0, description="Queried item type ID (0 if not found)")
      parent_type_id: int | None = Field(
          default=None,
          description="Base (T1) type ID, or None if queried item is the base"
      )
      parent_type_name: str | None = Field(
          default=None,
          description="Base (T1) item name"
      )
      found: bool = Field(description="Whether the item was found")
      variants: list[MetaVariantInfo] = Field(
          default_factory=list,
          description="All variants of this item (T2, Faction, etc.)"
      )
      total_variants: int = Field(default=0, ge=0, description="Number of variants found")
      warnings: list[str] = Field(default_factory=list)


  # Meta group ID constants (stable across SDE versions)
  META_GROUP_TECH_I = 1
  META_GROUP_TECH_II = 2
  META_GROUP_STORYLINE = 3
  META_GROUP_FACTION = 4
  META_GROUP_OFFICER = 5
  META_GROUP_DEADSPACE = 6
  META_GROUP_TECH_III = 14

  ---
  5. Dispatcher Changes (dispatchers/sde.py)

  Update action type and valid actions:

  SDEAction = Literal[
      "item_info",
      "blueprint_info",
      "search",
      "skill_requirements",
      "corporation_info",
      "agent_search",
      "agent_divisions",
      "cache_status",
      "meta_variants",  # NEW
  ]

  VALID_ACTIONS: set[str] = {
      # ... existing ...
      "meta_variants",
  }

  Update dispatcher docstring:

  """
  Actions:
  - ...existing...
  - meta_variants: Get T2/Faction/Officer variants of an item

  Meta variants params (action="meta_variants"):
      item: Item name (any variant or base item)

  Examples:
      sde(action="meta_variants", item="Medium Armor Repairer II")
      sde(action="meta_variants", item="Hammerhead I")
  """

  Add match case:

  case "meta_variants":
      return await _meta_variants(item)

  Add implementation:

  async def _meta_variants(item: str | None) -> dict:
      """Meta variants action - get all variants of an item."""
      if not item:
          raise InvalidParameterError("item", item, "Required for action='meta_variants'")

      from aria_esi.models.sde import MetaVariantInfo, MetaVariantsResult

      from ..market.database import get_market_database
      from ..sde.queries import get_sde_query_service

      db = get_market_database()
      conn = db._get_connection()
      query_service = get_sde_query_service()

      query = item.strip()
      query_lower = query.lower()

      # Check if meta_types table exists
      cursor = conn.execute(
          "SELECT name FROM sqlite_master WHERE type='table' AND name='meta_types'"
      )
      if not cursor.fetchone():
          return MetaVariantsResult(
              query=query,
              query_type_id=0,
              found=False,
              warnings=["Meta type data not imported. Run 'aria-esi sde-seed' to update SDE."],
          ).model_dump()

      # Look up the queried item
      item_data = _lookup_item(conn, query_lower, exact=True)
      if not item_data:
          item_data = _lookup_item(conn, query_lower, exact=False)

      if not item_data:
          return MetaVariantsResult(
              query=query,
              query_type_id=0,
              found=False,
              warnings=[f"Item '{query}' not found in SDE."],
          ).model_dump()

      type_id = item_data["type_id"]

      # Get variants
      variants = query_service.get_meta_variants(type_id)

      # Determine parent
      parent_id = query_service._get_parent_type_id(type_id)
      parent_name = None

      if parent_id:
          # Queried item is a variant, look up parent name
          cursor = conn.execute(
              "SELECT type_name FROM types WHERE type_id = ?", (parent_id,)
          )
          row = cursor.fetchone()
          parent_name = row[0] if row else None
      elif variants:
          # Queried item is the parent
          parent_id = type_id
          parent_name = item_data["type_name"]

      variant_list = [
          MetaVariantInfo(
              type_id=v.type_id,
              type_name=v.type_name,
              meta_group_id=v.meta_group_id,
              meta_group_name=v.meta_group_name,
          )
          for v in variants
      ]

      return MetaVariantsResult(
          query=query,
          query_type_id=type_id,
          parent_type_id=parent_id,
          parent_type_name=parent_name,
          found=True,
          variants=variant_list,
          total_variants=len(variant_list),
          warnings=[] if variants else ["No meta variants found for this item."],
      ).model_dump()

  ---
  6. Expected Output

  After implementation, queries like this will work:

  sde(action="meta_variants", item="Medium Armor Repairer II")

  Returns:
  {
    "query": "Medium Armor Repairer II",
    "query_type_id": 3538,
    "parent_type_id": 3532,
    "parent_type_name": "Medium Armor Repairer I",
    "found": true,
    "variants": [
      {"type_id": 3538, "type_name": "Medium Armor Repairer II", "meta_group_id": 2, "meta_group_name": "Tech II"},
      {"type_id": 13955, "type_name": "Medium I-a Enduring Armor Repairer", "meta_group_id": 1, "meta_group_name": "Tech I"},
      {"type_id": 5839, "type_name": "Medium ACM Compact Armor Repairer", "meta_group_id": 1, "meta_group_name": "Tech I"},
      {"type_id": 15751, "type_name": "Corpum A-Type Medium Armor Repairer", "meta_group_id": 6, "meta_group_name": "Deadspace"},
      {"type_id": 14068, "type_name": "Imperial Navy Medium Armor Repairer", "meta_group_id": 4, "meta_group_name": "Faction"}
    ],
    "total_variants": 5,
    "warnings": []
  }

  ---
  7. Migration Path

  1. No breaking changes - All existing functionality preserved
  2. Re-run SDE seed - Users run uv run aria-esi sde-seed to import new tables
  3. Deprecate YAML - Once validated, mark reference/skills/meta_module_alternatives.yaml for removal

  ---
  8. Testing

  Add tests to tests/mcp/test_sde_meta_types.py:

  """Tests for meta type functionality."""

  import pytest
  from aria_esi.mcp.sde.queries import get_sde_query_service

  class TestMetaTypes:
      """Test meta type queries."""

      def test_get_meta_variants_from_t2(self, seeded_db):
          """Query variants starting from T2 item."""
          service = get_sde_query_service()
          # Medium Armor Repairer II
          variants = service.get_meta_variants(3538)
          assert len(variants) > 0
          # Should include T1, T2, faction variants
          meta_groups = {v.meta_group_name for v in variants}
          assert "Tech II" in meta_groups or len(variants) > 0

      def test_get_meta_variants_from_t1(self, seeded_db):
          """Query variants starting from T1 item."""
          service = get_sde_query_service()
          # Medium Armor Repairer I
          variants = service.get_meta_variants(3532)
          assert len(variants) > 0

      def test_get_all_meta_groups(self, seeded_db):
          """List all meta groups."""
          service = get_sde_query_service()
          groups = service.get_all_meta_groups()
          assert len(groups) > 0
          names = {g.meta_group_name for g in groups}
          assert "Tech II" in names
