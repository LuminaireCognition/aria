# Migration Guide: Multi-LLM Provider Support

This guide covers migrating notification profiles from the single-provider (Anthropic-only) commentary system to the multi-LLM provider system. The migration is **fully backward compatible** -- existing profiles continue to work without changes.

## What Changed

The `commentary` section of notification profiles now supports three LLM providers:

| Provider | Environment Variable | Default Model |
|----------|---------------------|---------------|
| `anthropic` | `ANTHROPIC_API_KEY` | `claude-sonnet-4-5-20241022` |
| `openai` | `OPENAI_API_KEY` | `gpt-4o-mini` |
| `gemini` | `GEMINI_API_KEY` | `gemini-2.0-flash` |

A new `provider` field selects which backend to use. When omitted, it defaults to `"anthropic"`.

The default Anthropic model also changed from `claude-3-haiku-20240307` to `claude-sonnet-4-5-20241022`. Profiles that specify a model explicitly are unaffected.

## Do I Need to Change Anything?

**If you don't use commentary**: No changes needed. Profiles without a `commentary` section are unaffected.

**If you use commentary with Anthropic**: No changes required. Your profile will continue to use Anthropic with the same API key. The only behavioral difference is the default model upgrade (Haiku to Sonnet), which applies only if your profile omits the `model` field.

**If you want to switch providers**: Follow the steps below.

## Migration Steps

### Existing Profiles (No Action Required)

An existing commentary configuration like this:

```yaml
commentary:
  enabled: true
  model: "claude-3-haiku-20240307"
  timeout_ms: 3000
  warrant_threshold: 0.3
  cost_limit_daily_usd: 1.0
```

Continues to work identically. The system infers `provider: "anthropic"` and uses the explicitly specified model.

For clarity, you may optionally add the `provider` field:

```yaml
commentary:
  enabled: true
  provider: "anthropic"
  model: "claude-3-haiku-20240307"
  timeout_ms: 3000
  warrant_threshold: 0.3
  cost_limit_daily_usd: 1.0
```

### Switching to OpenAI

1. Get an API key from [platform.openai.com/api-keys](https://platform.openai.com/api-keys)

2. Add to your `.env` file:
   ```
   OPENAI_API_KEY=sk-your-key-here
   ```

3. Install the optional dependency:
   ```bash
   uv sync --extra openai
   ```

4. Update your profile YAML:
   ```yaml
   commentary:
     enabled: true
     provider: "openai"
     # model defaults to "gpt-4o-mini" when omitted
   ```

### Switching to Gemini

1. Get an API key from [aistudio.google.com/apikey](https://aistudio.google.com/apikey)

2. Add to your `.env` file:
   ```
   GEMINI_API_KEY=AIza-your-key-here
   ```

3. Install the optional dependency:
   ```bash
   uv sync --extra gemini
   ```

4. Update your profile YAML:
   ```yaml
   commentary:
     enabled: true
     provider: "gemini"
     # model defaults to "gemini-2.0-flash" when omitted
   ```

### Using Different Providers Per Profile

Each profile can use a different provider. This lets you compare providers or use cheaper models for high-volume profiles:

```yaml
# high-value-alerts.yaml
commentary:
  enabled: true
  provider: "anthropic"
  cost_limit_daily_usd: 2.0

# bulk-monitoring.yaml
commentary:
  enabled: true
  provider: "gemini"
  cost_limit_daily_usd: 0.50
```

All three API keys can coexist in `.env`. Only the keys for providers you actually use need to be set.

## Specifying a Model

When you set `provider`, the system uses that provider's default model unless you override it with `model`. The `model` value must be valid for the chosen provider:

```yaml
# Uses default anthropic model (claude-sonnet-4-5-20241022)
commentary:
  provider: "anthropic"

# Explicit model override
commentary:
  provider: "openai"
  model: "gpt-4o"
```

If you had an Anthropic model hardcoded (e.g., `claude-3-haiku-20240307`) and switch to OpenAI, remove or update the `model` field. An Anthropic model name sent to the OpenAI API will fail.

## Cost Tracking

Cost tracking now uses provider-specific token rates. The `cost_limit_daily_usd` field works the same way, but applies the correct per-provider pricing:

| Provider | Default Model | Approx. Cost/Commentary |
|----------|--------------|------------------------|
| Anthropic | Claude Sonnet | ~$0.00019 |
| OpenAI | GPT-4o-mini | ~$0.00011 |
| Gemini | Gemini 2.0 Flash | ~$0.00007 |

A profile's daily cost limit is tracked independently per profile, regardless of provider.

## Validation

Run validation to check for missing API keys or invalid provider names:

```bash
uv run aria-esi notifications validate
```

If a profile has commentary enabled but the required API key is not set, validation reports a warning:

```
[warning] Commentary provider 'openai' is enabled but OPENAI_API_KEY is not set in environment
```

This is a non-blocking warning. The profile still loads, but commentary generation will be skipped at runtime.

## Full Commentary Schema Reference

```yaml
commentary:
  enabled: false                          # Enable/disable commentary
  provider: "anthropic"                   # "anthropic", "openai", or "gemini"
  model: "claude-sonnet-4-5-20241022"     # Omit to use provider default
  timeout_ms: 3000                        # Max generation time (500-10000)
  max_tokens: 100                         # Max response tokens
  warrant_threshold: 0.3                  # Pattern significance threshold (0-1)
  cost_limit_daily_usd: 1.0              # Daily API cost limit
  style: "conversational"                 # "conversational" or "radio"
  max_chars: 120                          # Radio style character limit (50-500)
  persona: "paria"                        # Optional persona override
```

Only `enabled: true` and a valid API key are required to get started. All other fields have sensible defaults.
