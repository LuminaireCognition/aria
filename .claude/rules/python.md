---
paths:
  - "src/**/*.py"
  - "tests/**/*.py"
  - ".claude/scripts/**/*.py"
  - "pyproject.toml"
  - "uv.lock"
---

## Python Execution

**CRITICAL:** Always use `uv run` for Python. Never use bare `python`, `python3`, or `pip`.

**CRITICAL:** Never use `uv pip install` to add packages. All dependencies (including dev tools like pytest, mypy, pre-commit) are declared in `pyproject.toml` and pinned in `uv.lock`. Use `uv sync --dev` to install them. Ad-hoc `uv pip install` bypasses the lockfile, ignores pinned versions, and gets overwritten by the next `uv sync`.

```bash
# Install all dependencies (including dev tools)
uv sync --dev

# ARIA ESI CLI (preferred)
uv run aria-esi <command> [args]

# Python scripts (source code in src/aria_esi/)
uv run python -m aria_esi <args>

# Tests (always use -n auto for parallel execution)
uv run pytest -n auto
```

**Check call signatures before invoking tools.** For CLI subcommands, run `<command> --help` to confirm exact flag names. For MCP tools, review the parameter schema in the tool definition. Do not guess parameter or flag names from memory.

**Full reference:** `dev/docs/PYTHON_ENVIRONMENT.md`
