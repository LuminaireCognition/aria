---
paths:
  - ".claude/skills/**"
---

# Skill Output Rules

## Provenance Footer

When producing skill output, append a `Sources:` footer showing data origin. Format:

```
Sources: universe(route, activity) | market(prices) | SDE: item_info | Ref: npc_damage_types.md
```

- List each MCP dispatcher call made (action names only)
- List reference files consulted from `prerequisite_files`
- Omit pilot profile reads (assumed)
- Keep to one line

## Line Budgets

If a skill declares `preferred_max_lines` in its frontmatter, target that line count instead of the global 30-line default. This is a soft target, not a hard ceiling — complex or wide-scope queries may exceed it by up to 50% when every additional line directly answers the user's question. Simple queries should stay within the preferred target.
