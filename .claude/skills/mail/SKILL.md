---
name: mail
description: Read EVE mail headers and bodies. View inbox, filter unread, and read specific messages.
category: operations
triggers:
  - "/mail"
  - "my mail"
  - "check mail"
  - "EVE mail"
  - "inbox"
requires_pilot: true
esi_scopes:
  - esi-mail.read_mail.v1
argument-hint: "[--unread|--id N]"
allowed-tools: [Read, Grep, Glob, Bash, "mcp__aria-universe__pilot"]
injected_prerequisites:
  - .claude/skills/_shared/esi-error-handling.md
---

# ARIA EVE Mail Reader

Display query timestamp — mail data is volatile.

## Implementation

```python
# List mail
pilot(action="mail_list", unread_only=True, limit=50)

# Read specific mail
pilot(action="mail_read", mail_id=987654321)
```

CLI fallback: `uv run aria-esi mail`, `uv run aria-esi mail-read <id>`

> **HALLUCINATION GUARD:** Every mail subject, sender, body, and timestamp MUST come from a `pilot()` call in this session. NEVER fabricate mail content.

## Response Format

Present mail in a structured display including:
- **Header:** Query timestamp and unread count
- **Mail list:** Subject, sender, date, read/unread status, and mail ID
- **Mail body:** Sender, subject, date header followed by body text with original formatting preserved

Adapt format to RP level: markdown table for `off`, box-drawing for `on`/`full`.

## Error Handling

| Condition | Action |
|-----------|--------|
| ESI not configured | Direct to `uv run python .claude/scripts/aria-oauth-setup.py`, suggest EVE client (Alt+I) as alternative |
| Missing scope | Direct to setup script, specify `esi-mail.read_mail.v1` scope |

## Contextual Suggestions

| Context | Suggest |
|---------|---------|
| Has unread mail | "Read full messages with `mail-read <id>`" |
| Corp mail | "Check corp announcements for important info" |
| Trade mail | "Verify contract terms before accepting" |

## Cross-References

| Related Command | Use Case |
|-----------------|----------|
| `/contracts` | Check if trade mail relates to a contract |
| `/pilot` | Look up sender info |

## Behavior Notes

- **Brevity:** Default to table format unless RP mode requests formatted boxes
- **Sorting:** Most recent first
- **Unread First:** Show unread messages before read ones
- **Timestamps:** Use relative time for recent, full date for older
- **Body Formatting:** Preserve original line breaks and spacing
- **HTML:** Strip any HTML tags from mail body

## Reference: ESI Error Handling (injected)
<!-- prerequisite: .claude/skills/_shared/esi-error-handling.md -->
!`cat .claude/skills/_shared/esi-error-handling.md`
