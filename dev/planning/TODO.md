# ARIA Project TODO

Pending improvements and future expansion.

**Content Status:** Tiers 1-4 complete. Core mechanics, missions (L1-L4), exploration, mining, industry, wormholes, abyssal, FW, incursions all documented.

**Recent Completions (2026-02-02):**
- ✅ `/pi` skill complete with all 4 phases (chains, math, market, location-aware)
- ✅ `/assets` skill complete with smart insights and snapshot persistence
- ✅ Skill test harness with 3-layer validation (contract, structural, semantic)
- ✅ `/build-cost` character integration (blueprint ME/TE from ESI)
- ✅ Archetype fit stats caching (`fit update-stats` CLI with EOS integration)
- ✅ Archetype fit validation (`fit validate` CLI with omega/T2 consistency check)

---

## Pending: Skill Module Enhancements

New `/slash` commands or improvements to existing ones:

- [x] **`/pi`** - ~~Planetary interaction guidance~~ (COMPLETE - 2026-02-02)
- [ ] **`/wormhole`** - Wormhole daytrip support (hole identification, mass tracking, exit status)
- [ ] **Enhance `/mining-advisory`** - Fleet mining mode, boost calculations, compression recommendations
- [ ] **Enhance `/exploration`** - Wormhole-specific sites, C1-C3 vs C4+ warnings, sleeper spawn timers

---

## Pending: Structural Improvements

- [ ] **Add difficulty ratings** to guides (Beginner/Intermediate/Advanced tags)
- [ ] **Cross-reference related topics** (exploration → wormholes → gas harvesting)
- [ ] **Progression visualization** (activity unlock tree, ship flowcharts)
- [ ] **Update `data/INDEX.md`** - Add difficulty indicators, improve navigation

---

## Pending: UX Polish

- [ ] **Session state tracking** - Track current activity mode for contextual defaults
- [ ] **Schema validation** - JSON schema for profile files (IDE autocomplete, validation)
- [ ] **ARIA response examples** - Add example responses to skills for voice consistency

---

## Out of Scope

- Large fleet warfare, sovereignty, alliance operations
- General PvP (beyond FW entry point)

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Quick ideas:
- Document a mission you ran
- Add a ship fit you use
- Write a guide for an activity you know

---

*Last updated: 2026-02-02*
