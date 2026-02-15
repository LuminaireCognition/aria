# Release Process

Steps and policies for releasing new versions of ARIA.

## Versioning Policy

ARIA uses [Semantic Versioning](https://semver.org/):

- **Major (X.0.0)** — Breaking changes to CLAUDE.md contract, skill schema, persona system, or MCP dispatcher API
- **Minor (0.X.0)** — New skills, new MCP actions, new features, significant documentation restructuring
- **Patch (0.0.X)** — Bug fixes, reference data updates, typo corrections, minor doc improvements

Universe cache rebuilds are not version bumps — they're data refreshes.

## Pre-Release Checklist

### 1. Run Full Test Suite

```bash
uv run pytest -n auto
```

All tests must pass. No skips allowed unless documented in the test with a reason.

### 2. Run Linters and Type Checks

```bash
uv run ruff check src .claude/scripts
uv run ruff format --check src .claude/scripts
uv run mypy
```

### 3. Verify Documentation Freshness

```bash
# COMMANDS.md matches skill index
uv run python .claude/scripts/generate-commands-md.py --check

# Skill index matches skill directories
uv run python .claude/scripts/aria-skill-index.py --check

# No broken links
lychee '**/*.md'
```

See `dev/docs/DOC_FRESHNESS.md` for the full quarterly audit checklist.

### 4. Run Pre-Commit Hooks

```bash
uv run pre-commit run --all-files
```

### 5. Review CHANGELOG.md

- Ensure all notable changes since the last release are documented
- Follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format
- Categories: Added, Changed, Deprecated, Removed, Fixed, Security
- Each entry should explain *why*, not just *what*

### 6. Rebuild Universe Cache (if needed)

See "When to Rebuild Universe Cache" below.

### 7. Update Version

Update version string if applicable, then commit:

```bash
git add -A
git commit -m "Prepare release vX.Y.Z"
```

## Tagging

```bash
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin main --tags
```

## Post-Release

1. **Create GitHub Release** — use the tag, copy relevant CHANGELOG.md section as release notes
2. **Verify CI passes** on the tagged commit
3. **Announce** in relevant channels (Discord, EVE forums) if the release includes user-facing changes

### GitHub Release Notes Template

```markdown
## What's New

[Copy from CHANGELOG.md]

## Upgrade Notes

[Any breaking changes or migration steps]

## Full Changelog

https://github.com/LuminaireCognition/aria/compare/vPREVIOUS...vX.Y.Z
```

## Changelog Workflow

1. As you work on changes, add entries to the `[Unreleased]` section of `CHANGELOG.md`
2. At release time, rename `[Unreleased]` to `[X.Y.Z] - YYYY-MM-DD`
3. Add a fresh empty `[Unreleased]` section at the top
4. Update the comparison links at the bottom of the file

## Rollback

If a release introduces critical issues:

```bash
# Revert to previous release
git revert HEAD --no-edit   # if single commit
# or
git revert HEAD~N..HEAD     # if multiple commits

# Tag the fix
git tag -a vX.Y.Z -m "Release vX.Y.Z (rollback fix)"
git push origin main --tags
```

Do **not** delete tags or force-push main. Always roll forward with a new release.

## When to Rebuild Universe Cache

The universe cache contains static EVE data (solar systems, stargates, regions). Rebuild when:

- EVE Online releases an expansion that adds/modifies systems
- Stargates are added or removed (rare)
- Before major releases to ensure fresh data

```bash
uv run python -m aria_esi.cache.builder
```

This updates `.claude/scripts/aria_esi/data/universe_cache.json` with current system/stargate data from ESI. Takes ~3 hours due to API rate limits.

The cache does **not** need rebuilding for:
- Regular patches
- Balance changes
- Market/industry updates
