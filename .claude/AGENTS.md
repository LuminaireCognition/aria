# AGENTS.md instructions for ARIA

<INSTRUCTIONS>
## Python (CRITICAL)
Always use `uv run`. Never bare `python`, `python3`, or `pip`.

## Skills
Skills live in `.claude/skills/{name}/SKILL.md`. The system-reminder lists all
available skills with descriptions. When a skill matches the user's request,
read its SKILL.md and follow its workflow.

If SKILL.md declares `prerequisite_files`, read ALL listed files before
generating any output. These contain authoritative game data.

If SKILL.md declares `data_sources`, read those files when contextually
relevant (pilot profiles, ship rosters, etc.).

**Persona overlays:** If `has_persona_overlay: true` in `_index.json`, check
`{skill_overlay_path}/{name}.md` and append if found.

**`sde` vs `skills` disambiguation:** `sde` = static game data (skill_requirements, item_info). `skills` = training calculations (easy_80_plan, training_time). Do not call `skills(action="skill_requirements")` — it doesn't exist.
</INSTRUCTIONS>
