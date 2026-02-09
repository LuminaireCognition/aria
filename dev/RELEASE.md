# Release Checklist

Steps to follow before tagging a new release.

## Pre-Release

1. **Rebuild universe cache** (if EVE had a recent expansion)
   ```bash
   uv run python -m aria_esi.cache.builder
   ```
   This updates `.claude/scripts/aria_esi/data/universe_cache.json` with current system/stargate data from ESI. Takes ~3 hours due to API rate limits.

2. **Run tests**
   ```bash
   uv run pytest
   ```

3. **Run linters**
   ```bash
   uv run ruff check .
   uv run mypy .
   ```

4. **Update version** (if applicable)

5. **Commit any changes**
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

- Verify the release on GitHub
- Announce if needed

## When to Rebuild Universe Cache

The universe cache contains static EVE data (solar systems, stargates, regions). Rebuild when:

- EVE Online releases an expansion that adds/modifies systems
- Stargates are added or removed (rare)
- Before major releases to ensure fresh data

The cache does **not** need rebuilding for:
- Regular patches
- Balance changes
- Market/industry updates
