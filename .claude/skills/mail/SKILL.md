---
name: mail
description: Read EVE mail headers and bodies. View inbox, filter unread, and read specific messages.
model: haiku
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
---

# ARIA EVE Mail Reader

## Purpose

Query the capsuleer's EVE mail to display inbox and read messages. Essential for staying informed about corp communications, trade negotiations, and game events.

## ESI Write Capability

Unlike most ESI endpoints, mail has **write capability**:
- **POST /mail/** - Send new mail
- **POST /mail/labels/** - Create labels

**Current Implementation:** Read-only. Send capability documented but not implemented due to abuse potential.

## CRITICAL: Data Volatility

Mail data is **volatile** - changes frequently with new messages:

1. **Display query timestamp** - mail can arrive any moment
2. **Low cache time (30 seconds)** - reflects near-real-time state
3. **Read status updates** - marking mail read is an in-game action

## Trigger Phrases

- `/mail`
- "my mail"
- "check mail"
- "EVE mail"
- "inbox"
- "unread mail"
- "read mail"
- "show messages"

## ESI Requirement

**Requires:** `esi-mail.read_mail.v1` scope

If scope is not authorized:
```
EVE mail access requires ESI authentication.

To enable: uv run python .claude/scripts/aria-oauth-setup.py
Select "esi-mail.read_mail.v1" during scope selection.
```

## ESI Availability Check (CRITICAL)

**BEFORE making any ESI queries**, check the session hook output for ESI status:

```json
"esi": {"status": "UNAVAILABLE"}
```

### If ESI is UNAVAILABLE:

Mail has no local fallback. Respond immediately:

```
═══════════════════════════════════════════════════════════════════
ARIA COMM RELAY - UNAVAILABLE
───────────────────────────────────────────────────────────────────
GalNet mail access is currently unavailable.

Check your mail in the EVE client:
  • Press Alt+I or click EVE Mail in Neocom
  • Mobile: Use EVE Portal app

The connection usually recovers automatically.
═══════════════════════════════════════════════════════════════════
```

**DO NOT** attempt mail queries - they will timeout.

### If ESI is AVAILABLE:

Proceed with mail queries.

## Implementation

Run the ESI wrapper commands:
```bash
PYTHONPATH=.claude/scripts uv run python -m aria_esi mail [options]
PYTHONPATH=.claude/scripts uv run python -m aria_esi mail-read <mail_id>
PYTHONPATH=.claude/scripts uv run python -m aria_esi mail-labels
```

### Commands

| Command | Description |
|---------|-------------|
| `mail` | List mail headers (most recent) |
| `mail-read <id>` | Read specific mail body |
| `mail-labels` | List mail labels |

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--unread` | Show only unread mail | - |
| `--limit N` | Limit results | 50 |

### JSON Response Structure (mail)

```json
{
  "query_timestamp": "2026-01-15T14:30:00Z",
  "volatility": "volatile",
  "character_id": 2119654321,
  "summary": {
    "total_shown": 10,
    "unread_count": 3
  },
  "mail": [
    {
      "mail_id": 987654321,
      "from_id": 12345678,
      "from_name": "Corp CEO",
      "subject": "Fleet Op Tonight",
      "timestamp": "2026-01-15T12:00:00Z",
      "is_read": false,
      "labels": [1, 4],
      "recipients": [
        {"recipient_id": 2119654321, "recipient_type": "character"}
      ]
    }
  ]
}
```

### JSON Response Structure (mail-read)

```json
{
  "query_timestamp": "2026-01-15T14:30:00Z",
  "volatility": "stable",
  "mail": {
    "mail_id": 987654321,
    "from_id": 12345678,
    "from_name": "Corp CEO",
    "subject": "Fleet Op Tonight",
    "timestamp": "2026-01-15T12:00:00Z",
    "body": "Hey capsuleers!\n\nWe're running a fleet tonight at 20:00 EVE time.\nForm up in Jita, doctrine is armor cruisers.\n\nSee you there!\n- CEO",
    "labels": [1],
    "recipients": [
      {"recipient_id": 2119654321, "recipient_type": "character"}
    ]
  }
}
```

### Empty Response

```json
{
  "query_timestamp": "2026-01-15T14:30:00Z",
  "volatility": "volatile",
  "character_id": 2119654321,
  "summary": {
    "total_shown": 0,
    "unread_count": 0
  },
  "mail": [],
  "message": "No mail found"
}
```

## Recipient Types

| Type | Description |
|------|-------------|
| `character` | Individual player |
| `corporation` | Corp mail |
| `alliance` | Alliance mail |
| `mailing_list` | Mailing list |

## Response Formats

### Standard Display (rp_level: off or lite)

```markdown
## EVE Mail
*Query: 14:30 UTC | 3 unread*

| Subject | From | Date | Status |
|---------|------|------|--------|
| Fleet Op Tonight | Corp CEO | Jan 15 12:00 | Unread |
| Welcome to Corp | HR Bot | Jan 14 08:00 | Read |
| Trade Offer | Trader001 | Jan 13 15:30 | Read |

*Use `mail-read <id>` to read full message.*
```

### Formatted Version (rp_level: moderate or full)

```
═══════════════════════════════════════════════════════════════════
ARIA COMM RELAY - EVE MAIL
───────────────────────────────────────────────────────────────────
GalNet Sync: 14:30 UTC | Unread: 3
───────────────────────────────────────────────────────────────────
INBOX
───────────────────────────────────────────────────────────────────
  [UNREAD] Fleet Op Tonight
  From: Corp CEO | Jan 15 12:00 UTC
  ID: 987654321

  Welcome to Corp
  From: HR Bot | Jan 14 08:00 UTC
  ID: 987654320

  Trade Offer
  From: Trader001 | Jan 13 15:30 UTC
  ID: 987654319
───────────────────────────────────────────────────────────────────
Use `mail-read <id>` to read full message.
═══════════════════════════════════════════════════════════════════
```

### Mail Body Display

```
═══════════════════════════════════════════════════════════════════
ARIA COMM RELAY - MESSAGE
───────────────────────────────────────────────────────────────────
From:    Corp CEO
Subject: Fleet Op Tonight
Date:    Jan 15 2026, 12:00 UTC
───────────────────────────────────────────────────────────────────

Hey capsuleers!

We're running a fleet tonight at 20:00 EVE time.
Form up in Jita, doctrine is armor cruisers.

See you there!
- CEO

═══════════════════════════════════════════════════════════════════
```

## Error Handling

### ESI Not Configured

```
═══════════════════════════════════════════════════════════════════
ARIA COMM RELAY
───────────────────────────────────────────────────────────────────
EVE mail access requires ESI authentication.

Check your mail in the EVE client (Alt+I).

OPTIONAL: Enable access here (~5 min setup)
  uv run python .claude/scripts/aria-oauth-setup.py
═══════════════════════════════════════════════════════════════════
```

### Missing Scope

```
═══════════════════════════════════════════════════════════════════
ARIA COMM RELAY - SCOPE NOT AUTHORIZED
───────────────────────────────────────────────────────────────────
ESI is configured but mail scope is missing.

To enable:
  uv run python .claude/scripts/aria-oauth-setup.py

Select "esi-mail.read_mail.v1" during setup.
═══════════════════════════════════════════════════════════════════
```

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
