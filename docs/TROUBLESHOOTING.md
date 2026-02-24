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

### Game data seeding failed

If seeds failed during `./aria-init`, retry just the seeding step:
```bash
./aria-init --seed-only
```

Or retry individual commands:
```bash
uv run aria-esi sde-seed       # SDE database
uv run aria-esi eos-seed       # Fitting engine
uv run aria-esi market-seed    # Market prices
uv run aria-esi sov-update     # Sovereignty map
uv run aria-esi persona-context # Persona compilation
```

---

## DevContainer

### Container build fails

Check Docker Desktop is running and has sufficient resources (at least 4GB RAM recommended).

If the build fails during game data seeding, the container is still usable — retry with:
```bash
./aria-init --seed-only
```

### ESI OAuth not working in container

The OAuth wizard auto-detects containers and headless environments (SSH, no DISPLAY) and defaults to copy-paste mode — no local browser needed. You authorize in a browser on any machine and paste the callback URL back into the terminal.

If you want to use the automatic browser flow instead (e.g., with VS Code port forwarding), pass `--auto`. Port 8421 must be forwarded — verify in the VS Code **Ports** panel.

The script also binds to `0.0.0.0` in container environments so Docker Desktop port forwarding can reach the callback server.

### Firewall blocking a needed service

The container firewall restricts outbound traffic to an allowlist. If a new service is needed:

1. Check `.devcontainer/init-firewall.sh` for the allowed domains
2. Add the domain to the `ALLOWED_DOMAINS` array
3. Rebuild the container: `Dev Containers: Rebuild Container`

### userdata lost after rebuild

`userdata/` is mounted as a Docker volume and should persist. If data is missing:
```bash
docker volume ls | grep aria-userdata
```

If the volume exists but appears empty inside the container, check the mount in `.devcontainer/devcontainer.json`.

### "Permission denied" errors

The container runs as user `aria` (UID 1000). If you see permission errors on mounted files:
```bash
ls -la /workspace/userdata/
```

Ensure files are owned by `aria:aria` (UID/GID 1000).

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

## Credential Storage (Keyring)

ARIA stores ESI credentials in the system keyring when available (GNOME Keyring, KWallet, macOS Keychain). If the keyring is unavailable, credentials fall back to plaintext JSON files with `0600` permissions in `userdata/credentials/`.

### Credentials stored in plaintext despite keyring being installed

**Symptom:** After OAuth setup, credentials are in `userdata/credentials/*.json` instead of the system keyring, even though `gnome-keyring` is installed.

**Diagnosis:** Run the keyring status check:
```bash
uv run python -c "
from aria_esi.core.keyring_backend import get_keyring_status
import json
print(json.dumps(get_keyring_status(), indent=2))
"
```

If the output shows `"available": false` with a reason mentioning "locked", the keyring collection exists but is locked. This is the most common cause on Linux.

### Keyring collection is locked (Linux / GNOME Keyring)

**Cause:** The GNOME Keyring Login collection is unlocked at login by PAM. If PAM integration is not configured for your login method (TTY, SSH, non-GDM display manager), the collection stays locked and all keyring operations fail silently.

**Quick fix — unlock for this session:**
```bash
read -s -p "Password: " PASS && echo -n "$PASS" | gnome-keyring-daemon --unlock && unset PASS
```
This prompts for your login password without displaying it. The unlock lasts until logout.

After unlocking, re-run OAuth setup to migrate credentials to the keyring:
```bash
uv run python .claude/scripts/aria-oauth-setup.py
```

**Permanent fix — enable PAM auto-unlock:**

The `libpam-gnome-keyring` package must be installed (check with `dpkg -l libpam-gnome-keyring`). Then add these two lines to the PAM configuration for your login method:

```
auth     optional  pam_gnome_keyring.so
session  optional  pam_gnome_keyring.so auto_start
```

**Which PAM file to edit depends on how you log in:**

| Login method | PAM file | Notes |
|-------------|----------|-------|
| SSH (password auth) | `/etc/pam.d/sshd` | Most common for remote/headless servers |
| TTY console | `/etc/pam.d/login` | Local terminal logins |
| GDM (GNOME) | Usually pre-configured | Check `/etc/pam.d/gdm-password` |
| SDDM, LightDM | `/etc/pam.d/<your-dm>` | Often omitted by default |

**Important:** If you access the machine via SSH, you must update `/etc/pam.d/sshd` — updating only `/etc/pam.d/login` is not sufficient for SSH sessions. You may want to update both files if you use both login methods.

### How to verify the keyring is working

After unlocking or configuring PAM, verify with:
```bash
uv run python -c "
from aria_esi.core.keyring_backend import get_keyring_status
import json
print(json.dumps(get_keyring_status(), indent=2))
"
```

Expected output when working:
```json
{
  "available": true,
  "backend": "Keyring",
  "reason": null,
  "enabled": true,
  "env_disabled": false
}
```

### Intentionally disabling keyring

If you prefer plaintext storage (e.g., headless server with no keyring daemon), suppress the security warnings:
```bash
export ARIA_NO_KEYRING=1
```

Add to your shell profile to make it permanent.

---

## Data & Accuracy

### ARIA gives wrong information about game mechanics

ARIA verifies data against the SDE and trusted sources, but mistakes can happen:

1. **Recent game change?** SDE updates lag patches by days/weeks. Refresh with `uv run aria-esi sde-seed --force`.
2. **Mission-specific?** Wiki data may be outdated for rarely-run missions.

Report issues at the [GitHub repository](https://github.com/LuminaireCognition/aria/issues).

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

## Recovery / Starting Fresh

If your setup is in a broken state and you want to start over, these reset commands target specific subsystems without affecting the rest.

### Reset pilot data

Removes all pilot profiles, registry, and active-pilot config. You'll re-run setup afterward.

```bash
rm -rf userdata/pilots/*/
rm -f userdata/pilots/_registry.json
rm -f userdata/config.json
./aria-init
```

### Reset ESI credentials

Removes OAuth tokens. You'll need to re-authorize through the browser flow.

```bash
rm -rf userdata/credentials/
```

Then follow the ESI setup steps in [ESI.md](ESI.md) to re-authorize.

### Reset game data caches

Re-seeds universe graph and SDE data without touching pilot profiles or credentials.

```bash
./aria-init --seed-only
```

---

## Still stuck?

- **Ask ARIA:** Just describe the problem in conversation — ARIA can diagnose many issues.
- **Check the FAQ:** [FAQ.md](FAQ.md)
- **File an issue:** Report bugs at the GitHub repository.
