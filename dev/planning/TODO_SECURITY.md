# Security TODO Tracker

Security hardening tasks for ARIA credential management and LLM safety.

**Status:** Credential/session security complete. Major security findings from SECURITY_000.md review resolved.

**See also:** `REMEDIATION_BACKLOG.md` for consolidated security findings from all reviews.

---

## Recent Completions (from SECURITY_000.md Review)

| Finding | Status | Notes |
|---------|--------|-------|
| SEC-001: Persona file path allowlisting | ✅ Completed | Path + extension validation |
| SEC-002: Skill overlay path validation | ✅ Completed | Overlay + redirect validation |
| SEC-003: Replace pickle serialization | ✅ Completed | Safe `.universe` format + checksums |
| CTX-001: Singleton reset functions | ✅ Completed | 33 resets in pytest fixture |

**Remaining:** SEC-004 (download checksums), SEC-005 (tool gating) - see REMEDIATION_BACKLOG.md

---

## Completed

| Task | Status | Commit |
|------|--------|--------|
| File permission hardening (0600 credentials) | ✅ Done | `a11e555` |
| Cross-platform keyring integration | ✅ Done | `a72a1bd` |
| ESI client retry logic (tenacity) | ✅ Done | `eb7fbdf` |
| Session context input sanitization | ✅ Done | `6e00b64` |
| Alias validation (injection prevention) | ✅ Done | `6e00b64` |
| Silent exception logging (`ARIA_DEBUG`) | ✅ Done | `d59c8c0` |

**Optional dependencies:**
- `pip install aria[secure]` - keyring credential storage
- `pip install aria[resilient]` - tenacity retry logic

---

## Remaining (Low Priority)

- [ ] **Tier III: Structured Project Format** - Replace markdown project files with JSON schema for stronger validation. Deferred until community demand.

---

## Security Model

```
Credential Storage:
┌─────────────────────────────────────────┐
│ Tier II: keyring → System keychain      │
│          (macOS Keychain, Linux Secret  │
│           Service, Windows Vault)       │
├─────────────────────────────────────────┤
│ Tier I: JSON file with 0600 permissions │
└─────────────────────────────────────────┘

Session Context Hardening:
- Tier I: Input sanitization (length, HTML, directives)
- Tier II: Alias validation (16 forbidden patterns)
```

---

*Last Updated: 2026-02-02*
