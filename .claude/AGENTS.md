# AGENTS.md instructions for /Users/jskelton/EveOnline

<INSTRUCTIONS>
## Python execution (CRITICAL)
- Always use `uv run` for Python commands (e.g., `uv run aria-esi ...`, `uv run python -m ...`, `uv run pytest`).
- Never invoke bare `python`, `python3`, or `pip`. See `docs/PYTHON_ENVIRONMENT.md` for details and examples.

## Skills
A skill is a set of local instructions to follow that is stored in a `SKILL.md` file. Below is the list of skills that can be used. Each entry includes a name, description, and file path so you can open the source for full instructions when using a specific skill.
### Available skills
- agents-research: Monitor research agent partnerships and accumulated research points. Track passive RP generation from R&D agents. (file: /Users/jskelton/EveOnline/.claude/skills/agents-research/SKILL.md)
- arbitrage: Cross-region arbitrage opportunity scanner. Find profitable trade routes between trade hubs. (file: /Users/jskelton/EveOnline/.claude/skills/arbitrage/SKILL.md)
- aria-status: ARIA operational status report. Use when capsuleer requests status, sitrep, or operational summary. (file: /Users/jskelton/EveOnline/.claude/skills/aria-status/SKILL.md)
- clones: Clone and implant status tracking. Safety-critical for knowing your medical clone location and active implants before risky operations. (file: /Users/jskelton/EveOnline/.claude/skills/clones/SKILL.md)
- contracts: Personal contract management. View item exchange, courier, and auction contracts - both issued and received. (file: /Users/jskelton/EveOnline/.claude/skills/contracts/SKILL.md)
- corp: Corporation management and queries. Use for corp status, wallet, assets, blueprints, or industry jobs. (file: /Users/jskelton/EveOnline/.claude/skills/corp/SKILL.md)
- escape-route: PARIA escape route planning for Eve Online pirates. Find fastest routes to safe harbor from current position. (file: /Users/jskelton/EveOnline/.claude/skills/escape-route/SKILL.md)
- esi-query: Query EVE Online ESI API for live character data. Use when capsuleer asks for current location, skills, wallet, or standings. (file: /Users/jskelton/EveOnline/.claude/skills/esi-query/SKILL.md)
- exploration: ARIA exploration and hacking guidance for Eve Online. Use for relic/data site analysis, hacking tips, or exploration loot identification. (file: /Users/jskelton/EveOnline/.claude/skills/exploration/SKILL.md)
- find: Find market sources near your location. Use for finding blueprints, items, or specific market sources by proximity. (file: /Users/jskelton/EveOnline/.claude/skills/find/SKILL.md)
- first-run-setup: Conversational first-run configuration for new ARIA users. Guides capsuleer through profile setup via dialogue. (file: /Users/jskelton/EveOnline/.claude/skills/first-run-setup/SKILL.md)
- fitting: ARIA ship fitting assistance for Eve Online. Use for fitting exports, EFT format generation, module recommendations, tank analysis, or fitting optimization. (file: /Users/jskelton/EveOnline/.claude/skills/fitting/SKILL.md)
- fittings: View saved ship fittings from ESI. List fittings, filter by hull, and export to EFT format. (file: /Users/jskelton/EveOnline/.claude/skills/fittings/SKILL.md)
- help: Display available ARIA commands and capabilities. Use when capsuleer needs guidance on what ARIA can do. (file: /Users/jskelton/EveOnline/.claude/skills/help/SKILL.md)
- hunting-grounds: PARIA hunting ground analysis for Eve Online pirates. Analyze systems for target availability, traffic patterns, and competition. (file: /Users/jskelton/EveOnline/.claude/skills/hunting-grounds/SKILL.md)
- industry-jobs: Monitor personal manufacturing, research, copying, and invention jobs. View active jobs, completion times, and recent history. (file: /Users/jskelton/EveOnline/.claude/skills/industry-jobs/SKILL.md)
- journal: Log mission completions and exploration discoveries to operational records. (file: /Users/jskelton/EveOnline/.claude/skills/journal/SKILL.md)
- killmails: Kill and loss history analysis. Post-mortem on ship losses to understand what killed you and how to improve survivability. (file: /Users/jskelton/EveOnline/.claude/skills/killmails/SKILL.md)
- lp-store: Track LP balances and browse LP store offers. Essential for self-sufficient gameplay where LP store is the primary source of faction items. (file: /Users/jskelton/EveOnline/.claude/skills/lp-store/SKILL.md)
- mail: Read EVE mail headers and bodies. View inbox, filter unread, and read specific messages. (file: /Users/jskelton/EveOnline/.claude/skills/mail/SKILL.md)
- mark-assessment: PARIA target evaluation for Eve Online pirates. Assess potential marks based on ship type, likely cargo, and engagement viability. (file: /Users/jskelton/EveOnline/.claude/skills/mark-assessment/SKILL.md)
- mining: View mining ledger with ore extraction history. Track what you've mined, where, and when over the past 30 days. (file: /Users/jskelton/EveOnline/.claude/skills/mining/SKILL.md)
- mining-advisory: ARIA mining operations guidance for Eve Online. Use for ore recommendations, belt intel, Venture fitting, or mining optimization. (file: /Users/jskelton/EveOnline/.claude/skills/mining-advisory/SKILL.md)
- mission-brief: ARIA tactical intelligence briefing for Eve Online missions. Use for mission analysis, enemy intel, fitting advice, or combat preparation. (file: /Users/jskelton/EveOnline/.claude/skills/mission-brief/SKILL.md)
- orders: View active market orders and order history. Track buy/sell orders, escrow, and fill status. (file: /Users/jskelton/EveOnline/.claude/skills/orders/SKILL.md)
- pilot: View pilot identity and configuration. Shows full data for authenticated pilot, public data for others. (file: /Users/jskelton/EveOnline/.claude/skills/pilot/SKILL.md)
- price: EVE Online market price lookups. Use for item valuation, buy/sell spreads, or market analysis. (file: /Users/jskelton/EveOnline/.claude/skills/price/SKILL.md)
- ransom-calc: PARIA ransom calculation for Eve Online pirates. Calculate appropriate ransom amounts based on ship value, cargo, and implants. (file: /Users/jskelton/EveOnline/.claude/skills/ransom-calc/SKILL.md)
- route: Calculate safe travel routes between EVE Online systems. Use for route planning, security analysis, or navigation assistance. (file: /Users/jskelton/EveOnline/.claude/skills/route/SKILL.md)
- sec-status: PARIA security status tracking for Eve Online pirates. Monitor sec status, calculate tag costs, and track empire access restrictions. (file: /Users/jskelton/EveOnline/.claude/skills/sec-status/SKILL.md)
- skillqueue: Monitor EVE Online skill training queue and ETA. View current training progress and upcoming skills. (file: /Users/jskelton/EveOnline/.claude/skills/skillqueue/SKILL.md)
- threat-assessment: ARIA security and threat analysis for Eve Online. Use for system safety evaluation, activity risk assessment, or travel route analysis. (file: /Users/jskelton/EveOnline/.claude/skills/threat-assessment/SKILL.md)
- wallet-journal: View wallet transaction history and ISK flow analysis. Use for financial tracking, profit/loss analysis, or identifying income sources. (file: /Users/jskelton/EveOnline/.claude/skills/wallet-journal/SKILL.md)
### How to use skills
- Discovery: The list above is the skills available in this session (name + description + file path). Skill bodies live on disk at the listed paths.
- Trigger rules: If the user names a skill (with `$SkillName` or plain text) OR the task clearly matches a skill's description shown above, you must use that skill for that turn. Multiple mentions mean use them all. Do not carry skills across turns unless re-mentioned.
- Missing/blocked: If a named skill isn't in the list or the path can't be read, say so briefly and continue with the best fallback.
- How to use a skill (progressive disclosure):
  1) After deciding to use a skill, open its `SKILL.md`. Read only enough to follow the workflow.
  2) If `SKILL.md` points to extra folders such as `references/`, load only the specific files needed for the request; don't bulk-load everything.
  3) If `scripts/` exist, prefer running or patching them instead of retyping large code blocks.
  4) If `assets/` or templates exist, reuse them instead of recreating from scratch.
- Coordination and sequencing:
  - If multiple skills apply, choose the minimal set that covers the request and state the order you'll use them.
  - Announce which skill(s) you're using and why (one short line). If you skip an obvious skill, say why.
- Context hygiene:
  - Keep context small: summarize long sections instead of pasting them; only load extra files when needed.
  - Avoid deep reference-chasing: prefer opening only files directly linked from `SKILL.md` unless you're blocked.
  - When variants exist (frameworks, providers, domains), pick only the relevant reference file(s) and note that choice.
- Safety and fallback: If a skill can't be applied cleanly (missing files, unclear instructions), state the issue, pick the next-best approach, and continue.
</INSTRUCTIONS>
