# Contributing to ARIA

Thank you for your interest in contributing to ARIA! This project aims to create an immersive ship-board AI experience for all Eve Online players.

## Licensing Notice

Before contributing, please understand the project's licensing structure:

### Your Contributions

| Contribution Type | License Applied | Notes |
|-------------------|-----------------|-------|
| Framework code (scripts, skills) | MIT | Your code becomes MIT-licensed |
| PvE intel (`reference/pve-intel/`) | CC-BY-SA 4.0 | Required by source license |
| Examples and configs | MIT | Personal data patterns |
| Documentation | MIT | Unless wiki-derived |

### Important Considerations

1. **PvE Intelligence:** Content in `reference/pve-intel/` is derived from [EVE University Wiki](https://wiki.eveuniversity.org/) under CC-BY-SA 4.0. Any contributions to this directory must also be CC-BY-SA 4.0 compatible and include source attribution.

2. **EVE Online IP:** This project uses EVE Online intellectual property under CCP's [Developer License Agreement](https://developers.eveonline.com/license-agreement). Commercial use is restricted. By contributing, you acknowledge your contributions may incorporate EVE Online IP subject to CCP's terms.

3. **Original Work:** Please ensure your contributions are either original work or properly attributed under a compatible license.

## Ways to Contribute

### 1. Share Your Configuration

The most valuable contributions are example configurations for different factions and playstyles:

**Wanted Examples:**
- Caldari corporate trader
- Minmatar freedom fighter
- Amarr faithful servant
- Nullsec PvP pilot
- Wormhole explorer
- Market-focused industrialist
- Alpha clone starter

To contribute an example:
1. Create a directory under `examples/` (e.g., `examples/caldari-trader/`)
2. Include at minimum:
   - `pilot_profile.md`
   - `operational_profile.md`
   - `ship_status.md`
3. Optionally include populated logs with sample data
4. Submit a pull request

### 2. Improve PvE Intelligence

Add or improve intel files in `reference/pve-intel/`:
- Document enemy faction damage types
- Note spawn triggers and wave mechanics
- Add fitting recommendations
- Include tips from personal experience

**License Requirement:** PvE intel in this directory is CC-BY-SA 4.0. If adapting from EVE University Wiki, include source URL in the file header (see existing files for format). Original PvE research is also welcome and will be licensed CC-BY-SA 4.0.

### 3. Enhance Reference Data

Expand the reference materials in `reference/mechanics/`:
- Ore and mineral data
- Hacking strategies
- Exploration site information
- NPC damage profiles

### 4. Report Issues

Found a bug or have a suggestion? Open an issue on GitHub with:
- What you expected to happen
- What actually happened
- Steps to reproduce (if applicable)
- Your faction/playstyle configuration (if relevant)

### 5. Improve Documentation

Help make ARIA more accessible:
- Fix typos or unclear instructions
- Add FAQ entries
- Improve setup guides
- Translate documentation

## Development Guidelines

### Keep It In-Universe

ARIA maintains immersion. When contributing:
- Use Eve Online terminology
- Frame advice through in-universe context
- Respect faction lore and cultural differences

### Respect All Playstyles

ARIA supports many playstyles:
- Self-sufficient (no market)
- Market traders
- Mission runners
- Explorers
- PvP pilots
- Industrialists

Don't assume one playstyle is "correct."

### Data Volatility

Understand the volatility tiers:
- **Permanent:** Faction, identity (never changes)
- **Stable:** Home base, ship roster (days-weeks)
- **Semi-stable:** Standings, skills (hours)
- **Volatile:** Location, ship, wallet (seconds)

Never reference volatile data proactively in examples or documentation.

### File Formats

- Use Markdown for all documentation
- Follow existing file structure patterns
- Include comments explaining non-obvious sections
- Use the established status report formatting

### Code Quality

When contributing Python code:
- Add type hints for new functions and parameters
- Run `uv run mypy .` before submitting PRs
- See [docs/TYPING_ROADMAP.md](docs/TYPING_ROADMAP.md) for typing standards and roadmap
- Security-critical modules (`services/auth.py`, `services/keyring_backend.py`) require strict typing

## Code of Conduct

Be respectful and constructive:
- Welcome newcomers to Eve Online
- Don't mock playstyles different from your own
- Keep discussions focused on improving ARIA
- Remember: we're all capsuleers here

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amarr-example`)
3. Make your changes
4. Test with Claude Code to ensure it works
5. Submit a pull request with a clear description

## Questions?

Open a discussion on GitHub or ask ARIA directly (she might help, in character).

---

*"Contributing to the collective knowledge of New Eden, one commit at a time."*
