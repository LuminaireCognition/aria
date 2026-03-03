# Hacking Minigame Reference

Guide to Data and Relic site hacking mechanics.

Source: EVE University Wiki — validated YC128 (2026)

---

## Objective

Locate and disable the **System Core** by navigating your virus through the node grid. Fail conditions: virus coherence reaches 0, or time expires.

## Node States

| Color | Meaning |
|-------|---------|
| **Orange** | Explored (clicked) |
| **Green** | Adjacent to explored; clickable |
| **Gray** | Unexplored; not yet reachable |

## Distance Numbers

When you click a node, it may show a number (1-5) indicating distance to nearest important target (utility, defensive, or core). Lower = closer. Use these to navigate efficiently.

## Defensive Subsystems (Enemies)

| Type | Coherence | Attack | Priority | Notes |
|------|-----------|--------|----------|-------|
| **Firewall** | High | Low | Low | Tanks hits; safe to fight |
| **Antivirus** | Low | High | Medium | Kill fast or take heavy damage |
| **Restoration Node** | Medium | None | **HIGH** | Heals random enemy **+20 coherence** per turn |
| **Virus Suppressor** | Medium | None | **HIGH** | Reduces your Virus Strength by **-15** |

**Priority targets:** Always kill Restoration Nodes and Virus Suppressors immediately.

**Note:** Exact Coherence/Attack values for individual node types are not published in the EVE University wiki. The wiki presents node presence by difficulty tier via icons only. The qualitative descriptors (High/Low/Medium) above match wiki descriptions.

## Utility Subsystems (Powerups)

| Type | Effect | Use Immediately? |
|------|--------|------------------|
| **Self Repair** | +5-10 coherence/turn for 3 turns | Yes |
| **Kernel Rot** | **-50%** target coherence | Save for Antiviruses |
| **Polymorphic Shield** | Blocks next **2** attacks | Yes |
| **Secondary Vector** | **-20** coherence/turn for 3 turns | Save for tough targets |

**Strategy:** Collect ALL utility nodes before engaging defensives when possible.

## Combat Mechanics

Turn-based combat:
1. You attack (your virus strength = damage dealt)
2. If target survives, it counterattacks (its attack = damage to your coherence)
3. Repeat until one dies

## Virus Stats

| Stat | Description | How to Increase |
|------|-------------|-----------------|
| **Coherence** | Your HP | Skills, better analyzers |
| **Virus Strength** | Your damage | Ship bonuses, T2 modules |

### Base Stats by Module

| Module | Coherence | Virus Strength | Notes |
|--------|-----------|----------------|-------|
| Data Analyzer I | **40** | 20 | T1 module |
| Data Analyzer II | **60** | 30 | T2 module |
| Relic Analyzer I | **40** | 20 | T1 module |
| Relic Analyzer II | **60** | 30 | T2 module |
| Integrated Analyzer | *lower than T2* | *lower than T2* | Exact values unconfirmed — verify in-game |
| Zeugma Integrated Analyzer | *lower than T2* | *lower than T2* | Exact values unconfirmed — verify in-game |

**Important:** EVE University wiki states Integrated Analyzers have "lower Virus Coherence and Strength than specialized T2 counterparts" but does not publish specific values. Do not cite training-data estimates for these modules.

### Ship Bonuses to Virus Strength

| Ship Type | Bonus (per level of relevant skill) |
|-----------|-------------------------------------|
| T1 Exploration Frigates (Heron, Magnate, Imicus, Probe) | **+5 Virus Strength per skill level** (both analyzers) |
| Covert Ops frigates (Buzzard, Anathema, Cheetah, Helios) | **+10 Virus Strength** |
| Sisters of EVE ships (Astero, Stratios) | **+10 Virus Strength** |
| Strategic Cruisers (Covert Reconfiguration subsystem) | **+10 Virus Strength** |
| SoCT ships (Metamorphosis, Sunesis) | **+10 Virus Strength** |

### Skill Bonuses

| Skill | Effect |
|-------|--------|
| **Hacking** | +10 Coherence per level (Data sites) |
| **Archaeology** | +10 Coherence per level (Relic sites) |

## Effective Stats Example

Heron (T1 frig, skill level 5) + Relic Analyzer I + Archaeology V:
- Coherence: 40 (module) + 50 (Archaeology V) = **90**
- Virus Strength: 20 (module) + 25 (T1 frig bonus at skill 5) = **45**

## Strategic Tips

1. **Explore before fighting** — Map out the grid first
2. **Collect utilities immediately** — They're free power
3. **Use distance numbers** — Navigate toward low numbers
4. **Save Kernel Rot** — Best against high-coherence Antiviruses (halves their HP)
5. **Avoid dead ends** — Numbers help identify paths
6. **Rule of 6** — If your coherence > 6x the enemy's attack strength, you cannot lose that combat exchange
7. **Rule of 8** — The System Core is always placed at least 8 grid-spaces from the starting point; navigate away from the start to find it

## Site Difficulty Reference

> **Reference:** See `reference/mechanics/exploration_sites.md` for complete site classification, security prefixes, ISK estimates, and loot tables by site type.

---
Source: EVE University Wiki
Last validated: YC128 (2026)
