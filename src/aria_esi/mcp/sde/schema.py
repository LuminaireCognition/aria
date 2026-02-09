"""
SDE Schema Extensions for Market Database.

Defines SQL schema for EVE Static Data Export tables that extend
the market database with item classification, blueprint, and NPC
seeding information.
"""

# =============================================================================
# Schema Constants
# =============================================================================

# Version number for SDE schema (separate from market schema)
SDE_SCHEMA_VERSION = 1

# SQL to extend existing types table with description and published flag
EXTEND_TYPES_SQL = """
-- Add description column if not exists
-- SQLite doesn't have ADD COLUMN IF NOT EXISTS, so we check first
PRAGMA table_info(types);
"""

ALTER_TYPES_SQL = """
-- Add description to types table
ALTER TABLE types ADD COLUMN description TEXT;

-- Add published flag (1 = published, 0 = unpublished/internal)
ALTER TABLE types ADD COLUMN published INTEGER DEFAULT 1;
"""

# SQL to create SDE-specific tables
SDE_TABLES_SQL = """
-- Group classification (e.g., "Frigate", "Veldspar")
CREATE TABLE IF NOT EXISTS groups (
    group_id INTEGER PRIMARY KEY,
    group_name TEXT NOT NULL,
    group_name_lower TEXT NOT NULL,
    category_id INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_groups_name_lower ON groups(group_name_lower);
CREATE INDEX IF NOT EXISTS idx_groups_category ON groups(category_id);

-- Category classification (e.g., "Ship", "Asteroid")
CREATE TABLE IF NOT EXISTS categories (
    category_id INTEGER PRIMARY KEY,
    category_name TEXT NOT NULL,
    category_name_lower TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_categories_name_lower ON categories(category_name_lower);

-- Blueprint definitions
CREATE TABLE IF NOT EXISTS blueprints (
    type_id INTEGER PRIMARY KEY,
    manufacturing_time INTEGER,
    copying_time INTEGER,
    research_material_time INTEGER,
    research_time_time INTEGER,
    invention_time INTEGER,
    max_production_limit INTEGER DEFAULT 1
);

-- What blueprints produce (manufacturing outputs)
CREATE TABLE IF NOT EXISTS blueprint_products (
    blueprint_type_id INTEGER NOT NULL,
    product_type_id INTEGER NOT NULL,
    quantity INTEGER DEFAULT 1,
    PRIMARY KEY (blueprint_type_id, product_type_id)
);

CREATE INDEX IF NOT EXISTS idx_blueprint_products_product ON blueprint_products(product_type_id);

-- Blueprint manufacturing materials
-- activity_id: 1=Manufacturing, 9=Reactions, 11=Simple Reactions
CREATE TABLE IF NOT EXISTS blueprint_materials (
    blueprint_type_id INTEGER NOT NULL,
    material_type_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    activity_id INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (blueprint_type_id, material_type_id, activity_id)
);

CREATE INDEX IF NOT EXISTS idx_blueprint_materials_blueprint ON blueprint_materials(blueprint_type_id);
CREATE INDEX IF NOT EXISTS idx_blueprint_materials_activity ON blueprint_materials(activity_id);

-- NPC seeding (which corps sell which BPOs at NPC stations)
CREATE TABLE IF NOT EXISTS npc_seeding (
    type_id INTEGER NOT NULL,
    corporation_id INTEGER NOT NULL,
    PRIMARY KEY (type_id, corporation_id)
);

CREATE INDEX IF NOT EXISTS idx_npc_seeding_type ON npc_seeding(type_id);
CREATE INDEX IF NOT EXISTS idx_npc_seeding_corp ON npc_seeding(corporation_id);

-- NPC corporation info
CREATE TABLE IF NOT EXISTS npc_corporations (
    corporation_id INTEGER PRIMARY KEY,
    corporation_name TEXT NOT NULL,
    corporation_name_lower TEXT NOT NULL,
    faction_id INTEGER
);

CREATE INDEX IF NOT EXISTS idx_npc_corps_name_lower ON npc_corporations(corporation_name_lower);

-- Regions (for market queries beyond trade hubs)
CREATE TABLE IF NOT EXISTS regions (
    region_id INTEGER PRIMARY KEY,
    region_name TEXT NOT NULL,
    region_name_lower TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_regions_name_lower ON regions(region_name_lower);

-- NPC Stations (for nearby market search station name resolution)
-- Only NPC stations are stored here; player structures require auth to resolve
CREATE TABLE IF NOT EXISTS stations (
    station_id INTEGER PRIMARY KEY,
    station_name TEXT NOT NULL,
    station_name_lower TEXT NOT NULL,
    system_id INTEGER NOT NULL,
    region_id INTEGER NOT NULL,
    corporation_id INTEGER
);

CREATE INDEX IF NOT EXISTS idx_stations_name_lower ON stations(station_name_lower);
CREATE INDEX IF NOT EXISTS idx_stations_system ON stations(system_id);
CREATE INDEX IF NOT EXISTS idx_stations_region ON stations(region_id);
CREATE INDEX IF NOT EXISTS idx_stations_corp_region ON stations(corporation_id, region_id);

-- SDE metadata (version, import date, etc.)
INSERT OR REPLACE INTO metadata (key, value) VALUES ('sde_schema_version', '2');
"""

# SQL to check if SDE tables exist
CHECK_SDE_TABLES_SQL = """
SELECT name FROM sqlite_master
WHERE type='table' AND name IN ('groups', 'categories', 'blueprints', 'npc_seeding', 'stations');
"""

# SQL to get SDE table counts for status
SDE_STATUS_SQL = """
SELECT
    (SELECT COUNT(*) FROM groups) as group_count,
    (SELECT COUNT(*) FROM categories) as category_count,
    (SELECT COUNT(*) FROM blueprints) as blueprint_count,
    (SELECT COUNT(*) FROM blueprint_products) as product_count,
    (SELECT COUNT(*) FROM npc_seeding) as seeding_count,
    (SELECT COUNT(*) FROM npc_corporations) as npc_corp_count,
    (SELECT COUNT(*) FROM stations WHERE 1) as station_count;
"""

# =============================================================================
# Import SQL Templates
# =============================================================================

# These are parameterized queries for bulk import from Fuzzwork SQLite

IMPORT_GROUPS_SQL = """
INSERT OR REPLACE INTO groups (group_id, group_name, group_name_lower, category_id)
VALUES (?, ?, ?, ?);
"""

IMPORT_CATEGORIES_SQL = """
INSERT OR REPLACE INTO categories (category_id, category_name, category_name_lower)
VALUES (?, ?, ?);
"""

IMPORT_TYPES_SQL = """
INSERT OR REPLACE INTO types (
    type_id, type_name, type_name_lower,
    group_id, category_id, market_group_id,
    volume, packaged_volume, description, published
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
"""

IMPORT_BLUEPRINTS_SQL = """
INSERT OR REPLACE INTO blueprints (
    type_id, manufacturing_time, copying_time,
    research_material_time, research_time_time,
    invention_time, max_production_limit
)
VALUES (?, ?, ?, ?, ?, ?, ?);
"""

IMPORT_BLUEPRINT_PRODUCTS_SQL = """
INSERT OR REPLACE INTO blueprint_products (blueprint_type_id, product_type_id, quantity)
VALUES (?, ?, ?);
"""

IMPORT_BLUEPRINT_MATERIALS_SQL = """
INSERT OR REPLACE INTO blueprint_materials (blueprint_type_id, material_type_id, quantity, activity_id)
VALUES (?, ?, ?, ?);
"""

IMPORT_NPC_SEEDING_SQL = """
INSERT OR REPLACE INTO npc_seeding (type_id, corporation_id)
VALUES (?, ?);
"""

IMPORT_NPC_CORPORATIONS_SQL = """
INSERT OR REPLACE INTO npc_corporations (
    corporation_id, corporation_name, corporation_name_lower, faction_id
)
VALUES (?, ?, ?, ?);
"""

IMPORT_REGIONS_SQL = """
INSERT OR REPLACE INTO regions (region_id, region_name, region_name_lower)
VALUES (?, ?, ?);
"""

IMPORT_STATIONS_SQL = """
INSERT OR REPLACE INTO stations (
    station_id, station_name, station_name_lower,
    system_id, region_id, corporation_id
)
VALUES (?, ?, ?, ?, ?, ?);
"""

# =============================================================================
# Skill Tables SQL
# =============================================================================

# SQL to create skill-related tables
SKILL_TABLES_SQL = """
-- Skill attributes (training parameters)
-- rank is the training time multiplier (1-8 typically)
CREATE TABLE IF NOT EXISTS skill_attributes (
    type_id INTEGER PRIMARY KEY,
    rank INTEGER NOT NULL,
    primary_attribute TEXT,
    secondary_attribute TEXT
);

-- Skill prerequisites (what skills are needed to train this skill)
CREATE TABLE IF NOT EXISTS skill_prerequisites (
    skill_type_id INTEGER NOT NULL,
    prerequisite_skill_id INTEGER NOT NULL,
    prerequisite_level INTEGER NOT NULL,
    PRIMARY KEY (skill_type_id, prerequisite_skill_id)
);

CREATE INDEX IF NOT EXISTS idx_skill_prereqs_skill ON skill_prerequisites(skill_type_id);
CREATE INDEX IF NOT EXISTS idx_skill_prereqs_prereq ON skill_prerequisites(prerequisite_skill_id);

-- Type requirements (skills needed to use ships/modules)
-- Includes ships, modules, drones, and other items that require skills
CREATE TABLE IF NOT EXISTS type_skill_requirements (
    type_id INTEGER NOT NULL,
    required_skill_id INTEGER NOT NULL,
    required_level INTEGER NOT NULL,
    PRIMARY KEY (type_id, required_skill_id)
);

CREATE INDEX IF NOT EXISTS idx_type_reqs_type ON type_skill_requirements(type_id);
CREATE INDEX IF NOT EXISTS idx_type_reqs_skill ON type_skill_requirements(required_skill_id);
"""

# Import SQL for skill data
IMPORT_SKILL_ATTRIBUTES_SQL = """
INSERT OR REPLACE INTO skill_attributes (type_id, rank, primary_attribute, secondary_attribute)
VALUES (?, ?, ?, ?);
"""

IMPORT_SKILL_PREREQUISITES_SQL = """
INSERT OR REPLACE INTO skill_prerequisites (skill_type_id, prerequisite_skill_id, prerequisite_level)
VALUES (?, ?, ?);
"""

IMPORT_TYPE_SKILL_REQUIREMENTS_SQL = """
INSERT OR REPLACE INTO type_skill_requirements (type_id, required_skill_id, required_level)
VALUES (?, ?, ?);
"""

# =============================================================================
# Agent Tables SQL
# =============================================================================

# SQL to create agent-related tables
AGENT_TABLES_SQL = """
-- NPC agent divisions (Security, Distribution, Mining, etc.)
CREATE TABLE IF NOT EXISTS agent_divisions (
    division_id INTEGER PRIMARY KEY,
    division_name TEXT NOT NULL,
    division_name_lower TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_divisions_name_lower ON agent_divisions(division_name_lower);

-- NPC agent types (basic agent, research agent, storyline, etc.)
CREATE TABLE IF NOT EXISTS agent_types (
    agent_type_id INTEGER PRIMARY KEY,
    agent_type_name TEXT NOT NULL
);

-- NPC agents
CREATE TABLE IF NOT EXISTS agents (
    agent_id INTEGER PRIMARY KEY,
    agent_name TEXT NOT NULL,
    agent_name_lower TEXT NOT NULL,
    division_id INTEGER,
    corporation_id INTEGER NOT NULL,
    station_id INTEGER,
    system_id INTEGER,
    level INTEGER NOT NULL,
    agent_type_id INTEGER,
    FOREIGN KEY (division_id) REFERENCES agent_divisions(division_id),
    FOREIGN KEY (corporation_id) REFERENCES npc_corporations(corporation_id),
    FOREIGN KEY (station_id) REFERENCES stations(station_id),
    FOREIGN KEY (agent_type_id) REFERENCES agent_types(agent_type_id)
);

CREATE INDEX IF NOT EXISTS idx_agents_name_lower ON agents(agent_name_lower);
CREATE INDEX IF NOT EXISTS idx_agents_corporation ON agents(corporation_id);
CREATE INDEX IF NOT EXISTS idx_agents_division ON agents(division_id);
CREATE INDEX IF NOT EXISTS idx_agents_level ON agents(level);
CREATE INDEX IF NOT EXISTS idx_agents_corp_level ON agents(corporation_id, level);
CREATE INDEX IF NOT EXISTS idx_agents_corp_div_level ON agents(corporation_id, division_id, level);
CREATE INDEX IF NOT EXISTS idx_agents_station ON agents(station_id);
CREATE INDEX IF NOT EXISTS idx_agents_system ON agents(system_id);
"""

# Import SQL for agent data
IMPORT_AGENT_DIVISIONS_SQL = """
INSERT OR REPLACE INTO agent_divisions (division_id, division_name, division_name_lower)
VALUES (?, ?, ?);
"""

IMPORT_AGENT_TYPES_SQL = """
INSERT OR REPLACE INTO agent_types (agent_type_id, agent_type_name)
VALUES (?, ?);
"""

IMPORT_AGENTS_SQL = """
INSERT OR REPLACE INTO agents (
    agent_id, agent_name, agent_name_lower,
    division_id, corporation_id, station_id, system_id,
    level, agent_type_id
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
"""

# =============================================================================
# Meta Type Tables SQL
# =============================================================================

# SQL to create meta type tables
META_TYPE_TABLES_SQL = """
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
"""

# Import SQL for meta type data
IMPORT_META_GROUPS_SQL = """
INSERT OR REPLACE INTO meta_groups (meta_group_id, meta_group_name, meta_group_name_lower)
VALUES (?, ?, ?);
"""

IMPORT_META_TYPES_SQL = """
INSERT OR REPLACE INTO meta_types (type_id, parent_type_id, meta_group_id)
VALUES (?, ?, ?);
"""
