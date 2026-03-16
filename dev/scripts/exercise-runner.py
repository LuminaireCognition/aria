#!/usr/bin/env python3
"""
Exercise runner for ARIA skill exercises.

Parses SKILL_EXERCISE_QUERIES.md, runs each query via `claude -p`,
and captures stdout per output file.

Key fix: passes --allowedTools so Claude can use the full skill chain
(Skill tool → Read prerequisite files → MCP tools) instead of
falling back to training data and hallucinating.

Usage:
    uv run python dev/scripts/exercise-runner.py --filter NONE,LOW
    uv run python dev/scripts/exercise-runner.py --skills help,price --dry-run
    uv run python dev/scripts/exercise-runner.py --filter NONE --parallel 4 --timeout 180
    uv run python dev/scripts/exercise-runner.py --explicit --skills fitting --filter NONE
    uv run python dev/scripts/exercise-runner.py --changed --explicit --dry-run
    uv run python dev/scripts/exercise-runner.py --changed --explicit --timeout 180
"""

from __future__ import annotations

import argparse
import copy
import json
import logging
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
HOOKS_DIR = PROJECT_ROOT / "dev" / "scripts" / "hooks"
log = logging.getLogger(__name__)
QUERIES_PATH = PROJECT_ROOT / "dev" / "reviews" / "SKILL_EXERCISE_QUERIES.md"
OUTPUT_BASE = PROJECT_ROOT / "dev" / "reviews" / "exercise-outputs"

# ---------------------------------------------------------------------------
# Tool allowlist for claude -p
# ---------------------------------------------------------------------------
# Without --allowedTools, claude -p has no user to approve tool use, so it
# silently falls back to training data — the root cause of hallucinations.
#
# We allow read-only tools + Skill + MCP, but block Edit/Write/Agent to
# prevent unintended side effects during exercise runs.

ALLOWED_TOOLS = [
    # Core read tools for skill loading chain
    "Read",
    "Glob",
    "Grep",
    # Skill invocation (critical — triggers SKILL.md + prerequisite loading)
    "Skill",
    # Deferred tool discovery (required to load MCP tools at runtime)
    "ToolSearch",
    # CLI fallback for skills that shell out to aria-esi
    "Bash(uv run:*)",
    # Web access for skills that fetch external data
    "WebFetch",
    "WebSearch",
    # MCP tools — the full ARIA universe suite
    "mcp__aria-universe__universe",
    "mcp__aria-universe__market",
    "mcp__aria-universe__sde",
    "mcp__aria-universe__skills",
    "mcp__aria-universe__fitting",
    "mcp__aria-universe__killmails",
    "mcp__aria-universe__pilot",
    "mcp__aria-universe__status",
]

# ---------------------------------------------------------------------------
# Query parser
# ---------------------------------------------------------------------------

# Matches: ### skill-name
SKILL_RE = re.compile(r"^###\s+(\S+)")
# Matches: - **ESI:** LEVEL
ESI_RE = re.compile(r"^\s*-\s*\*\*ESI:\*\*\s*(\w+)")
# Matches: N. "query text"
QUERY_RE = re.compile(r'^\s*(\d+)\.\s*"(.+)"$')
# Matches <system-reminder>...</system-reminder> blocks leaked into stdout
SYSTEM_REMINDER_RE = re.compile(
    r"\s*<system-reminder>.*?</system-reminder>\s*",
    re.DOTALL,
)


def parse_queries(md_path: Path) -> list[dict]:
    """
    Parse SKILL_EXERCISE_QUERIES.md into a list of query dicts.

    Each dict: {skill, esi_level, query_num, query_text}
    Multi-line queries use literal \\n in the markdown (on one line).
    """
    text = md_path.read_text()
    lines = text.splitlines()

    queries = []
    current_skill = None
    current_esi = None

    for line in lines:
        # Skill header
        m = SKILL_RE.match(line)
        if m:
            raw = m.group(1)
            # Strip trailing markup like *(persona-exclusive: paria)*
            current_skill = raw.split("*")[0].rstrip()
            current_esi = None
            continue

        # ESI level
        m = ESI_RE.match(line)
        if m:
            current_esi = m.group(1)
            continue

        # Query line
        m = QUERY_RE.match(line)
        if m and current_skill:
            query_num = int(m.group(1))
            query_text = m.group(2)
            # Convert literal \n to actual newlines (for EFT blocks etc.)
            query_text = query_text.replace("\\n", "\n")
            queries.append({
                "skill": current_skill,
                "esi_level": current_esi or "UKN",
                "query_num": query_num,
                "query_text": query_text,
            })

    return queries


# ---------------------------------------------------------------------------
# Stream output parser
# ---------------------------------------------------------------------------


def _parse_stream_output(raw: str) -> tuple[str, list[dict]]:
    """
    Parse claude -p --verbose --output-format stream-json output.

    The verbose stream-json format emits one JSON object per line with
    conversation-level events (not Anthropic API streaming deltas):

      {"type":"assistant", "message":{"content":[...]}} — model turns
      {"type":"user", "message":{"content":[...]}}      — tool results
      {"type":"result", "result":"..."}                  — final text

    Returns (text_content, tool_calls) where tool_calls is a list of
    {tool, input, id, result?} dicts.
    """
    text_parts = []
    tool_calls = []
    tool_results: dict[str, str] = {}  # tool_use_id → result text

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        etype = event.get("type", "")

        # Assistant turns contain text and tool_use blocks.
        # Reset text_parts each turn so only the LAST assistant turn's
        # text survives — earlier turns contain intermediate reasoning
        # that inflates output and produces false quality signals.
        if etype == "assistant":
            msg = event.get("message", {})
            current_turn_text = []
            for block in msg.get("content", []):
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    current_turn_text.append(block.get("text", ""))
                elif block.get("type") == "tool_use":
                    tool_calls.append({
                        "tool": block.get("name", ""),
                        "id": block.get("id", ""),
                        "input": block.get("input", {}),
                    })
            if current_turn_text:
                text_parts = current_turn_text  # reset, don't accumulate

        # User turns contain tool results
        elif etype == "user":
            msg = event.get("message", {})
            for block in msg.get("content", []):
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_result":
                    tool_id = block.get("tool_use_id", "")
                    result_text = str(block.get("content", ""))[:2000]
                    tool_results[tool_id] = result_text

    # Attach results to their tool calls
    for tc in tool_calls:
        if tc["id"] in tool_results:
            tc["result"] = tool_results[tc["id"]]

    return "".join(text_parts), tool_calls


# ---------------------------------------------------------------------------
# Query filter
# ---------------------------------------------------------------------------


def filter_queries(
    queries: list[dict],
    esi_levels: list[str] | None = None,
    skill_names: list[str] | None = None,
) -> list[dict]:
    """Filter queries by ESI level and/or skill name."""
    result = queries
    if esi_levels:
        levels = {l.upper() for l in esi_levels}
        result = [q for q in result if q["esi_level"] in levels]
    if skill_names:
        names = {n.lower() for n in skill_names}
        result = [q for q in result if q["skill"].lower() in names]
    return result


# ---------------------------------------------------------------------------
# Changed skill detection
# ---------------------------------------------------------------------------


def detect_changed_skills(base: str = "main") -> list[str]:
    """Detect skills with modified SKILL.md files relative to a base branch.

    Scans git diff for changes under .claude/skills/*/SKILL.md and returns
    the skill directory names. This lets the exercise runner target exactly
    the skills touched in the current branch.
    """
    try:
        # Staged + unstaged changes vs base branch
        result = subprocess.run(
            ["git", "diff", "--name-only", base, "--", ".claude/skills/"],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT),
        )
        if result.returncode != 0:
            # Fallback: diff against working tree only (no base branch)
            result = subprocess.run(
                ["git", "diff", "--name-only", "--", ".claude/skills/"],
                capture_output=True, text=True, cwd=str(PROJECT_ROOT),
            )
        paths = result.stdout.strip().splitlines()
    except FileNotFoundError:
        return []

    skills = set()
    for p in paths:
        # .claude/skills/{name}/SKILL.md → name
        parts = p.split("/")
        if len(parts) >= 4 and parts[0] == ".claude" and parts[1] == "skills":
            skill_name = parts[2]
            # Skip shared/internal dirs
            if not skill_name.startswith("_"):
                skills.add(skill_name)
    return sorted(skills)


# ---------------------------------------------------------------------------
# Git state assertions
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Brevity checks
# ---------------------------------------------------------------------------

def parse_yaml_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter as a dict using regex (no yaml dependency)."""
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {}
    result = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            value = value.strip()
            # Coerce numeric values
            try:
                value = int(value)
            except ValueError:
                pass
            result[key.strip()] = value
    return result


BREVITY_EXEMPT_SKILLS = {"help"}


def _check_brevity(query_label: str, response_lines: int) -> str | None:
    """Return 'verbose' flag if response exceeds brevity cap, unless exempt."""
    skill_name = query_label.rsplit("-q", 1)[0]
    if skill_name in BREVITY_EXEMPT_SKILLS:
        return None
    # Read per-skill preferred_max_lines from SKILL.md frontmatter
    index_path = PROJECT_ROOT / ".claude" / "skills" / skill_name / "SKILL.md"
    max_lines = 30  # global default
    if index_path.exists():
        frontmatter = parse_yaml_frontmatter(index_path.read_text())
        max_lines = frontmatter.get("preferred_max_lines", 30)
    soft_ceiling = int(max_lines * 1.5)
    if response_lines > soft_ceiling:
        return "verbose"
    return None


# ---------------------------------------------------------------------------
# Quality checks
# ---------------------------------------------------------------------------


def quality_check(
    tool_calls: list[dict],
    body: str,
    query: dict,
    explicit: bool,
) -> list[str]:
    """
    Run post-query quality checks and return a list of flag strings.

    Flags:
    - no-skill: In explicit mode, Skill tool was never invoked
    - no-skill-ok: Skill not invoked but has injected_prerequisites (not a defect)
    - mcp-fail(N): N MCP tool calls had "validation failed" in result
    - brevity-N: N non-header content lines (verbose response)
    - global-data: Killmail response scope=global on personal query (auto-resolve failed)
    - contracts-failed: Contracts MCP action returned structured error
    - skill-gate-violation: MCP/ToolSearch call appeared before first Skill call
    """
    flags: list[str] = []

    # 1. no-skill: In explicit mode, verify Skill tool was used
    if explicit:
        has_skill = any(tc["tool"] == "Skill" for tc in tool_calls)
        if not has_skill:
            flags.append("no-skill")

    # 2. mcp-fail: Count MCP tool calls with validation failures
    mcp_failures = 0
    for tc in tool_calls:
        if tc["tool"].startswith("mcp__"):
            result_text = tc.get("result", "")
            if "validation failed" in result_text.lower():
                mcp_failures += 1
    if mcp_failures:
        flags.append(f"mcp-fail({mcp_failures})")

    # 3. brevity: Count non-header content lines
    content_lines = [
        line for line in body.splitlines()
        if line.strip() and not line.startswith("#") and not line.startswith("---")
    ]
    query_label = f"{query['skill']}-q{query['query_num']}"
    brevity_flag = _check_brevity(query_label, len(content_lines))
    if brevity_flag:
        flags.append(brevity_flag)

    # 4. global-data: Killmail response with scope=global on personal queries
    #    (After auto-resolve fix, character_id=None in input is expected —
    #    the dispatcher resolves it server-side. Check response scope instead.)
    query_text = query.get("query_text", "").lower()
    if query["skill"] in ("killmails", "killmail") and "my" in query_text:
        for tc in tool_calls:
            if tc["tool"] == "mcp__aria-universe__killmails":
                result_text = tc.get("result", "")
                if '"scope": "global"' in result_text or '"scope":"global"' in result_text:
                    flags.append("global-data")
                    break

    # 4b. contracts-failed: contracts MCP action returned structured error
    if query["skill"] == "contracts":
        for tc in tool_calls:
            if tc["tool"] == "mcp__aria-universe__pilot":
                result_text = tc.get("result", "")
                if "contracts_failed" in result_text:
                    flags.append("contracts-failed")
                    break

    # 5. no-skill-ok: Distinguish injected-prerequisite skills from enforcement failures
    if explicit and "no-skill" in flags:
        skill_name = query.get("skill", "")
        index_path = PROJECT_ROOT / ".claude" / "skills" / "_index.json"
        if index_path.exists():
            index = json.loads(index_path.read_text())
            skill_meta = next(
                (s for s in index["skills"] if s["name"] == skill_name), None
            )
            if skill_meta and skill_meta.get("injected_prerequisites"):
                flags.remove("no-skill")
                flags.append("no-skill-ok")

    # 6. skill-gate-violation: MCP/ToolSearch call appears before first Skill call
    first_skill_idx = None
    for i, tc in enumerate(tool_calls):
        if tc["tool"] == "Skill":
            first_skill_idx = i
            break
    if first_skill_idx is not None:
        # Check if any mcp__ or ToolSearch call precedes the first Skill call
        for tc in tool_calls[:first_skill_idx]:
            if tc["tool"].startswith("mcp__") or tc["tool"] == "ToolSearch":
                flags.append("skill-gate-violation")
                break
    elif tool_calls and "no-skill-ok" not in flags:
        # No Skill call at all — check if MCP/ToolSearch were used.
        # Skip when no-skill-ok: injected-prerequisite skills don't need
        # the Skill tool, so MCP calls without it are expected behavior.
        for tc in tool_calls:
            if tc["tool"].startswith("mcp__") or tc["tool"] == "ToolSearch":
                flags.append("skill-gate-violation")
                break

    return flags


# ---------------------------------------------------------------------------
# Query runner
# ---------------------------------------------------------------------------


def run_query(
    query: dict,
    output_dir: Path,
    seq: int,
    timeout: int = 120,
    model: str | None = None,
    effort: str | None = None,
    explicit: bool = False,
) -> dict:
    """
    Run a single query via `claude -p` and capture output.

    If explicit=True, the query is prefixed with /<skill-name> so the Skill
    tool is invoked directly, bypassing natural language trigger matching.

    Returns a result dict with status, output_path, duration, etc.
    """
    filename = f"{seq:02d}-{query['skill']}-q{query['query_num']}.md"
    output_path = output_dir / filename

    # In explicit mode, prefix query with /<skill> to force skill invocation
    input_text = query["query_text"]
    if explicit:
        input_text = f"/{query['skill']} {input_text}"

    # Build header
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    header = (
        f"# Skill: {query['skill']}\n"
        f"# Query: \"{query['query_text'][:200]}\"\n"
        f"# ESI Level: {query['esi_level']}\n"
        f"# Mode: {'explicit' if explicit else 'implicit'}\n"
        f"# Timestamp: {timestamp}\n"
        f"---\n\n"
    )

    # Build command — use --output-format stream-json to capture tool calls
    cmd = ["claude", "-p", "--verbose", "--output-format", "stream-json"]
    if model:
        cmd.extend(["--model", model])
    if effort:
        cmd.extend(["--effort", effort])

    # Allowed tools — the critical fix for hallucination prevention.
    # Without this, claude -p can't use tools (no interactive approval)
    # and falls back to training data.
    cmd.extend(["--allowedTools", ",".join(ALLOWED_TOOLS)])

    cmd.extend([
        "--append-system-prompt",
        "The local git repository is fully up to date with the remote. "
        "Do not run git fetch, git pull, git push, or any git commands "
        "that contact a remote repository.",
    ])

    # Strip CLAUDECODE env var so subprocesses aren't blocked by nesting check.
    # Set SSH BatchMode to prevent interactive passphrase prompts from
    # Claude Code's own git startup operations (SSH writes to /dev/tty,
    # bypassing capture_output).
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    env["GIT_SSH_COMMAND"] = "ssh -o BatchMode=yes"
    # Disable keyring probe — it can block indefinitely in non-TTY subprocesses
    # when the system keyring daemon requires interactive authentication.
    env["ARIA_NO_KEYRING"] = "1"

    # Install skill-enforcer hook for explicit mode
    settings_local = PROJECT_ROOT / ".claude" / "settings.local.json"
    saved_settings = None
    if explicit and HOOKS_DIR.exists():
        try:
            if settings_local.exists():
                saved_settings = settings_local.read_text()
                existing = json.loads(saved_settings)
            else:
                existing = {}
            merged = copy.deepcopy(existing)
            merged.setdefault("hooks", {})

            # Replace hooks with absolute paths for deterministic exercise runs.
            # Production settings use $CLAUDE_PROJECT_DIR which may not resolve
            # reliably in all claude -p contexts. Exercise runs need absolute paths.
            cleanup_cmd = str(HOOKS_DIR / "skill-gate-cleanup-turn.sh")
            hook_cmd = str(HOOKS_DIR / "skill-enforcer.sh")
            merged["hooks"]["UserPromptSubmit"] = [
                {"hooks": [{"type": "command", "command": cleanup_cmd}]},
                {"hooks": [{"type": "command", "command": hook_cmd}]},
            ]
            gate_cmd = str(HOOKS_DIR / "skill-gate.sh")
            merged["hooks"]["PreToolUse"] = [
                {
                    # Empty matcher = fire on all tools. The script's Phase 2
                    # allowlist handles read-only tools internally.
                    "hooks": [
                        {"type": "command", "command": gate_cmd},
                    ],
                },
            ]
            session_cleanup_cmd = str(HOOKS_DIR / "skill-gate-cleanup.sh")
            merged["hooks"]["SessionEnd"] = [
                {
                    "hooks": [
                        {"type": "command", "command": session_cleanup_cmd},
                    ]
                },
            ]
            # F3: Deny rules to protect infrastructure files during exercise runs
            merged.setdefault("permissions", {})
            merged["permissions"].setdefault("deny", [])
            deny_rules = [
                # Block subagent spawning — subagents bypass --allowedTools and
                # PreToolUse hooks, undermining both the edit sandbox and skill gate.
                "Agent",
                # Authoritative edit/write sandbox.
                "Edit",
                "Write",
                # Infrastructure protection (defense-in-depth)
                "Edit(/.claude/settings*)",
                "Edit(/.claude/hooks/*)",
                "Write(/.claude/settings*)",
                "Write(/.claude/hooks/*)",
                "Edit(/dev/scripts/hooks/*)",
                "Write(/dev/scripts/hooks/*)",
            ]
            existing_deny = set(merged["permissions"]["deny"])
            for rule in deny_rules:
                if rule not in existing_deny:
                    merged["permissions"]["deny"].append(rule)
            settings_local.write_text(json.dumps(merged, indent=2) + "\n")
        except Exception:
            saved_settings = None  # Don't restore on error

    start = time.monotonic()

    # Use Popen with start_new_session so claude and all its child
    # processes (MCP servers, bash shells, aria-esi CLI) live in a
    # dedicated process group. On timeout we kill the entire group,
    # preventing orphaned grandchild processes.
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=env,
        start_new_session=True,
    )

    try:
        stdout_raw, stderr_raw = proc.communicate(
            input=input_text, timeout=timeout,
        )
        duration = time.monotonic() - start

        # Parse JSON output to extract text and tool calls
        stdout, tool_calls = _parse_stream_output(stdout_raw)

        # Strip <system-reminder> tags that leak into stdout
        stdout = SYSTEM_REMINDER_RE.sub("", stdout).strip()

        # Save tool call log if any were captured
        if tool_calls:
            tool_log_path = output_path.with_suffix(".tools.json")
            tool_log_path.write_text(json.dumps(tool_calls, indent=2) + "\n")

        # Debug: dump raw stdout when parse produced nothing or when
        # system-reminder stripping removed significant content
        raw_clean = SYSTEM_REMINDER_RE.sub("", stdout_raw).strip()
        if (not stdout and not tool_calls and stdout_raw.strip()) or \
                len(stdout_raw) - len(raw_clean) > 200:
            raw_path = output_path.with_suffix(".raw")
            raw_path.write_text(header + stdout_raw)

        if proc.returncode != 0 and not stdout:
            body = f"# ERROR (exit {proc.returncode})\n\n{stderr_raw[:500]}"
        elif not stdout:
            # Include stderr for diagnosis when claude -p exits cleanly but
            # produces no output (e.g., hook failures, rate limits, startup errors)
            stderr_hint = ""
            if stderr_raw and stderr_raw.strip():
                stderr_hint = f"\n\n```\nstderr: {stderr_raw[:300]}\n```"
            body = f"# EMPTY RESPONSE{stderr_hint}"
        else:
            body = stdout

        # Append compact Tool Trace footer for human readability
        if tool_calls:
            trace_lines = ["\n---\n## Tool Trace\n"]
            for tc in tool_calls:
                tool_name = tc["tool"]
                inp = tc.get("input", {})
                if tool_name == "Read":
                    summary = inp.get("file_path", "?")
                elif tool_name == "Skill":
                    summary = inp.get("skill", "?")
                elif tool_name.startswith("mcp__"):
                    action = inp.get("action", "?")
                    summary = f"{tool_name.split('__')[-1]}({action})"
                else:
                    summary = str(inp)[:80]
                trace_lines.append(f"- `{tool_name}` → {summary}")
            body += "\n".join(trace_lines)

        output_path.write_text(header + body)

        # Quality checks
        quality_flags = quality_check(
            tool_calls=tool_calls,
            body=body,
            query=query,
            explicit=explicit,
        )

        return {
            "seq": seq,
            "filename": filename,
            "skill": query["skill"],
            "query_num": query["query_num"],
            "status": "ok" if proc.returncode == 0 and stdout else
                      "empty" if proc.returncode == 0 else
                      f"error:{proc.returncode}",
            "duration": round(duration, 1),
            "lines": len(body.splitlines()),
            "quality": quality_flags,
        }

    except subprocess.TimeoutExpired:
        # Kill the entire process group (claude + all children)
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            proc.kill()
        # Drain pipe buffers - process is dead, returns immediately
        stdout_raw, stderr_raw = proc.communicate()
        duration = time.monotonic() - start

        # Parse whatever partial stream output was captured
        partial_text, tool_calls = _parse_stream_output(stdout_raw)
        partial_text = SYSTEM_REMINDER_RE.sub('', partial_text).strip()

        # Save tool trace if any calls were captured
        if tool_calls:
            tool_log_path = output_path.with_suffix('.tools.json')
            tool_log_path.write_text(json.dumps(tool_calls, indent=2) + '\n')

        # Build timeout output with partial data
        body = f"# TIMEOUT after {timeout}s\n"
        if partial_text:
            body += f"\n## Partial Output\n\n{partial_text}\n"
        if tool_calls:
            trace_lines = ["\n---\n## Tool Trace (partial)\n"]
            for tc in tool_calls:
                tool_name = tc["tool"]
                inp = tc.get("input", {})
                if tool_name == "Read":
                    summary = inp.get("file_path", "?")
                elif tool_name == "Skill":
                    summary = inp.get("skill", "?")
                elif tool_name.startswith("mcp__"):
                    action = inp.get("action", "?")
                    summary = f"{tool_name.split('__')[-1]}({action})"
                else:
                    summary = str(inp)[:80]
                trace_lines.append(f"- `{tool_name}` \u2192 {summary}")
            body += "\n".join(trace_lines)

        output_path.write_text(header + body)

        # Run quality checks on partial data
        quality_flags = quality_check(
            tool_calls=tool_calls,
            body=body,
            query=query,
            explicit=explicit,
        )

        return {
            "seq": seq,
            "filename": filename,
            "skill": query["skill"],
            "query_num": query["query_num"],
            "status": "timeout",
            "duration": round(duration, 1),
            "lines": len(body.splitlines()),
            "quality": quality_flags,
        }

    finally:
        # Restore original settings.local.json
        if saved_settings is not None:
            settings_local.write_text(saved_settings)
        elif explicit and settings_local.exists() and saved_settings is None:
            # We created settings.local.json from scratch — remove our hook
            try:
                current = json.loads(settings_local.read_text())
                hooks = current.get("hooks", {})
                hooks.pop("UserPromptSubmit", None)
                hooks.pop("PreToolUse", None)
                if current == {} or current == {"hooks": {}}:
                    settings_local.unlink()
                else:
                    settings_local.write_text(json.dumps(current, indent=2) + "\n")
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Manifest generation
# ---------------------------------------------------------------------------


def generate_manifest(
    output_dir: Path,
    queries: list[dict],
    results: list[dict],
    filter_desc: str,
    model: str | None,
    effort: str | None,
    timeout: int,
    parallel: int,
) -> None:
    """Generate MANIFEST.md with run metadata."""
    run_id = output_dir.name
    total_lines = sum(r["lines"] for r in results)
    total_files = len(results)
    ok = sum(1 for r in results if r["status"] == "ok")
    empty = sum(1 for r in results if r["status"] == "empty")
    errors = sum(1 for r in results if r["status"].startswith("error"))
    timeouts = sum(1 for r in results if r["status"] == "timeout")

    lines = [
        "# Exercise Run Manifest\n",
        f"- **Run ID:** {run_id}",
        f"- **Date:** {datetime.now().strftime('%Y-%m-%d')}",
        f"- **Filter:** {filter_desc}",
        f"- **Model:** {model or 'default'}",
        f"- **Effort:** {effort or 'default'}",
        f"- **Timeout:** {timeout}s",
        f"- **Parallel workers:** {parallel}",
        f"- **Queries executed:** {total_files}",
        f"- **Results:** {ok} ok, {empty} empty, {errors} errors, {timeouts} timeouts",
        f"- **Total output:** {total_files} files, {total_lines} lines",
        "",
        "## File Index",
        "",
        "| # | Skill | Query | ESI | Status | Duration | Quality |",
        "|---|-------|-------|-----|--------|----------|---------|",
    ]

    for r, q in zip(results, queries):
        query_short = q["query_text"][:60].replace("\n", " ").replace("|", "\\|")
        quality_str = ", ".join(r.get("quality", [])) or "-"
        lines.append(
            f"| {r['seq']:02d} | {r['skill']} | {query_short} | "
            f"{q['esi_level']} | {r['status']} | {r['duration']}s | {quality_str} |"
        )

    # Quality flag summary
    all_flags: list[str] = []
    for r in results:
        all_flags.extend(r.get("quality", []))
    if all_flags:
        flag_counts = Counter(
            # Normalize parametric flags like mcp-fail(2) → mcp-fail
            re.sub(r"\(.*\)", "", f) for f in all_flags
        )
        lines.append("")
        lines.append("## Quality Summary")
        lines.append("")
        # Separate defect flags from informational flags
        defect_flags = {k: v for k, v in flag_counts.items() if k != "no-skill-ok"}
        info_flags = {k: v for k, v in flag_counts.items() if k == "no-skill-ok"}
        for flag, count in sorted(defect_flags.items(), key=lambda x: -x[1]):
            lines.append(f"- **{flag}**: {count} occurrence(s)")
        for flag, count in info_flags.items():
            lines.append(f"- **{flag}**: {count} (injected prereqs, not a defect)")

    manifest = output_dir / "MANIFEST.md"
    manifest.write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def preflight_checks() -> list[str]:
    """Run environment checks before exercises."""
    warnings = []
    # 1. Stale reference data (>30 days)
    stale_threshold = time.time() - (30 * 86400)
    reference_dir = Path("reference")
    if reference_dir.is_dir():
        stale_files = [
            str(p) for pattern in ("**/*.json", "**/*.yaml")
            for p in reference_dir.glob(pattern)
            if p.stat().st_mtime < stale_threshold
        ]
        if stale_files:
            warnings.append(
                f"{len(stale_files)} reference files older than 30 days "
                f"(e.g., {stale_files[0]})"
            )
    # 3. Universe graph exists
    graph_path = Path("src/aria_esi/data/universe.universe")
    if not graph_path.is_file():
        warnings.append(f"Universe graph not found: {graph_path}")
    return warnings


def main():
    parser = argparse.ArgumentParser(
        description="Run ARIA skill exercise queries",
    )
    parser.add_argument(
        "--filter",
        help="Comma-separated ESI levels to include (e.g., NONE,LOW)",
    )
    parser.add_argument(
        "--skills",
        help="Comma-separated skill names to include (e.g., help,price)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Timeout per query in seconds (default: 120)",
    )
    parser.add_argument(
        "--model",
        help="Claude model to use (passed to claude -p --model)",
    )
    parser.add_argument(
        "--effort",
        choices=["low", "medium", "high"],
        help="Reasoning effort level (passed to claude -p --effort)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and filter queries without executing",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="Number of parallel workers (default: 1)",
    )
    parser.add_argument(
        "--explicit",
        action="store_true",
        help="Invoke skills explicitly via /<skill> instead of relying on "
             "natural language trigger matching. Bypasses skill-not-firing issues.",
    )
    parser.add_argument(
        "--changed",
        action="store_true",
        help="Auto-detect skills with modified SKILL.md files in the current "
             "branch (vs main). Combines with --skills if both specified.",
    )
    parser.add_argument(
        "--changed-base",
        default="main",
        help="Base branch for --changed detection (default: main)",
    )
    parser.add_argument(
        "--queries-file",
        type=Path,
        default=QUERIES_PATH,
        help="Path to queries markdown file",
    )

    args = parser.parse_args()

    # Fail fast: check for claude CLI
    if not args.dry_run:
        if not shutil.which("claude"):
            print("Error: 'claude' CLI not found in PATH", file=sys.stderr)
            sys.exit(1)

    # Parse queries
    queries = parse_queries(args.queries_file)
    print(f"Parsed {len(queries)} queries from {args.queries_file.name}")

    # Resolve --changed to skill names
    if args.changed:
        changed = detect_changed_skills(args.changed_base)
        if not changed:
            print("Warning: --changed found no modified skills", file=sys.stderr)
        else:
            print(f"Detected {len(changed)} changed skills: {', '.join(changed)}")
        # Merge with explicit --skills if provided
        if args.skills:
            explicit = args.skills.split(",")
            merged = sorted(set(changed) | set(explicit))
            args.skills = ",".join(merged)
        else:
            args.skills = ",".join(changed) if changed else None

    # Filter
    esi_levels = args.filter.split(",") if args.filter else None
    skill_names = args.skills.split(",") if args.skills else None
    filtered = filter_queries(queries, esi_levels, skill_names)

    filter_desc_parts = []
    if args.changed:
        filter_desc_parts.append("changed")
    if args.explicit:
        filter_desc_parts.append("explicit")
    if esi_levels:
        filter_desc_parts.append(f"ESI:{','.join(esi_levels)}")
    if skill_names:
        filter_desc_parts.append(f"skills:{','.join(skill_names)}")
    filter_desc = " + ".join(filter_desc_parts) if filter_desc_parts else "ALL"

    print(f"After filtering ({filter_desc}): {len(filtered)} queries")

    if args.dry_run:
        print()
        mode = "explicit (/<skill> prefix)" if args.explicit else "implicit (natural language)"
        print(f"Dry run — queries that would execute ({mode}):")
        print()
        for i, q in enumerate(filtered, 1):
            query_short = q["query_text"][:80].replace("\n", "\\n")
            prefix = f"/{q['skill']} " if args.explicit else ""
            print(f"  {i:02d}. [{q['skill']}] (ESI:{q['esi_level']}) \"{prefix}{query_short}\"")
        print()
        print(f"Total: {len(filtered)} queries")
        return

    if not filtered:
        print("No queries match the filter. Nothing to do.")
        return

    # Create output directory
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir = OUTPUT_BASE / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {output_dir}")
    print(f"Allowed tools: {len(ALLOWED_TOOLS)} tools whitelisted")

    preflight_warnings = preflight_checks()
    for w in preflight_warnings:
        print(f"  WARNING: {w}")

    # Run queries
    results = []
    if args.parallel <= 1:
        # Sequential execution
        for seq, query in enumerate(filtered, 1):
            query_short = query["query_text"][:60].replace("\n", "\\n")
            print(f"  [{seq:02d}/{len(filtered)}] {query['skill']} q{query['query_num']}: \"{query_short}\"")
            result = run_query(query, output_dir, seq, args.timeout, args.model, args.effort, args.explicit)
            print(f"          → {result['status']} ({result['duration']}s, {result['lines']} lines)")
            results.append(result)
    else:
        # Parallel execution
        futures = {}
        with ThreadPoolExecutor(max_workers=args.parallel) as executor:
            for seq, query in enumerate(filtered, 1):
                future = executor.submit(
                    run_query, query, output_dir, seq, args.timeout, args.model,
                    args.effort, args.explicit,
                )
                futures[future] = (seq, query)

            for future in as_completed(futures):
                seq, query = futures[future]
                result = future.result()
                query_short = query["query_text"][:60].replace("\n", "\\n")
                print(f"  [{seq:02d}/{len(filtered)}] {query['skill']} q{query['query_num']}: "
                      f"{result['status']} ({result['duration']}s)")
                results.append(result)

        # Sort results by sequence number
        results.sort(key=lambda r: r["seq"])

    # Generate manifest
    generate_manifest(
        output_dir, filtered, results,
        filter_desc, args.model, args.effort, args.timeout, args.parallel,
    )

    # Summary
    ok = sum(1 for r in results if r["status"] == "ok")
    empty = sum(1 for r in results if r["status"] == "empty")
    errors = sum(1 for r in results if r["status"].startswith("error"))
    timeouts = sum(1 for r in results if r["status"] == "timeout")
    print()
    print(f"Done: {ok} ok, {empty} empty, {errors} errors, {timeouts} timeouts")
    print(f"Output: {output_dir}")


if __name__ == "__main__":
    main()
