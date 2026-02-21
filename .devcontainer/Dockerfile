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

# -- System packages ----------------------------------------------------------
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

# -- Claude Code CLI ----------------------------------------------------------
RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}

# -- uv (Python package manager) ---------------------------------------------
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# -- Create non-root user ----------------------------------------------------
ARG USERNAME=aria
RUN groupadd --gid 1000 ${USERNAME} && \
    useradd --uid 1000 --gid 1000 -m -s /bin/zsh ${USERNAME} && \
    echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/${USERNAME} && \
    chmod 0440 /etc/sudoers.d/${USERNAME}

# -- uv for non-root user ----------------------------------------------------
RUN cp /root/.local/bin/uv /usr/local/bin/uv && \
    cp /root/.local/bin/uvx /usr/local/bin/uvx

# -- Persist bash/zsh history -------------------------------------------------
RUN mkdir -p /commandhistory && \
    touch /commandhistory/.zsh_history && \
    chown -R ${USERNAME}:${USERNAME} /commandhistory

ENV HISTFILE=/commandhistory/.zsh_history

# -- Workspace and config directories ----------------------------------------
RUN mkdir -p /workspace /home/${USERNAME}/.claude && \
    chown -R ${USERNAME}:${USERNAME} /workspace /home/${USERNAME}/.claude

# -- ZSH configuration -------------------------------------------------------
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

# -- Firewall script ---------------------------------------------------------
COPY init-firewall.sh /usr/local/bin/
USER root
RUN chmod +x /usr/local/bin/init-firewall.sh && \
    echo "${USERNAME} ALL=(root) NOPASSWD: /usr/local/bin/init-firewall.sh" \
    > /etc/sudoers.d/${USERNAME}-firewall && \
    chmod 0440 /etc/sudoers.d/${USERNAME}-firewall

# -- Post-create/start scripts -----------------------------------------------
COPY post-create.sh post-start.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/post-create.sh /usr/local/bin/post-start.sh

USER ${USERNAME}
