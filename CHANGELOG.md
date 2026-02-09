# Changelog

All notable changes to ARIA will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

#### Industry Feature Enhancements
- **Profit Per Hour calculation** for `/build-cost` skill
  - New `calculate_profit_per_hour()` function in `industry_costs.py`
  - TE (Time Efficiency) calculations: Blueprint TE 0-20 + Facility TE bonuses
  - Facility TE bonuses: Raitaru 15%, Azbel 20%, Sotiyo 30%
  - New helper functions: `format_time_duration()`, `format_isk()`
  - Updated SKILL.md output format with Manufacturing Time and Profit/Hour rows

- **Component Manufacturing Chains** (`--full-chain` flag) for recursive BOM resolution
  - New `industry_chains.py` service with `ChainResolver` class
  - Recursive chain resolution with circular reference protection (max depth: 5)
  - Terminal materials definition: minerals, PI P0/P1, moon materials, ice products, salvage
  - Build vs Buy analysis comparing component market price to build cost
  - Resolution modes: buy_all_components, build_ship_components, build_all
  - Reference data: `reference/industry/terminal_materials.json`

- **Reactions Skill** (`/reactions`) for moon goo and fuel block calculations
  - New `reactions.py` service with fuel block cost/profit calculations
  - Fuel block recipes for all four factions (Nitrogen/Caldari, Hydrogen/Minmatar, Helium/Amarr, Oxygen/Gallente)
  - Reaction time formula: `base_time × (1 - reactions_skill × 0.04) × (1 - refinery_bonus)`
  - Refinery bonuses: Athanor 0%, Tatara 25%
  - Reference data: `reference/industry/fuel_blocks.json`
  - New skill: `.claude/skills/reactions/SKILL.md`
  - Schema change: Added `activity_id` column to `blueprint_materials` table
  - SDE importer now imports activityID 1 (Manufacturing), 9 (Reactions), 11 (Simple Reactions)
  - Re-run `uv run aria-esi sde-seed --force` to import reaction data

#### Meta Types SDE Ingest
- New `sde(action="meta_variants")` MCP action for T2/Faction/Officer variant lookups
- Import `invMetaGroups` and `invMetaTypes` tables from Fuzzwork SDE
- Query any item to find all meta variants (T1, T2, Faction, Deadspace, Officer)
- Bidirectional lookup: query T2 item to find siblings, or T1 to find all variants
- New dataclasses: `MetaGroup`, `MetaVariant` in queries.py
- New models: `MetaGroupInfo`, `MetaVariantInfo`, `MetaVariantsResult`
- Meta group constants: `META_GROUP_TECH_I`, `META_GROUP_TECH_II`, `META_GROUP_FACTION`, etc.
- Re-run `uv run aria-esi sde-seed` to populate new tables

#### Skill Test Harness Layer 3 (Semantic Evals)
- G-Eval LLM-as-judge framework for skill response quality validation
- New optional dependency: `test-semantic` group with `deepeval>=0.21.0`
- Eval configuration files: `tests/skills/evals/*.eval.yaml`
- Ground truth data: `tests/skills/ground_truth/missions/the_blockade_l4.json`
- Weighted scoring across factual accuracy, completeness, actionability, persona consistency
- Infrastructure tests validate eval config loading and weight sums
- Implemented `invoke_skill()` using Tier 2 API invoker with mock tool support
- Implemented `get_active_persona()` to read pilot profile for consistency checks
- Added `load_skill_fixture_mocks()` helper for fixture-based mock responses
- Run with: `uv run pytest -m semantic` (requires ANTHROPIC_API_KEY)

#### Asset Audit: Smart Insights
- New `--insights` flag for `/assets` command
- Forgotten asset detection (low-value items in remote locations)
- Consolidation suggestions with jump distances to home/trade hubs
- Duplicate ship detection across locations
- New service: `src/aria_esi/services/asset_insights.py`
- Trade hub reference data: `reference/constants/trade_hubs.json`
- Snapshot persistence now includes location values and insights summary
- Combined `--insights --snapshot` persists full analysis to YAML snapshots

#### PI Helper: Location-Aware Planning
- New `/pi near [product]` command to find optimal planets near home systems
- Planet type caching service for PI location planning
- New CLI commands: `cache-planets`, `pi-near`, `pi-planets`
- P0→P4 production chain tracing with planet type requirements
- New service: `src/aria_esi/services/planet_cache.py`

#### Build Cost: T2 Invention Chains
- T2 invention cost calculations with `--t2` flag
- Invention success rate calculator (base rate + skills + decryptors)
- Decryptor comparison with ME/TE/runs modifiers
- T2 BPC stats calculation from invention
- Expected cost amortization across BPC runs
- Invention reference data: `reference/industry/invention_materials.json`

#### Build Cost: Character Integration
- `--use-character` flag to use pilot's actual blueprint ME/TE from ESI
- Character blueprint detection and best-match selection (BPO preference)
- Skill-aware invention bonuses from character's trained skills
- Industry capability summary (manufacturing slots, science slots, time reduction)
- New service: `src/aria_esi/services/character_industry.py`
- Added step-by-step workflow documentation for ESI-authenticated cost calculations

#### Archetype Fit Stats Caching
- New `aria-esi fit update-stats` CLI command for batch stats calculation
- Calculates DPS, EHP, tank type, resists, damage profiles via EOS fitting engine
- Tank classification (active/buffer/passive) with regen rates
- Primary damage and resist derivation for mission matching
- Optional ISK estimation via Jita market prices
- Writes stats section to archetype YAML files
- Supports `--all`, `--hull`, `--dry-run`, `--no-prices`, `--region` options

#### Archetype Fit Validation
- New `aria-esi fit validate` CLI command for fit quality checks
- Omega/T2 consistency validation: warns if `omega_required: false` with T2 modules
- Runs all validators: header, EFT, stats, variant_group, omega consistency
- New `_validate_omega_consistency()` check in `validator.py`
- New `_has_t2_modules()` helper function for T2 module detection

### Security

#### SEC-001/SEC-002: Path Allowlisting Implementation
- **SEC-001 (Critical):** Persona file path allowlisting to prevent arbitrary file inclusion
- **SEC-002 (High):** Skill overlay and redirect path validation
- New `ALLOWED_EXTENSIONS` constant (`.md`, `.yaml`, `.json` only)
- New `validate_persona_file_path()` combining prefix allowlist with extension checking
- New `safe_read_persona_file()` with validation, extension check, and size limits (100KB default)
- Pilot directory validation in notification persona loader (format: `{numeric_id}_{name}`)
- Compile-time redirect validation via `validate_skill_redirects()` in persona-context command
- Runtime path validation documented in CLAUDE.md
- Comprehensive test coverage in `tests/core/test_path_security.py` and `tests/integration/test_security_paths.py`
- Attack vectors covered: path traversal, absolute paths, wrong extensions, non-allowlisted prefixes, symlink escapes

### Changed

#### Security Documentation Update
- Updated `dev/reviews/SECURITY_000.md` with mitigation status for all findings
- Added verification commands section for security audits
- Marked 4 of 5 original security findings as mitigated
- Updated `SECURITY.md` with implemented security controls documentation
- Added Security section to `docs/README.md`
- Updated `docs/PERSONA_LOADING.md` with path validation implementation reference

#### Test Infrastructure (CTX-001)
- Expanded `reset_all_singletons` pytest fixture with 14 additional singleton resets
- Added resets for RedisQ services: name_resolver, war_context, database, registry, preset_loader, threat_cache, notification_manager, npc_faction_mapper, persona_loader, entity_watchlist_manager, fetch_queue, poller, entity_filter
- Added reset for MCP trace context
- Total singleton resets in fixture: 33 (prevents cross-test contamination)
- Updated fixture docstring with comprehensive reset documentation

### Removed

- Removed `scripts/update_eos_data.py` - functionality fully replaced by `aria-esi eos-seed` CLI command with superior features (commit pinning, break-glass mode, cache invalidation)

## [0.1.0] - 2026-01-30

### Initial Release

First public release of ARIA - Adaptive Reasoning & Intelligence Array.

### Features

- **40+ slash commands** for tactical intel, market analysis, and operations
- **Multi-pilot support** with per-pilot profiles and credentials
- **Optional ESI integration** for live game data (works fully without it)
- **Five faction personas** (Gallente, Caldari, Minmatar, Amarr, Pirate)
- **Roleplay mode** off by default, full immersion available
- **MCP server** for universe navigation and market queries
- **CLI tools** for route planning, market prices, and system activity

### Notable Commands

| Category | Commands |
|----------|----------|
| Tactical | `/mission-brief`, `/threat-assessment`, `/fitting`, `/gatecamp` |
| Navigation | `/route`, `/orient` |
| Financial | `/price`, `/arbitrage`, `/assets`, `/orders` |
| Operations | `/mining-advisory`, `/exploration`, `/pi`, `/skillplan` |

### Documentation

- Comprehensive docs in `docs/` directory
- Example pilot configurations for common playstyles
- Quick reference guide (`docs/TLDR.md`)
- First-run setup guide (`docs/FIRST_RUN.md`)
