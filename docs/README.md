# ARIA Documentation Index

Quick navigation for ARIA documentation.

<p><strong>Quick Links:</strong>
<a href="./TLDR.md">TL;DR</a> |
<a href="./FIRST_RUN.md">First Run</a> |
<a href="./ESI.md">ESI Setup</a> |
<a href="./FAQ.md">FAQ</a> |
<a href="../README.md">Project README</a>
</p>

## Where to Start

**New to ARIA?**
→ Read [TLDR.md](TLDR.md) (1-page overview)
→ Then [FIRST_RUN.md](FIRST_RUN.md) (setup guide)

**Setting up ESI?**
→ [ESI.md](ESI.md) (authentication guide)

**Multiple characters?**
→ [MULTI_PILOT_ARCHITECTURE.md](MULTI_PILOT_ARCHITECTURE.md)

**Want roleplay mode?**
→ [PERSONA_LOADING.md](PERSONA_LOADING.md)

**Building or contributing?**
→ [PYTHON_ENVIRONMENT.md](PYTHON_ENVIRONMENT.md)

Setup paths:
- From terminal: `./aria-init`
- In Claude Code: `/setup`

---

## Getting Started

| Document | Description |
|----------|-------------|
| [TLDR.md](TLDR.md) | Quick reference - install, configure, run |
| [FIRST_RUN.md](FIRST_RUN.md) | Detailed first-time setup guide |
| [ESI.md](ESI.md) | EVE SSO/ESI integration (optional) |
| [FAQ.md](FAQ.md) | Frequently asked questions |

## User Guides

| Document | Description |
|----------|-------------|
| [DATA_FILES.md](DATA_FILES.md) | Where your data lives, what to update |
| [MULTI_PILOT_ARCHITECTURE.md](MULTI_PILOT_ARCHITECTURE.md) | Managing multiple EVE characters |
| [CONTEXT_AWARE_TOPOLOGY.md](CONTEXT_AWARE_TOPOLOGY.md) | Home systems, routes, geographic context |

## Features

| Document | Description |
|----------|-------------|
| [NOTIFICATION_PROFILES.md](NOTIFICATION_PROFILES.md) | Discord notifications (profiles, recipes, commentary) |
| [ADHOC_MARKETS.md](ADHOC_MARKETS.md) | Custom market scope definitions |
| [REALTIME_CONFIGURATION.md](REALTIME_CONFIGURATION.md) | Real-time intel configuration |

## Roleplay System

| Document | Description |
|----------|-------------|
| [PERSONA_LOADING.md](PERSONA_LOADING.md) | How faction personas work |
| [EXPERIENCE_ADAPTATION.md](EXPERIENCE_ADAPTATION.md) | Adjusting to player experience level |

## Reference

| Document | Description |
|----------|-------------|
| [DATA_SOURCES.md](DATA_SOURCES.md) | External data sources (wiki, DOTLAN, etc.) |
| [DATA_VERIFICATION.md](DATA_VERIFICATION.md) | How ARIA verifies game data |
| [PROTOCOLS.md](PROTOCOLS.md) | Communication and data protocols |
| [ROUTE_SCENARIOS.md](ROUTE_SCENARIOS.md) | Route planning examples |

## Development

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System components and data flow |
| [PYTHON_ENVIRONMENT.md](PYTHON_ENVIRONMENT.md) | Python/uv setup for contributors |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Installation and deployment methods |
| [TESTING.md](TESTING.md) | Test tiers, coverage, and running tests |
| [TYPING_ROADMAP.md](TYPING_ROADMAP.md) | Type checking roadmap and status |
| [COMMAND_SUGGESTIONS.md](COMMAND_SUGGESTIONS.md) | How ARIA suggests commands |
| [SESSION_CONTEXT.md](SESSION_CONTEXT.md) | Session initialization internals |
| [CONTEXT_POLICY.md](CONTEXT_POLICY.md) | Context management policies |

## Security

| Document | Description |
|----------|-------------|
| [../SECURITY.md](../SECURITY.md) | Security policy and implemented controls |
| [../dev/reviews/SECURITY_000.md](../dev/reviews/SECURITY_000.md) | Full security review with mitigation status |

**Key security features:**
- Path validation prevents traversal attacks on persona files
- Data integrity checks verify external data before loading
- Safe serialization avoids pickle deserialization risks
- Untrusted data delimiters protect against prompt injection

## Additional Resources

- **[../README.md](../README.md)** - Main project README
- **[../CONTRIBUTING.md](../CONTRIBUTING.md)** - Contribution guidelines
- **[../examples/](../examples/)** - Example pilot configurations
- **[../personas/](../personas/)** - Faction persona definitions
