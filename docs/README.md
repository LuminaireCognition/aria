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
→ Or use [DevContainer](DEPLOYMENT.md#option-a-devcontainer-zero-host-setup) for zero-install setup

**Setting up ESI?**
→ [ESI.md](ESI.md) (authentication guide)

**Multiple characters?**
→ [MULTI_PILOT_ARCHITECTURE.md](MULTI_PILOT_ARCHITECTURE.md)

**Want roleplay mode?**
→ [PERSONA_LOADING.md](PERSONA_LOADING.md)

**Want to understand how it works?**
→ [ARCHITECTURE.md](ARCHITECTURE.md) (system diagram & data flow)

**Building or contributing?**
→ [Developer docs](../dev/docs/README.md)

Setup paths:
- From terminal: `./aria-init`
- In Claude Code: `/setup`

---

## Getting Started

| Document | Description |
|----------|-------------|
| [TLDR.md](TLDR.md) | Quick reference - install, configure, run |
| [FIRST_RUN.md](FIRST_RUN.md) | Detailed first-time setup guide |
| [COMMANDS.md](COMMANDS.md) | All 48 slash commands with examples |
| [ESI.md](ESI.md) | EVE SSO/ESI integration (optional) |
| [FAQ.md](FAQ.md) | Frequently asked questions |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Common issues and solutions |

## User Guides

| Document | Description |
|----------|-------------|
| [MULTI_PILOT_ARCHITECTURE.md](MULTI_PILOT_ARCHITECTURE.md) | Managing multiple EVE characters |
| [CONTEXT_AWARE_TOPOLOGY.md](CONTEXT_AWARE_TOPOLOGY.md) | Home systems, routes, geographic context |

## Features

| Document | Description |
|----------|-------------|
| [FEATURES.md](FEATURES.md) | Feature showcase — all capabilities at a glance |
| [NOTIFICATION_PROFILES.md](NOTIFICATION_PROFILES.md) | Discord notifications setup and configuration |
| [NOTIFICATION_COOKBOOK.md](NOTIFICATION_COOKBOOK.md) | Advanced recipes, examples, and troubleshooting |
| [ADHOC_MARKETS.md](ADHOC_MARKETS.md) | Custom market scope definitions |
| [REALTIME_CONFIGURATION.md](REALTIME_CONFIGURATION.md) | Real-time intel configuration |

## Roleplay System

| Document | Description |
|----------|-------------|
| [PERSONA_LOADING.md](PERSONA_LOADING.md) | How faction personas work |

## Reference

| Document | Description |
|----------|-------------|
| [ROUTE_SCENARIOS.md](ROUTE_SCENARIOS.md) | Route planning examples |

## System Overview

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System components and data flow |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Installation and deployment methods |

For developer documentation (testing, typing, MCP internals, AI runtime instructions), see [dev/docs/](../dev/docs/README.md).

## Security

| Document | Description |
|----------|-------------|
| [../SECURITY.md](../SECURITY.md) | Security policy and implemented controls |
| [../dev/reviews/archive/SECURITY_000.md](../dev/reviews/archive/SECURITY_000.md) | Full security review with mitigation status |

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
