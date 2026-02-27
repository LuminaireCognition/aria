---
name: pi
description: Planetary Interaction guide for production chains, planet resources, and colony planning.
model: haiku
category: operations
triggers:
  - "/pi"
  - "PI production chain"
  - "what planet for [resource]"
  - "how to make [P1/P2/P3/P4 item]"
  - "planetary interaction"
  - "PI guide"
  - "what planets have [resource]"
requires_pilot: false
prerequisite_files:
  - reference/mechanics/planetary-interaction.json
---

# ARIA Planetary Interaction Module

## Command Syntax

```
/pi chain <product>           # Show production chain for an item
/pi planets <resource>        # Find planets with a resource
/pi single-planet             # Show P2 products makeable on single planet
/pi skills                    # PI skill recommendations
/pi profit [product]          # Profit analysis with market prices
/pi near <product>            # Find planets near home systems for production
```

## Location-Aware Planning

The `/pi near` command finds planets near your home systems that can produce a specific PI product.

### CLI Commands

```bash
# Build planet cache for nearby systems
uv run aria-esi cache-planets --around Dodixie --jumps 15

# Find planets for Robotics production near home
uv run aria-esi pi-near Robotics

# Check what planets are in a specific system
uv run aria-esi pi-planets Dodixie
```

### Example: `/pi near`

```
## PI Location Finder: [Product] ([Tier])

**Required P0 Resources:** [from reference file]
**Single-Planet Options:** [planet types with all required P0]
**Home Systems:** [from topology config]

### Nearby Systems with Suitable Planets

| System | [Planet Type] | [Planet Type] | Distance |
|--------|---------------|---------------|----------|
| [system] | [count] | [count] | [N] jumps |
```

### Building the Planet Cache

Planet types must be cached before `/pi near` can work.

```bash
uv run aria-esi cache-planets --around Dodixie --jumps 10
uv run aria-esi cache-planets --region "Sinq Laison"
uv run aria-esi cache-planets --systems Jita Perimeter Maurasi
uv run aria-esi cache-planets           # View cache statistics
uv run aria-esi cache-planets --clear   # Clear cache
```

Planet data is cached to: `userdata/cache/planet_types.json`

### POCO Tax Awareness

When using `/pi profit`, you can specify POCO tax rate:

```
/pi profit Robotics --poco-tax 5
```

- NPC-controlled POCOs (Interbus): 10% base tax
- Player-owned POCOs: 0-100% (varies by owner)

## Data Source

All PI data comes from `reference/mechanics/planetary-interaction.json`:
- Production chains (P0 -> P1 -> P2 -> P3 -> P4)
- Planet resources by type
- Production cycle times and quantities
- Skill requirements
- Export costs per unit by tier

**CRITICAL:** Always read the reference file before answering PI questions. Do not rely on training data for specific schematics or resource locations.

## Response Patterns

### Production Chain Query

When asked about producing an item:

1. Read `reference/mechanics/planetary-interaction.json`
2. Find the item in p2_schematics, p3_schematics, or p4_schematics
3. Trace backwards to raw resources (P0)
4. Present the full chain with inputs, planet types, and viable single-planet options

### Planet Resource Query

When asked about planets for a resource:

1. Read `reference/mechanics/planetary-interaction.json`
2. Check `planet_resources` section
3. List all planet types containing that resource, what P1 it produces, and downstream P2 products

### Single-Planet P2 Query

Read `single_planet_p2` from reference file. Present grouped by planet type.

### Skill Recommendations

Read skill requirements from reference file. Present in priority order: production skills first (Command Center Upgrades, Interplanetary Consolidation), then scanning skills (Planetology, Advanced Planetology).

## Profit Calculation

When asked about PI profit (`/pi profit <product>`):

1. **Read product from reference schematics.** Determine tier (P2/P3/P4) and get production constants for the product's tier (output quantity, input quantity, cycle time).
2. **Extract ALL input names from the schematic.** Build complete item list including the product itself.
3. **Fetch prices:** `market(action="prices", items=[product, ...all inputs])`. **Post-fetch validation:** If any input price is missing, display a warning and do NOT present profit numbers.
4. **Calculate:** input_cost, output_value, export tax (from `export_costs_per_unit` in reference file * POCO tax rate), net profit, margin, ISK/hour.

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--poco-tax` | 10% | POCO export tax rate (player-owned POCOs vary) |
| `--region` | jita | Price source region |

### Profit Response Format

```
## PI Profit Analysis: [Product]

**Product:** [Name] ([Tier])
**Cycle Time:** [from reference]
**Output:** [N] units/cycle

### Market Prices ([Region])

| Item | Role | Price/Unit |
|------|------|------------|
| [product] | Output | [fetched] |
| [input] | Input | [fetched] |

### Production Economics

| Metric | Value |
|--------|-------|
| **Output Value** | [computed] |
| **Input Cost** | [computed] |
| **Gross Profit** | [computed] |
| **Export Tax ([rate]%)** | [computed] |
| **Net Profit** | [computed] |
| **Margin** | [computed] |
| **ISK/Hour** | [computed] |

### Tax Sensitivity

| POCO Tax | Net Profit | Margin |
|----------|------------|--------|
| 5% | [computed] | [computed] |
| 10% | [computed] | [computed] |
| 15% | [computed] | [computed] |
```

For P4 products, note they require Barren or Temperate planets. If profit is negative, warn the pilot and suggest lower POCO tax, vertical integration, or different product.

## DO NOT

- **DO NOT** guess production chains - always read the reference file
- **DO NOT** recommend specific systems (PI is done anywhere)
- **DO NOT** discuss Equinox colony materials (separate sovereignty system)

## Notes

- P4 production requires Barren or Temperate planets (High Tech Production Plant restriction)
- Export tax is based on tier, not market value
