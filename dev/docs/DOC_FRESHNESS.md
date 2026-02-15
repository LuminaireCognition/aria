# Documentation Freshness Audit

Quarterly process for keeping ARIA documentation accurate and up-to-date.

## Cadence

Run this audit **once per quarter** (or before any major release). Add it to the release checklist in `dev/RELEASE.md`.

## What to Check

### 1. Broken Links

```bash
# Install lychee if not available
# https://github.com/lycheeverse/lychee

# Run link checker on all markdown files
lychee '**/*.md'
```

CI runs this automatically on every PR. This step catches any links that broke between PRs (e.g., renamed external pages).

### 2. COMMANDS.md Freshness

```bash
uv run python .claude/scripts/generate-commands-md.py --check
```

If this exits non-zero, the skill index has changed but `docs/COMMANDS.md` wasn't regenerated. Fix with:

```bash
uv run python .claude/scripts/generate-commands-md.py
```

### 3. Skill Index Consistency

```bash
uv run python .claude/scripts/aria-skill-index.py --check
```

Verifies that `_index.json` matches the actual skill directories on disk.

### 4. Stale Terminology

The pre-commit hook catches deprecated terms automatically. For a manual check:

```bash
grep -rn --include="*.md" --include="*.yaml" --exclude-dir=archive -E '\brp_level:\s*lite\b' .
```

Should return zero results (the migration note in `rp-levels.md` is acceptable).

### 5. Command Count

Compare the count in `docs/COMMANDS.md` footer against the skill index:

```bash
# Skill count from index
python -c "import json; print(json.load(open('.claude/skills/_index.json'))['skill_count'])"

# Count from COMMANDS.md footer (should match)
grep -o '[0-9]* commands' docs/COMMANDS.md
```

### 6. Reference File Spot-Check

Verify that files referenced in `CLAUDE.md` still exist:

```bash
# Extract file references and check each one
grep -oP '`[a-zA-Z/._ -]+\.md`' CLAUDE.md | tr -d '`' | while read f; do
  [ -f "$f" ] || echo "MISSING: $f"
done
```

## Audit Log

Record each audit completion here:

| Date | Auditor | Issues Found | Notes |
|------|---------|-------------|-------|
| 2026-02-15 | Initial setup | N/A | Baseline — all checks pass |
