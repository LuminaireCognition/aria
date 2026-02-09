• 1. Repository map (concise)

  - Key directories/files: .claude/ contains Claude Code integration (boot hook, context assembly, skill index, and skill prompts),
    with skill frontmatter driving behavior. README.md:L179-L211, .claude/hooks/aria-boot.sh:L1-L144, .claude/scripts/aria-context-
    assembly.py:L1-L176, .claude/scripts/aria-skill-index.py:L1-L200, .claude/skills/aria-status/SKILL.md:L1-L165
  - Core runtime: src/aria_esi/ provides the aria-esi CLI and the aria-universe MCP server entrypoint; the MCP server loads the
    universe graph and registers dispatchers. pyproject.toml:L13-L15, src/aria_esi/mcp/server.py:L1-L115
  - Personas/overlays: persona context and overlay resolution are defined in docs and persona shared guidance, including untrusted-
    data delimiter rules. docs/PERSONA_LOADING.md:L11-L196, personas/_shared/skill-loading.md:L149-L198
  - Data and templates: pilot data lives under userdata/, templates in templates/, and static reference in reference/.
    README.md:L189-L231
  - Protocol docs: context budget/provenance, data verification, and volatility protocols are centralized in docs/. docs/
    CONTEXT_POLICY.md:L1-L198, docs/DATA_VERIFICATION.md:L1-L200, docs/PROTOCOLS.md:L1-L159
  - Tests: MCP context/policy and context sanitization tests are present. tests/mcp/test_context.py:L1-L120, tests/mcp/
    test_policy.py:L1-L200, tests/test_context_sanitization.py:L1-L120
  - Execution flow: session start triggers the boot hook, which runs prerequisite checks, security preflight, ESI sync, context
    assembly, and skill index update. .claude/hooks/aria-boot.sh:L92-L126, .claude/hooks/aria-boot.d/boot-operations.sh:L403-L449
  - Execution flow: context assembly generates .session-context.json, and session protocol defines how ARIA consumes it. .claude/
    scripts/aria-context-assembly.py:L1-L176, docs/SESSION_CONTEXT.md:L1-L60
  - Execution flow: ARIA follows CLAUDE.md for pilot resolution and persona_context loading, then uses MCP dispatchers where
    available. CLAUDE.md:L62-L191, docs/PERSONA_LOADING.md:L11-L154
  - Execution flow: MCP server registers dispatchers; dispatchers validate actions and enforce policy. src/aria_esi/mcp/
    server.py:L72-L115, src/aria_esi/mcp/tools.py:L31-L92, src/aria_esi/mcp/dispatchers/universe.py:L65-L289, src/aria_esi/mcp/
    policy.py:L292-L399
  - Execution flow: tool outputs are wrapped with metadata and logged; budgets are tracked. src/aria_esi/mcp/context.py:L1-L508, src/
    aria_esi/mcp/context_budget.py:L1-L136, src/aria_esi/mcp/context_policy.py:L1-L199
  - Execution flow: CLI fallback includes dry-run commands for profile sync and migrations. src/aria_esi/__main__.py:L147-L167
  - Prompt composition: system guardrails live in CLAUDE.md and explicitly govern untrusted data handling and tool usage preferences.
    CLAUDE.md:L17-L191
  - Prompt composition: skill prompts are SKILL.md files with YAML frontmatter (schema defined in ADR-002) and indexed by aria-skill-
    index.py. dev/decisions/ADR-002-skill-metadata-schema.md:L17-L61, .claude/scripts/aria-skill-index.py:L1-L200, .claude/skills/
    aria-status/SKILL.md:L1-L165
  - Prompt composition: persona_context defines precomputed file lists and overlay resolution; overlays are treated as untrusted
    data. docs/PERSONA_LOADING.md:L11-L196, personas/_shared/skill-loading.md:L149-L198

  2. LLM integration review (deep)

  Model invocation layer

  - Current: model choice is declared per skill (frontmatter) and runtime is external to Python; repo entrypoints are CLI + MCP
    tools. dev/decisions/ADR-002-skill-metadata-schema.md:L17-L55, .claude/skills/aria-status/SKILL.md:L1-L12, pyproject.toml:L13-L15
  - Missing/Risk: no in-repo LLM client wrapper (timeouts/retries/streaming/fallbacks) if you later add direct model calls; this is
    an inferred gap from the lack of LLM SDKs/entrypoints. pyproject.toml:L13-L69
  - Change: if direct model calls are planned, add src/aria_esi/llm/adapter.py with timeout/backoff patterns aligned to existing
    retry utilities. src/aria_esi/core/retry.py:L1-L114

  Prompting

  - Current: system guardrails and untrusted-data rules are explicit; persona_context uses precomputed file lists; overlays are
    treated as data. CLAUDE.md:L17-L176, docs/PERSONA_LOADING.md:L11-L154, personas/_shared/skill-loading.md:L149-L179
  - Missing/Risk: delimiter protocol is conceptual only; there is no compiled prompt artifact that actually wraps persona/overlay
    text at boot, so compliance relies on the LLM. docs/PERSONA_LOADING.md:L155-L185, personas/_shared/skill-loading.md:L149-L179
  - Change: add a boot-time compiled context file that concatenates persona/overlay content wrapped in <untrusted-data> tags and load
    it as a single artifact. .claude/hooks/aria-boot.d/boot-operations.sh:L383-L441, .claude/scripts/aria-context-assembly.py:L1-L176

  Tool/MCP use

  - Current: unified dispatchers validate actions and call policy gating; context wrappers add _meta and summarization; centralized
    limits are defined; typed models exist. src/aria_esi/mcp/dispatchers/universe.py:L65-L289, src/aria_esi/mcp/dispatchers/
    market.py:L79-L320, src/aria_esi/mcp/policy.py:L292-L399, src/aria_esi/mcp/context.py:L1-L508, src/aria_esi/mcp/
    context_policy.py:L1-L199, src/aria_esi/mcp/models.py:L1-L144
  - Missing/Risk: policy is action-only and does not elevate sensitivity when use_pilot_skills is true; dispatchers do not pass
    context to policy; byte-size limits are defined but not enforced. src/aria_esi/mcp/dispatchers/fitting.py:L31-L99, src/aria_esi/
    mcp/policy.py:L114-L116, src/aria_esi/mcp/context_policy.py:L183-L196, src/aria_esi/mcp/context.py:L90-L167
  - Change: make PolicyEngine.get_action_sensitivity context-aware for fitting, pass context into check_capability, and enforce byte
    limits in wrap_output/wrap_output_multi. src/aria_esi/mcp/policy.py:L276-L345, src/aria_esi/mcp/dispatchers/fitting.py:L31-L99,
    src/aria_esi/mcp/context.py:L90-L200

  Data access

  - Current: session context assembly sanitizes and validates fields/aliases; session context usage is documented; data verification
    and volatility rules are explicit. .claude/scripts/aria-context-assembly.py:L39-L176, tests/test_context_sanitization.py:L1-L120,
    docs/SESSION_CONTEXT.md:L1-L60, docs/DATA_VERIFICATION.md:L1-L200, docs/PROTOCOLS.md:L5-L159, dev/decisions/ADR-003-data-
    volatility-protocol.md:L1-L39
  - Missing/Risk: provenance/citations are required by docs but not embedded in tool output metadata; no chunking/RAG for large
    reference data. docs/CONTEXT_POLICY.md:L143-L154, src/aria_esi/mcp/context.py:L52-L167
  - Change: add _meta.source and _meta.as_of fields and a small retrieval helper for reference data to limit context injection and
    ensure provenance. docs/CONTEXT_POLICY.md:L143-L154, src/aria_esi/mcp/context.py:L52-L167

  Output quality

  - Current: Pydantic models enforce schema constraints; _meta wrappers add counts and timestamps; tests cover context/sanitization.
    src/aria_esi/mcp/models.py:L1-L144, src/aria_esi/mcp/context.py:L52-L167, tests/mcp/test_context.py:L1-L120, tests/
    test_context_sanitization.py:L1-L120
  - Missing/Risk: skill outputs are unvalidated free text and there are no golden tests/evals for skill prompts. .claude/skills/aria-
    status/SKILL.md:L20-L165, .claude/scripts/aria-skill-index.py:L123-L200
  - Change: add golden tests for key skills and enforce wrapper usage in dispatchers via lint/test. tests/mcp/test_context.py:L73-
    L120, .claude/skills/aria-status/SKILL.md:L20-L165

  Observability

  - Current: structured logging supports JSON output; MCP calls are logged with sanitized params and budget; policy logs audit
    decisions. src/aria_esi/core/logging.py:L1-L173, src/aria_esi/mcp/context.py:L381-L507, src/aria_esi/mcp/policy.py:L371-L401
  - Missing/Risk: no trace/turn IDs to correlate LLM ↔ tools ↔ CLI; policy audit logs don’t include skill/pilot context. src/
    aria_esi/mcp/context.py:L419-L507, src/aria_esi/mcp/policy.py:L371-L401
  - Change: add optional trace_id/turn_id fields in dispatcher params, propagate to log_context and policy audit logs. src/aria_esi/
    mcp/context.py:L419-L507, src/aria_esi/mcp/policy.py:L371-L401

  Safety & security

  - Current: untrusted data guardrails are explicit; overlay delimiters are defined; context assembly sanitization is tested; boot
    preflight blocks unsafe persona paths; credentials are checked for secure permissions and keyring is supported. CLAUDE.md:L17-
    L60, personas/_shared/skill-loading.md:L149-L179, .claude/scripts/aria-context-assembly.py:L39-L176, tests/
    test_context_sanitization.py:L1-L120, .claude/hooks/aria-boot.sh:L92-L126, src/aria_esi/core/auth.py:L1-L175
  - Missing/Risk: broad command permissions (including raw python3/pip3) violate the uv run policy and expand the blast radius if a
    prompt is compromised. .claude/settings.local.json:L64-L67, CLAUDE.md:L144-L157
  - Change: tighten .claude/settings.local.json to remove bare Python/Pip and rely on uv run wrappers; add a skill preflight check
    for overlay paths. .claude/settings.local.json:L64-L83, CLAUDE.md:L144-L157, .claude/hooks/aria-boot.d/boot-operations.sh:L403-
    L449

  Cost/perf

  - Current: explicit budgets/limits and summarization rules exist; context budget tracking warns at thresholds; ESI client has
    timeouts and retries. docs/CONTEXT_POLICY.md:L17-L141, src/aria_esi/mcp/context_policy.py:L183-L196, src/aria_esi/mcp/
    context_budget.py:L33-L105, src/aria_esi/mcp/context.py:L360-L377, src/aria_esi/core/client.py:L127-L149, src/aria_esi/core/
    retry.py:L1-L114
  - Missing/Risk: budgets are advisory only and there’s no hard byte-size enforcement at wrapper level. src/aria_esi/mcp/
    context_policy.py:L183-L196, src/aria_esi/mcp/context.py:L90-L167
  - Change: enforce per-tool byte budgets in wrap_output and wrap_output_multi with truncation metadata. src/aria_esi/mcp/
    context.py:L90-L200, src/aria_esi/mcp/context_policy.py:L183-L196

  Human-in-the-loop

  - Current: ESI is read-only and volatile data should only be returned on explicit request; CLI supports dry-run modes for write-
    like operations. CLAUDE.md:L5-L15, docs/PROTOCOLS.md:L18-L32, src/aria_esi/__main__.py:L147-L167
  - Missing/Risk: skill metadata does not include a standardized confirmation/dry-run requirement for write actions. dev/decisions/
    ADR-002-skill-metadata-schema.md:L17-L35
  - Change: extend skill metadata schema to include requires_confirmation and enforce “dry-run then confirm” in skill guidance. dev/
    decisions/ADR-002-skill-metadata-schema.md:L17-L35, .claude/skills/aria-status/SKILL.md:L32-L40

  Review rubric

  - Reliability: 3/5 — ESI retry/timeouts exist, but no model-invocation adapter and no hard output-size enforcement. src/aria_esi/
    core/retry.py:L1-L114, src/aria_esi/core/client.py:L127-L149, src/aria_esi/mcp/context_policy.py:L183-L196
  - Security: 4/5 — policy gating, untrusted-data rules, and boot preflight are strong, but settings permissions are too broad and
    context-sensitive auth is missing. src/aria_esi/mcp/policy.py:L292-L345, CLAUDE.md:L17-L60, .claude/hooks/aria-boot.sh:L92-
    L126, .claude/settings.local.json:L64-L67, src/aria_esi/mcp/dispatchers/fitting.py:L31-L99
  - Maintainability: 4/5 — dispatchers and centralized limits are clean, and skill metadata schema is defined. src/aria_esi/mcp/
    dispatchers/universe.py:L65-L289, src/aria_esi/mcp/context_policy.py:L1-L199, dev/decisions/ADR-002-skill-metadata-schema.md:L17-
    L61
  - Observability: 3/5 — JSON logging and MCP call logs exist, but no trace/turn correlation. src/aria_esi/core/logging.py:L1-L173,
    src/aria_esi/mcp/context.py:L419-L507
  - Data governance: 3/5 — verification and volatility protocols are solid, but provenance fields aren’t enforced in outputs. docs/
    DATA_VERIFICATION.md:L1-L200, docs/PROTOCOLS.md:L5-L159, src/aria_esi/mcp/context.py:L52-L167
  - Cost control: 3/5 — context budgets and summarization exist, but no hard byte enforcement. docs/CONTEXT_POLICY.md:L33-L141, src/
    aria_esi/mcp/context_budget.py:L33-L105, src/aria_esi/mcp/context.py:L90-L167
  - Skill-readiness: 3/5 — frontmatter schema and index are present, but no runtime preflight or golden tests. dev/decisions/ADR-002-
    skill-metadata-schema.md:L17-L61, .claude/scripts/aria-skill-index.py:L123-L200

  3. Claude Code Skills extension plan (primary focus)

  1. Define skill boundaries/taxonomy aligned to MCP dispatchers: keep core app in src/aria_esi (MCP server + CLI), and treat skills
     as high-level orchestration around dispatchers; use ADR-002 categories to map skills to domains (tactical/operations/financial/
     identity/system). dev/decisions/ADR-002-skill-metadata-schema.md:L17-L35, src/aria_esi/mcp/dispatchers/__init__.py:L1-L29
  2. Establish explicit skill I/O contracts: create JSON Schemas for SkillInput/SkillOutput that include _meta fields aligned to
     context policy, and require source/as_of for any external data. docs/CONTEXT_POLICY.md:L38-L154, src/aria_esi/mcp/
     context.py:L52-L167
  3. Package/version skills: standardize a per-skill layout (SKILL.md, schema.json, fixtures/, tests/, CHANGELOG.md), and keep
     _index.json auto-generated via aria-skill-index.py at boot. .claude/scripts/aria-skill-index.py:L1-L200, .claude/hooks/aria-
     boot.d/boot-operations.sh:L370-L381
  4. Add a skill router/preflight: use _index.json trigger map and metadata (requires_pilot, data_sources, esi_scopes) to gate
     execution; prefer MCP tools per CLAUDE.md and fall back to CLI when MCP is unavailable. CLAUDE.md:L161-L197, .claude/scripts/
     aria-skill-index.py:L195-L200
  5. Testing strategy: add unit tests for the router and preflight, golden tests for output format of top skills, and mock MCP
     dispatchers using existing MCP test patterns. tests/mcp/test_context.py:L1-L120, tests/mcp/test_policy.py:L1-L200
  6. Security model: enforce least-privilege file access for skills, validate overlay paths at boot, and tighten tool permissions
     in .claude/settings.local.json to align with uv run only. .claude/hooks/aria-boot.sh:L92-L126, .claude/settings.local.json:L64-
     L83, CLAUDE.md:L144-L157, personas/_shared/skill-loading.md:L149-L179
  7. Draft skill specs (examples derived from existing dispatchers and protocols):

  # Skill: market-arbitrage-scan (financial)
  input_schema:
    type: object
    properties:
      min_profit_pct: {type: number, minimum: 1}
      min_volume: {type: integer, minimum: 1}
      max_results: {type: integer, minimum: 1, maximum: 50}
      buy_from: {type: array, items: {type: string}}
      sell_to: {type: array, items: {type: string}}
    required: []
  tools:
    - market(action="arbitrage_scan", min_profit_pct, min_volume, max_results, buy_from, sell_to)
  output_schema:
    type: object
    properties:
      opportunities: {type: array}
      _meta: {type: object}
  example_prompts:
    - "Scan for 10%+ arbitrage between Jita and Amarr"

  src/aria_esi/mcp/dispatchers/market.py:L79-L320, src/aria_esi/mcp/context_policy.py:L82-L109

  # Skill: route-risk-brief (tactical)
  input_schema:
    type: object
    properties:
      origin: {type: string}
      destination: {type: string}
      mode: {type: string, enum: ["shortest", "safe", "unsafe"]}
    required: [origin, destination]
  tools:
    - universe(action="route", origin, destination, mode)
    - universe(action="gatecamp_risk", route)
  output_schema:
    type: object
    properties:
      route: {type: array}
      risk_summary: {type: object}
      _meta: {type: object}
  example_prompts:
    - "Give me a gatecamp risk brief from Dodixie to Jita"

  src/aria_esi/mcp/dispatchers/universe.py:L65-L289, src/aria_esi/mcp/context_policy.py:L61-L71

  4. Priority-ranked action list

  | Priority | Change description | Files to touch | Effort | Risk addressed |
  |---|---|---|---|---|
  | P0 | Enforce auth-sensitive policy when use_pilot_skills is true | src/aria_esi/mcp/policy.py:L292-L345, src/aria_esi/mcp/
  dispatchers/fitting.py:L31-L99, tests/mcp/test_policy.py:L94-L194 | S | Unauthorized access to authenticated data |
  | P0 | Add skill preflight/router that validates requires_pilot, data_sources, and esi_scopes | .claude/scripts/aria-skill-
  index.py:L123-L200, CLAUDE.md:L62-L157 | M | Skills executing without required data/scopes |
  | P1 | Enforce per-tool byte size limits and add provenance fields in _meta | src/aria_esi/mcp/context.py:L90-L200, src/aria_esi/
  mcp/context_policy.py:L183-L196, docs/CONTEXT_POLICY.md:L143-L154 | M | Context overflow, poor provenance |
  | P1 | Add trace/turn IDs to MCP logging and policy audit logs | src/aria_esi/mcp/context.py:L419-L507, src/aria_esi/mcp/
  policy.py:L371-L401, src/aria_esi/core/logging.py:L1-L173 | S | Low observability across turns |
  | P2 | Tighten .claude/settings.local.json command permissions to remove raw python/pip | .claude/settings.local.json:L64-L83,
  CLAUDE.md:L144-L157 | S | Prompt-injection blast radius |
  | P2 | Add CI/boot check for skill index staleness (--check) | .claude/scripts/aria-skill-index.py:L1-L200, .claude/hooks/aria-
  boot.d/boot-operations.sh:L370-L381 | S | Skill metadata drift |

  5. Code-level recommendations (patch-ready)

  Issue 1: Context-aware policy for fitting (auth-sensitive)

  - Proposed code changes: src/aria_esi/mcp/policy.py:L276-L345, src/aria_esi/mcp/dispatchers/fitting.py:L31-L99

  diff --git a/src/aria_esi/mcp/policy.py b/src/aria_esi/mcp/policy.py
  @@
  -    def get_action_sensitivity(self, dispatcher: str, action: str) -> SensitivityLevel:
  +    def get_action_sensitivity(
  +        self, dispatcher: str, action: str, context: dict[str, Any] | None = None
  +    ) -> SensitivityLevel:
  @@
  -        dispatcher_actions = DEFAULT_ACTION_SENSITIVITY.get(dispatcher, {})
  -        return dispatcher_actions.get(
  -            action, dispatcher_actions.get("_default", SensitivityLevel.PUBLIC)
  -        )
  +        if dispatcher == "fitting" and action == "calculate_stats" and context:
  +            if context.get("use_pilot_skills"):
  +                return SensitivityLevel.AUTHENTICATED
  +        dispatcher_actions = DEFAULT_ACTION_SENSITIVITY.get(dispatcher, {})
  +        return dispatcher_actions.get(
  +            action, dispatcher_actions.get("_default", SensitivityLevel.PUBLIC)
  +        )
  @@
  -        sensitivity = self.get_action_sensitivity(dispatcher, action)
  +        sensitivity = self.get_action_sensitivity(dispatcher, action, context)
  diff --git a/src/aria_esi/mcp/dispatchers/fitting.py b/src/aria_esi/mcp/dispatchers/fitting.py
  @@
  -        check_capability("fitting", action)
  +        check_capability("fitting", action, context={"use_pilot_skills": use_pilot_skills})

  - New config/env vars: none.
  - Tests to add: add a test that denies use_pilot_skills when policy allows only public. tests/mcp/test_policy.py:L175-L194

  Issue 2: Enforce per-tool output byte budget and provenance in _meta

  - Proposed code changes: src/aria_esi/mcp/context.py:L90-L200, src/aria_esi/mcp/context_policy.py:L183-L196

  diff --git a/src/aria_esi/mcp/context.py b/src/aria_esi/mcp/context.py
  @@
  -from .context_policy import GLOBAL
  +from .context_policy import GLOBAL
  @@
   def wrap_output(
       data: dict[str, Any],
       items_key: str,
       max_items: int = 50,
   ) -> dict[str, Any]:
  @@
       data["_meta"] = OutputMeta(
           count=len(items),
           truncated=truncated,
           truncated_from=original_count if truncated else None,
       ).to_dict()
  +    _enforce_output_bytes(data, items_key)

       return data
  +
  +def _enforce_output_bytes(data: dict[str, Any], items_key: str) -> None:
  +    """Trim list payloads if serialized output exceeds GLOBAL.MAX_OUTPUT_SIZE_BYTES."""
  +    try:
  +        size = len(json.dumps(data))
  +    except (TypeError, ValueError):
  +        return
  +    if size <= GLOBAL.MAX_OUTPUT_SIZE_BYTES:
  +        return
  +    items = data.get(items_key)
  +    if isinstance(items, list) and len(items) > 1:
  +        ratio = GLOBAL.MAX_OUTPUT_SIZE_BYTES / max(size, 1)
  +        new_len = max(1, int(len(items) * ratio))
  +        data[items_key] = items[:new_len]
  +        meta = data.setdefault("_meta", {})
  +        meta["truncated"] = True
  +        meta["truncated_from"] = len(items)
  +        meta["original_bytes"] = size

  - New config/env vars: none (uses GLOBAL.MAX_OUTPUT_SIZE_BYTES).
  - Tests to add: add a test that forces truncation when output size exceeds the max. tests/mcp/test_context.py:L73-L120

  Issue 3: Skill preflight script to validate requires_pilot, data_sources, esi_scopes

  - Proposed code changes: new script plus documentation hook. .claude/scripts/aria-skill-index.py:L123-L200, CLAUDE.md:L62-L157

  diff --git a/.claude/scripts/aria-skill-preflight.py b/.claude/scripts/aria-skill-preflight.py
  new file mode 100755
  --- /dev/null
  +++ b/.claude/scripts/aria-skill-preflight.py
  @@
  +#!/usr/bin/env python3
  +import json
  +from pathlib import Path
  +
  +def load_active_pilot(root: Path) -> str | None:
  +    cfg = root / "userdata" / "config.json"
  +    reg = root / "userdata" / "pilots" / "_registry.json"
  +    if cfg.exists():
  +        active = json.loads(cfg.read_text()).get("active_pilot")
  +    else:
  +        active = None
  +    if reg.exists() and active:
  +        data = json.loads(reg.read_text())
  +        for p in data.get("pilots", []):
  +            if str(p.get("character_id")) == str(active):
  +                return p.get("directory")
  +    return None
  +
  +def main():
  +    root = Path(__file__).resolve().parents[2]
  +    idx = root / ".claude" / "skills" / "_index.json"
  +    payload = json.loads(idx.read_text())
  +    # Lookup skill by name from argv, validate data_sources and esi_scopes.
  +    # Emit {"ok": bool, "missing_sources": [], "missing_scopes": []}
  +    print(json.dumps({"ok": True}))
  +
  +if __name__ == "__main__":
  +    main()

  - New config/env vars: optional ARIA_SKILL_PREFLIGHT=1 to require checks before skill use.
  - Tests to add: tests/test_skill_preflight.py validating missing pilot/data sources and missing scopes; add a fixture that points
    to a temp userdata/ tree.

  6. Checklists

  - LLM integration checklist: [ ] System guardrails and untrusted-data rules are enforced by compiled context artifacts, not just
    instructions. CLAUDE.md:L17-L60, docs/PERSONA_LOADING.md:L155-L185
  - LLM integration checklist: [ ] Direct model invocation (if added) has timeout/backoff and streaming handling documented. src/
    aria_esi/core/retry.py:L1-L114
  - LLM integration checklist: [ ] Tool outputs include _meta with provenance (source, as_of) and byte limits are enforced. docs/
    CONTEXT_POLICY.md:L143-L154, src/aria_esi/mcp/context.py:L52-L167
  - MCP/tooling checklist: [ ] All dispatchers validate actions and call check_capability with relevant context. src/aria_esi/mcp/
    dispatchers/universe.py:L213-L221, src/aria_esi/mcp/dispatchers/market.py:L246-L255, src/aria_esi/mcp/dispatchers/fitting.py:L31-
    L99
  - MCP/tooling checklist: [ ] Context budgets are tracked and reset per turn; oversized outputs are truncated. src/aria_esi/mcp/
    context_budget.py:L33-L136, src/aria_esi/mcp/context.py:L90-L200
  - MCP/tooling checklist: [ ] Structured logs include trace IDs and policy audit decisions. src/aria_esi/core/logging.py:L1-L173,
    src/aria_esi/mcp/policy.py:L371-L401
  - Claude Code Skills checklist: [ ] Every skill has ADR-002 frontmatter and is indexed in _index.json. dev/decisions/ADR-002-skill-
    metadata-schema.md:L17-L61, .claude/scripts/aria-skill-index.py:L1-L200
  - Claude Code Skills checklist: [ ] Skill overlays follow untrusted-data delimiter rules and remain within allowlisted paths.
    personas/_shared/skill-loading.md:L149-L179, .claude/hooks/aria-boot.sh:L92-L126
  - Claude Code Skills checklist: [ ] Skills requiring pilot data declare data_sources/esi_scopes and pass preflight before
    execution. .claude/skills/aria-status/SKILL.md:L12-L17, dev/decisions/ADR-002-skill-metadata-schema.md:L17-L35

  7. Implementation Status

  P0 Issues - COMPLETE
  - [x] Context-aware policy for fitting (use_pilot_skills escalates to AUTHENTICATED)
    - src/aria_esi/mcp/policy.py - get_action_sensitivity now accepts context parameter
    - src/aria_esi/mcp/dispatchers/fitting.py - passes use_pilot_skills context to check_capability
    - tests/mcp/test_policy.py - TestContextAwareSensitivity class validates behavior
  - [x] Skill preflight validation script
    - .claude/scripts/aria-skill-preflight.py - validates requires_pilot, data_sources, esi_scopes
    - tests/test_skill_preflight.py - comprehensive test coverage

  P1 Issues - COMPLETE (2026-01-23)
  - [x] Enforce per-tool byte size limits and add provenance fields in _meta
    - src/aria_esi/mcp/context.py:
      - OutputMeta extended with source and as_of fields
      - _enforce_output_bytes() helper for single-list outputs
      - _enforce_output_bytes_multi() helper for multi-list outputs
      - wrap_output(), wrap_scalar_output(), wrap_output_multi() accept source/as_of params
      - Byte enforcement integrated into wrap functions with metadata tracking
    - tests/mcp/test_context.py:
      - TestByteEnforcement class with 7 tests
      - TestProvenance class with 9 tests
  - [x] Add trace/turn IDs to MCP logging and policy audit logs
    - src/aria_esi/mcp/context.py:
      - _trace_id_var and _turn_id_var ContextVars added
      - set_trace_context(), get_trace_context(), reset_trace_context() functions
      - log_context decorator includes trace context in all log entries
      - Supports _trace_id/_turn_id kwargs for caller-provided context
    - src/aria_esi/mcp/policy.py:
      - _audit_log() includes trace_id and turn_id when set
    - tests/mcp/test_context.py:
      - TestTraceContext class with 5 tests
    - tests/mcp/test_policy.py:
      - TestPolicyAuditWithTrace class with 2 tests

  P2 Issues - COMPLETE
  - [x] Tighten .claude/settings.local.json command permissions
    - Removed bare python/pip entries, restricted to `Bash(uv run python:*)`
  - [x] Add CI/boot check for skill index staleness
    - .claude/scripts/aria-skill-index.py - implemented `--check` flag

  Polish (Pre-merge cleanup)
  - [x] Add @log_context("fitting") decorator to fitting dispatcher for observability consistency
  - [x] Use wrap_scalar_output() in fitting dispatcher for metadata consistency
