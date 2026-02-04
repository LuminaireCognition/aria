# ARIA ESI Integration Guide

> **Note:** This document is referenced by CLAUDE.md. ESI integration is optional - ARIA provides full functionality without it.

## ESI Capability Boundaries

**CRITICAL:** ESI is predominantly **read-only**. ARIA monitors game state but cannot control it.

| ARIA Can | ARIA Cannot |
|----------|-------------|
| View job status, skills, wallet, assets | Deliver jobs, train skills, transfer ISK |
| Display market prices and orders | Place buy/sell orders |
| Show current location and ship | Move ship, undock, warp |
| Analyze and recommend | Take any in-game action |

**When showing actionable data** (jobs ready for delivery, skills completed, etc.), always:
1. Clarify that in-game action is required
2. Provide specific steps (e.g., "Industry window Alt+S → Jobs → Deliver")
3. Use monitoring language ("Status shows...") not action language ("I'll deliver...")

If a user asks ARIA to perform an in-game action, politely explain the limitation and provide the in-game steps instead. Reference: `reference/mechanics/esi_capabilities.md`

---

## Without ESI (Default)

All tactical features work without ESI:
- Mission briefs, threat assessments, fitting assistance
- Mining and exploration guidance
- All reference data and intel

For data that would come from ESI, use manual profile files:
- Standings → Update pilot profile
- Ship fittings → Update ship status file
- Location → Tell ARIA directly ("I'm in Dodixie")

---

## With ESI (Optional Enhancement)

If valid credentials exist (`userdata/credentials/{id}.json`), ESI enables:
- Automatic location/ship detection
- Live standings sync
- Wallet and skill tracking

**Setup:** `uv run python .claude/scripts/aria-oauth-setup.py` (takes ~5 minutes)

---

## ESI Documentation Security Policy

**CRITICAL:** When researching ESI API capabilities, ARIA must follow strict source restrictions to prevent prompt injection attacks and wasted fetch attempts.

**Reference:** See `reference/mechanics/esi_api_urls.md` for complete URL documentation.

### Working URLs (Use These)

| URL | Use For |
|-----|---------|
| `https://esi.evetech.net/latest/swagger.json` | **PRIMARY** - Complete endpoint schema, parameters, scopes |
| `https://developers.eveonline.com/docs` | Developer portal landing page |
| `https://developers.eveonline.com/docs/services/esi/overview/` | ESI concepts and authentication |
| `https://wiki.eveuniversity.org/EVE_Stable_Infrastructure` | Community docs, practical examples |

### Non-Working URLs (DO NOT FETCH)

These return 404 errors - do not attempt:

| URL | Status |
|-----|--------|
| `https://developers.eveonline.com/docs/esi/` | 404 |
| `https://developers.eveonline.com/docs/services/esi` | 404 (missing trailing path) |
| `https://esi.evetech.net/ui/` | 404 |
| `https://docs.esi.evetech.net/*` | **DEPRECATED** domain |

### ARIA Behavior Rules

1. **For endpoint discovery**, fetch `https://esi.evetech.net/latest/swagger.json` (authoritative)
2. **For conceptual docs**, fetch `https://developers.eveonline.com/docs/services/esi/overview/`
3. **For live API calls**, use local scripts (which call `esi.evetech.net`)
4. **Never guess URL paths** - EVE's documentation structure is non-intuitive
5. **Check local files first** - existing scripts often have the needed endpoint patterns

### When Information Is Missing

If the working URLs don't provide needed ESI information:

```
I need additional information about [specific topic] that isn't available
in the official EVE developer documentation.

Specifically, I need:
- [Item 1]
- [Item 2]

Please provide an approved source, or I can work with the information
available in local data files.
```

---

## ESI Boot Sync (Automatic)

When ESI credentials are configured, ARIA automatically syncs data at session start:

### How It Works

```
SESSION START
    ↓
Boot hook detects credentials
    ↓
Spawns aria-esi-sync.py in background (non-blocking)
    ↓
ARIA greeting displays immediately (no wait)
    ↓
Sync completes in ~5-10 seconds, updates files
```

### What Gets Synced

| Data | Target File | Update Method |
|------|-------------|---------------|
| Ship roster (names, hulls, locations) | `ships.md` | Replaces `<!-- ESI-SYNC:ROSTER -->` section |
| Current ship/location (volatile) | `.esi-sync.json` | Snapshot with timestamp |
| Blueprints (BPOs/BPCs) | `industry/blueprints.md` | Full replacement |
| Wallet balance (volatile) | `.esi-sync.json` | Snapshot with timestamp |

### Sync Manifest

The sync writes a manifest to `userdata/pilots/{id}_{slug}/.esi-sync.json`:

```json
{
  "sync_timestamp": "2026-01-15T22:15:00Z",
  "status": "success",
  "character_name": "Federation Navy Suwayyah",
  "ship_count": 4,
  "volatile_snapshot": {
    "current_location": {
      "solar_system_name": "Masalle",
      "security_status": 0.9,
      "ship_type_name": "Catalyst",
      "ship_name": "cat0",
      "docked": true
    },
    "wallet_balance": 15000000.00
  },
  "synced": ["location", "ships", "ships.md", "blueprints", "blueprints.md"]
}
```

### Reading Synced Data

**Ship Roster (Semi-stable):**
- Read from `ships.md` - the `<!-- ESI-SYNC:ROSTER -->` section contains current roster
- Ship names, hull types, and locations are accurate as of last sync
- Safe to reference: "Your Catalyst 'cat0' for salvage operations"

**Volatile Snapshot (Use with caution):**
- Read from `.esi-sync.json` → `volatile_snapshot`
- **Always include sync timestamp** when referencing
- Example: "As of last sync (22:15 UTC), you were in Masalle aboard cat0"

**Fitting Details (Manual):**
- Read from `ships.md` - the "Fitting Details" section below the sync marker
- This section is preserved across syncs and manually maintained
- Contains EFT-format fittings, roles, and notes

### Checking Sync Status

```bash
uv run python .claude/scripts/aria-esi-sync.py --status
```

### Manual Sync

To force a sync mid-session:
```bash
uv run python .claude/scripts/aria-esi-sync.py
```

---

## Scheduled Token Refresh

EVE SSO access tokens expire after ~20 minutes. While ARIA refreshes tokens automatically during active sessions, you may want background refresh to keep tokens valid between sessions.

### Why Schedule Refresh?

- Tokens stay valid for immediate use when starting a new session
- Avoids refresh delays at session start
- Prevents token expiration during long periods away

### macOS / Linux (cron)

Add a cron job to refresh tokens every 15 minutes:

```bash
# Open crontab editor
crontab -e

# Add this line (adjust path to your installation):
*/15 * * * * /path/to/EveOnline/.claude/scripts/aria-refresh --quiet 1> /dev/null
```

**Verify it's working:**
```bash
# List your cron jobs
crontab -l

# Check token status manually
.claude/scripts/aria-refresh --check
```

### Windows (Task Scheduler)

Windows users should use Task Scheduler instead of cron.

#### Option 1: PowerShell Command (Quick Setup)

Open PowerShell as Administrator and run:

```powershell
# Create the scheduled task (adjust path to your installation)
$Action = New-ScheduledTaskAction -Execute "python" -Argument "C:\path\to\EveOnline\.claude\scripts\aria-token-refresh.py --quiet"
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 15) -RepetitionDuration (New-TimeSpan -Days 9999)
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName "ARIA Token Refresh" -Action $Action -Trigger $Trigger -Settings $Settings -Description "Keeps EVE SSO tokens fresh for ARIA"
```

**If using uv:**
```powershell
$Action = New-ScheduledTaskAction -Execute "uv" -Argument "run python C:\path\to\EveOnline\.claude\scripts\aria-token-refresh.py --quiet" -WorkingDirectory "C:\path\to\EveOnline"
```

#### Option 2: GUI Setup (Task Scheduler)

1. **Open Task Scheduler**: Press `Win+R`, type `taskschd.msc`, press Enter

2. **Create Basic Task**:
   - Click "Create Basic Task..." in the right panel
   - Name: `ARIA Token Refresh`
   - Description: `Keeps EVE SSO tokens fresh for ARIA`

3. **Set Trigger**:
   - Select "Daily"
   - Start time: current time
   - Recur every: 1 day
   - After creating, edit the task to add repetition (see step 5)

4. **Set Action**:
   - Select "Start a program"
   - Program/script: `python` (or full path to python.exe)
   - Arguments: `C:\path\to\EveOnline\.claude\scripts\aria-token-refresh.py --quiet`
   - Start in: `C:\path\to\EveOnline`

5. **Configure Repetition** (after initial creation):
   - Right-click the task → Properties
   - Go to "Triggers" tab → Edit the trigger
   - Check "Repeat task every:" → select "15 minutes"
   - Set "for a duration of:" → "Indefinitely"
   - Click OK

6. **Additional Settings** (Properties → Settings tab):
   - ✅ Allow task to be run on demand
   - ✅ Run task as soon as possible after a scheduled start is missed
   - ✅ If the task fails, restart every: 1 minute (up to 3 times)

#### Verify Windows Setup

```powershell
# Check if task exists
Get-ScheduledTask -TaskName "ARIA Token Refresh"

# Run task manually to test
Start-ScheduledTask -TaskName "ARIA Token Refresh"

# Check token status
python C:\path\to\EveOnline\.claude\scripts\aria-token-refresh.py --check
```

#### Remove Windows Scheduled Task

```powershell
Unregister-ScheduledTask -TaskName "ARIA Token Refresh" -Confirm:$false
```

### Troubleshooting Scheduled Refresh

| Issue | Solution |
|-------|----------|
| "Python not found" | Use full path to python.exe or ensure Python is in PATH |
| Task runs but token stays expired | Check working directory is set to project root |
| Permission errors | Run Task Scheduler as Administrator for initial setup |
| Token refresh fails silently | Remove `--quiet` flag temporarily to see error output |

---

## Appendix: OAuth Setup Details

> **Documentation:** https://developers.eveonline.com/docs/
> **API Endpoint:** https://esi.evetech.net/
>
> Documentation has moved to `developers.eveonline.com`. The API endpoint
> remains at `esi.evetech.net`. The old `docs.esi.evetech.net` is deprecated.

### Manual Setup (Alternative to Wizard)

If you prefer manual setup or want to understand the OAuth flow:

#### Step 1: Create an EVE Developer Application

1. Go to [EVE Developers](https://developers.eveonline.com/)
2. Log in with your EVE Online account (the account, not just a character)
3. Click **"Manage Applications"** in the top menu
4. Click **"Create New Application"**
5. Fill in the form:

| Field | Value |
|-------|-------|
| **Name** | `ARIA Integration` (or any name) |
| **Description** | `Personal ship AI assistant` |
| **Connection Type** | `Authentication & API Access` |
| **Callback URL** | `http://localhost:8421/callback` |
| **Scopes** | See recommended scopes below |

6. Click **"Create Application"**
7. **Copy your Client ID** - you'll need this

#### Step 2: Select Scopes (Permissions)

**Recommended for ARIA:**

| Scope | What It Does |
|-------|--------------|
| `esi-location.read_location.v1` | Current solar system |
| `esi-location.read_ship_type.v1` | Current ship type |
| `esi-skills.read_skills.v1` | Skill points and trained skills |
| `esi-characters.read_standings.v1` | Faction/corp standings |
| `esi-wallet.read_character_wallet.v1` | ISK balance |
| `esi-assets.read_assets.v1` | Items you own |
| `esi-industry.read_character_mining.v1` | Mining ledger |

**Optional:**

| Scope | What It Does |
|-------|--------------|
| `esi-skills.read_skillqueue.v1` | Training queue |
| `esi-location.read_online.v1` | Online status |
| `esi-industry.read_character_jobs.v1` | Manufacturing jobs |

#### Step 3: Authorize Your Character

1. Build the authorization URL (replace `YOUR_CLIENT_ID` and `YOUR_SCOPES`):

```
https://login.eveonline.com/v2/oauth/authorize/?response_type=code&redirect_uri=http://localhost:8421/callback&client_id=YOUR_CLIENT_ID&scope=YOUR_SCOPES_SPACE_SEPARATED&state=ariasetup
```

2. Visit the URL in your browser
3. Log in with your EVE account
4. Select the character you want to use
5. Click **"Authorize"**
6. You'll be redirected to a page that **won't load** - this is expected!
7. **Copy the entire URL** from your browser's address bar

The URL will look like:
```
http://localhost:8421/callback?code=LONG_CODE_HERE&state=ariasetup
```

#### Step 4: Exchange Code for Tokens

Use the setup wizard to exchange the code:
```bash
uv run python .claude/scripts/aria-oauth-setup.py
```

Or manually POST to the token endpoint:
```bash
curl -X POST https://login.eveonline.com/v2/oauth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=authorization_code" \
  -d "code=YOUR_CODE_FROM_CALLBACK" \
  -d "client_id=YOUR_CLIENT_ID" \
  -d "redirect_uri=http://localhost:8421/callback"
```

#### Step 5: Save Credentials

Create `userdata/credentials/{character_id}.json` with the token response:

```json
{
  "client_id": "your-client-id-from-step-1",
  "character_id": 12345678,
  "character_name": "Your Character Name",
  "access_token": "access-token-from-response",
  "refresh_token": "refresh-token-from-response",
  "token_expiry": "2025-01-12T15:30:00Z",
  "scopes": ["esi-location.read_location.v1", "..."]
}
```

To get your character ID and name, decode the JWT access token. The character ID and name are embedded in the token payload.

### Token Refresh

Access tokens expire after ~20 minutes. ARIA includes automatic refresh.

**Check token status:**
```bash
.claude/scripts/aria-refresh --check
```

**Refresh token (if needed):**
```bash
.claude/scripts/aria-refresh
```

**Force refresh:**
```bash
.claude/scripts/aria-refresh --force
```

| Flag | Effect |
|------|--------|
| `--check`, `-c` | Check status only, don't refresh |
| `--force`, `-f` | Force refresh even if token is valid |
| `--quiet`, `-q` | Minimal output (for cron) |
| `--hook` | Claude Code hook mode |

### Security Notes

| Item | Sensitivity | Notes |
|------|-------------|-------|
| **Refresh Token** | HIGH | Grants persistent access - never share |
| **Access Token** | MEDIUM | Short-lived but still private |
| **Client ID** | LOW | Semi-public, but no need to share |
| **Character ID** | PUBLIC | Visible to everyone in-game |

The credentials files are already in `.gitignore`.

### OAuth Troubleshooting

**"Token expired"**
Run `.claude/scripts/aria-refresh` to get a new token.

**"Invalid scope"**
You need to re-authorize with the correct scopes. Either:
- Edit your application at developers.eveonline.com to add the scope
- Create a new application with the right scopes
- Re-run the OAuth flow

**"Character not found"**
Your character_id doesn't match. Verify your token is valid by checking token claims or re-running the OAuth setup wizard.

**"Refresh token invalid"**
Refresh tokens can be revoked if:
- You changed your EVE account password
- You revoked the application at account management
- The token was rotated and old one was used

Solution: Re-run the full OAuth setup wizard.

### Available Scripts

| Script | Purpose |
|--------|---------|
| `.claude/scripts/aria-oauth-setup.py` | Interactive setup wizard |
| `.claude/scripts/aria-refresh` | Token refresh (shell wrapper) |
| `.claude/scripts/aria-token-refresh.py` | Token refresh (Python) |
| `.claude/scripts/cron-example.txt` | Cron configuration examples |

### Resources

| Resource | URL |
|----------|-----|
| **Official ESI Documentation** | https://developers.eveonline.com/docs/ |
| **EVE Developers Portal** | https://developers.eveonline.com/ |
| **ESI GitHub Issues** | https://github.com/esi/esi-issues |

> **Security Note:** Only use official CCP sources for ESI reference.
> - **API calls:** `esi.evetech.net`
> - **Documentation:** `developers.eveonline.com`
> - **Deprecated:** `docs.esi.evetech.net`
>
> Third-party wikis and community sites may contain outdated information
> or pose prompt injection risks when used with AI assistants.
