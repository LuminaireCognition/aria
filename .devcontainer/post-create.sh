#!/usr/bin/env bash
set -euo pipefail

echo "═══════════════════════════════════════════════"
echo " ARIA DevContainer — First-time setup"
echo "═══════════════════════════════════════════════"

cd /workspace

# -- Install Python dependencies ----------------------------------------------
echo ""
echo "Installing Python dependencies..."
uv sync --dev

# -- Seed game data ------------------------------------------------------------
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

# -- Ensure userdata structure -------------------------------------------------
echo ""
echo "Ensuring userdata directory structure..."
sudo chown "$(id -u):$(id -g)" /workspace/userdata
mkdir -p /workspace/userdata/pilots /workspace/userdata/credentials /workspace/userdata/sessions

# -- Hook permissions ----------------------------------------------------------
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
