# Ship Archetype Library

Curated, EOS-validated ship fittings for common PvE activities. Used as on-demand `data_sources` by fitting skills to prevent hallucination in fit generation.

## Schema

Each archetype YAML contains:

| Field | Purpose |
|-------|---------|
| `archetype.hull` | Ship name |
| `archetype.skill_tier` | t1, meta, t2_budget, t2_optimal (see `_shared/skill_tiers.yaml`) |
| `eft` | Complete EFT fitting block, validated via EOS |
| `skill_requirements` | Required/recommended skills for the fit |
| `stats` | DPS, EHP, tank, validated_date — from EOS |
| `damage_tuning` | Faction-specific module/drone/ammo overrides |
| `notes` | Engagement range, warnings, purpose |
| `upgrade_path` | Next tier modules and ship progression |

## Directory Structure

```
_shared/              Shared configs (module tiers, faction tuning, skill tiers)
hulls/{class}/{hull}/pve/{activity}/{level}/{tier}.yaml
```

## Context Efficiency

These files are **never auto-loaded**. Skills read `INDEX.md` on-demand (~30 lines) to find a matching archetype, then read one YAML (~50-80 lines) if matched. Zero additions to `prerequisite_files` or always-loaded context.

**History:** Directory was deleted in commit `24dda20a` as dead code (no skill consumed the files). Restored with active consumer paths in `/mission-brief`, `/fitting`, `/ship-next`, and `/fit-budget`.
