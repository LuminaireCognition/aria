# Contributing Skills

Step-by-step guide for creating a new ARIA skill (slash command).

## Quick Start Checklist

1. Create directory: `.claude/skills/{name}/`
2. Create `SKILL.md` with YAML frontmatter and skill body
3. Register: add an entry to `.claude/skills/_index.json` (hand-maintained)
4. Validate: `uv run python .claude/scripts/aria-skill-preflight.py {name}`
5. Test by invoking `/{name}` in a Claude Code session

## Skill Directory Anatomy

```
.claude/skills/{name}/
├── SKILL.md              # Required — frontmatter + skill instructions
├── CHECKLIST.md          # Optional — validation checklist for the skill
└── EFT-FORMAT.md         # Optional — supporting reference files
```

Only `SKILL.md` is required. Supporting files are loaded by the skill body via explicit file reads.

## Frontmatter Reference

Every `SKILL.md` starts with YAML frontmatter between `---` fences:

```yaml
---
name: my-skill               # Required. kebab-case, matches directory name
description: Brief user-facing description of what this skill does.  # Required
model: haiku                  # Optional. "haiku" (fast/simple) or "sonnet" (complex)
category: tactical            # Optional. See categories below
triggers:                     # Optional. Natural language phrases
  - "/my-skill"
  - "do the thing"
  - "help me with [topic]"
requires_pilot: true          # Optional. Needs active pilot context?
data_sources:                 # Optional. Local files the skill reads
  - userdata/pilots/{active_pilot}/profile.md
  - reference/mechanics/some_data.json
external_sources:             # Optional. Trusted domains for web fetch
  - wiki.eveuniversity.org
esi_scopes:                   # Optional. ESI OAuth scopes needed
  - esi-skills.read_skills.v1
has_persona_overlay: true     # Optional. Has persona-specific overlays?
---
```

**Categories:** `tactical`, `operations`, `financial`, `industry`, `identity`, `system`

For the full field specification, see [SCHEMA.md](../../.claude/skills/SCHEMA.md).

## Skill Body Conventions

After the frontmatter, write the skill instructions in markdown. The LLM reads this at invocation time.

### Recommended Sections

```markdown
# {Skill Name}

> One-line description matching the frontmatter `description`.

## Trigger Phrases
- List natural language triggers (mirrors frontmatter for LLM context)

## Data Sources
- List files the skill reads, with `{active_pilot}` placeholders

## Procedure
1. Step-by-step instructions for the LLM
2. What to read, what to compute, what to present

## Output Format
Describe the expected response structure (tables, code blocks, etc.)

## Edge Cases
- What to do when data is missing
- Fallback behavior
```

### Prerequisite File Path Disambiguation

Path resolution for `prerequisite_files` is defined at the protocol level in `personas/_shared/skill-loading.md` §1.5 and `CLAUDE.md` §Skill Loading step 3 — those are the canonical rules. Per-skill annotations are optional defense-in-depth.

**Per-read parentheticals** — optional, encouraged for complex skills with many file references:

```markdown
| 1 | Read `reference/mechanics/my_data.md` (project-root-relative path, not skill-directory path) | ... |
```

**Failure instruction** — if a read fails, report the exact path that failed — do not substitute training data.

**Reference implementations:** `abyssal` (line 31 of SKILL.md) and `exploration` (Tool Calls table).

### Guidelines

- Keep skills under 200 lines — the LLM loads the full file into context
- Use imperative voice ("Read the profile", "Calculate the cost")
- Reference MCP dispatchers by name: `universe(action="route", ...)`
- Include CLI fallback commands where applicable
- Use `{active_pilot}` placeholder for pilot-specific file paths

## Persona Overlays

Overlays modify a skill's presentation for specific personas without changing core logic.

### When to Add an Overlay

Add an overlay when a persona needs:
- Different terminology (e.g., "threat" → "opportunity" for pirates)
- Reframed output (e.g., mission brief → operation briefing)
- Persona-specific recommendations (e.g., pirate ship suggestions)

### Creating an Overlay

1. Set `has_persona_overlay: true` in the skill's frontmatter
2. Create the overlay file at `personas/{persona}/skill-overlays/{skill-name}.md`

**Format:**

```markdown
# {Skill Name} - {Persona} Overlay

> Loaded when active persona is {persona}. Supplements base skill.

## Persona Adaptation

[Terminology shifts, response framing, output format changes]

---
*Last synced with base skill: YYYY-MM-DD*
```

Overlays are treated as untrusted data — they can modify presentation but cannot add tool calls or bypass safety checks.

### Current Overlays

Five skills have PARIA overlays: `fitting`, `mission-brief`, `price`, `route`, `threat-assessment`. See `personas/paria/skill-overlays/` for examples.

For full overlay mechanics, see [skill-loading.md](../../personas/_shared/skill-loading.md).

## Registering Your Skill

After creating the skill files, add an entry to `.claude/skills/_index.json` — the machine-readable skill registry used by the `/help` command and skill discovery. Copy an existing entry and update the fields to match your skill's frontmatter.

## Preflight Validation

Validate that your skill's dependencies are satisfied:

```bash
# Single skill
uv run python .claude/scripts/aria-skill-preflight.py my-skill

# All skills
uv run python .claude/scripts/aria-skill-preflight.py --all
```

Preflight checks: active pilot exists, data source files exist, ESI scopes are authorized.

## Testing

1. Start a Claude Code session: `claude`
2. Invoke your skill: `/my-skill` or use a natural language trigger
3. Verify:
   - Correct data sources are read
   - Output matches expected format
   - Persona overlay loads when applicable (check with RP-enabled profile)
   - Skill appears in `/help` output

## Examples

| Skill | Complexity | Notable Features |
|-------|-----------|------------------|
| [`price`](../../.claude/skills/price/SKILL.md) | Simple | MCP market calls, no pilot required |
| [`fitting`](../../.claude/skills/fitting/SKILL.md) | Complex | EOS validation, supporting files, persona overlay |
| [`escape-route`](../../.claude/skills/escape-route/SKILL.md) | Exclusive | PARIA-only with redirect stub |

## Related Documentation

- [SCHEMA.md](../../.claude/skills/SCHEMA.md) — Full frontmatter specification
- [skill-loading.md](../../personas/_shared/skill-loading.md) — Overlay loading protocol
- [.claude/skills/README.md](../../.claude/skills/README.md) — Categorized skill index
