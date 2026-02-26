# Remove Persona-Exclusive Skill Gate

**Status:** COMPLETED
**Implemented:** 2026-02-24 (commit `8221f233`)
**Related:** `_index.json`, `persona.py`, `skill-loading.md`, `CLAUDE.md`

---

## Executive Summary

The `persona_exclusive` mechanism gates 5 skills behind pirate persona selection. This proposal removes the gate entirely so all skills are available to all users regardless of persona. It also removes the `unrestricted_skills` bypass flag (which exists solely to work around the gate) and the `redirect` plumbing in the index builder.

**Affected skills:** `escape-route`, `hunting-grounds`, `mark-assessment`, `ransom-calc`, `sec-status`

---

## Previous Architecture

```
.claude/skills/escape-route/SKILL.md          ← stub (blocks non-paria users)
personas/paria-exclusive/escape-route.md       ← real skill implementation
.claude/skills/_index.json                     ← persona_exclusive + redirect fields
```

**Loading flow (before removal):**
1. Skill invoked → check `_index.json` for `persona_exclusive`
2. If set and persona doesn't match → show stub, stop
3. If set and persona matches → load from `redirect` path
4. `unrestricted_skills: true` in manifest → bypass check (FORGE persona)

**Supporting plumbing:**
- `persona_exclusive` field in `_index.json` (5 entries)
- `redirect` field handling in `aria-skill-index.py` (lines 170-193)
- `unrestricted_skills` flag in `persona.py` context builder (lines 189, 197, 242, 282-283)
- `validate_persona_context()` exclusive skill validation (lines 863-902)
- `validate_skill_redirects()` entire function (lines 530-582)
- `exclusive_skills` tracking in validation output (lines 747, 892, 922-924)
- Pirate-exclusive section in `generate-commands-md.py` (lines 62-68, 103-119, 159-161)
- `SECTION_ORDER` entry `"Pirate-Exclusive Commands"` in `generate-commands-md.py`
- 5 stub SKILL.md files (47 lines each of "you can't use this" messaging)
- `personas/paria-exclusive/` directory (5 full skill implementations)
- Variant matching logic documented in `skill-loading.md` (lines 23-64)

---

## Changes

### 1. Move real skill implementations into `.claude/skills/`

Replace each stub with the real implementation from `personas/paria-exclusive/`:

| Stub (delete) | Source (move) | Destination |
|----------------|---------------|-------------|
| `.claude/skills/escape-route/SKILL.md` | `personas/paria-exclusive/escape-route.md` | `.claude/skills/escape-route/SKILL.md` |
| `.claude/skills/hunting-grounds/SKILL.md` | `personas/paria-exclusive/hunting-grounds.md` | `.claude/skills/hunting-grounds/SKILL.md` |
| `.claude/skills/mark-assessment/SKILL.md` | `personas/paria-exclusive/mark-assessment.md` | `.claude/skills/mark-assessment/SKILL.md` |
| `.claude/skills/ransom-calc/SKILL.md` | `personas/paria-exclusive/ransom-calc.md` | `.claude/skills/ransom-calc/SKILL.md` |
| `.claude/skills/sec-status/SKILL.md` | `personas/paria-exclusive/sec-status.md` | `.claude/skills/sec-status/SKILL.md` |

**Frontmatter cleanup:** Remove `persona_exclusive` from each moved file's frontmatter. Remove any "PARIA-exclusive" notes from the body text.

### 2. Delete `personas/paria-exclusive/` directory

Empty after step 1. Remove entirely.

### 3. Clean `_index.json`

Remove `persona_exclusive` field from all 5 entries. These skills become normal entries with their `category`, `triggers`, `description`, etc. already populated from the real implementations.

**Regenerate:** `uv run python .claude/scripts/aria-skill-index.py`

### 4. Clean `aria-skill-index.py`

Remove the redirect-merging block (lines 170-193):

```python
# DELETE: Handle persona-exclusive skills: read metadata from redirect target
if "redirect" in frontmatter and "persona_exclusive" in frontmatter:
    ...
```

No other frontmatter fields depend on this code path.

### 5. Clean `persona.py`

**a) `build_persona_context()` (lines ~189-283):**
- Remove `unrestricted_skills` variable initialization (line 189)
- Remove `unrestricted_skills = manifest.get(...)` (line 197)
- Remove `"unrestricted_skills": unrestricted_skills` from context dict (line 242)
- Remove the YAML output block for `unrestricted_skills` (lines 281-283)

**b) `validate_persona_context()` (lines ~863-928):**
- Remove the entire exclusive skill validation block (lines 863-902): the `unrestricted` variable, the loop checking `persona_exclusive`, redirect path validation, and `exclusive_skills` list population
- Remove `exclusive_skills` from the `validated` dict initialization (line 747)
- Remove `exclusive_skills_ok` and `exclusive_skills_missing` from summary (lines 922-924)

**c) `validate_skill_redirects()` (lines 530-582):**
- Delete the entire function. It only validates redirect paths, which no longer exist.
- Remove any callers of this function.

### 6. Clean `generate-commands-md.py`

- Remove `"Pirate-Exclusive Commands"` from `SECTION_ORDER`
- Remove the pirate skill filtering block (lines 62-68)
- Remove the special-case `"Pirate-Exclusive Commands"` rendering (lines 103-119)
- The 5 formerly-exclusive skills will now sort into their natural categories (e.g., `tactical` → "Combat & Tactical")

### 7. Clean CLAUDE.md

**Skill Loading section (step 2):** Remove the entire `persona_exclusive` check:

```markdown
2. **Check `_index.json` for `persona_exclusive`**
   - If set, check if it matches `persona_context.persona` OR `persona_context.fallback`
   - Match → load from `redirect` path
   - No match → skill unavailable. Display the stub from `.claude/skills/{name}/SKILL.md`.
     **STOP HERE. Do not continue to steps 3-5. The stub is the final output.**
```

Replace with a direct "Load base skill" as the new step 2.

**Stub behavior note:** Remove the paragraph about accepting stubs at face value.

### 8. Clean `personas/_shared/skill-loading.md`

- Remove "Check Exclusivity" section (lines 21-64): the `persona_exclusive` check, variant matching table, unrestricted_skills flag docs
- Remove references to `personas/{persona}-exclusive/` directory pattern

### 9. Clean `dev/docs/CONTRIBUTING_SKILLS.md`

- Remove the entire "Persona-Exclusive Skills" section (lines 130-163)

### 10. Clean `dev/docs/CONTRIBUTING_PERSONAS.md`

- Remove `unrestricted_skills` from the manifest example (line 52)
- Remove FORGE `unrestricted_skills: true` reference in the comparison table (line 238)

### 11. Clean `personas/forge/manifest.yaml`

- Remove `unrestricted_skills: true` line (line 7). The flag has no purpose without the gate.

### 12. Clean test files

**`tests/test_persona.py`:**
- Remove `test_rejects_traversal_in_redirect` (lines ~835-854)
- Remove `test_allows_valid_redirect_path` (lines ~873-902)
- Remove any tests that reference `persona_exclusive`, `exclusive_skills`, or `redirect` in skill index context

**`tests/integration/test_security_paths.py`:**
- Remove `test_rejects_traversal_in_redirect` (line ~236)
- Remove `test_rejects_absolute_redirect_path` (line ~264)
- Remove `test_rejects_wrong_extension_redirect` (line ~288)
- Remove `test_valid_redirect_passes` (line ~319)
- Remove `validate_skill_redirects` import and all tests that use it

### 13. Clean `personas/README.md`

- Remove `paria-exclusive/` from the directory tree (lines 41-46)
- Remove the `{persona}-exclusive/` section (lines 146-153) explaining exclusive skills

### 14. Clean `dev/docs/PERSONA_LOADING.md`

- Remove `paria-exclusive/` from the persona directory tree (line 235)

### 15. Clean `.claude/scripts/count_persona_tokens.py`

- Remove `paria-exclusive` group from file groups (lines 87-93)
- Remove `paria_exclusive` analysis from pirate session section (lines 159, 163)

### 16. Clean `SECURITY.md` and `dev/docs/PERSONA_LOADING.md`

- Remove `validate_skill_redirects()` from key functions lists (deleted function)

### 17. Archive/review docs (low priority, leave as-is)

These files contain historical references. No code depends on them:

- `dev/reviews/PROJECT_REVIEW_2026-01.md` — historical review
- `dev/reviews/SECURITY_000.md` — historical security review
- `dev/reviews/CONTEXT_MANAGEMENT_REVIEW.md` — historical flow diagram
- `dev/planning/REMEDIATION_BACKLOG.md` — completed remediation record (superseded)
- `CHANGELOG.md` — historical changelog entry for when function was added
- `dev/archive/*` — already archived
- SKILL_ROUND2_REMAINING_ISSUES.md — historical (deleted)

---

## What Survives (unchanged)

These related persona mechanisms are **not affected** and remain intact:

| Mechanism | Purpose | Status |
|-----------|---------|--------|
| `has_persona_overlay` | Persona-flavored voice for shared skills | Keep |
| `skill_overlay_path` / `overlay_fallback_path` | Overlay file resolution | Keep |
| `persona_context.persona` / `.fallback` | Persona identity for overlays + RP | Keep |
| `rp_level` | Controls RP intensity | Keep |
| Persona file loading (session init steps 3-4) | Voice, identity, terminology | Keep |
| Path security validation (`SEC-001`/`SEC-002`) | Validates overlay paths | Keep (minus redirect validation) |

---

## Validation

After implementation:

```bash
# Regenerate skill index
uv run python .claude/scripts/aria-skill-index.py

# Regenerate commands reference
uv run python .claude/scripts/generate-commands-md.py

# Run tests
uv run pytest -n auto

# Verify no dangling references
grep -r "persona_exclusive" --include="*.py" --include="*.md" --include="*.json" \
  --exclude-dir=dev/archive --exclude-dir=dev/reviews --exclude-dir=dev/proposals

# Verify exclusive directory removed
test ! -d personas/paria-exclusive && echo "CLEAN"
```

---

## Implementation Notes

Steps 1-12 completed in commit `8221f233`. Steps 13-16 completed in follow-up cleanup.

Step 17 (archive/review docs) deferred — these are historical records with no code impact.

---

## Risk

**Low.** This is a removal of a restriction. No skill behavior changes — only access widens. Persona overlays (which adapt skill *voice*) remain functional and separate from this gate.
