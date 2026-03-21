MCP tools are preferred when available. If `universe` appears in your tool list, MCP is connected.

### MCP Fallback Behavior

| Skill | MCP Dispatcher Call | CLI Fallback |
|-------|---------------------|--------------|
| `/route` | `universe(action="route", ...)` | `aria-esi route` |
| `/threat-assessment` | `universe(action="activity", systems=[...])` | `aria-esi activity` |
| `/escape-route` | `universe(action="route", mode="safe", ...)` | `aria-esi route --safe` |
| `/hunting-grounds` | `universe(action="hotspots", ...)` | `aria-esi hotspots` |
| `/fw-frontlines` | `universe(action="fw_frontlines", ...)` | `aria-esi fw-frontlines` |
| `/orient` | `universe(action="local_area", ...)` | `aria-esi orient` |
| (gatecamp analysis) | `universe(action="gatecamp_risk", ...)` | `aria-esi gatecamp-risk` |
| (system info) | `universe(action="systems", systems=[...])` | `aria-esi sysinfo <system>` |
| `/killmail` | `killmails(action="analyze", killmail_input=...)` | `aria-esi analyze-killmail` |
| `/mail` | `pilot(action="mail_list", ...)` | `aria-esi mail` |
| `/mining` | `pilot(action="mining_ledger", ...)` | `aria-esi mining` |
| `/contracts` | `pilot(action="contracts", ...)` | `aria-esi contracts` |
| `/fittings` | `pilot(action="fittings_list", ...)` | `aria-esi fittings` |
| `/lp-store` | `pilot(action="lp_balance")` / `pilot(action="lp_offers", ...)` | `aria-esi lp` / `aria-esi lp-offers` |
| `/build-cost` | `market(action="build_cost", ...)` | `aria-esi build-cost` |
| `/hunting-grounds` | `universe(action="territory_analysis", ...)` | `aria-esi territory` |
| (roaming route) | `universe(action="roam_route", ...)` | `aria-esi roam-route` |
| `/find` (proximity) | `market(action="find_nearby", proximity=...)` | `aria-esi find --proximity` |
