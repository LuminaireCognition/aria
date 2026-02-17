# Multi-LLM Service Support for Notifications

**Status:** Implemented
**Date:** 2026-02-16
**Scope:** `src/aria_esi/services/redisq/notifications/commentary.py`, `core/config.py`, notification profile YAML schema

## Problem Statement

The notification commentary system is hard-coded to Anthropic's Claude API. The coupling exists at three layers:

1. **Configuration:** `AriaSettings` only defines `ANTHROPIC_API_KEY` (via `validation_alias`). No other provider keys are recognized.
2. **Client instantiation:** `CommentaryGenerator._get_client()` imports and constructs `AsyncAnthropic` unconditionally.
3. **API call shape:** `generate_commentary()` calls `client.messages.create()` with Anthropic-specific parameters (`system`, `messages`, `max_tokens`).

Users who prefer (or already pay for) OpenAI or Google Gemini cannot use commentary without also maintaining an Anthropic account. Since commentary is an optional, low-volume feature (typically < $1/day), forcing a specific provider is an unnecessary friction point.

## Current Architecture

### Call Flow

```
NotificationManager._generate_commentary_for_profile()
  → create_commentary_generator(config=profile.commentary.to_dict())
    → CommentaryGenerator.__init__(api_key=config.get("api_key") or settings.anthropic_api_key)
      → _get_client() → AsyncAnthropic(api_key=...)
        → client.messages.create(model=..., system=..., messages=[...])
```

### Hardcoded Touchpoints

| File | Line(s) | Coupling |
|------|---------|----------|
| `core/config.py` | 221-225 | `anthropic_api_key` field with `ANTHROPIC_API_KEY` alias |
| `commentary.py` | 66 | `DEFAULT_MODEL = "claude-sonnet-4-5-20241022"` |
| `commentary.py` | 71-73 | Cost constants assume Haiku pricing |
| `commentary.py` | 392-405 | `_load_api_key()` reads only `settings.anthropic_api_key` |
| `commentary.py` | 424 | `from anthropic import AsyncAnthropic` |
| `commentary.py` | 426 | `AsyncAnthropic(api_key=...)` |
| `commentary.py` | 498-506 | `client.messages.create()` with Anthropic message schema |
| `config.py` (notifications) | 30 | `model: str = "claude-sonnet-4-5-20241022"` default |
| `redisq.py` | 369 | Warning message references `ANTHROPIC_API_KEY` by name |
| `prompts.py` | — | Prompt templates are provider-agnostic (no coupling) |
| `pyproject.toml` | 20 | `anthropic>=0.76.0` is a core dependency |

### Profile YAML (Current)

```yaml
commentary:
  enabled: true
  model: "claude-sonnet-4-5-20241022"
  persona: aria-mk4
  style: radio
  # ... no provider field
```

The `model` field implicitly assumes Anthropic model identifiers.

## Proposed Design

### Design Principles

1. **Profile-level provider selection** — each notification profile independently chooses its LLM provider.
2. **Provider as configuration, not code** — adding a new provider should require no code changes beyond a thin adapter.
3. **Backward-compatible defaults** — existing profiles without a `provider` field continue to use Anthropic.
4. **Single responsibility** — `CommentaryGenerator` delegates to a provider-specific client; it doesn't contain provider logic itself.

### YAML Schema Change (v4)

```yaml
commentary:
  enabled: true
  provider: anthropic          # NEW: "anthropic" | "openai" | "gemini"
  model: "claude-sonnet-4-5-20241022"
  timeout_ms: 3000
  max_tokens: 100
  warrant_threshold: 0.3
  cost_limit_daily_usd: 1.0
  style: radio
  persona: aria-mk4
```

- `provider` defaults to `"anthropic"` when omitted (backward compat).
- `model` retains its current meaning: the model identifier native to the selected provider.
- No other fields change semantics.

### Environment Variables

```bash
# .env — only the key for your chosen provider(s) is required
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AIza...
```

All three keys are optional. A key is only required if a profile references that provider.

### AriaSettings Extension

```python
# core/config.py — add alongside existing anthropic_api_key
openai_api_key: Optional[str] = Field(
    default=None,
    validation_alias="OPENAI_API_KEY",
    description="OpenAI API key for LLM commentary generation",
)

gemini_api_key: Optional[str] = Field(
    default=None,
    validation_alias="GEMINI_API_KEY",
    description="Google Gemini API key for LLM commentary generation",
)
```

### Provider Abstraction

Introduce a minimal `LLMProvider` protocol and three implementations:

```
src/aria_esi/services/redisq/notifications/
  llm_providers/
    __init__.py          # Provider registry + factory
    _protocol.py         # LLMProvider protocol
    _anthropic.py        # Anthropic adapter
    _openai.py           # OpenAI adapter
    _gemini.py           # Gemini adapter
```

#### Protocol

```python
# _protocol.py
from typing import Protocol, NamedTuple

class LLMResponse(NamedTuple):
    text: str
    input_tokens: int
    output_tokens: int

class LLMProvider(Protocol):
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        max_tokens: int,
        timeout_seconds: float,
    ) -> LLMResponse: ...

    async def close(self) -> None: ...
```

#### Anthropic Adapter (Extract from Current Code)

```python
# _anthropic.py
class AnthropicProvider:
    def __init__(self, api_key: str):
        from anthropic import AsyncAnthropic
        self._client = AsyncAnthropic(api_key=api_key)

    async def generate(self, system_prompt, user_prompt, model, max_tokens, timeout_seconds):
        response = await asyncio.wait_for(
            self._client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            ),
            timeout=timeout_seconds,
        )
        text = response.content[0].text.strip() if response.content else ""
        return LLMResponse(
            text=text,
            input_tokens=getattr(response.usage, "input_tokens", 500),
            output_tokens=getattr(response.usage, "output_tokens", 50),
        )

    async def close(self):
        self._client = None
```

#### OpenAI Adapter

```python
# _openai.py
class OpenAIProvider:
    def __init__(self, api_key: str):
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(api_key=api_key)

    async def generate(self, system_prompt, user_prompt, model, max_tokens, timeout_seconds):
        response = await asyncio.wait_for(
            self._client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            ),
            timeout=timeout_seconds,
        )
        text = response.choices[0].message.content.strip() if response.choices else ""
        usage = response.usage
        return LLMResponse(
            text=text,
            input_tokens=getattr(usage, "prompt_tokens", 500),
            output_tokens=getattr(usage, "completion_tokens", 50),
        )

    async def close(self):
        await self._client.close()
```

#### Gemini Adapter

```python
# _gemini.py
class GeminiProvider:
    def __init__(self, api_key: str):
        from google import genai
        self._client = genai.Client(api_key=api_key)

    async def generate(self, system_prompt, user_prompt, model, max_tokens, timeout_seconds):
        response = await asyncio.wait_for(
            self._client.aio.models.generate_content(
                model=model,
                contents=user_prompt,
                config={
                    "system_instruction": system_prompt,
                    "max_output_tokens": max_tokens,
                },
            ),
            timeout=timeout_seconds,
        )
        text = response.text.strip() if response.text else ""
        usage = response.usage_metadata
        return LLMResponse(
            text=text,
            input_tokens=getattr(usage, "prompt_token_count", 500),
            output_tokens=getattr(usage, "candidates_token_count", 50),
        )

    async def close(self):
        self._client = None
```

#### Provider Factory

```python
# __init__.py
PROVIDER_DEFAULTS = {
    "anthropic": {"model": "claude-sonnet-4-5-20241022", "key_field": "anthropic_api_key"},
    "openai":    {"model": "gpt-4o-mini",                "key_field": "openai_api_key"},
    "gemini":    {"model": "gemini-2.0-flash",            "key_field": "gemini_api_key"},
}

def create_provider(provider_name: str, api_key: str | None = None) -> LLMProvider:
    """Create an LLM provider by name. Falls back to AriaSettings for API key."""
    if not api_key:
        from ....core.config import get_settings
        settings = get_settings()
        key_field = PROVIDER_DEFAULTS[provider_name]["key_field"]
        api_key = getattr(settings, key_field)

    if not api_key:
        raise RuntimeError(f"{PROVIDER_DEFAULTS[provider_name]['key_field'].upper()} not configured")

    if provider_name == "anthropic":
        from ._anthropic import AnthropicProvider
        return AnthropicProvider(api_key)
    elif provider_name == "openai":
        from ._openai import OpenAIProvider
        return OpenAIProvider(api_key)
    elif provider_name == "gemini":
        from ._gemini import GeminiProvider
        return GeminiProvider(api_key)
    else:
        raise ValueError(f"Unknown provider: {provider_name}")
```

### CommentaryGenerator Changes

The generator becomes provider-agnostic:

```python
class CommentaryGenerator:
    def __init__(self, ..., provider: LLMProvider, ...):
        self._provider = provider
        # Remove: self._api_key, self._client

    async def generate_commentary(self, ...):
        # Replace client.messages.create() with:
        response = await asyncio.wait_for(
            self._provider.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=self._model,
                max_tokens=self._max_tokens,
                timeout_seconds=timeout_seconds,
            ),
            timeout=timeout_seconds,
        )
        text = response.text
        # ... rest of validation logic unchanged
```

### Factory Update

```python
def create_commentary_generator(persona_loader=None, config=None):
    config = config or {}
    provider_name = config.get("provider", "anthropic")
    provider = create_provider(provider_name, api_key=config.get("api_key"))

    # Default model per provider if not specified
    if "model" not in config:
        config["model"] = PROVIDER_DEFAULTS[provider_name]["model"]

    return CommentaryGenerator(
        provider=provider,
        # ... rest unchanged
    )
```

### Cost Tracking

Cost estimation constants become per-provider:

```python
COST_PER_1K_TOKENS = {
    "anthropic": {"input": 0.00025, "output": 0.00125},   # Haiku-class
    "openai":    {"input": 0.00015, "output": 0.00060},   # GPT-4o-mini
    "gemini":    {"input": 0.00010, "output": 0.00040},   # Flash
}
```

`CommentaryMetrics.daily_cost_estimate` would accept a `provider` parameter or store the provider name at construction time.

## Dependency Management

### Current State

`anthropic>=0.76.0` is a **core** dependency in `pyproject.toml`. This means it's installed even if commentary is never used.

### Proposed Approach: Optional Provider Packages

```toml
[project.dependencies]
# ... keep anthropic as core (MCP server also uses it)

[project.optional-dependencies]
openai = ["openai>=1.0.0"]
gemini = ["google-genai>=1.0.0"]
```

Each provider adapter uses a lazy import (`from openai import AsyncOpenAI` inside the method). If the package isn't installed, the factory raises a clear error:

```
RuntimeError: openai provider requires 'openai' package. Install with: uv pip install aria[openai]
```

`anthropic` remains a core dependency because the MCP server infrastructure already requires it.

## Validation Changes

### CommentaryConfig.validate()

Add provider validation:

```python
VALID_PROVIDERS = {"anthropic", "openai", "gemini"}

def validate(self) -> list[str]:
    errors = []
    if self.provider and self.provider not in VALID_PROVIDERS:
        errors.append(f"Unknown provider '{self.provider}'. Valid: {', '.join(sorted(VALID_PROVIDERS))}")
    # ... existing validations unchanged
```

### CLI Warning Update

```python
# redisq.py — current:
"Commentary disabled: ANTHROPIC_API_KEY not configured"

# proposed:
"Commentary disabled: {KEY_NAME} not configured for provider '{provider}'"
```

### Notification Validate Command

`aria-esi notifications validate` should verify that the API key for each profile's chosen provider is present in the environment, producing a warning (not error) if missing.

## Migration Path

### Phase 1: Provider Abstraction (Non-Breaking)

1. Create `llm_providers/` package with protocol and Anthropic adapter.
2. Refactor `CommentaryGenerator` to use provider protocol.
3. Add `provider` field to `CommentaryConfig` (defaults to `"anthropic"`).
4. All existing profiles continue working — zero changes required.
5. Add `openai_api_key` and `gemini_api_key` to `AriaSettings`.
6. Update `.env.example` with all three key placeholders.

### Phase 2: OpenAI + Gemini Adapters

1. Implement `OpenAIProvider` and `GeminiProvider`.
2. Add `openai` and `gemini` optional dependency groups.
3. Update `notifications validate` to check provider key availability.
4. Update documentation (`NOTIFICATION_PROFILES.md`, `NOTIFICATION_COOKBOOK.md`).

### Phase 3: Provider-Aware Defaults

1. Model default auto-selection based on provider.
2. Per-provider cost constants in `CommentaryMetrics`.
3. Consider provider-specific prompt tuning if quality divergence is observed.

## Schema Version

The addition of the `provider` field is backward-compatible (defaults to `"anthropic"`). Two options:

- **Option A:** No schema version bump. The field is purely additive with a safe default.
- **Option B:** Bump to schema version 4. Cleaner for validation but requires updating all templates.

Recommendation: **Option A** — no version bump. The `provider` field is optional and defaults preserve existing behavior.

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Prompt quality varies across providers | Medium | Token validation (`validate_preserved_tokens`) catches hallucinated game data regardless of provider. Monitor quality per-provider. |
| `NO_COMMENTARY` signal not respected by non-Anthropic models | Low | Signal is in the system prompt. All major models follow system instructions. Add integration tests per provider. |
| Token counting differences affect cost limits | Low | Cost tracking is approximate anyway (uses estimates). Per-provider constants are sufficient. |
| New SDK dependency conflicts | Low | Lazy imports + optional dependency groups. Providers only loaded when configured. |
| Users configure provider but forget to install package | Medium | Clear error message with install command at factory creation time. |

## Testing Strategy

1. **Unit tests:** Mock `LLMProvider.generate()` — provider-agnostic by design.
2. **Integration tests (tier 2):** One test per provider, gated by `{PROVIDER}_API_KEY` env var (same pattern as existing Anthropic tests).
3. **Validation tests:** Verify `CommentaryConfig.validate()` catches invalid providers.
4. **Backward compat:** Existing test suite passes without changes (Anthropic default).

## Files Changed

| File | Change |
|------|--------|
| `src/aria_esi/core/config.py` | Add `openai_api_key`, `gemini_api_key` fields |
| `src/aria_esi/services/redisq/notifications/llm_providers/__init__.py` | New — factory + registry |
| `src/aria_esi/services/redisq/notifications/llm_providers/_protocol.py` | New — `LLMProvider` protocol |
| `src/aria_esi/services/redisq/notifications/llm_providers/_anthropic.py` | New — extracted from commentary.py |
| `src/aria_esi/services/redisq/notifications/llm_providers/_openai.py` | New — OpenAI adapter |
| `src/aria_esi/services/redisq/notifications/llm_providers/_gemini.py` | New — Gemini adapter |
| `src/aria_esi/services/redisq/notifications/commentary.py` | Replace direct Anthropic usage with provider protocol |
| `src/aria_esi/services/redisq/notifications/config.py` | Add `provider` field to `CommentaryConfig` |
| `src/aria_esi/commands/redisq.py` | Update warning message, pass provider through |
| `pyproject.toml` | Add `openai`, `gemini` optional dependency groups |
| `.env.example` | Add `OPENAI_API_KEY`, `GEMINI_API_KEY` placeholders |
| `docs/NOTIFICATION_PROFILES.md` | Document provider field, multi-LLM setup |
| `tests/` | Provider-specific integration tests |

## Estimated Scope

- ~200 lines new code (providers package)
- ~50 lines modified (commentary.py refactor)
- ~30 lines config changes
- ~100 lines tests
- ~50 lines documentation updates
