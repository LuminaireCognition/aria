# aria-review Prompt Catalog

This file is the single source of truth for available review templates.
The dispatcher reads this to route commands.

---

## skill-review

- **Template**: `prompts/skill-review.md`
- **Description**: End-to-end skill audit. Primary focus on data grounding
  discipline (MCP-first enforcement, prompt hygiene, failure handling,
  context efficiency). Secondary focus on dead weight identification
  with a bias toward removal. Produces a reduction inventory with
  estimated token savings.
- **Target type**: `skill` (a directory containing SKILL.md)
- **Arguments**: `<skill-path-or-name>` or `ALL`
- **Examples**:
  - `/aria-review skill-review mission-brief`
  - `/aria-review skill-review .claude/skills/mission-brief`
  - `/aria-review skill-review ALL`

---

## proposal

- **Template**: `prompts/proposal.md`
- **Description**: Implementation readiness review for proposals. Assesses
  whether a proposal is specific enough for an AI coding agent to implement
  unambiguously in 1-2 iterations. Produces a ship decision, blockers,
  specification gaps, and a readiness checklist.
- **Target type**: `proposal` (a markdown file under `dev/proposals/`)
- **Arguments**: `<proposal-name-or-path>`
- **Examples**:
  - `/aria-review proposal CONTEXT_EFFICIENCY_PROPOSAL`
  - `/aria-review proposal dev/proposals/CONTEXT_EFFICIENCY_PROPOSAL.md`

---

<!-- To add a new template:
     1. Create prompts/<name>.md with YAML front-matter and prompt body
     2. Add an entry here following the format above
     3. Done — SKILL.md does not need to change -->
