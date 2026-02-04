"""
Pydantic models for SDE MCP tools.

These models define the data structures for item lookups,
blueprint information, and NPC seeding queries.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# Base Model
# =============================================================================


class SDEModel(BaseModel):
    """
    Base model for SDE data with MCP-friendly serialization.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")


# =============================================================================
# Item Info Models
# =============================================================================


class ItemCategory(SDEModel):
    """Category classification (e.g., Ship, Module, Asteroid)."""

    category_id: int = Field(ge=1, description="Category ID")
    category_name: str = Field(description="Category name")


class ItemGroup(SDEModel):
    """Group classification (e.g., Frigate, Veldspar, Mining Laser)."""

    group_id: int = Field(ge=1, description="Group ID")
    group_name: str = Field(description="Group name")
    category_id: int = Field(ge=1, description="Parent category ID")


class ItemInfo(SDEModel):
    """
    Detailed item information from SDE.

    Includes classification hierarchy, description, and market info.
    For skill items, includes training attributes.
    """

    type_id: int = Field(ge=1, description="EVE type ID")
    type_name: str = Field(description="Item name")
    description: str | None = Field(default=None, description="Item description")
    group_id: int | None = Field(default=None, ge=1, description="Group ID")
    group_name: str | None = Field(default=None, description="Group name")
    category_id: int | None = Field(default=None, ge=1, description="Category ID")
    category_name: str | None = Field(default=None, description="Category name")
    market_group_id: int | None = Field(default=None, ge=1, description="Market group ID")
    volume: float | None = Field(default=None, ge=0, description="Volume in m³")
    packaged_volume: float | None = Field(default=None, ge=0, description="Packaged volume in m³")
    is_published: bool = Field(default=True, description="Whether item is published in game")
    is_blueprint: bool = Field(default=False, description="True if this is a blueprint item")
    # Skill-specific fields (only populated when category is Skill)
    skill_rank: int | None = Field(
        default=None, ge=1, le=16, description="Training time multiplier (1-16)"
    )
    skill_primary_attribute: str | None = Field(
        default=None, description="Primary training attribute (intelligence, memory, etc.)"
    )
    skill_secondary_attribute: str | None = Field(
        default=None, description="Secondary training attribute"
    )
    skill_prerequisites: list[dict] | None = Field(
        default=None,
        description="Prerequisites for this skill (only for Skill category items)",
    )


class ItemInfoResult(SDEModel):
    """Result from sde_item_info tool."""

    item: ItemInfo | None = Field(default=None, description="Item info if found")
    found: bool = Field(description="Whether the item was found")
    query: str = Field(description="Original search query")
    suggestions: list[str] = Field(
        default_factory=list,
        description="Suggested item names if not found",
    )
    warnings: list[str] = Field(default_factory=list)


# =============================================================================
# Blueprint Models
# =============================================================================


class BlueprintSource(SDEModel):
    """Source where a blueprint can be acquired."""

    source_type: Literal["npc", "loot", "invention", "reward"] = Field(
        description="How the blueprint is acquired"
    )
    corporation_id: int | None = Field(default=None, ge=1, description="NPC corp ID if NPC-seeded")
    corporation_name: str | None = Field(default=None, description="NPC corp name if NPC-seeded")
    region: str | None = Field(default=None, description="Region where available")
    region_id: int | None = Field(default=None, ge=1, description="Region ID for market queries")
    suggested_regions: list[tuple[int, str]] | None = Field(
        default=None,
        description="All regions for this corporation: list of (region_id, region_name)",
    )
    notes: str | None = Field(default=None, description="Additional acquisition notes")


class BlueprintMaterial(SDEModel):
    """Material required for blueprint manufacturing."""

    type_id: int = Field(ge=1, description="Material type ID")
    type_name: str = Field(description="Material name")
    quantity: int = Field(ge=1, description="Base quantity required")


class BlueprintInfo(SDEModel):
    """
    Complete blueprint information.

    Includes product, materials, times, and acquisition sources.
    """

    blueprint_type_id: int = Field(ge=1, description="Blueprint type ID")
    blueprint_name: str = Field(description="Blueprint item name")
    product_type_id: int = Field(ge=1, description="Product type ID")
    product_name: str = Field(description="Product item name")
    product_quantity: int = Field(default=1, ge=1, description="Units produced per run")
    manufacturing_time: int | None = Field(
        default=None,
        ge=0,
        description="Base manufacturing time in seconds",
    )
    copying_time: int | None = Field(
        default=None,
        ge=0,
        description="Base copying time in seconds",
    )
    research_me_time: int | None = Field(
        default=None,
        ge=0,
        description="Base ME research time in seconds",
    )
    research_te_time: int | None = Field(
        default=None,
        ge=0,
        description="Base TE research time in seconds",
    )
    invention_time: int | None = Field(
        default=None,
        ge=0,
        description="Base invention time in seconds",
    )
    max_production_limit: int = Field(
        default=1,
        ge=1,
        description="Maximum runs for BPC",
    )
    materials: list[BlueprintMaterial] = Field(
        default_factory=list,
        description="Manufacturing materials",
    )
    sources: list[BlueprintSource] = Field(
        default_factory=list,
        description="Where to acquire the blueprint",
    )


class BlueprintInfoResult(SDEModel):
    """Result from sde_blueprint_info tool."""

    blueprint: BlueprintInfo | None = Field(default=None, description="Blueprint info if found")
    found: bool = Field(description="Whether a blueprint was found")
    query: str = Field(description="Original search query")
    searched_as: Literal["product", "blueprint"] = Field(
        default="product",
        description="Whether query matched product or blueprint name",
    )
    suggestions: list[str] = Field(
        default_factory=list,
        description="Suggested item names if not found",
    )
    warnings: list[str] = Field(default_factory=list)


# =============================================================================
# Skill Models
# =============================================================================


class SkillPrerequisite(SDEModel):
    """A skill required before training another skill."""

    skill_id: int = Field(ge=1, description="Prerequisite skill type ID")
    skill_name: str = Field(description="Prerequisite skill name")
    required_level: int = Field(ge=1, le=5, description="Required level (1-5)")


class SkillInfo(SDEModel):
    """
    Complete skill information including training attributes.

    Provides all data needed for training time calculations.
    """

    type_id: int = Field(ge=1, description="Skill type ID")
    type_name: str = Field(description="Skill name")
    rank: int = Field(ge=1, le=16, description="Training time multiplier (1-16)")
    primary_attribute: str | None = Field(
        default=None,
        description="Primary training attribute (intelligence, memory, etc.)",
    )
    secondary_attribute: str | None = Field(
        default=None,
        description="Secondary training attribute",
    )
    prerequisites: list[SkillPrerequisite] = Field(
        default_factory=list,
        description="Skills required before training this skill",
    )


class TypeSkillRequirement(SDEModel):
    """A skill required to use a ship, module, or other item."""

    skill_id: int = Field(ge=1, description="Required skill type ID")
    skill_name: str = Field(description="Required skill name")
    required_level: int = Field(ge=1, le=5, description="Required level (1-5)")


class SkillRequirementNode(SDEModel):
    """
    A node in the skill requirement tree.

    Represents a skill at a specific level with its own prerequisites.
    Used for building the full prerequisite chain.
    """

    skill_id: int = Field(ge=1, description="Skill type ID")
    skill_name: str = Field(description="Skill name")
    required_level: int = Field(ge=1, le=5, description="Level required for parent")
    rank: int = Field(ge=1, le=16, default=1, description="Training time multiplier")
    primary_attribute: str | None = Field(default=None)
    secondary_attribute: str | None = Field(default=None)


class SkillRequirementsResult(SDEModel):
    """
    Result from sde_skill_requirements tool.

    Contains both direct requirements and the full prerequisite tree.
    """

    item: str = Field(description="Item name queried")
    item_type_id: int = Field(ge=0, description="Item type ID (0 if not found)")
    item_category: str | None = Field(
        default=None, description="Item category (Ship, Module, etc.)"
    )
    found: bool = Field(description="Whether the item was found")
    direct_requirements: list[TypeSkillRequirement] = Field(
        default_factory=list,
        description="Skills directly required to use this item",
    )
    full_prerequisite_tree: list[SkillRequirementNode] = Field(
        default_factory=list,
        description="All skills needed including prerequisites of prerequisites",
    )
    total_skills: int = Field(default=0, ge=0, description="Total unique skills in tree")
    warnings: list[str] = Field(default_factory=list)


class TrainingTimeRequest(SDEModel):
    """A single skill level to calculate training time for."""

    skill_name: str = Field(description="Skill name")
    from_level: int = Field(ge=0, le=4, default=0, description="Current skill level (0-4)")
    to_level: int = Field(ge=1, le=5, description="Target skill level (1-5)")


class TrainingTimeResult(SDEModel):
    """
    Result from skill_training_time tool.

    Provides detailed training time breakdown.
    """

    skills: list[dict] = Field(
        default_factory=list,
        description="Per-skill training time breakdown",
    )
    total_skillpoints: int = Field(default=0, ge=0, description="Total SP needed")
    total_training_seconds: int = Field(
        default=0, ge=0, description="Total training time in seconds"
    )
    total_training_formatted: str = Field(default="", description="Human-readable training time")
    attributes_used: dict | None = Field(
        default=None,
        description="Character attributes used for calculation",
    )
    warnings: list[str] = Field(default_factory=list)


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
        description="Base (T1) type ID, or None if queried item is the base",
    )
    parent_type_name: str | None = Field(default=None, description="Base (T1) item name")
    found: bool = Field(description="Whether the item was found")
    variants: list[MetaVariantInfo] = Field(
        default_factory=list,
        description="All variants of this item (T2, Faction, etc.)",
    )
    total_variants: int = Field(default=0, ge=0, description="Number of variants found")
    warnings: list[str] = Field(default_factory=list)


# =============================================================================
# Search Models
# =============================================================================


class SearchResultItem(SDEModel):
    """Single item in search results."""

    type_id: int = Field(ge=1)
    type_name: str
    group_name: str | None = None
    category_name: str | None = None
    is_blueprint: bool = False


class SDESearchResult(SDEModel):
    """Result from sde_search tool."""

    items: list[SearchResultItem] = Field(default_factory=list)
    total_found: int = Field(ge=0, description="Total matching items")
    query: str = Field(description="Search query")
    category_filter: str | None = Field(default=None, description="Category filter applied")
    limit: int = Field(ge=1, description="Maximum results requested")
    warnings: list[str] = Field(default_factory=list)


# =============================================================================
# Status Models
# =============================================================================


class SDEStatusResult(SDEModel):
    """Result from sde_cache_status tool."""

    seeded: bool = Field(description="Whether SDE data has been imported")
    category_count: int = Field(default=0, ge=0)
    group_count: int = Field(default=0, ge=0)
    type_count: int = Field(default=0, ge=0, description="Published types")
    blueprint_count: int = Field(default=0, ge=0)
    npc_seeding_count: int = Field(default=0, ge=0)
    npc_corporation_count: int = Field(default=0, ge=0)
    sde_version: str | None = Field(default=None, description="SDE schema version")
    import_timestamp: str | None = Field(default=None, description="Last import timestamp")
    database_path: str | None = Field(default=None)
    database_size_mb: float | None = Field(default=None, ge=0)


# =============================================================================
# Constants
# =============================================================================

# Example corporation ID - Use SDEQueryService.get_corporation_regions() for dynamic lookups
# Kept for convenience in examples and documentation only
ORE_CORPORATION_ID = 1000129
ORE_CORPORATION_NAME = "Outer Ring Excavations"

# Category IDs for common lookups
# These are stable across SDE versions and validated during import
# For dynamic lookup by name, use SDEQueryService.get_category_id()
CATEGORY_SHIP = 6
CATEGORY_MODULE = 7
CATEGORY_CHARGE = 8
CATEGORY_BLUEPRINT = 9
CATEGORY_SKILL = 16
CATEGORY_DRONE = 18
CATEGORY_ASTEROID = 25

# Meta group ID constants (stable across SDE versions)
META_GROUP_TECH_I = 1
META_GROUP_TECH_II = 2
META_GROUP_STORYLINE = 3
META_GROUP_FACTION = 4
META_GROUP_OFFICER = 5
META_GROUP_DEADSPACE = 6
META_GROUP_TECH_III = 14
