# Tool Call Trace Capture for Exercise Runner

## Problem

The exercise runner (`dev/scripts/exercise-runner.py`) captures only the final text output from each query. We infer skill compliance (prerequisite file reads, MCP tool usage) from Sources footers in the response text. This is unreliable:

- **mission-brief** declares 12+ `prerequisite_files` but its Sources footer only mentions the cached wiki file
- **fitting q2** (file 09) has no Sources footer at all — we can't tell if it read anything
- A model could cite a source in the footer without actually reading it

Tool call traces would make compliance verification definitive: did the model actually call `Read` on every `prerequisite_files` path? Did it call `sde()` before stating game stats?

## Current State

The runner already uses `--output-format json` and has a `_parse_json_output()` function that tries to extract tool calls from a `messages` array. However, **`claude -p --output-format json` does not include tool call data** — it only returns `{result, session_id, usage, model}`. No `.tools.json` files were generated in the 20260309-151556 run because there was nothing to extract.

## Proposed Solution: Switch to `stream-json`

Replace `--output-format json` with `--output-format stream-json`, which emits newline-delimited JSON events including `tool_use` content blocks with full inputs and results.

### Event Structure

```jsonl
{"type":"stream_event","event":{"type":"content_block_start","content_block":{"type":"tool_use","id":"abc","name":"Read","input":{}}}}
{"type":"stream_event","event":{"type":"content_block_delta","delta":{"type":"input_json_delta","partial_json":"..."}}}
{"type":"stream_event","event":{"type":"content_block_stop"}}
```

Tool results appear as `tool_result` blocks in subsequent messages. Text output appears as `text_delta` events.

### Implementation Changes

**1. Replace `_parse_json_output()` with a stream parser**

```python
def _parse_stream_output(raw: str) -> tuple[str, list[dict]]:
    """
    Parse claude -p --output-format stream-json output.

    Returns (text_content, tool_calls) where tool_calls is a list of
    {tool, input, id, result?} dicts extracted from the event stream.
    """
    text_parts = []
    tool_calls = []
    current_tool = None  # accumulates input JSON deltas
    current_tool_input = ""

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        # Unwrap stream_event wrapper if present
        if event.get("type") == "stream_event":
            event = event.get("event", event)

        etype = event.get("type", "")

        # Text deltas → final response text
        if etype == "content_block_delta":
            delta = event.get("delta", {})
            if delta.get("type") == "text_delta":
                text_parts.append(delta.get("text", ""))
            elif delta.get("type") == "input_json_delta":
                current_tool_input += delta.get("partial_json", "")

        # Tool use start
        elif etype == "content_block_start":
            block = event.get("content_block", {})
            if block.get("type") == "tool_use":
                current_tool = {
                    "tool": block.get("name", ""),
                    "id": block.get("id", ""),
                }
                current_tool_input = ""

        # Tool use end — finalize input
        elif etype == "content_block_stop":
            if current_tool is not None:
                try:
                    current_tool["input"] = json.loads(current_tool_input)
                except (json.JSONDecodeError, ValueError):
                    current_tool["input"] = current_tool_input
                tool_calls.append(current_tool)
                current_tool = None
                current_tool_input = ""

        # Result message (contains tool_result blocks)
        elif etype == "message_start":
            msg = event.get("message", {})
            if msg.get("role") == "tool":
                for block in msg.get("content", []):
                    if block.get("type") == "tool_result":
                        tool_id = block.get("tool_use_id", "")
                        for tc in tool_calls:
                            if tc.get("id") == tool_id and "result" not in tc:
                                result_content = str(block.get("content", ""))
                                tc["result"] = result_content[:2000]
                                break

    return "".join(text_parts), tool_calls
```

**2. Update `run_query()` command construction**

```python
# Before
cmd = ["claude", "-p", "--output-format", "json"]

# After
cmd = ["claude", "-p", "--output-format", "stream-json"]
```

**3. Update output format in `run_query()`**

Replace the `_parse_json_output` call with `_parse_stream_output`. The rest of the function (header generation, file writing, tool log saving) stays the same — it already writes `.tools.json` sidecar files when `tool_calls` is non-empty.

**4. Generate a compact trace summary in the `.md` output**

Append a `## Tool Trace` section at the bottom of each output file for human readability:

```python
if tool_calls:
    trace_lines = ["\n---\n## Tool Trace\n"]
    for tc in tool_calls:
        tool_name = tc["tool"]
        # Compact input summary
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
```

### Output Structure Per Query

After the change, each query produces:

| File | Contents |
|------|----------|
| `NN-skill-qN.md` | Header + response text + Tool Trace footer |
| `NN-skill-qN.tools.json` | Full tool call log with inputs and truncated results |

### What This Enables

**Automated prerequisite compliance checks** — compare `_index.json` prerequisite_files against actual Read calls in `.tools.json`:

```python
def check_prereq_compliance(skill_name: str, tool_log: list[dict]) -> list[str]:
    """Return list of prerequisite_files that were NOT read."""
    index = json.loads(Path("_index.json").read_text())
    skill = next(s for s in index["skills"] if s["name"] == skill_name)
    required = set(skill.get("prerequisite_files", []))

    read_paths = {
        tc["input"]["file_path"]
        for tc in tool_log
        if tc["tool"] == "Read" and "file_path" in tc.get("input", {})
    }

    # Normalize: prerequisite paths are project-root-relative
    project_root = str(Path(__file__).resolve().parent.parent.parent)
    read_relative = {
        p.removeprefix(project_root + "/") for p in read_paths
    }

    return sorted(required - read_relative)
```

**Automated Sources footer validation** — cross-check MCP calls in trace against Sources footer claims.

**Skill loading chain verification** — confirm the sequence: `Skill` invoke → `Read` SKILL.md → `Read` prerequisite files → MCP calls → response.

## Scope & Risk

- **Changed:** `_parse_json_output` → `_parse_stream_output`, command flag `json` → `stream-json`
- **Unchanged:** Query parsing, filtering, parallel execution, manifest generation, output file naming
- **Risk:** Stream-json output is larger than json output (many events per query). `subprocess.run(capture_output=True)` buffers stdout in memory. At ~100KB per query this is fine; if queries produce very large tool results the 2000-char truncation in the parser keeps it bounded.
- **Fallback:** If stream-json parsing fails for a query (malformed stream), the parser returns the raw text and an empty tool list — same behavior as today.

## Not In Scope

- **Post-run compliance report generation** — this proposal captures the data. A follow-up can add a `--check-compliance` flag that reads `.tools.json` files and produces a compliance summary.
- **Sources footer format standardization** — separate concern (report issue H3).
- **Agent SDK migration** — `stream-json` with `claude -p` is sufficient. The Agent SDK would give cleaner hooks but adds a dependency and changes the runner's architecture significantly.
