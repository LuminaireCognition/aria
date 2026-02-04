# Tactical Notification Style Enhancement Proposal

## Executive Summary

This proposal enhances the **existing notification commentary system** to support a high-fidelity "radio voice" style for real-time tactical alerts (killmails, gatecamp warnings) while **preserving factual data exactly**. Rather than introducing a new pipeline, this extends `commentary.py` and `prompts.py` with style presets that apply the linguistic patterns described in the research document.

Key outcomes:
- Radio-voice style for tactical Discord notifications (kills, camps, threats).
- Clear separation between **persona** (character identity) and **style** (formatting rules).
- Strict data preservation enforced at the prompt level.
- No changes to CLI, MCP, or skill outputs—these remain clean and precise.

---

## Problem Statement

The notification commentary system currently applies persona voice but lacks fine-grained control over **style**—the specific linguistic patterns (brevity, minimization, subject ellipsis) that create the "operator voice" described in the research document.

Current gaps:
- **Style is conflated with persona** — PARIA's identity is defined, but not the specific formatting rules for radio-style brevity.
- **No panic suppression** — High-severity events aren't linguistically minimized.
- **Inconsistent constraints** — Sentence/character limits are implicit, not configurable per style.

---

## Goals

- **Tactical notifications gain radio voice**: Killmails and threat alerts use operator-style brevity.
- **Persona and style are orthogonal**: Any persona (ARIA, PARIA) can speak in radio style or conversational style.
- **Data preservation is explicit**: Protected tokens are defined and enforced at the prompt level (optional post-gen validation can be added later).
- **Existing infrastructure is extended**: No new modules; changes to `commentary.py`, `prompts.py`, `persona.py`.

## Non-Goals

- Styling CLI output, MCP responses, or skill outputs.
- Introducing a new `comms/` module or pipeline.
- Deterministic lexicon replacement (EVE terminology is too precise for regex substitution).
- Applying style to structured outputs (tables, embeds, code blocks).

---

## Current State

| Component | Location | Purpose |
|-----------|----------|---------|
| Commentary generation | `notifications/commentary.py` | LLM-generated text for Discord |
| Prompt construction | `notifications/prompts.py` | System/user prompts for LLM |
| Voice summaries | `notifications/persona.py` | Condensed persona context |
| Persona definitions | `personas/*/voice.md` | Full persona identity |

The existing system works. This proposal adds **style presets** as a layer within it.

Notes from current implementation:
- System prompt currently constrains commentary to 2 sentences and under 200 characters.
  - **Migration required:** These constraints should be removed from the base system prompt and moved into `STYLE_GUIDANCE` to avoid conflicts with style-specific rules (e.g., conversational allows 3 sentences).
- There is no post-generation validator; only the NO_COMMENTARY signal is checked.
  - **Enhancement:** This proposal adds `validate_preserved_tokens()` for defense-in-depth.
- Commentary configuration supports `max_tokens`, not `max_chars`.

---

## Proposed Design

### Conceptual Model: Persona vs. Style

```
PERSONA (who is speaking)          STYLE (how they speak)
├── ARIA                           ├── conversational (default)
├── PARIA                          ├── radio (tactical brevity)
├── PARIA-S (Serpentis)            └── formal (future option)
└── ...

Any persona can use any style. Style is selected per-channel or per-intent.
```

**Note on Two-Layer Model:** The research document distinguishes between a *Procedural Layer* (zero redundancy, adjectives stripped—pure data) and a *Cultural Layer* (folksy grammar, litotes, minimization—the "Yeager" voice). This proposal implicitly handles both through the persona + style combination:

- **Procedural** aspects are enforced via `DATA_PRESERVATION_RULES` (exact system names, ISK values, timestamps)
- **Cultural** aspects are guided via `STYLE_GUIDANCE` (minimization, subject ellipsis, confidence inversion)

EVE notifications are primarily Cultural Layer output—we're adding color to factual data, not generating pure tactical brevity codes. If future use cases require explicit layer switching (e.g., pure coordinate callouts vs. status commentary), this model can be extended.

### Type Definitions

Add shared types to avoid circular imports between `commentary.py` and `prompts.py`:

```python
# In notifications/types.py (NEW FILE)

from enum import Enum

class CommentaryStyle(Enum):
    """Style presets for commentary generation."""
    CONVERSATIONAL = "conversational"  # Default: natural prose
    RADIO = "radio"                    # Tactical brevity, operator cadence


class StressLevel(Enum):
    """
    Stress level for style conditioning.

    CRITICAL: Stress level has a COUNTERINTUITIVE relationship to output tone.
    This implements "Yeager voice" panic suppression (see research document §2.2.2):

    - HIGH stress → *calmer* linguistic output (minimization engaged, no fillers)
    - LOW stress  → personality can breathe (fillers permitted, more expressive)

    The operator who says "taking a little rattle" while their engine is on fire
    is demonstrating supreme confidence. Panic in the voice destroys that signal.
    """
    LOW = "low"        # Routine intel, market updates → expressive, fillers OK
    MODERATE = "moderate"  # Watchlist activity, system changes → balanced
    HIGH = "high"      # Active combat, gatecamps, losses → calm understatement
```

Both `commentary.py` and `prompts.py` import from `types.py`, breaking the import cycle.

### Style-Specific Prompt Guidance

Add to `notifications/prompts.py`:

```python
from notifications.types import CommentaryStyle

# IMPORTANT: Style guidance is the SINGLE SOURCE OF TRUTH for length constraints.
# The base system prompt should NOT include sentence/character limits—those are
# defined here per-style. This avoids conflicts between base constraints and
# style-specific rules.

STYLE_GUIDANCE = {
    CommentaryStyle.CONVERSATIONAL: """
STYLE: Conversational
- Natural prose, 1-3 sentences
- No hard character limit (respect max_chars if provided, otherwise unlimited)
- Can use complete sentences with subjects
- Personality appropriate to persona
""",

    CommentaryStyle.RADIO: """
STYLE: Radio operator voice
- Maximum 2 sentences, respect max_chars as soft guidance (default 200, but shorter is better)
- Ideal output is 30-80 characters; 200 is the upper bound, not a target
- Subject ellipsis: start with verbs or nouns, rarely use "I" or "We"
- Minimize danger language: "taking a little heat" not "under heavy fire"
- Confidence through understatement: severity inversely correlates with alarm
- Plain text only (no markdown, no code blocks)
- No Hollywood tropes or real-world prowords ("Over and out", "10-4")
- Avoid real-world military brevity codes unless already present in input/persona vocabulary
- Stress-aware fillers: thoughtful pauses (...) ONLY when stress_level is LOW or MODERATE
- No fillers or hedging when stress_level is HIGH

EXAMPLES:
- Watchlist kill (conversational): "Hostile pilot destroyed a Thorax in Tama."
- Watchlist kill (radio): "Watchlist hit. Thorax down, Tama."
- Gatecamp detected (conversational): "Warning: A gatecamp has been detected in Amamake with multiple hostiles."
- Gatecamp detected (radio): "Camp on Amamake gate. Eyes open."
- High-value loss (conversational): "A friendly pilot lost a ship worth 2,145,900,000 ISK."
- High-value loss (radio): "Friendly down, 2.1B ISK. Stings."
""",
}
```

### Data Preservation (Prompt-Level)

Rather than a separate guard module, enforce preservation in the prompt:

```python
# In prompts.py

DATA_PRESERVATION_RULES = """
DATA PRESERVATION (CRITICAL):
- When referencing game data, use EXACT values from the notification:
  - System names: verbatim (no variations)
  - Ship names: verbatim (no synonyms like "Vexor" → "cruiser")
  - ISK values: use the abbreviated format shown (e.g., "2.1B"), do not expand or re-round
- EVE terminology (warp, pod, bubble, gate, cyno) must NOT be translated
- NEVER invent or guess: kill IDs, timestamps, pilot names, or ship counts
- Add tactical INSIGHT, not summaries of what's already shown
- If you have nothing new to add, output NO_COMMENTARY
"""
```

**Design Decision: ISK Format Alignment**

The notification system uses abbreviated ISK values throughout for readability:
- Discord embed: `format_isk()` → "2.1B ISK"
- LLM notification_text: `format_isk()` → "2.1B ISK"
- Commentary output: abbreviated form preserved

This ensures consistency between what users see in the embed and what the LLM references. The `notification_text` passed to the LLM uses the same `format_isk()` helper as the embed formatter.

**Design Decision: Plain Text Output**

The "plain text only" rule applies to **LLM output only**, not the final Discord rendering. The formatter intentionally wraps commentary in Discord markdown (`*italics*`, `---` separator) for visual distinction. The LLM must not emit markdown because:
1. It could conflict with the formatter's wrapping
2. Raw markdown characters could mis-render if not properly escaped

Prompt clarification: *"Plain text only—no markdown (the system will style your output)"*

### Data Preservation Validator (Post-Generation)

Prompt-level enforcement alone relies on model compliance. A lightweight post-generation validator provides defense-in-depth:

```python
# In commentary.py

def validate_preserved_tokens(output: str, context: PatternContext) -> bool:
    """
    Check that critical tokens from context appear unchanged in output.

    This is a whitelist check: if a protected value isn't present verbatim,
    reject the output. The validator is cheap (string containment) and
    deterministic, providing a hard guarantee that prompt guidance alone
    cannot offer.

    Args:
        output: The generated commentary text
        context: Pattern context containing protected tokens

    Returns:
        True if all protected tokens are preserved, False otherwise
    """
    for token in context.protected_tokens:
        if token not in output:
            return False
    return True


async def generate_commentary(self, ...) -> str | None:
    # ... generation logic ...

    commentary = response.content

    # Validate protected tokens before returning
    if not validate_preserved_tokens(commentary, pattern_context):
        logger.warning(
            "Commentary failed token validation, returning NO_COMMENTARY",
            pattern=pattern_context.pattern_type,
        )
        return None

    return commentary
```

**Protected tokens** are extracted from `PatternContext.patterns[].context` dict and include:
- System names (e.g., "Amamake", "Tama") via `context["system_name"]`
- Ship names (e.g., "Thorax", "Vexor Navy Issue") via `context["ship_name"]`
- Faction names (e.g., "Serpentis") via `context["faction_display"]`

**Note:** ISK values are intentionally excluded from token validation because:
1. The abbreviated format ("2.1B") involves lossy rounding
2. Comparing "2.1B" against the original value requires tolerance logic
3. Prompt-based preservation is sufficient for numeric values

The validator runs after generation but before returning, ensuring corrupted output never reaches Discord.

### Stress Level Context

Stress level is derived from pattern severity metadata rather than an exhaustive pattern-type map. This ensures new pattern types automatically receive correct stress handling based on their declared severity:

```python
# In commentary.py

from notifications.types import StressLevel

# Severity → stress level mapping (derived from pattern metadata)
SEVERITY_STRESS_MAP = {
    "critical": StressLevel.HIGH,    # Losses, active camps → calm understatement
    "warning": StressLevel.MODERATE, # Watchlist activity → balanced
    "info": StressLevel.LOW,         # Routine intel → expressive, fillers OK
}


def get_stress_level(pattern: PatternContext) -> StressLevel:
    """
    Derive stress level from pattern severity metadata.

    This approach ensures new high-severity pattern types automatically
    receive panic suppression without requiring map maintenance.
    """
    return SEVERITY_STRESS_MAP.get(pattern.severity, StressLevel.MODERATE)
```

The prompt builder includes stress level:
```
Current stress level: {stress_level.value}
```

### Integration Point

Modify `CommentaryGenerator` to accept style, max_chars, and pass stress context:

```python
# In commentary.py

from notifications.types import CommentaryStyle, StressLevel

async def generate_commentary(
    self,
    pattern_context: PatternContext,
    notification_text: str,
    style: CommentaryStyle | None = None,  # Override instance default
    max_chars: int | None = None,  # Override instance default (soft upper bound)
    timeout_ms: int | None = None,
) -> str | None:
    # ... existing logic ...

    # Use instance defaults with per-call overrides
    effective_style = style or self._style
    effective_max_chars = max_chars if max_chars is not None else self._max_chars

    # Derive stress level from pattern severity
    stress_level = get_stress_level(pattern_context)

    # Build prompts with style guidance
    system_prompt = build_system_prompt(
        voice_summary,
        style=effective_style,
        stress_level=stress_level,
        max_chars=effective_max_chars,  # Thread through to prompt builder
    )
```

**Design Decision: Per-Call Overrides**

Both `style` and `max_chars` support per-call overrides while defaulting to instance configuration. This allows:
- Different intents (watchlist vs. gatecamp) to use different character limits
- Testing with explicit values without reconfiguring the generator

### Profile Configuration

Notification profiles gain a `style` field:

```yaml
# userdata/notifications/tactical-intel.yaml
name: tactical-intel
commentary:
  enabled: true
  model: claude-3-haiku-20240307
  style: radio      # NEW: style preset
  max_chars: 200    # NEW: optional soft upper bound (default 200 for radio)
  persona: paria-s
```

**Note:** `max_chars` is soft guidance, not a hard truncation. The LLM is instructed to aim for 30-80 characters when possible, with 200 as the upper bound for complex threat warnings. Shorter is always better for radio style.

---

## Style Rules Reference

Based on the research document, the radio style applies these transformations:

| Rule | Example (Standard) | Example (Radio) |
|------|-------------------|-----------------|
| Subject ellipsis | "I see the target" | "Eyes on target." |
| Minimization | "Critical damage!" | "Taking a little rattle." |
| Brevity | "The ship was destroyed by..." | "Ship down." |
| Confidence inversion | High severity → high alarm | High severity → calm understatement |

**Important**: These are **LLM guidance**, not regex replacements. The LLM applies them contextually while preserving EVE terminology.

---

## What This Proposal Does NOT Do

1. **No lexicon replacement layer** — EVE terms like "warp," "pod," "bubble" have precise meanings. We don't substitute them with military equivalents.

2. **No CLI/MCP styling** — These outputs are for programmatic integration and debugging. They remain clean, direct, and unstyled.

3. **No new module** — All changes are within the existing `notifications/` package.

4. **No deterministic transformations** — Style is applied by the LLM, guided by prompts, not by regex or rule engines.

---

## Implementation Plan

### Phase 1: Style Infrastructure
- Create `notifications/types.py` with `CommentaryStyle` and `StressLevel` enums
- Add `SEVERITY_STRESS_MAP` and `get_stress_level()` to `commentary.py`
- Add `STYLE_GUIDANCE` dict with few-shot examples to `prompts.py`
- Add `DATA_PRESERVATION_RULES` (including EVE terminology rule) to prompts
- Add prompt constraints: plain text only, no Hollywood prowords, avoid non-EVE brevity codes
- Modify `build_system_prompt()` to accept style, stress_level, and max_chars parameters
- **Migration:** Remove hardcoded 2-sentence/200-char constraint from base system prompt

### Phase 2: Profile Integration
- Add `style` field to notification profile schema
- Add optional `max_chars` field (soft upper bound; default: 200 for radio, unlimited for conversational)
- Wire style and max_chars through `CommentaryGenerator`
- Default to `conversational` for backward compatibility

### Phase 3: Validation & Hardening
- Add `validate_preserved_tokens()` post-generation validator
- Extract protected tokens from `PatternContext` (system names, ISK values, ship names)
- Add golden tests comparing radio vs. conversational output
- Verify data preservation with adversarial test cases
- Load test to confirm no latency regression

---

## Configuration Example

```yaml
# Notification profile with radio style
name: lowsec-tactical
display_name: "Lowsec Tactical Intel"
enabled: true

commentary:
  enabled: true
  model: claude-3-haiku-20240307
  style: radio
  max_chars: 250    # Slightly higher for complex threat warnings
  persona: paria
  timeout_ms: 3000
  max_tokens: 100

triggers:
  watchlist_activity: true
  gatecamp_detected: true
  high_value_threshold: 100000000
```

---

## Testing Strategy

- **Unit tests**: `CommentaryStyle` enum, `StressLevel` enum, prompt construction with style
- **Golden tests**: Same killmail → different styles → verify characteristics
- **Sentiment inversion tests**: High-severity events (losses, camps) should produce *calmer* radio output than low-severity events; verify inverse correlation
- **Stress-level tests**: Verify fillers (ellipsis) appear only in LOW stress contexts, never in HIGH
- **Preservation tests**: Inject protected tokens, verify they survive unchanged
- **Validator tests**: Test `validate_preserved_tokens()` with missing/corrupted tokens
- **EVE terminology tests**: Verify "pod", "warp", "bubble" are not translated to military terms
- **Regression tests**: Existing notification profiles produce identical output
- **Stress derivation tests**: Verify new patterns with `severity: critical` automatically get `StressLevel.HIGH`

### Deterministic Golden Test Plan
- **Replay-first fixtures**: Store golden responses keyed by `model + system_prompt + user_prompt` hash; tests only read fixtures by default.
- **Fake LLM client**: Inject a stubbed client in tests that returns fixture text and usage data (no network calls).
- **Record mode (opt-in)**: Add a `--record` or env flag to call the real LLM once and write/update fixtures; CI runs replay-only.
- **Prompt snapshot tests**: Assert system/user prompt text includes style constraints (no markdown, no prowords, stress-level rule).
- **Trait checks**: Validate output properties (sentence count, max_chars, no forbidden tokens) independently of exact text to reduce churn.

---

## Design Decisions (Implementation Notes)

The following decisions were made during implementation to resolve ambiguities in the original proposal:

### 1. ISK Value Format: Abbreviated

**Decision:** Use abbreviated ISK format ("2.1B") consistently across embed, notification_text, and commentary.

**Rationale:**
- Users see abbreviated values in Discord embeds via `format_isk()`
- Commentary referencing "2,145,900,000 ISK" next to "2.1B ISK" would be jarring
- The `notification_text` passed to the LLM now uses `format_isk()` to match the embed

**Impact:**
- `manager.py`: notification_text uses `format_isk(kill.total_value)`
- `prompts.py`: DATA_PRESERVATION_RULES updated to "use the abbreviated format shown"

### 2. Protected Tokens: Names Only (No ISK)

**Decision:** Exclude ISK values from token validation; protect only names from `pattern.context`.

**Rationale:**
- Abbreviated ISK format involves lossy rounding (2,145,900,000 → "2.1B")
- Exact string matching is impractical for abbreviated values
- Prompt-based preservation is sufficient for numeric values
- `ProcessedKill` doesn't have resolved names; they come from `pattern.context`

**Impact:**
- `extract_protected_tokens()` extracts from `pattern.context["system_name"]`, `["ship_name"]`, `["faction_display"]`
- Removed dead code checking for nonexistent `ProcessedKill.solar_system_name`

### 3. Plain Text Rule: LLM Output Only

**Decision:** "Plain text only" applies to LLM output, not the final Discord rendering.

**Rationale:**
- The formatter intentionally wraps commentary in `*italics*` and `---` separator
- This is a presentation layer applied *after* LLM generation
- The LLM must not emit markdown to avoid conflicts with formatter wrapping

**Impact:**
- Prompt clarified: "Plain text only—no markdown (the system will style your output)"

### 4. Per-Call Parameter Overrides

**Decision:** `max_chars` supports per-call overrides (matching `style` behavior).

**Rationale:**
- Allows different intents to use different character limits
- Enables testing with explicit values without reconfiguring generator

**Impact:**
- `generate_commentary()` accepts optional `max_chars` parameter
- Falls back to instance default when not provided

### 5. Resolved Names Passed Explicitly

**Decision:** System and ship names are passed explicitly to `extract_protected_tokens()` and `validate_preserved_tokens()` rather than expecting patterns to populate them.

**Rationale:**
- Names are resolved at the manager level via SDE lookup
- Pattern detection happens earlier in the pipeline without name resolution
- Passing names explicitly ensures token validation works regardless of pattern type
- Avoids requiring all pattern types to populate `system_name`/`ship_name` in their context

**Impact:**
- `extract_protected_tokens(context, system_name, ship_name)` accepts optional resolved names
- `validate_preserved_tokens(output, context, system_name, ship_name)` passes names through
- `generate_commentary()` accepts `system_name` and `ship_name` for validation
- Manager passes resolved names through the commentary generation chain

### 6. notification_text Matches Embed Format

**Decision:** The `notification_text` passed to the LLM uses identical fallback format as the embed.

**Rationale:**
- Avoids mismatch between "Ship" (LLM context) and "Ship 17740" (embed)
- Ensures the LLM sees exactly what users see
- Supports "use EXACT values from the notification" prompt guidance

**Impact:**
- `notification_text` uses `ship_name or f"Ship {kill.victim_ship_type_id}"`
- `notification_text` uses `system_name or f"System {kill.solar_system_id}"`
- Pod kills use "Capsule" consistently

### 6a. Display Strings Passed to Validation

**Decision:** The manager passes `system_display` and `ship_display` (the computed display strings) to token validation, not the raw resolved names.

**Rationale:**
- Ensures fallback strings like "System 30002813" are also protected
- The validator protects what users actually see, not intermediate values

**Impact:**
- Manager passes `system_display` (e.g., "Tama" or "System 30002813") to validation
- Manager passes `ship_display` (e.g., "Vexor" or "Ship 17740" or "Capsule") to validation

### 6b. Validator Catches Case Corruption Only

**Accepted Limitation:** The validator catches **case corruption** (same letters, different case) but not **value corruption** (completely different strings).

**Rationale:**
- The validator checks: "if token is referenced case-insensitively but not exact, fail"
- If the LLM outputs a completely different value, it's not a case mismatch
- The LLM might legitimately choose not to reference a value at all
- Adding value similarity checking would require fuzzy matching complexity

**Example:**
- "Tama" → "tama": **Caught** (case corruption)
- "Tama" → "Amamake": **Not caught** (different value, not referenced)
- "System 30002813" → "system 30002813": **Caught** (case corruption)
- "System 30002813" → "System 30002812": **Not caught** (different ID, not the same token)

### 7. ISK Preservation is Prompt-Only

**Decision:** ISK value preservation relies on prompt guidance only; no post-generation validation.

**Rationale:**
- Abbreviated format ("2.1B") involves lossy rounding from exact values
- Validating "2.1B" against "2,145,900,000" requires tolerance logic
- The complexity/benefit ratio doesn't justify a validator
- Prompt guidance has proven sufficient in practice

**Accepted Risk:** If the LLM outputs a different abbreviated value (e.g., "2B" instead of "2.1B"), it will pass validation. This is acceptable because:
- ISK values are supplementary context, not safety-critical
- Major corruption (wrong order of magnitude) is rare with good prompt guidance
- Defense-in-depth is maintained for names (the more critical data)

### 8. Global "No Markdown" Rule

**Decision:** Both conversational and radio styles include "plain text only—no markdown" guidance.

**Rationale:**
- All commentary is wrapped in Discord markdown by the formatter
- Conversational output with markdown could double-style or break formatting
- Consistent guidance across styles reduces prompt complexity

**Impact:**
- `STYLE_GUIDANCE[CONVERSATIONAL]` now includes the plain text rule

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| LLM ignores style guidance | Few-shot examples in prompt; model selection |
| Data corruption | Defense-in-depth: prompt rules + `validate_preserved_tokens()` post-gen check |
| Style drift across personas | Style guidance is persona-independent; persona voice is separate |
| Increased prompt size | Style guidance is ~150 tokens with examples; negligible impact |
| Filler misuse in combat | Stress level conditioning; explicit HIGH stress rules |
| New pattern types miss stress handling | Stress derived from severity metadata, not exhaustive pattern map |
| Circular imports | Enums in shared `types.py` module, imported by both `commentary.py` and `prompts.py` |

---

## Summary

This proposal extends the existing notification commentary system with **style presets** that enable radio-voice tactical alerts. By keeping style orthogonal to persona and limiting scope to Discord notifications, we gain the benefits of the research document's linguistic analysis without over-engineering.

**Reference:** The linguistic foundations for this proposal are documented in `dev/proposals/EmulatingRadioVoiceinTextLLMs.md`, which provides the research basis for sentiment inversion, stress-aware output, and the "Yeager voice" panic suppression mechanism.

Changes are confined to:
- `notifications/types.py` (new) — `CommentaryStyle` and `StressLevel` enums
- `notifications/commentary.py` — Stress derivation, parameter threading, post-gen validator
- `notifications/prompts.py` — Style guidance with few-shot examples, preservation rules
- Notification profile schema — `style` and `max_chars` fields

CLI, MCP, and skill outputs are unchanged. EVE terminology is preserved. The persona system continues to define *who* is speaking; style presets define *how* they speak in tactical contexts.
