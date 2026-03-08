# ESI Error Handling (Shared Fragment)

This fragment is loaded as a prerequisite by all ESI-dependent skills. Follow these rules when an MCP tool or CLI command returns an ESI error.

## Error Classification

| Error Signal | Meaning | User Message |
|-------------|---------|--------------|
| `"error": "scope_not_authorized"` | ESI is connected but the specific scope isn't authorized | "ESI is connected but the **{scope_name}** scope isn't authorized. Re-run OAuth setup to add it: `uv run aria-esi setup`" |
| `"error": "capability_denied"` | Policy layer blocked the action (e.g., restricted mode) | "This action is restricted by current policy settings." |
| Credentials `RuntimeError` / `"error": "no_credentials"` | ESI isn't configured at all | "ESI authentication isn't configured yet. Run `uv run aria-esi setup` to connect your character." |

## Mandatory Rules

1. **Never say "ESI isn't configured" when the error is `scope_not_authorized`.** The user has ESI — they just need to add one scope. Saying ESI is unconfigured is misleading and sends them down the wrong troubleshooting path.

2. **Always include the specific scope name** from the skill's `esi_scopes` field (e.g., `esi-fittings.read_fittings.v1`). Generic "re-run setup" without naming the scope is unhelpful.

3. **Always include the setup command:** `uv run aria-esi setup`

4. **Never produce a dead-end response.** After reporting an ESI error, always offer an actionable alternative:
   - Another skill that works without the missing scope
   - An in-game method to access the same information
   - A public data source (zKillboard, market tools, etc.)

5. **Check the `setup_command` or `hint` field** in MCP error responses — if present, use it verbatim instead of constructing your own.
