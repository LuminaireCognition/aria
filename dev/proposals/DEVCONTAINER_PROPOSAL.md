# ARIA DevContainer Proposal

**Status:** PROPOSED (initial draft 2026-02-21)
**Owner:** DX
**Scope:** DevContainer configuration, Docker Desktop onboarding, MCP-in-container topology
**Related:** `dev/proposals/LINUX_VM_DOCKER_RUNTIME_PROPOSAL.md` (historical — Docker was deferred), `docs/FIRST_RUN.md`, `CLAUDE.md`, `.mcp.json`

---

## Executive Summary

Provide a `.devcontainer/` configuration so that users with Docker Desktop can clone the ARIA repo, open it in VS Code or Claude Code, and have a fully functional development environment — Python toolchain, game data, MCP server, and Claude Code — without installing anything on the host beyond Docker Desktop and an editor.

This follows the [Claude Code reference devcontainer](https://github.com/anthropics/claude-code/tree/main/.devcontainer) pattern and is the standard approach embraced by the broader developer community for reproducible environments.

**What ships:**
- `.devcontainer/devcontainer.json` — container settings, mounts, env vars.
- `.devcontainer/Dockerfile` — image based on the Claude Code reference, extended with Python 3.13, `uv`, and ARIA system dependencies.
- `.devcontainer/init-firewall.sh` — network allowlist (Claude API, ESI, Fuzzwork, etc.).
- `.devcontainer/post-create.sh` — one-time setup: `uv sync --dev`, game data seeding.
- `.devcontainer/post-start.sh` — per-start: validate caches, print status.
- Documentation updates to `docs/FIRST_RUN.md` and `README.md`.

**What does NOT ship:**
- `docker-compose.yml` — the devcontainer spec handles orchestration.
- Changes to the non-container workflow — `uv` on bare metal remains fully supported.
- Multi-container topology — MCP runs in-process, not as a sidecar.

---

## Problem Statement

1. **Onboarding friction.** New users must install `uv`, Python 3.11+, and run `aria-init` (which downloads ~100MB of game data). OS-level differences (macOS vs Linux, system Python versions, locale settings) cause support issues.

2. **No Docker path despite demand.** The prior proposal (`LINUX_VM_DOCKER_RUNTIME_PROPOSAL.md`) explicitly deferred Docker pending MCP topology and OAuth validation. Those concerns are addressable now — MCP runs in-process (no container-to-host networking needed), and OAuth uses a localhost callback that works with Docker Desktop's port forwarding.

3. **Claude Code has a reference devcontainer.** Anthropic ships a [production-ready devcontainer](https://code.claude.com/docs/en/devcontainer) with firewall, ZSH, and session persistence. ARIA should extend it rather than inventing a parallel container story.

4. **Developer-standard workflow.** Devcontainers are a [VS Code first-class feature](https://code.visualstudio.com/docs/devcontainers/containers), supported by GitHub Codespaces, JetBrains, and the broader ecosystem. Users expect to click "Reopen in Container" and start working.

---

## Goals

1. A user with Docker Desktop and VS Code (or Claude Code CLI) can go from `git clone` to a working ARIA session in one command.
2. The MCP server (`aria-universe`) works inside the container with zero extra configuration.
3. ESI OAuth flow works from inside the container (localhost port forwarding via Docker Desktop).
4. Game data seeding happens once at image build / first create, not on every container start.
5. `userdata/` persists across container rebuilds via a named volume.
6. The firewall allowlist is scoped to exactly the domains ARIA needs.
7. The bare-metal `uv` workflow is unaffected.

## Non-Goals

1. Multi-container orchestration (MCP as a sidecar, Redis, databases).
2. Production deployment — this is a development environment.
3. Replacing the native `uv` workflow.
4. Podman or other non-Docker runtimes (may work, not tested or supported).
5. GitHub Codespaces support (possible future extension, not validated).

---

## Design

### Container Architecture

```
┌─────────────────────────────────────────────────┐
│  DevContainer                                   │
│                                                 │
│  ┌───────────┐  ┌──────────────┐  ┌──────────┐ │
│  │ Claude    │  │ MCP Server   │  │ Python   │ │
│  │ Code CLI  │──│ (in-process) │  │ 3.13+uv  │ │
│  └───────────┘  └──────────────┘  └──────────┘ │
│        │                                        │
│  ┌─────┴─────────────────────────────────────┐  │
│  │  /workspace (bind mount from host)        │  │
│  │  ├── src/          (source code)          │  │
│  │  ├── .claude/      (hooks, skills)        │  │
│  │  ├── .mcp.json     (MCP config)           │  │
│  │  ├── reference/    (game data)            │  │
│  │  └── userdata/ ──► named volume           │  │
│  └───────────────────────────────────────────┘  │
│                                                 │
│  Firewall: allow Claude API, ESI, Fuzzwork,     │
│            zkillboard, GitHub, PyPI, uv          │
│            deny everything else                  │
└─────────────────────────────────────────────────┘
```

**Key decisions:**

- **MCP runs in-process.** The `.mcp.json` config uses `uv run python -m aria_esi.mcp.server` with `cwd: src`. This works identically inside the container — no container-to-host networking, no sidecar. Claude Code spawns the MCP server as a child process inside the same container.

- **`userdata/` is a named volume.** Credentials, pilot profiles, and config survive container rebuilds. The workspace itself is a bind mount (source code stays on the host filesystem for git operations), but `userdata/` is symlinked to a Docker volume so that `docker compose down && up` doesn't destroy pilot data.

- **Game data seeds at `postCreateCommand`.** SDE database (~60MB), fitting engine data, market seed, and sovereignty map download once when the container is first created. Subsequent starts skip seeding if caches are valid.

### File Layout

```
.devcontainer/
├── devcontainer.json      # Container configuration
├── Dockerfile             # Image definition
├── init-firewall.sh       # Network security rules
├── post-create.sh         # One-time setup (uv sync, game data seeding)
└── post-start.sh          # Per-start validation
```

### `devcontainer.json`

```jsonc
{
  "name": "ARIA - EVE Online Tactical Assistant",
  "build": {
    "dockerfile": "Dockerfile",
    "args": {
      "TZ": "${localEnv:TZ:UTC}",
      "PYTHON_VERSION": "3.13",
      "UV_VERSION": "latest",
      "CLAUDE_CODE_VERSION": "latest"
    }
  },
  "runArgs": [
    "--cap-add=NET_ADMIN",
    "--cap-add=NET_RAW"
  ],
  "customizations": {
    "vscode": {
      "extensions": [
        "anthropic.claude-code",
        "ms-python.python",
        "charliermarsh.ruff"
      ],
      "settings": {
        "python.defaultInterpreterPath": "/usr/local/bin/python",
        "editor.formatOnSave": true,
        "editor.defaultFormatter": "charliermarsh.ruff",
        "terminal.integrated.defaultProfile.linux": "zsh"
      }
    }
  },
  "remoteUser": "aria",
  "mounts": [
    // Persist command history across rebuilds
    "source=aria-bashhistory-${devcontainerId},target=/commandhistory,type=volume",
    // Persist Claude Code config (auth tokens, settings)
    "source=aria-claude-config-${devcontainerId},target=/home/aria/.claude,type=volume",
    // Persist userdata (pilot profiles, credentials, config)
    "source=aria-userdata-${devcontainerId},target=/workspace/userdata,type=volume"
  ],
  "containerEnv": {
    "DEVCONTAINER": "true",
    "CLAUDE_CONFIG_DIR": "/home/aria/.claude",
    "POWERLEVEL9K_DISABLE_GITSTATUS": "true",
    // Forward host Anthropic key if set (for Claude Code auth)
    "ANTHROPIC_API_KEY": "${localEnv:ANTHROPIC_API_KEY}"
  },
  "workspaceMount": "source=${localWorkspaceFolder},target=/workspace,type=bind,consistency=cached",
  "workspaceFolder": "/workspace",
  "postCreateCommand": ".devcontainer/post-create.sh",
  "postStartCommand": "sudo /usr/local/bin/init-firewall.sh && .devcontainer/post-start.sh",
  "waitFor": "postStartCommand",
  // OAuth callback port (ESI uses localhost:8421 by default)
  "forwardPorts": [8421]
}
```

**Notes on mount strategy:**

- `userdata/` as a named volume means it is **not visible on the host filesystem**. This is intentional — credentials should not leak onto the host. Users who want host-visible userdata can switch to a bind mount in their local override.
- The workspace bind mount uses `consistency=cached` for macOS Docker Desktop performance (avoids osxfs overhead on the large `src/` tree).
- `.claude` config volume persists Claude Code authentication tokens so users don't re-auth on every rebuild.

### `Dockerfile`

```dockerfile
# =============================================================================
# ARIA DevContainer
# Based on the Claude Code reference devcontainer pattern
# =============================================================================
FROM debian:bookworm-slim

ARG TZ=UTC
ENV TZ="$TZ"

ARG PYTHON_VERSION=3.13
ARG UV_VERSION=latest
ARG CLAUDE_CODE_VERSION=latest

# ── System packages ──────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Core tools
    less git procps sudo curl wget ca-certificates \
    # Shell
    zsh fzf man-db \
    # Firewall
    iptables ipset iproute2 dnsutils aggregate \
    # Build dependencies for Python packages (igraph, numpy)
    gcc g++ make pkg-config \
    libxml2-dev zlib1g-dev \
    # JSON processing (used by aria-init, boot hooks)
    jq \
    # Editors
    nano vim \
    # Node.js (for Claude Code CLI)
    nodejs npm \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# ── Claude Code CLI ──────────────────────────────────────────────────────────
RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}

# ── uv (Python package manager) ─────────────────────────────────────────────
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# ── Create non-root user ────────────────────────────────────────────────────
ARG USERNAME=aria
RUN groupadd --gid 1000 ${USERNAME} && \
    useradd --uid 1000 --gid 1000 -m -s /bin/zsh ${USERNAME} && \
    echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/${USERNAME} && \
    chmod 0440 /etc/sudoers.d/${USERNAME}

# ── uv for non-root user ────────────────────────────────────────────────────
RUN cp /root/.local/bin/uv /usr/local/bin/uv && \
    cp /root/.local/bin/uvx /usr/local/bin/uvx

# ── Persist bash/zsh history ─────────────────────────────────────────────────
RUN mkdir -p /commandhistory && \
    touch /commandhistory/.zsh_history && \
    chown -R ${USERNAME}:${USERNAME} /commandhistory

ENV HISTFILE=/commandhistory/.zsh_history

# ── Workspace and config directories ────────────────────────────────────────
RUN mkdir -p /workspace /home/${USERNAME}/.claude && \
    chown -R ${USERNAME}:${USERNAME} /workspace /home/${USERNAME}/.claude

# ── ZSH configuration ───────────────────────────────────────────────────────
USER ${USERNAME}

ARG ZSH_IN_DOCKER_VERSION=1.2.0
RUN sh -c "$(wget -O- https://github.com/deluan/zsh-in-docker/releases/download/v${ZSH_IN_DOCKER_VERSION}/zsh-in-docker.sh)" -- \
    -p git \
    -p fzf \
    -x

ENV SHELL=/bin/zsh
ENV EDITOR=nano
ENV VISUAL=nano
ENV DEVCONTAINER=true

WORKDIR /workspace

# ── Firewall script ─────────────────────────────────────────────────────────
COPY init-firewall.sh /usr/local/bin/
USER root
RUN chmod +x /usr/local/bin/init-firewall.sh && \
    echo "${USERNAME} ALL=(root) NOPASSWD: /usr/local/bin/init-firewall.sh" \
    > /etc/sudoers.d/${USERNAME}-firewall && \
    chmod 0440 /etc/sudoers.d/${USERNAME}-firewall

# ── Post-create/start scripts ───────────────────────────────────────────────
COPY post-create.sh post-start.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/post-create.sh /usr/local/bin/post-start.sh

USER ${USERNAME}
```

**Why Debian bookworm-slim instead of Node.js base?**

The Claude Code reference uses `node:20` as the base because Claude Code is a Node.js tool. ARIA is a Python project that also needs Node.js for Claude Code. Starting from `debian:bookworm-slim` gives us control over both runtimes without inheriting the Node.js image's opinionated layout. `nodejs` and `npm` are installed via apt — sufficient for installing the Claude Code CLI globally.

**Why not Python base?**

`uv` manages Python versions independently of the system Python. Starting from a Python base image would add a redundant interpreter. `uv` downloads and manages the exact Python version needed.

### `init-firewall.sh`

Adapted from the [Claude Code reference](https://github.com/anthropics/claude-code/blob/main/.devcontainer/init-firewall.sh), extended with ARIA-specific domains.

```bash
#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# ARIA DevContainer Firewall
# Restricts outbound access to only the services ARIA needs.
# Based on the Claude Code reference init-firewall.sh.
# =============================================================================

# ── Preserve Docker DNS before flushing ──────────────────────────────────────
DOCKER_DNS=$(grep nameserver /etc/resolv.conf | awk '{print $2}' | head -1)

# ── Create ipset for allowed destinations ────────────────────────────────────
ipset create allowed-domains hash:ip -exist
ipset flush allowed-domains

# ── Resolve and add allowed domains ──────────────────────────────────────────
ALLOWED_DOMAINS=(
    # Claude Code / Anthropic
    "api.anthropic.com"
    "statsig.anthropic.com"
    "sentry.io"

    # Package registries
    "registry.npmjs.org"
    "pypi.org"
    "files.pythonhosted.org"

    # uv (Astral)
    "astral.sh"
    "github.com"
    "objects.githubusercontent.com"
    "raw.githubusercontent.com"

    # EVE Online ESI
    "esi.evetech.net"
    "login.eveonline.com"
    "developers.eveonline.com"

    # EVE data sources
    "www.fuzzwork.co.uk"
    "market.fuzzwork.co.uk"
    "zkillboard.com"
    "zkillredisq.stream"

    # EVE community (mission data, wiki)
    "wiki.eveuniversity.org"

    # GitHub (for EOS data, git operations)
    "api.github.com"
    "codeload.github.com"

    # Discord (notification webhooks, optional)
    "discord.com"
    "discordapp.com"
)

for domain in "${ALLOWED_DOMAINS[@]}"; do
    for ip in $(dig +short "$domain" 2>/dev/null | grep -E '^[0-9]'); do
        ipset add allowed-domains "$ip" -exist
    done
done

# ── Flush existing rules ────────────────────────────────────────────────────
iptables -F OUTPUT
iptables -F INPUT
iptables -F FORWARD

# ── Allow loopback ──────────────────────────────────────────────────────────
iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT

# ── Allow established connections ───────────────────────────────────────────
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# ── Allow DNS ───────────────────────────────────────────────────────────────
iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
iptables -A OUTPUT -p tcp --dport 53 -j ACCEPT

# ── Allow Docker DNS specifically ───────────────────────────────────────────
if [ -n "$DOCKER_DNS" ]; then
    iptables -A OUTPUT -d "$DOCKER_DNS" -j ACCEPT
fi

# ── Allow SSH ───────────────────────────────────────────────────────────────
iptables -A OUTPUT -p tcp --dport 22 -j ACCEPT

# ── Allow host network (Docker Desktop bridge) ─────────────────────────────
HOST_NETWORK=$(ip route | grep default | awk '{print $3}')
if [ -n "$HOST_NETWORK" ]; then
    HOST_SUBNET=$(ip route | grep -v default | grep "$(ip route | grep default | awk '{print $5}')" | awk '{print $1}' | head -1)
    if [ -n "$HOST_SUBNET" ]; then
        iptables -A OUTPUT -d "$HOST_SUBNET" -j ACCEPT
    fi
fi

# ── Allow ipset members ─────────────────────────────────────────────────────
iptables -A OUTPUT -m set --match-set allowed-domains dst -j ACCEPT

# ── Add GitHub IP ranges (CIDR blocks, must come after flush) ──────────────
GITHUB_META=$(curl -s https://api.github.com/meta 2>/dev/null || true)
if [ -n "$GITHUB_META" ]; then
    for cidr in $(echo "$GITHUB_META" | jq -r '.git[],.web[],.api[]' 2>/dev/null | grep -v ':'); do
        # Use iptables directly for CIDR ranges (too many IPs to add to ipset)
        iptables -A OUTPUT -d "$cidr" -j ACCEPT 2>/dev/null || true
    done
fi

# ── Default deny ────────────────────────────────────────────────────────────
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT DROP

# ── Verification ────────────────────────────────────────────────────────────
echo "Firewall configured. Verifying..."

# Should fail
if curl -s --max-time 3 https://example.com >/dev/null 2>&1; then
    echo "WARNING: example.com is reachable (firewall may not be working)"
else
    echo "  ✓ example.com blocked (expected)"
fi

# Should succeed
if curl -s --max-time 5 https://esi.evetech.net/latest/status/ >/dev/null 2>&1; then
    echo "  ✓ ESI API reachable"
else
    echo "  ⚠ ESI API unreachable (may be temporary)"
fi

echo "Firewall setup complete."
```

### `post-create.sh`

Runs once when the container is first created. Handles all one-time setup.

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "═══════════════════════════════════════════════"
echo " ARIA DevContainer — First-time setup"
echo "═══════════════════════════════════════════════"

cd /workspace

# ── Install Python dependencies ─────────────────────────────────────────────
echo ""
echo "Installing Python dependencies..."
uv sync --dev

# ── Seed game data ───────────────────────────────────────────────────────────
echo ""
echo "Seeding game data (this runs once, ~100MB download)..."

echo "  → SDE database..."
uv run aria-esi sde-seed || echo "  ⚠ SDE seed failed (can retry with: uv run aria-esi sde-seed)"

echo "  → Fitting engine data..."
uv run aria-esi eos-seed || echo "  ⚠ EOS seed failed (can retry with: uv run aria-esi eos-seed)"

echo "  → Market prices..."
uv run aria-esi market-seed || echo "  ⚠ Market seed failed (can retry with: uv run aria-esi market-seed)"

echo "  → Sovereignty map..."
uv run aria-esi sov-update || echo "  ⚠ Sov update failed (can retry with: uv run aria-esi sov-update)"

# ── Ensure userdata structure ────────────────────────────────────────────────
echo ""
echo "Ensuring userdata directory structure..."
mkdir -p /workspace/userdata/pilots /workspace/userdata/credentials /workspace/userdata/sessions

# ── Hook permissions ─────────────────────────────────────────────────────────
chmod +x .claude/hooks/*.sh 2>/dev/null || true
chmod +x .claude/scripts/aria-boot-sync 2>/dev/null || true
chmod +x .claude/scripts/aria-refresh 2>/dev/null || true

echo ""
echo "═══════════════════════════════════════════════"
echo " Setup complete!"
echo ""
echo " Next steps:"
echo "   1. Run: ./aria-init          (configure your pilot)"
echo "   2. Run: claude               (start ARIA)"
echo ""
echo " Optional:"
echo "   • ESI setup: uv run python .claude/scripts/aria-oauth-setup.py"
echo "   • Retry seeds: ./aria-init --seed-only"
echo "═══════════════════════════════════════════════"
```

### `post-start.sh`

Runs on every container start (including restarts). Lightweight validation only.

```bash
#!/usr/bin/env bash
set -euo pipefail

cd /workspace

# Quick validation — do not re-download anything
if [ -f "userdata/config.json" ] && command -v uv &>/dev/null; then
    echo "ARIA environment ready."
else
    echo "ARIA environment ready (run ./aria-init to configure your pilot)."
fi
```

---

## MCP Server Topology

**No changes needed.** The existing `.mcp.json` works as-is inside the container:

```json
{
  "mcpServers": {
    "aria-universe": {
      "command": "uv",
      "args": ["run", "python", "-m", "aria_esi.mcp.server"],
      "cwd": "src"
    }
  }
}
```

Claude Code starts the MCP server as a child process. Both Claude Code and the MCP server run inside the same container. No cross-container networking, no port mapping, no sidecar orchestration.

This was the primary blocker identified in the prior proposal's Docker validation gates:

> **MCP topology validated:** End-to-end test proving MCP tool calls work through the container boundary.

The answer: there is no container boundary to cross. MCP is in-process.

---

## ESI OAuth Flow

ESI OAuth uses a localhost redirect (`http://localhost:8421/callback`). Docker Desktop forwards ports listed in `forwardPorts` to the container automatically.

Flow:
1. User runs `uv run python .claude/scripts/aria-oauth-setup.py` inside the container.
2. Script opens `https://login.eveonline.com/v2/oauth/authorize?...&redirect_uri=http://localhost:8421/callback` in the host browser.
3. After EVE SSO login, browser redirects to `http://localhost:8421/callback`.
4. Docker Desktop forwards port 8421 to the container.
5. The Python callback server inside the container receives the authorization code.
6. Token exchange completes. Credentials are written to `userdata/credentials/`.

**Validation needed:** The OAuth setup script (`aria-oauth-setup.py`) binds to `("localhost", port)` at lines 315/324 (where `DEFAULT_PORT = 8421` at line 76). In a container, `localhost` resolves to `127.0.0.1`, so Docker Desktop's port-forwarded connection will be refused. The fix: when `DEVCONTAINER=true`, bind to `("0.0.0.0", port)` instead. This is a one-line conditional.

This resolves the second Docker validation gate from the prior proposal:

> **OAuth flow validated:** ESI OAuth redirect works with container localhost port publishing.

---

## Firewall Allowlist

The devcontainer firewall uses a default-deny policy. Only these domains are reachable:

| Domain | Purpose |
|--------|---------|
| `api.anthropic.com` | Claude API (Claude Code) |
| `statsig.anthropic.com` | Claude Code telemetry |
| `sentry.io` | Claude Code error reporting |
| `registry.npmjs.org` | Claude Code install |
| `pypi.org`, `files.pythonhosted.org` | Python packages |
| `astral.sh` | uv installer |
| `github.com`, `api.github.com` | Git operations, EOS data |
| `esi.evetech.net` | EVE Online ESI API |
| `login.eveonline.com` | ESI OAuth |
| `developers.eveonline.com` | ESI app registration |
| `www.fuzzwork.co.uk`, `market.fuzzwork.co.uk` | SDE database, market data |
| `zkillboard.com` | Kill data |
| `zkillredisq.stream` | Real-time kill feed |
| `wiki.eveuniversity.org` | Mission data |
| `discord.com`, `discordapp.com` | Notification webhooks |

This resolves the third Docker validation gate:

> **Network hardening documented:** MCP binds to 127.0.0.1, docker-compose.yml uses 127.0.0.1:PORT:PORT.

Since MCP is in-process, there is no MCP port to expose. The firewall handles the rest.

---

## User Workflows

### Workflow 1: VS Code + Docker Desktop (recommended)

```
1. Install Docker Desktop
2. Install VS Code + "Dev Containers" extension
3. git clone <aria-repo> && code aria
4. VS Code prompt: "Reopen in Container" → click yes
5. Wait ~3 minutes (first time: image build + game data seeding)
6. Terminal opens inside container
7. Run: ./aria-init
8. Run: claude
```

### Workflow 2: Claude Code CLI + Docker Desktop

```
1. Install Docker Desktop
2. git clone <aria-repo> && cd aria
3. devcontainer up --workspace-folder .
4. devcontainer exec --workspace-folder . bash
5. Run: ./aria-init && claude
```

### Workflow 3: Native (unchanged)

```
1. Install uv
2. git clone <aria-repo> && cd aria
3. uv sync --dev
4. ./aria-init
5. claude
```

---

## Volume Strategy

| Mount | Type | Purpose | Survives rebuild? |
|-------|------|---------|-------------------|
| `/workspace` | Bind | Source code (host filesystem) | Yes (host) |
| `/workspace/userdata` | Named volume | Pilot profiles, credentials, config | Yes |
| `/home/aria/.claude` | Named volume | Claude Code auth, settings | Yes |
| `/commandhistory` | Named volume | Shell history | Yes |

**Why named volume for `userdata/` instead of bind mount?**

- **Security:** Credentials don't appear on the host filesystem.
- **Performance:** Named volumes are faster than bind mounts on macOS Docker Desktop.
- **Isolation:** Container and host don't share file permission semantics.

**Trade-off:** Users cannot browse `userdata/` from the host file explorer. They can access it via `docker volume inspect` or by opening a terminal inside the container. Users who prefer host visibility can edit the `mounts` array in `.devcontainer/devcontainer.json` (which is local to their clone and git-ignored for personal changes) or use Docker CLI volume overrides (`docker run -v`).

**Note on uv-managed Python:** Python installations managed by `uv` (stored in `~/.local/share/uv/python/`) live inside the container filesystem and are **not persisted** across rebuilds. Running `uv sync` on rebuild will re-download the Python interpreter (~30s on a fast connection). This is acceptable — `postCreateCommand` already runs `uv sync --dev` — but worth knowing if a rebuild feels slower than expected.

---

## What Changes in Existing Code

### Confirmed: No changes needed

| Component | Status | Rationale |
|-----------|--------|-----------|
| `.mcp.json` | Unchanged | `uv run` works identically in container |
| `CLAUDE.md` | Unchanged | Session init reads `userdata/` — same paths |
| `aria-init` | Unchanged | Bash script, works in Debian container |
| `.claude/hooks/` | Unchanged | Bash scripts, same paths |
| `.claude/scripts/` | Unchanged | Python scripts via `uv run`, same paths |
| `src/` | Unchanged | Python source, no platform-specific code |
| `pyproject.toml` | Unchanged | `uv sync` handles everything |

### Changes needed

| Component | Change |
|-----------|--------|
| `docs/FIRST_RUN.md` | Add "DevContainer" section alongside "Quick Setup" |
| `README.md` | Add devcontainer to the getting-started options |
| `.claude/scripts/aria-oauth-setup.py` | Bind callback server to `0.0.0.0` when `DEVCONTAINER=true` (currently binds `("localhost", port)` at lines 315/324, `DEFAULT_PORT = 8421` at line 76) |

---

## Test Plan

| Scenario | Preconditions | Expected Outcome |
|----------|---------------|-------------------|
| Fresh build, macOS Docker Desktop | Clean clone, no prior container | Image builds, `uv sync` succeeds, game data seeds, container starts |
| Fresh build, Linux Docker Engine | Clean clone, no prior container | Same as above |
| `aria-init` inside container | Container running, no prior pilot | Creates `userdata/pilots/0_{slug}/`, templates generated |
| `claude` session start | Pilot configured, MCP available | Boot hooks fire, MCP server starts, tools available |
| MCP tool call | Active session | `universe(action="systems", systems=["Jita"])` returns data |
| ESI OAuth flow | Docker Desktop port forwarding | Browser opens, callback received, credentials saved |
| Container rebuild | Existing userdata volume | Pilot profiles, credentials, config preserved |
| Container rebuild | Existing Claude config volume | Claude Code auth preserved, no re-login |
| Firewall: ESI reachable | Firewall active | `curl https://esi.evetech.net/latest/status/` succeeds |
| Firewall: blocked domain | Firewall active | `curl https://example.com` fails |
| Game data retry | SDE seed failed during post-create | `uv run aria-esi sde-seed` succeeds on manual retry |
| arm64 build (Apple Silicon) | Docker Desktop on Apple Silicon Mac | Image builds, `uv sync` completes, container starts and runs correctly |
| Volume mount vs .gitkeep | Named volume on `/workspace/userdata` | Named volume mount does not shadow repo's `userdata/.gitkeep` and `userdata/README.md`; `post-create.sh` creates expected subdirectories |
| Native workflow unaffected | No Docker, bare `uv` install | `uv sync && ./aria-init && claude` works as before |

---

## Rejected Alternatives

1. **Multi-container `docker-compose.yml` with MCP sidecar.** MCP is already in-process via `.mcp.json`. Splitting it into a sidecar adds networking complexity, startup ordering, and health checks — all for zero benefit since Claude Code already spawns MCP as a child process.

2. **Baking game data into the Docker image.** Game data changes with EVE patches (~monthly). Baking it into the image means rebuilding on every patch. Seeding at `postCreateCommand` downloads current data once and caches it in the workspace.

3. **`docker-compose.yml` for orchestration.** The devcontainer spec handles single-container orchestration natively. Adding compose adds a file, a concept, and a failure mode without enabling any capability we need.

4. **Podman support.** Devcontainers with Podman have known quirks (rootless networking, volume permissions). Supporting it adds test matrix surface for a user base that hasn't requested it. Can be added later if demanded.

5. **GitHub Codespaces as primary path.** Codespaces would work but adds latency (remote VM) and cost ($0.18/hr). A local devcontainer is free and faster. Codespaces compatibility can be validated as a future extension.

6. **Bind mount for `userdata/`.** Simpler but leaks credentials onto the host and suffers from Docker Desktop's bind mount performance penalty on macOS. Named volume is the right default; bind mount is available as a user override.

7. **Custom base image published to a registry.** Adds CI/CD complexity (image build pipeline, registry auth, version management). The Dockerfile builds in ~2 minutes from public base images. Not worth the infrastructure until rebuild time becomes a real user complaint.

---

## Risks, Mitigations, and Rollback

**Risk:** OAuth callback server binds `127.0.0.1`, not `0.0.0.0`, so port forwarding fails.
**Mitigation:** Check and fix in `aria-oauth-setup.py` before shipping. One-line change if needed.
**Rollback:** User runs OAuth on host or sets `DEVCONTAINER=false`.

**Risk:** Game data seeding fails during `postCreateCommand` (network issue, API down).
**Mitigation:** Each seed command has independent error handling with retry instructions. `post-create.sh` uses `|| echo "warning"` — container creation doesn't fail. User can retry individual seeds.
**Rollback:** `uv run aria-esi sde-seed` (etc.) at any time.

**Risk:** Named volume for `userdata/` confuses users who expect files on the host.
**Mitigation:** Document the volume strategy in `FIRST_RUN.md`. Provide instructions for switching to a bind mount.
**Rollback:** User edits the `mounts` array in `.devcontainer/devcontainer.json` to use a bind mount instead.

**Risk:** Firewall blocks a domain ARIA needs (new dependency, API endpoint change).
**Mitigation:** `init-firewall.sh` is in the repo — users can add domains and rebuild. Error messages from blocked connections are visible (connection refused, not silent timeout).
**Rollback:** Remove the firewall (`postStartCommand` → remove the sudo line). Or add the missing domain.

**Risk:** Docker Desktop performance on macOS with large bind mounts.
**Mitigation:** `consistency=cached` on the workspace mount. Named volumes for `userdata/` and `.claude/` (the most-accessed paths). The `src/` tree is ~11MB — well within acceptable bind mount performance.
**Rollback:** N/A — this is an optimization already applied.

---

## Implementation Plan

### Phase 1 — Core DevContainer (steps 1-5)

1. Create `.devcontainer/Dockerfile` with Debian base, Python via uv, Node.js, Claude Code CLI, ZSH, firewall tools.
2. Create `.devcontainer/devcontainer.json` with mounts, env vars, extensions, port forwarding.
3. Create `.devcontainer/init-firewall.sh` with ARIA-specific domain allowlist.
4. Create `.devcontainer/post-create.sh` with `uv sync` and game data seeding.
5. Create `.devcontainer/post-start.sh` with lightweight validation.

**Gate:** Build image, start container, verify `uv run aria-esi --version` works.

### Phase 2 — OAuth + MCP Validation (steps 6-8)

6. Verify MCP server starts inside container: `claude` session with tool calls.
7. Verify OAuth callback: check bind address in `aria-oauth-setup.py`, fix if needed.
8. Test ESI OAuth end-to-end with Docker Desktop port forwarding.

**Gate:** Full `claude` session with MCP tools and ESI auth working.

### Phase 3 — Documentation (steps 9-10)

9. Add devcontainer getting-started section to `docs/FIRST_RUN.md`.
10. Add devcontainer option to `README.md` getting-started block.

---

## Acceptance Checklist

**DevContainer files:**
- [ ] `.devcontainer/devcontainer.json` exists with correct mounts, env vars, and port forwarding.
- [ ] `.devcontainer/Dockerfile` builds successfully on both `amd64` and `arm64` (Apple Silicon).
- [ ] `.devcontainer/init-firewall.sh` blocks `example.com` and allows `esi.evetech.net`.
- [ ] `.devcontainer/post-create.sh` runs `uv sync --dev` and seeds game data.
- [ ] `.devcontainer/post-start.sh` runs without error on container restart.

**Functional:**
- [ ] `uv run aria-esi --version` works inside container.
- [ ] `./aria-init` completes successfully inside container.
- [ ] `claude` starts a session with MCP tools available (`universe`, `market`, `sde`, etc.).
- [ ] ESI OAuth flow completes with Docker Desktop port forwarding (port 8421).
- [ ] `userdata/` persists across `devcontainer rebuild`.
- [ ] Claude Code auth persists across `devcontainer rebuild`.
- [ ] Shell history persists across `devcontainer rebuild`.

**Security:**
- [ ] Firewall default policy is DROP for INPUT, FORWARD, OUTPUT.
- [ ] Only allowlisted domains are reachable from inside the container.
- [ ] Credentials in `userdata/credentials/` are not visible on the host filesystem (named volume).

**Non-regression:**
- [ ] Native `uv` workflow (`uv sync && ./aria-init && claude`) works on bare metal with no devcontainer files interfering.
- [ ] CI pipeline (`pytest -n auto`) passes with no changes.

**Documentation:**
- [ ] `docs/FIRST_RUN.md` includes DevContainer getting-started section.
- [ ] `README.md` lists DevContainer as a getting-started option.

---

## Proposed Decision

Approve the devcontainer as a first-class onboarding path alongside native `uv` setup:

- **DevContainer** — zero-install experience for users with Docker Desktop. Recommended for new users and Windows (via WSL2 + Docker Desktop).
- **Native `uv`** — remains the primary path for developers who prefer bare metal. No changes.

The devcontainer uses Claude Code's reference pattern (firewall, session persistence, VS Code integration) extended with ARIA's Python toolchain and game data seeding. MCP runs in-process — no multi-container orchestration needed.
