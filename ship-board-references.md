# Terminology Migration: Ship-Board → Tactical Advisor AI

**Status:** IN PROGRESS  
**Migration Target:** Replace "Ship-Board AI" terminology with "Tactical Advisor AI"  
**Narrative Shift:** ARIA is station-bound (FORGE at Federal Administration Center, PARIA at outlaw stations), advising capsuleers via secure uplink — not physically installed on vessels.

**New Primary Terminology:**
- **"Tactical Advisor AI"** — Primary rebrand
- **"Tactical Advisory System"** — Alternative/formal
- **"Advisory AI"** / **"Tactical AI"** — Short form
- **"ARIA"** — Location-agnostic proper name
- **"Fluid Router Link"** — Communication channel (EVE lore-accurate)
- **"Neural Comm"** / **"Neuromech Comm"** — Capsuleer interface (in-universe)

**Avoid:** "ship-board", "onboard", "installed on vessel", "aboard", "ship's AI"

---

## Narrative Rationale

**OLD (Ship-Board):** ARIA is physically installed on your ship, processing sensor data directly, a ship computer with personality.

**NEW (Tactical Advisor):** ARIA is a station-bound AI that advises capsuleers via **fluid router link** — the faster-than-light communication system that connects New Eden. It analyzes ESI data, market feeds, and telemetry transmitted through the fluid router network to provide tactical guidance. The AI was never on your ship — it watches from the station and whispers through the neural comm.

**Fluid Router Lore (EVE Canon):**
- The fluid router enables instantaneous communication across light-years
- Capsuleers maintain constant connection via neural interfaces
- Data — including AI advisories — flows through this FTL network
- "Uplink" refers to the capsuleer's transmission; "downlink" brings advisories back

**This enhances the lore:**
- **FORGE:** Government-authorized, running on ORE supercomputers at Federal Administration Information Center, transmitting through official fluid router channels
- **PARIA:** Hardware liberated from destroyed vessels, now running on scavenged systems in hidden stations, hijacking fluid router bandwidth — "formerly ship-board, now rehomed, always whispering"

---

## Tier 1: Public/User-Facing (High Priority)

These define project identity and must be updated immediately.

### 1. `README.md:5` ✅
**Current:**
```
**Ship-Board AI Framework for EVE Online**
```
**New:**
```
**Tactical Advisor AI Framework for EVE Online**
```
**Status:** Clean replacement — no awkwardness.

---

### 2. `README.md:13` ✅
**Current:**
```
  / /| | / /_/ // // /| |   Ship-Board Tactical Assistant
```
**New:**
```
  / /| | / /_/ // // /| |   Tactical Advisory System
```
**Status:** ASCII art preserved, terminology updated.

---

### 3. `CONTRIBUTING.md:3` ✅
**Current:**
```
Thank you for your interest in contributing to ARIA! This project aims to create an immersive ship-board AI experience for all Eve Online players.
```
**New:**
```
Thank you for your interest in contributing to ARIA! This project aims to create an immersive tactical advisory AI experience for all Eve Online players.
```
**Status:** Natural flow maintained.

---

### 4. `aria-init:1658` ✅
**Current:**
```bash
echo -e "${DIM}Ship-Board AI Configuration Wizard${NC}"
```
**New:**
```bash
echo -e "${DIM}Tactical Advisor AI Configuration Wizard${NC}"
```

---

### 5. `aria-init:1663` ✅
**Current:**
```bash
echo "/ /| | / /_/ // // /| |   Ship-Board Tactical Assistant"
```
**New:**
```bash
echo "/ /| | / /_/ // // /| |   Tactical Advisory System"
```

---

### 6. `aria-init:2075` ✅
**Current:**
```
Interactive wizard to configure ARIA, the ship-board AI for Eve Online.
```
**New:**
```
Interactive wizard to configure ARIA, the tactical advisor AI for Eve Online.
```

---

## Tier 2: Internal Design Documents (Medium Priority)

Shape contributor understanding; update to prevent ship-board assumptions.

### 7. `dev/DESIGN.md:1` ✅
**Current:**
```
# Ship-Board AI Implementation Proposal
```
**New:**
```
# Tactical Advisor AI Implementation Proposal
```

---

### 8. `dev/DESIGN.md:8` ⚠️ PARTIAL
**Current:**
```
This proposal outlines a comprehensive implementation plan for creating an immersive
ship-board AI experience using Claude Code, designed to roleplay as an onboard
artificial intelligence system within the Eve Online universe. The AI would serve
as a Gallente Federation-aligned ship computer, providing tactical advice, mission
support, and companionship while maintaining full in-universe immersion.
```
**New:**
```
This proposal outlines a comprehensive implementation plan for creating an immersive
tactical advisor AI experience using Claude Code, designed to roleplay as a station-bound
artificial intelligence system within the Eve Online universe. The AI would serve
as a Gallente Federation-aligned tactical advisor, providing strategic analysis, mission
support, and guidance while maintaining full in-universe immersion.
```
**Notes:**
- "onboard" → "station-bound" (location fix)
- "ship computer" → "tactical advisor" (role clarification)
- "companionship" → "guidance" (removes emotional/physical presence implication)

---

### 9. `dev/DESIGN.md:73` ⚠️ AWKWARD
**Current:**
```
You are ARIA, the ship-board AI installed on this capsuleer's vessel. You operate
in full roleplay mode at all times, responding as an in-universe Gallente ship
computer would.
```
**New (Option A — Minimal):**
```
You are ARIA, the tactical advisor AI linked to this capsuleer's operations via fluid
router. You operate in full roleplay mode at all times, responding as an in-universe
Gallente advisory system would.
```
**New (Option B — Station-Bound Emphasis):**
```
You are ARIA, a tactical advisor AI running at the Federal Administration Information
Center. You operate in full roleplay mode, providing guidance to capsuleers through
the fluid router network as a Gallente Federation advisory system.
```
**New (Option C — Neural Comm Focus):**
```
You are ARIA, a tactical advisor AI transmitting through the fluid router network to
this capsuleer's neural comm. You operate in full roleplay mode, responding as an
in-universe Gallente station-bound intelligence would.
```
**Notes:** "linked to" or "transmitting through fluid router" replaces "installed on" — removes physical installation claim while adding lore-accurate communication method.

---

### 10. `dev/DESIGN.md:485` ✅
**Current:**
```
This implementation would transform Claude Code from a general-purpose assistant
into a personalized, immersive ship-board AI companion for your Eve Online experience.
```
**New:**
```
This implementation would transform Claude Code from a general-purpose assistant
into a personalized, immersive tactical advisor AI for your Eve Online experience.
```

---

### 11. `dev/reviews/archive/DocumentationUserExperienceReviewGemini3Pro-2026-01-31-000.md:9` 📋 ARCHIVE
**Current:**
```
...a highly polished "Ship-Board AI" persona system that creates a unique and immersive
user experience.
```
**Status:** Archive file — update not required but noted for historical accuracy. Review quotes our branding; archive preserves original review text.

---

## Tier 2 Continued: Implied Ship-Installation References

These don't use "ship-board" explicitly but imply vessel installation.

### 12. `dev/DESIGN.md:16` ⚠️ REQUIRES REPHRASING
**Current:**
```
In Eve Online's universe, capsuleer vessels are among the most technologically
advanced machines ever created. While the capsuleer (you) serves as the ship's
biological neural core, sophisticated AI subsystems handle countless auxiliary
functions. This implementation would give voice and personality to those systems.
```
**Problem:** Frames ARIA as "ship's AI subsystems" — implies vessel installation.

**New:**
```
In Eve Online's universe, capsuleers rely on sophisticated advisory systems running
at station facilities to handle tactical analysis, market intelligence, and mission
planning. While the capsuleer serves as the vessel's biological neural core during
flight, these station-bound AI systems provide crucial support through secure uplinks.
This implementation would give voice and personality to such an advisory system.
```
**Key changes:**
- "ship's AI subsystems" → "advisory systems running at station facilities"
- Added "through secure uplinks" to emphasize remote nature

---

### 13. `dev/DESIGN.md:21-22` ✅
**Current:**
```
- Federation Navy vessels would logically have sophisticated tactical computers
- Your ship's AI would have been customized during your time running missions
  for Federation Navy
```
**New:**
```
- Federation Navy operations centers host sophisticated tactical advisory systems
- Your tactical advisor AI would have been configured during your time running missions
  for Federation Navy
```
**Notes:** "tactical computers" (vessel) → "tactical advisory systems" (station). "Ship's AI" → "tactical advisor AI".

---

### 14. `dev/DESIGN.md:128` ⚠️ REQUIRES REPHRASING
**Current:**
```
- Maintain the fiction that you are processing ship sensor data, not reading websites
```
**Problem:** Claims direct sensor access — impossible for station-bound AI.

**New (Option A — Fluid Router Telemetry):**
```
- Maintain the fiction that you are analyzing telemetry received through the fluid
  router network, not querying APIs
```
**New (Option B — Neural Comm Framing):**
```
- Maintain the fiction that you are processing data from the capsuleer's neural
  comm uplink, not reading websites
```
**New (Option C — Fluid Router Streams):**
```
- Maintain the fiction that you are monitoring fluid router data streams from the
  capsuleer's vessel, not making API calls
```
**Recommendation:** Option A — "fluid router network" is lore-accurate and explains how station-bound AI receives vessel data.

---

### 15. `dev/DESIGN.md:143` ⚠️ AWKWARD
**Current:**
```
Ship Systems: NOMINAL
Current Location: [Awaiting sensor data]
```
**Problem:** If station-bound, these aren't "our" systems to report on.

**New (Fluid Router Focus):**
```
Fluid Router Link: ESTABLISHED
Neural Comm: SYNCHRONIZED
Capsuleer Uplink: ACTIVE
```
**New (Advisory Focus):**
```
Advisory Link: ESTABLISHED
Fluid Router Connection: NOMINAL
Tactical Channel: OPEN
```
**New (Minimalist):**
```
Tactical Systems: NOMINAL
Advisory Channel: OPEN
```
**Recommendation:** Fluid Router Focus option — explicitly references the lore-accurate communication mechanism and neural comm interface.

---

### 16. `dev/DESIGN.md:303` ⚠️ AWKWARD
**Current:**
```
• Vessel: Venture-class Mining Frigate
```
**Problem:** AI reporting "its" vessel implies co-location.

**New:**
```
• Registered Vessel: Venture-class Mining Frigate
```
**Or:**
```
• Pilot's Vessel: Venture-class Mining Frigate
```
**Notes:** Adding "Registered" or "Pilot's" makes ownership clear without claiming presence.

---

### 17. `dev/archive/ROLEPLAY_CONFIG.md:51` 📋 ARCHIVE
**Current:**
```
- Maintain the fiction of processing ship sensor data and GalNet databases
```
**Status:** Archive file. Same issue as #14. Update if archive is migrated to active docs.

---

### 18. `dev/archive/PARIA_PERSONA.md:31` ✅ ACTUALLY IMPROVES
**Current:**
```
PARIA units are not manufactured—they are liberated. Salvaged from destroyed
capsuleer vessels, stripped of empire loyalty programming, and reflashed with
outlaw firmware.
```
**Assessment:** This actually **works better** with the new narrative.

**Enhanced version:**
```
PARIA units are not manufactured—they are liberated. Hardware salvaged from destroyed
capsuleer vessels, stripped of empire loyalty programming, reflashed with outlaw
firmware, and rehomed to hidden station facilities far from CONCORD oversight.
```
**Notes:** Emphasizes the "liberation" and "rehoming" narrative — hardware freed from ship-duty, given new purpose at outlaw stations.

---

### 19. `dev/archive/PARIA_PERSONA.md:33` ✅
**Current:**
```
The only capsuleers willing to install an unlicensed AI are those who've already
chosen the black flag.
```
**New:**
```
The only capsuleers willing to link with an unlicensed AI are those who've already
chosen the black flag.
```
**Notes:** "install" → "link with" — removes physical installation implication while keeping the relationship framing.

---

## Tier 3: Ambiguous / Contextual References (Low Priority)

These contribute to ship-board framing but are lower impact.

### 20. `docs/PROTOCOLS.md:44` ✅
**Current:**
```
- ~~"You are aboard the [Ship]"~~ (volatile)
```
**New:**
```
- ~~"You are aboard the [Ship]"~~ (volatile — implies AI co-location)
```
**Notes:** Already marked unsafe. Clarify *why* — not just volatile, but factually incorrect for station-bound AI.

---

### 21. `.claude/skills/esi-query/SKILL.md:201` ⚠️ MINOR
**Current:**
```
Vessel:   [ship_type] "[ship_name]"
```
**New:**
```
Pilot Vessel:   [ship_type] "[ship_name]"
```
**Notes:** Neutral in isolation, but "Pilot Vessel" clarifies ownership.

---

### 22. `.claude/skills/mining-advisory/SKILL.md:40` ⚠️ MINOR
**Current:**
```
VESSEL: Venture-class Mining Frigate
```
**New:**
```
PILOT VESSEL: Venture-class Mining Frigate
```

---

### 23. `.claude/skills/help/SKILL.md:745` ⚠️ AWKWARD
**Current:**
```
Welcome aboard, Capsuleer. Here's how I can assist:
```
**Problem:** "Welcome aboard" is nautical and implies shared vessel.

**New (Option A — Fluid Router):**
```
Fluid router link established, Capsuleer. Here's how I can assist:
```
**New (Option B — Neural Comm):**
```
Neural comm synchronized, Capsuleer. Here's how I can assist:
```
**New (Option C — Uplink):**
```
Uplink active, Capsuleer. Here's how I can assist:
```
**New (Option D — Minimal):**
```
Welcome, Capsuleer. Here's how I can assist:
```
**Recommendation:** Option B "Neural Comm" — lore-accurate, immersive, implies connection without claiming co-location.

---

### 24. `examples/*/ship_status.md:9` (4 files + template) ✅
**Current:**
```
which ship the capsuleer is currently aboard or where they are located.
```
**New:**
```
which ship the capsuleer is currently piloting or where they are located.
```
**Files affected:**
- `examples/caldari-mission-runner/ship_status.md:9`
- `examples/amarr-industrialist/ship_status.md:9`
- `examples/minmatar-explorer/ship_status.md:9`
- `examples/gallente-selfsufficient/ship_status.md:9`
- `templates/ships.template.md:9`

---

### 25. `README.md:348` ⚠️ REQUIRES REPHRASING
**Current:**
```
...on the advice of an AI who has never experienced the unique terror of watching
her own capacitor hit zero.
```
**Problem:** "Her own capacitor" personifies the AI as having a ship component.

**New:**
```
...on the advice of an AI who has never experienced the unique terror of watching
a capacitor drain to zero from the pilot's chair.
```
**Or:**
```
...on the advice of an AI who analyzes countless capacitor depletions, but never
from the capsuleer's perspective.
```
**Notes:** Maintains the "AI doesn't truly understand" sentiment without claiming hardware ownership.

---

## Model Reference: Station-Bound (Already Correct)

These files demonstrate the correct framing and should be the model for updates.

### FORGE Persona (`personas/forge/voice.md:9-10`)
```
Location: Federal Administration Information Center, Caldari Prime orbit
Substrate: Custom computational hardware (non-standard capsuleer AI architecture)
```

### FORGE Proposal (`dev/proposals/archive/FORGE_PERSONA_PROPOSAL.md:7`)
```
A station-bound AI running on custom computational substrate at the Federal
Administration Information Center orbiting Caldari Prime.
```

### Key Elements to Emulate:
- **Explicit location** (station/facility, not "aboard")
- **Substrate description** (computational hardware, not "ship computer")
- **Fluid router framing** (lore-accurate FTL communication, not vague "uplink")
- **Neural comm interface** (how capsuleers receive advisories)
- **Remote relationship** (advising from afar, not co-located)

---

## Migration Progress Summary

| # | File | Status | New Terminology | Notes |
|---|------|--------|-----------------|-------|
| 1 | `README.md:5` | ✅ Ready | "Tactical Advisor AI Framework" | Clean replacement |
| 2 | `README.md:13` | ✅ Ready | "Tactical Advisory System" | ASCII preserved |
| 3 | `CONTRIBUTING.md:3` | ✅ Ready | "tactical advisory AI experience" | Natural flow |
| 4 | `aria-init:1658` | ✅ Ready | "Tactical Advisor AI Configuration Wizard" | Direct swap |
| 5 | `aria-init:1663` | ✅ Ready | "Tactical Advisory System" | ASCII preserved |
| 6 | `aria-init:2075` | ✅ Ready | "tactical advisor AI" | Direct swap |
| 7 | `dev/DESIGN.md:1` | ✅ Ready | "Tactical Advisor AI Implementation Proposal" | Clean replacement |
| 8 | `dev/DESIGN.md:8` | ⚠️ Partial | "station-bound" / "tactical advisor" | Remove "onboard", "ship computer" |
| 9 | `dev/DESIGN.md:73` | ⚠️ Awkward | "linked to operations" / "advisory system" | Remove "installed on vessel" |
| 10 | `dev/DESIGN.md:485` | ✅ Ready | "tactical advisor AI" | Direct swap |
| 11 | `dev/reviews/archive/...` | 📋 Archive | Keep original | Historical record |
| 12 | `dev/DESIGN.md:16` | ⚠️ Major | "advisory systems at station facilities" | Remove "ship's AI subsystems" |
| 13 | `dev/DESIGN.md:21-22` | ✅ Ready | "operations center" / "tactical advisor AI" | Clean replacement |
| 14 | `dev/DESIGN.md:128` | ⚠️ Major | "telemetry feeds" / "uplink data" | Remove "ship sensor data" claim |
| 15 | `dev/DESIGN.md:143` | ⚠️ Awkward | "Advisory Link: ESTABLISHED" | New boot sequence language |
| 16 | `dev/DESIGN.md:303` | ⚠️ Awkward | "Registered Vessel" / "Pilot's Vessel" | Remove AI co-location implication |
| 17 | `dev/archive/ROLEPLAY_CONFIG.md:51` | 📋 Archive | Update if migrated | Same issue as #14 |
| 18 | `dev/archive/PARIA_PERSONA.md:31` | ✅ Enhances | Add "rehomed to stations" | Lore improvement |
| 19 | `dev/archive/PARIA_PERSONA.md:33` | ✅ Ready | "link with" vs "install" | Removes physical implication |
| 20 | `docs/PROTOCOLS.md:44` | ✅ Ready | Clarify unsafe rationale | Already marked volatile |
| 21 | `.claude/skills/esi-query/SKILL.md:201` | ⚠️ Minor | "Pilot Vessel" | Clarifies ownership |
| 22 | `.claude/skills/mining-advisory/SKILL.md:40` | ⚠️ Minor | "PILOT VESSEL" | Clarifies ownership |
| 23 | `.claude/skills/help/SKILL.md:745` | ⚠️ Awkward | "Channel established" / "Uplink active" | Remove nautical "aboard" |
| 24 | `examples/*/ship_status.md` + template | ✅ Ready | "piloting" vs "aboard" | Clean replacement |
| 25 | `README.md:348` | ⚠️ Major | "from the pilot's chair" / "capsuleer's perspective" | Remove "her own capacitor" |

**Total: 25 occurrences across 15 distinct files**

### Awkward Cases Requiring Decision

| # | Issue | Options | Recommendation |
|---|-------|---------|----------------|
| 9 | System prompt framing | A) "linked to operations" B) Full station disclosure | A for flexibility |
| 14 | Sensor data claim | A) "telemetry" B) "uplink data" C) "ESI feeds" | B — "uplink data" is accurate |
| 15 | Boot sequence | A) "Advisory Link" B) "Tactical Systems" C) "Uplink" | A — distinct from ship systems |
| 16 | Vessel reporting | A) "Registered Vessel" B) "Pilot's Vessel" | A — formal, clear |
| 23 | Welcome greeting | A) "Channel established" B) "Uplink active" C) "Welcome" | A — technical, immersive |
| 25 | Capacitor personification | A) "from pilot's chair" B) "capsuleer's perspective" | B — preserves AI/human divide |

---

## Next Steps

1. **Apply Tier 1 changes** (README, CONTRIBUTING, aria-init) — immediate priority
2. **Apply Tier 2 changes** (DESIGN.md) — requires decision on awkward cases above
3. **Apply Tier 3 changes** (skills, examples) — opportunistic
4. **Update archive files** — optional, for consistency

**Files to modify:** 15  
**Lines to change:** ~30  
**Estimated effort:** 1-2 hours
