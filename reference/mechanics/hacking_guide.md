# Hacking Minigame Reference

Guide to Data and Relic site hacking mechanics.

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
| **Restoration Node** | Medium | None | **HIGH** | Heals random enemy 20 coherence/turn |
| **Virus Suppressor** | Medium | None | **HIGH** | Reduces your strength by 15 (min 10) |

**Priority targets:** Always kill Restoration Nodes and Virus Suppressors immediately.

## Utility Subsystems (Powerups)

| Type | Effect | Use Immediately? |
|------|--------|------------------|
| **Self Repair** | +5-10 coherence/turn for 3 turns | Yes |
| **Kernel Rot** | -50% target coherence | Save for Antiviruses |
| **Polymorphic Shield** | Blocks next 2 attacks | Yes |
| **Secondary Vector** | 20 damage/turn for 3 turns | Save for tough targets |

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

| Module | Coherence | Strength |
|--------|-----------|----------|
| Data Analyzer I | 20 | 20 |
| Data Analyzer II | 30 | 30 |
| Relic Analyzer I | 20 | 20 |
| Relic Analyzer II | 30 | 30 |
| Integrated Analyzer | 25 | 25 |
| Zeugma Integrated Analyzer | 30 | 30 |

### Ship Bonuses

| Ship Type | Virus Strength Bonus |
|-----------|---------------------|
| T1 Exploration Frigates | +5 |
| Covert Ops Frigates | +10 |
| Sisters of EVE ships | +10 |

### Skill Bonuses

| Skill | Effect |
|-------|--------|
| **Hacking** | +10 coherence/level (Data sites) |
| **Archaeology** | +10 coherence/level (Relic sites) |

## Effective Stats Example

Heron (T1 frig) + Relic Analyzer I + Archaeology V:
- Coherence: 20 + 50 = **70**
- Strength: 20 + 5 = **25**

## Strategic Tips

1. **Explore before fighting** - Map out the grid first
2. **Collect utilities immediately** - They're free power
3. **Use distance numbers** - Navigate toward low numbers
4. **Save Kernel Rot** - Best against high-coherence Antiviruses
5. **Avoid dead ends** - Numbers help identify paths
6. **Rule of 6** - If your coherence > 6x enemy attack, you can't lose that fight

## Site Difficulty Reference

> **Reference:** See `reference/mechanics/exploration_sites.md` for complete site classification, difficulty ratings, ISK estimates, and loot tables by site type.

---
Source: EVE University Wiki
Last updated: YC128 (2026)
