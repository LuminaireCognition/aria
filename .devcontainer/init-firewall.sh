#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# ARIA DevContainer Firewall
# Restricts outbound access to only the services ARIA needs.
# Based on the Claude Code reference init-firewall.sh.
# =============================================================================

# -- Preserve Docker DNS before flushing --------------------------------------
DOCKER_DNS=$(grep nameserver /etc/resolv.conf | awk '{print $2}' | head -1)

# -- Create ipset for allowed destinations ------------------------------------
ipset create allowed-domains hash:ip -exist
ipset flush allowed-domains

# -- Resolve and add allowed domains ------------------------------------------
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

# -- Flush existing rules ----------------------------------------------------
iptables -F OUTPUT
iptables -F INPUT
iptables -F FORWARD

# -- Allow loopback -----------------------------------------------------------
iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT

# -- Allow established connections --------------------------------------------
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# -- Allow DNS ----------------------------------------------------------------
iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
iptables -A OUTPUT -p tcp --dport 53 -j ACCEPT

# -- Allow Docker DNS specifically --------------------------------------------
if [ -n "$DOCKER_DNS" ]; then
    iptables -A OUTPUT -d "$DOCKER_DNS" -j ACCEPT
fi

# -- Allow SSH ----------------------------------------------------------------
iptables -A OUTPUT -p tcp --dport 22 -j ACCEPT

# -- Allow host network (Docker Desktop bridge) ------------------------------
HOST_NETWORK=$(ip route | grep default | awk '{print $3}')
if [ -n "$HOST_NETWORK" ]; then
    HOST_SUBNET=$(ip route | grep -v default | grep "$(ip route | grep default | awk '{print $5}')" | awk '{print $1}' | head -1)
    if [ -n "$HOST_SUBNET" ]; then
        iptables -A OUTPUT -d "$HOST_SUBNET" -j ACCEPT
    fi
fi

# -- Allow ipset members -----------------------------------------------------
iptables -A OUTPUT -m set --match-set allowed-domains dst -j ACCEPT

# -- Add GitHub IP ranges (CIDR blocks, must come after flush) ----------------
GITHUB_META=$(curl -s https://api.github.com/meta 2>/dev/null || true)
if [ -n "$GITHUB_META" ]; then
    for cidr in $(echo "$GITHUB_META" | jq -r '.git[],.web[],.api[]' 2>/dev/null | grep -v ':'); do
        # Use iptables directly for CIDR ranges (too many IPs to add to ipset)
        iptables -A OUTPUT -d "$cidr" -j ACCEPT 2>/dev/null || true
    done
fi

# -- Default deny -------------------------------------------------------------
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT DROP

# -- Verification -------------------------------------------------------------
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
