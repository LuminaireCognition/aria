# Exercise Run Remediation: ESI:MED Path Resolution, Pipe Sandboxing & Timeout Diagnostics

## Context

Exercise run `20260314-202602` tested 14 ESI:MED queries across 7 skills. Pass rate was 71.4% (10/14). Three systemic issues emerged that affect skill reliability beyond just this run:

1. **Reference file path confusion** — model resolves `data_sources` paths relative to the skill directory instead of the project root (5 failures across all exercise runs)
2. **jq pipe sandbox cascade failures** — piped Bash commands trigger sandbox approval in `claude -p`, cancelling parallel sibling calls
3. **No diagnostic output on timeouts** — 4 queries (28.6%) timed out with zero captured data, making root cause analysis impossible

---

## Issue 1: Reference File Path Resolution

### Problem

Skills declare reference files in `data_sources` as project-root-relative paths (e.g., `reference/mechanics/standings_thresholds.json`). The model must issue `Read` calls with these paths at runtime. Across all exercise runs:

- **181 total Read calls** targeting `reference/` paths
- **15 failures** (8.3% failure rate)
- **5 failures** were the skill-dir-relative pattern: model prepends `.claude/skills/{name}/` to the path

The standings skill demonstrates the failure mode clearly:

| Query | Path used | Correct? |
|-------|-----------|----------|
| q1 (fresh context) | `reference/mechanics/standings_thresholds.json` | Yes |
| q2 (later in session) | `.claude/skills/standings/reference/mechanics/standings_thresholds.json` | No |
| q3 (later in session) | `.claude/skills/standings/reference/mechanics/standings_thresholds.json` | No |

The model's path memory degrades as context grows. By q2/q3, it associates `reference/` paths with the skill directory it loaded from.

### Root Cause

Four skills list reference files as `data_sources` (runtime Read) instead of `injected_prerequisites` (load-time injection via `!cat`). The injection pattern has a **0% failure rate** across 9 skills that use it. The runtime-read pattern has an **8.3% failure rate**.

### Two Loading Strategies — Comparison

| Strategy | Mechanism | Skills | Path failures |
|----------|-----------|--------|---------------|
| **Injection** (`!cat`) | Content baked into prompt at skill load time | 9 pure + 2 hybrid | **0** |
| **Runtime Read** | Agent calls `Read("reference/...")` during execution | 4 pure + 2 hybrid | **15** |

### Proposed Fix: Promote 4 Skills to Injection

All four runtime-only reference skills meet the injection eligibility criteria from SCHEMA.md (static path, stable content, <2,000 lines, always needed):

| Skill | Files | Lines added | Always needed? |
|-------|-------|-------------|----------------|
| **standings** | `standings_thresholds.json`, `epic_arcs.json` | +327 | Yes — every query needs thresholds |
| **isk-compare** | `isk_estimates.yaml` | +536 | Yes — the entire skill is a comparison table |
| **sec-status** | `security_status.json` | +84 | Yes — every sec-status query needs thresholds |
| **ship-next** | `archetypes/INDEX.md` | +41 | Yes — ship recommendations require archetype index |

**Total context cost: ~988 lines.** For comparison, `skillplan` already injects 2,219 lines successfully.

This approach aligns with the documented Claude Code skill system:
- `!cat` injection is the documented mechanism for pre-loading data into skill prompts
- `${CLAUDE_SKILL_DIR}` is explicitly for skill-bundled files, NOT project-root reference data
- The docs recommend keeping conditional/large reference as supporting files for on-demand loading — but these 4 files are small and always needed

#### Changes per skill

**standings/SKILL.md:**

1. Move `reference/mechanics/standings_thresholds.json` and `reference/mechanics/epic_arcs.json` from `data_sources` to `injected_prerequisites` in frontmatter
2. Add injection blocks at the end of SKILL.md:

````markdown
## Injected Reference Data

### Standings Thresholds (injected)
<!-- prerequisite: reference/mechanics/standings_thresholds.json -->
!`cat reference/mechanics/standings_thresholds.json`

### Epic Arcs (injected)
<!-- prerequisite: reference/mechanics/epic_arcs.json -->
!`cat reference/mechanics/epic_arcs.json`
````

3. Update `_index.json` entry: move paths from `data_sources` to `injected_prerequisites`
4. Update SKILL.md prose: change "Read `reference/mechanics/standings_thresholds.json`" to "Use the injected standings thresholds data below"

**isk-compare/SKILL.md:**

1. Move `reference/activities/isk_estimates.yaml` from `data_sources` to `injected_prerequisites`
2. Add injection block
3. Update `_index.json`
4. Update SKILL.md prose references

**sec-status/SKILL.md:**

1. Move `reference/mechanics/security_status.json` from `data_sources` to `injected_prerequisites`
2. Add injection block
3. Update `_index.json`
4. Update SKILL.md prose references

**ship-next/SKILL.md:**

1. Move `reference/archetypes/INDEX.md` from `data_sources` to `injected_prerequisites`
2. Add injection block
3. Update `_index.json`
4. Update SKILL.md prose references

#### For hybrid skills (fitting, mission-brief)

The conditionally-needed files (weapon JSONs, archetype templates) should remain as runtime reads. Add an explicit path anchor to each SKILL.md to reduce the skill-dir-relative confusion:

```markdown
**Path resolution:** All `reference/` paths are relative to the project root,
NOT relative to this skill's directory. Read `reference/mechanics/missiles.json`,
not `.claude/skills/fitting/reference/mechanics/missiles.json`.
```

---

## Issue 2: jq Pipe Sandbox Cascade Failures

### Problem

The standings SKILL.md (lines 178-179) includes jq filter examples:

```
Filter by name: `jq '.standings[] | select(.name == "CreoDron")'`
Filter by type: `jq '.standings[] | select(.from_type == "npc_corp")'`
```

The same text appears in `agents-research/SKILL.md` (lines 163-164).

The model follows these examples and pipes CLI output through jq. Claude Code's sandbox splits piped commands into constituent operations. The exercise runner's allowlist (`Bash(uv run:*)`) approves the `uv run` portion but not `jq`. In non-interactive `claude -p` mode, the unapproved `jq` operation is auto-denied.

**Cascade effect:** When one tool call in a parallel batch is denied, Claude Code cancels ALL sibling parallel calls. A single `standings | jq` failure kills the parallel `skills | jq` call too, forcing a full retry cycle.

Observed cost per incident: 2-4 wasted tool calls + ~10s retry delay.

### Proposed Fix

**A. Remove jq filter examples from SKILL.md files** (primary fix)

The CLI returns structured JSON. The model can parse it directly from the tool result without piping through external processors.

In `standings/SKILL.md`, replace the jq filter examples with:

```markdown
Parse the JSON directly from the CLI output. Do not pipe through `jq` or other external processors.
```

Apply the same change to `agents-research/SKILL.md`.

**B. Add no-pipe guidance to shared ESI error handling** (defense-in-depth)

In `.claude/skills/_shared/esi-error-handling.md`, add:

```markdown
## CLI Output Parsing

CLI commands return structured JSON. Parse it directly from the tool result.
Do NOT pipe CLI output through `jq`, `python3`, or other processors — piped
commands may be blocked by sandbox restrictions, cancelling parallel calls.
```

This propagates to all 19 skills that inject the shared error handling file.

---

## Issue 3: Partial Output Capture on Timeouts

### Problem

The exercise runner's timeout handler (lines 622-641 of `exercise-runner.py`) kills the process and writes `# TIMEOUT after 160s` with no diagnostic data. The `claude -p --output-format stream-json` format writes JSON events incrementally — by 160s, dozens of events (tool calls, assistant turns) may have been written to the stdout pipe buffer. All are discarded.

Four queries timed out in run 20260314-202602 (fit-check, fit-budget, ship-next x2). Without tool traces, we cannot determine whether the bottleneck is ESI latency, excessive tool calls, model thinking time, or a blocking prompt.

### Root Cause

```python
except subprocess.TimeoutExpired:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except OSError:
        proc.kill()
    proc.wait()          # pipes not drained
    duration = time.monotonic() - start
    body = f"# TIMEOUT after {timeout}s"  # no partial data
```

After `SIGKILL`, the process is dead but its pipe buffers still contain data. `proc.wait()` reaps the process without reading stdout/stderr. `proc.communicate()` would drain the buffers first.

### Proposed Fix

Replace the timeout handler with:

```python
except subprocess.TimeoutExpired:
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
            trace_lines.append(f"- `{tool_name}` -> {summary}")
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
```

The existing `_parse_stream_output` already handles malformed JSON (catches `JSONDecodeError` and skips truncated lines), so a mid-kill truncation is safe.

---

## Implementation Order

| Priority | Issue | Effort | Impact |
|----------|-------|--------|--------|
| **P0** | Promote 4 skills to injection | ~1hr | Eliminates 100% of runtime path failures for these skills |
| **P1** | Remove jq examples + add no-pipe guidance | ~30min | Eliminates cascade failures in exercise runs and production |
| **P2** | Partial output capture on timeouts | ~30min | Enables root cause analysis for the 4 timed-out skills |

P0 and P1 can be done in parallel. P2 is independent.

## Verification

After implementing all three fixes:

1. Re-run the ESI:MED exercise suite: `uv run python dev/scripts/exercise-runner.py --filter MED --explicit --timeout 180`
2. Verify: no "File does not exist" errors in `.tools.json` files for standings, isk-compare, sec-status, ship-next
3. Verify: no jq/python pipe blocks in `.tools.json` files
4. Verify: timed-out queries now have `.tools.json` files with partial tool traces
5. Compare pass rate against the 71.4% baseline
