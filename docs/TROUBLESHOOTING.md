# Troubleshooting

Single reference for common ARIA issues. Jump to the section that matches your problem.

---

## Setup & Installation

### "Command not found: aria-esi"

Ensure uv's bin directory is in your PATH:
```bash
export PATH="$HOME/.local/bin:$PATH"
```

Add this to your shell profile (`~/.bashrc`, `~/.zshrc`) to make it permanent.

### Python version issues

ARIA requires Python 3.11+. Check your version:
```bash
python --version
uv python list
```

### Dependency conflicts

Use uv's isolated environment reset:
```bash
uv sync --reinstall
```

### "File not found" errors during setup

Run the setup wizard again — it creates all required directories and templates:
```bash
./aria-init
```

---

## Boot & Session

### Boot sequence doesn't appear

Check that the hook script is executable:
```bash
ls -la .claude/hooks/aria-boot.sh
# Should show: -rwxr-xr-x
```

If not executable:
```bash
chmod +x .claude/hooks/aria-boot.sh
```

### ARIA doesn't adapt to my faction

Ensure your pilot profile exists and has a faction set:

**File:** `userdata/pilots/{your_pilot}/profile.md`
```markdown
- **Primary Faction:** GALLENTE
```

Valid values: `GALLENTE`, `CALDARI`, `MINMATAR`, `AMARR`, `PIRATE`, `ANGEL_CARTEL`, `SERPENTIS`, `GURISTAS`, `BLOOD_RAIDERS`, `SANSHAS_NATION`

After changing faction, regenerate persona context and restart:
```bash
uv run aria-esi persona-context
```

### Commands aren't working

Make sure you're running inside Claude Code (`claude` command). ARIA slash commands only work within the Claude Code environment, not in a regular terminal.

---

## ESI & Authentication

### ESI token expired

```bash
.claude/scripts/aria-refresh
```

If refresh fails, re-run the full setup wizard:
```bash
uv run python .claude/scripts/aria-oauth-setup.py
```

### ESI data seems stale

Token may need refresh:
```bash
.claude/scripts/aria-refresh
```

Check token status:
```bash
.claude/scripts/aria-refresh --check
```

### "Invalid scope"

Re-authorize with the correct scopes. Either:
- Edit your application at [developers.eveonline.com](https://developers.eveonline.com) to add the missing scope
- Create a new application with the correct scopes
- Re-run the OAuth flow: `uv run python .claude/scripts/aria-oauth-setup.py`

### "Character not found"

Your `character_id` doesn't match. Verify your token is valid by re-running the OAuth setup wizard.

### "Refresh token invalid"

Refresh tokens can be revoked if you:
- Changed your EVE account password
- Revoked the application at account management
- Used a rotated token

**Fix:** Re-run the full OAuth setup wizard:
```bash
uv run python .claude/scripts/aria-oauth-setup.py
```

### How do I keep tokens fresh automatically?

Set up scheduled token refresh (every 15 minutes):

**macOS / Linux:**
```bash
crontab -e
# Add this line:
*/15 * * * * /path/to/aria/.claude/scripts/aria-refresh --quiet 1> /dev/null
```

**Windows 11:** Use WSL2 and configure cron inside WSL2. See [ESI.md](ESI.md#scheduled-token-refresh).

### Scheduled refresh troubleshooting

| Issue | Solution |
|-------|----------|
| `uv not found` in cron | Install uv: https://docs.astral.sh/uv/ |
| Refresh runs but token stays expired | Check working directory and credential file permissions |
| Token refresh fails silently | Remove `--quiet` flag temporarily to see error output |

---

## Data & Accuracy

### ARIA gives wrong information about game mechanics

ARIA verifies data against the SDE and trusted sources, but mistakes can happen:

1. **Recent game change?** SDE updates lag patches by days/weeks.
2. **Mission-specific?** Wiki data may be outdated for rarely-run missions.

Report issues at the [GitHub repository](https://github.com/aria-eve/aria/issues).

### Market prices seem off

Market data comes from Fuzzwork (aggregated from ESI) and is typically 5-15 minutes old. For time-sensitive trades, verify in-game.

### System activity data is old

System activity (kills, jumps) comes from ESI and is typically 1 hour old. For real-time data, enable the zKillboard RedisQ poller — see [REALTIME_CONFIGURATION.md](REALTIME_CONFIGURATION.md).

---

## Notifications (Discord)

### Profile not loading

1. Check file exists in `userdata/notifications/`
2. Verify `.yaml` or `.yml` extension
3. Validate YAML: `uv run aria-esi notifications validate`
4. Check `enabled: true` in the profile

### Webhook errors

- Verify URL starts with `https://discord.com/api/webhooks/`
- Ensure the webhook hasn't been deleted in Discord
- Test it: `uv run aria-esi notifications test <profile-name>`

### Notifications not sending

Check these in order:
1. Profile is `enabled: true`
2. Monitored system is in the profile's topology
3. Throttle window hasn't suppressed the notification
4. Not in quiet hours
5. Trigger conditions are met

See [NOTIFICATION_PROFILES.md](NOTIFICATION_PROFILES.md) for full configuration reference.

---

## Market Scopes

### "Scope not found"

- Check scope name spelling
- Verify `owner_character_id` if the scope is character-owned
- List available scopes: use `/price` and ask ARIA to list scopes

### Stale data warnings

Refresh the scope data or use `force_refresh=True` when querying.

See [ADHOC_MARKETS.md](ADHOC_MARKETS.md) for full market scope documentation.

---

## Still stuck?

- **Ask ARIA:** Just describe the problem in conversation — ARIA can diagnose many issues.
- **Check the FAQ:** [FAQ.md](FAQ.md)
- **File an issue:** Report bugs at the GitHub repository.
