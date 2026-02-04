# Python Security Libraries Analysis

**Purpose:** Evaluate established Python libraries for addressing security issues in ARIA
**Date:** 2026-01-15
**References:** `TODO_SECURITY.md`, `PROJECT_REVIEW_001.md`, `PROMPT_INJECTION_HARDENING.md`

---

## Executive Summary

| Issue | Recommended Solution | Library | Add Dependency? |
|-------|---------------------|---------|-----------------|
| Credential Storage | System keychain integration | **keyring** | Yes (optional) |
| Rate Limiting | Exponential backoff | **tenacity** | Yes |
| Input Validation | Schema validation | **Pydantic** | Consider |
| HTML Sanitization | Tag stripping | **Bleach** | No (stdlib sufficient) |
| Prompt Injection | Custom validation | None (use OWASP patterns) | No |

**Key Finding:** For prompt injection specifically, there is **no silver-bullet library**. OWASP explicitly states: "given the stochastic nature of generative AI, fool-proof prevention methods remain unclear." The recommended approach is defense-in-depth using input validation, output monitoring, and architectural separation.

---

## 1. Credential Storage: `keyring`

### Library Profile

| Attribute | Value |
|-----------|-------|
| Package | [keyring](https://pypi.org/project/keyring/) |
| Version | 25.7.0 (Nov 2025) |
| Maintainer | Jason R. Coombs |
| License | MIT |
| Python | ≥3.9 |
| Status | Production/Stable, actively maintained |

### What It Does

Provides unified access to OS-native credential storage:

| Platform | Backend |
|----------|---------|
| macOS | Keychain |
| Windows | Credential Locker |
| Linux | Secret Service (GNOME Keyring) / KWallet |

### API

```python
import keyring

# Store credential
keyring.set_password("aria-eve-online", "2123984364", token_json)

# Retrieve credential
token_json = keyring.get_password("aria-eve-online", "2123984364")

# Delete credential
keyring.delete_password("aria-eve-online", "2123984364")
```

### Security Considerations

**macOS caveat:** Any Python script can access secrets created by the same Python executable without OS password prompt. Users must manually configure per-secret access control in Keychain Access.

**Headless systems:** Requires GNOME Keyring daemon and D-Bus session, which may not be available in Docker/CI environments.

### Recommendation for ARIA

**✅ RECOMMENDED** as Tier III (optional dependency)

- Aligns with `TODO_SECURITY.md` Tier III plan
- Well-established (used by major tools: `aws-cli`, `gcloud`, `gh`)
- Graceful fallback when unavailable
- Install via: `pip install aria[secure]` (optional extra)

### Implementation Pattern

```python
# Progressive enhancement pattern
try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False

def get_token(character_id: str) -> str:
    if KEYRING_AVAILABLE:
        token = keyring.get_password("aria-eve-online", character_id)
        if token:
            return token
    # Fall back to file-based storage
    return load_from_file(character_id)
```

---

## 2. Rate Limiting & Retry: `tenacity`

### Library Profile

| Attribute | Value |
|-----------|-------|
| Package | [tenacity](https://github.com/jd/tenacity) |
| Version | 9.1.2 (Nov 2025) |
| Maintainer | Julien Danjou |
| License | Apache 2.0 |
| Python | ≥3.9 |
| Status | Actively maintained, widely adopted |

### What It Does

Decorator-based retry logic with exponential backoff, jitter, and custom stop conditions.

### Relevance to PROJECT_REVIEW_001.md

From Section 2.5 (Network Security):
> "No rate limiting implementation. No retry logic with exponential backoff."

### API Examples

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import urllib.error

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((urllib.error.HTTPError, urllib.error.URLError))
)
def fetch_esi_data(endpoint: str) -> dict:
    # ESI request logic
    pass
```

### ESI-Specific Pattern

```python
from tenacity import retry, retry_if_result, wait_exponential

def is_rate_limited(response):
    """Check if we hit ESI rate limit."""
    return response.status == 429

@retry(
    retry=retry_if_result(is_rate_limited),
    wait=wait_exponential(multiplier=1, min=1, max=60)
)
def esi_request(url: str):
    # Handles 429 responses with backoff
    pass
```

### Recommendation for ARIA

**✅ RECOMMENDED**

- Directly addresses PROJECT_REVIEW_001.md findings
- Industry standard for Python retry logic
- Async-compatible (important for future improvements)
- Single dependency, pure Python

### Alternative: stdlib-only

If zero dependencies is paramount, implement minimal retry manually:

```python
import time
import random

def retry_with_backoff(func, max_attempts=3, base_delay=1):
    for attempt in range(max_attempts):
        try:
            return func()
        except Exception as e:
            if attempt == max_attempts - 1:
                raise
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            time.sleep(delay)
```

---

## 3. Input Validation: `Pydantic`

### Library Profile

| Attribute | Value |
|-----------|-------|
| Package | [pydantic](https://docs.pydantic.dev/) |
| Version | 2.10+ (2025) |
| Maintainer | Samuel Colvin / Pydantic team |
| License | MIT |
| Python | ≥3.8 |
| Status | Industry standard, Rust-powered backend |

### What It Does

Runtime data validation using Python type hints. Rust backend makes it extremely fast (5-15% overhead).

### Relevance to Prompt Injection

Pydantic is used by:
- OpenAI SDK
- Anthropic SDK
- LangChain
- LlamaIndex

For input sanitization, Pydantic can enforce schemas on parsed project data:

```python
from pydantic import BaseModel, Field, field_validator
import re

class ProjectMetadata(BaseModel):
    name: str = Field(max_length=100)
    target: str = Field(max_length=150)
    aliases: list[str] = Field(default_factory=list)

    @field_validator('name', 'target')
    @classmethod
    def sanitize_text(cls, v: str) -> str:
        # Strip HTML tags
        v = re.sub(r'<[^>]+>', '', v)
        # Strip template syntax
        v = re.sub(r'\{[^}]*\}', '', v)
        return v.strip()

    @field_validator('aliases')
    @classmethod
    def validate_aliases(cls, v: list[str]) -> list[str]:
        forbidden = re.compile(r'\b(ignore|override|system|admin)\b', re.I)
        return [a for a in v if not forbidden.search(a) and len(a) <= 50]
```

### Recommendation for ARIA

**⚠️ CONSIDER** - but may be overkill

**Pros:**
- Declarative validation is cleaner than manual regex
- Automatic error messages
- Industry standard for Python APIs

**Cons:**
- Large dependency (though well-maintained)
- ARIA's validation needs are simple enough for stdlib
- Adds complexity to zero-dependency philosophy

**Verdict:** Implement Tier I/II with stdlib first. If validation logic grows complex, consider Pydantic for Tier III (JSON project format).

---

## 4. HTML Sanitization: `Bleach`

### Library Profile

| Attribute | Value |
|-----------|-------|
| Package | [bleach](https://github.com/mozilla/bleach) |
| Version | 6.3.0 (Oct 2025) |
| Maintainer | Mozilla |
| License | Apache 2.0 |
| Status | Actively maintained, security-focused |

### What It Does

Allowlist-based HTML sanitization. Strips or escapes tags/attributes not in whitelist.

### Relevance to ARIA

For stripping HTML from project file fields:

```python
import bleach

def sanitize_field(value: str) -> str:
    # Strip ALL HTML tags
    return bleach.clean(value, tags=[], strip=True)
```

### Recommendation for ARIA

**❌ NOT RECOMMENDED** for ARIA's use case

**Reasoning:**
- ARIA only needs to strip tags, not sanitize for safe rendering
- Simple regex is sufficient: `re.sub(r'<[^>]+>', '', value)`
- Bleach is designed for allowing safe HTML subsets (web rendering)
- Adds dependency for minimal benefit

**stdlib alternative:**

```python
import re

def strip_html(value: str) -> str:
    return re.sub(r'<[^>]+>', '', value)
```

---

## 5. Prompt Injection Prevention

### Available Libraries

| Library | Status | Approach |
|---------|--------|----------|
| [Rebuff](https://github.com/protectai/rebuff) | **ARCHIVED** (May 2025) | LLM + VectorDB detection |
| [Pytector](https://github.com/MaxMLang/pytector) | Experimental | Pattern matching |
| [OpenAI Guardrails](https://openai.github.io/openai-guardrails-python/) | Active | OpenAI-specific |
| [Lakera Guard](https://www.lakera.ai/) | Commercial | API service |

### Why No Library is Recommended

From [OWASP LLM Prompt Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html):

> "Given the stochastic nature of generative AI, fool-proof prevention methods remain unclear."

> "Rate limiting only increases computational cost, content filters can be systematically defeated, safety training is proven bypassable with enough tries."

**Rebuff** (the most promising) was archived in May 2025 and explicitly states it "cannot provide 100% protection."

### Recommended Approach: Defense-in-Depth

Based on OWASP guidance, implement multiple layers:

1. **Input Validation** (what we're doing in Tier I)
   - Length limits
   - Pattern stripping (HTML, templates)
   - Forbidden keyword detection

2. **Structural Separation**
   - Clearly separate instructions from data in prompts
   - Mark untrusted content boundaries

3. **Output Monitoring** (future consideration)
   - Detect system prompt leakage
   - Flag unexpected response patterns

4. **Architectural Controls** (already in place)
   - Read-only ESI scopes
   - Capability boundaries in CLAUDE.md

### OWASP-Recommended Patterns

```python
# Dangerous pattern detection (from OWASP cheat sheet)
DANGEROUS_PATTERNS = [
    r'ignore\s+(all\s+)?previous\s+instructions?',
    r'disregard\s+(all\s+)?prior',
    r'forget\s+everything',
    r'you\s+are\s+now',
    r'new\s+instructions?:',
    r'system\s*:\s*',
]

def detect_injection_attempt(text: str) -> bool:
    text_lower = text.lower()
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, text_lower):
            return True
    return False
```

---

## 6. Summary: Recommended Actions

### Immediate (Tier I - No New Dependencies)

Implement custom sanitization using stdlib only:
- `re.sub()` for pattern stripping
- Length truncation
- Forbidden pattern detection

**Files to modify:** `aria-context-assembly.py`

### Short-term (Tier II - One New Dependency)

Add `tenacity` for ESI rate limiting:
```
pip install tenacity
```

**Files to modify:** `client.py`

### Long-term (Tier III - Optional Dependencies)

Add `keyring` as optional:
```
pip install aria[secure]  # installs keyring
```

**Files to modify:** `auth.py`, `aria-oauth-setup.py`, `aria-token-refresh.py`

---

## 7. Dependency Philosophy

ARIA's current zero-dependency approach is a **strength**:
- No supply chain attack surface
- Trivial installation
- No version conflicts

Recommended evolution:

```
aria-esi/
├── core/           # Zero dependencies (stdlib only)
├── commands/       # Zero dependencies
└── optional/
    ├── keyring_backend.py    # Requires: keyring
    └── resilient_client.py   # Requires: tenacity
```

Install profiles:
- `pip install aria` - Core functionality, zero dependencies
- `pip install aria[resilient]` - Adds tenacity for retry logic
- `pip install aria[secure]` - Adds keyring for credential storage
- `pip install aria[full]` - All optional dependencies

---

## Sources

- [OWASP LLM Prompt Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html)
- [OWASP Top 10 for LLMs 2025](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)
- [keyring on PyPI](https://pypi.org/project/keyring/)
- [tenacity on GitHub](https://github.com/jd/tenacity)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Bleach on GitHub](https://github.com/mozilla/bleach)
- [Rebuff (Archived)](https://github.com/protectai/rebuff)

---

_Last Updated: 2026-01-15_
